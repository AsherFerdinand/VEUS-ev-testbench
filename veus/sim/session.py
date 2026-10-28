"""Per-client EV runs with mechanical dynamics and conserved energy accounting."""

import math
from collections import deque
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from veus.sensors.config import SensorSuiteConfig
from veus.sensors.virtual import SensorSuite
from veus.control.longitudinal import Command, LongitudinalController, Observation
from veus.model.energy_battery import EnergyBattery
from veus.model.motor import ElectricMotor
from veus.model.vehicle import HighPerformanceVehicle
from veus.sim.dynamics import LongitudinalSimulator, VehicleState


class RunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    mass_kg: float = Field(default=1800, ge=500, le=5000)
    max_power_kw: float = Field(default=150, ge=10, le=1000)
    max_torque_nm: float = Field(default=300, ge=10, le=1500)
    friction: float = Field(default=0.9, ge=0, le=1.5)
    grade_percent: float = Field(default=0, ge=-30, le=30)
    initial_speed_kmh: float = Field(default=0, ge=0, le=200)
    duration_s: float = Field(default=30, ge=1, le=120)
    battery_capacity_kwh: float = Field(default=60, ge=1, le=200)
    initial_soc: float = Field(default=0.8, ge=0, le=1)
    battery_voltage_v: float = Field(default=400, ge=100, le=1000)
    battery_resistance_ohm: float = Field(default=0.05, ge=0, le=1)
    discharge_limit_a: float = Field(default=500, ge=0, le=2000)
    charge_limit_a: float = Field(default=200, ge=0, le=1000)
    drive_efficiency: float = Field(default=0.9, gt=0, le=1)
    regen_efficiency: float = Field(default=0.7, gt=0, le=1)
    regen_enabled: bool = True
    target_speed_kmh: float = Field(default=80, ge=0, le=160)
    lead_speed_kmh: float = Field(default=60, ge=0, le=160)
    initial_gap_m: float = Field(default=50, ge=1, le=300)
    time_headway_s: float = Field(default=1.8, ge=0.5, le=4)
    standstill_gap_m: float = Field(default=5, ge=1, le=20)
    max_acceleration_ms2: float = Field(default=2, gt=0, le=4)
    comfort_deceleration_ms2: float = Field(default=3, gt=0, le=6)
    aeb_ttc_s: float = Field(default=2, ge=0.5, le=5)
    detection_delay_s: float = Field(default=0, ge=0, le=2)
    actuation_delay_s: float = Field(default=0, ge=0, le=2)
    lead_brake_start_s: float = Field(default=3, ge=0, le=120)
    lead_deceleration_ms2: float = Field(default=6, gt=0, le=10)
    sensors: SensorSuiteConfig = Field(default_factory=SensorSuiteConfig)
    mode: Literal[
        "manual", "acceleration", "braking", "coast", "cruise", "acc", "aeb"
    ] = "manual"

    @model_validator(mode="after")
    def sensor_horizon(self):
        if any(
            f.start_time_s + f.duration_s > self.duration_s + 1e-9
            for f in self.sensors.faults
        ):
            raise ValueError("Sensor fault events must end within the run duration")
        return self


class Controls(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    throttle: float = Field(default=0, ge=0, le=1)
    brake: float = Field(default=0, ge=0, le=1)


class SimulationSession:
    dt_s = 0.01
    steps_per_frame = 10

    def __init__(self, config: RunConfig | None = None):
        self.reset(config or RunConfig())

    def reset(self, config: RunConfig) -> None:
        self.config = config
        self.sim = LongitudinalSimulator(
            vehicle=HighPerformanceVehicle(mass_kg=config.mass_kg),
            motor=ElectricMotor(
                max_torque_nm=config.max_torque_nm, max_power_kw=config.max_power_kw
            ),
            friction_coefficient=config.friction,
            gradient_rad=math.atan(config.grade_percent / 100),
        )
        self.state = VehicleState(velocity_ms=config.initial_speed_kmh / 3.6)
        self.controls = Controls()
        self.status = "ready"
        self.ticks = 0
        self.last = None
        self.battery = EnergyBattery(
            config.battery_capacity_kwh,
            config.initial_soc,
            config.battery_voltage_v,
            config.battery_resistance_ohm,
            config.discharge_limit_a,
            config.charge_limit_a,
        )
        self.initial_energy_j = self.battery.energy_j
        self.initial_kinetic_j = 0.5 * config.mass_kg * self.state.velocity_ms**2
        self.energy = dict(
            consumed_j=0.0,
            recovered_j=0.0,
            battery_heat_j=0.0,
            conversion_loss_j=0.0,
            friction_heat_j=0.0,
            road_work_j=0.0,
        )
        self.electrical = dict(
            terminal_power_w=0.0, current_a=0.0, voltage_v=config.battery_voltage_v
        )
        self.regen_force_n = 0.0
        self.battery_limited = False
        self.has_lead = config.mode in {"acc", "aeb"}
        self.controller = (
            LongitudinalController(
                config.mode,
                config.target_speed_kmh / 3.6,
                config.time_headway_s,
                config.standstill_gap_m,
                config.max_acceleration_ms2,
                config.comfort_deceleration_ms2,
                config.aeb_ttc_s,
            )
            if config.mode in {"cruise", "acc", "aeb"}
            else None
        )
        self.controller_state = "inactive"
        self.requested_acceleration = 0.0
        self.collision = False
        self.minimum_gap = config.initial_gap_m if self.has_lead else None
        self.aeb_trigger_time_s = None
        self.sensor_delay_ticks = round(config.detection_delay_s / self.dt_s)
        self.actuator_delay_ticks = round(config.actuation_delay_s / self.dt_s)
        self.observations = deque(maxlen=self.sensor_delay_ticks + 1)
        self.commands = deque(maxlen=self.actuator_delay_ticks + 1)
        self.sensor_suite = (
            SensorSuite(config.sensors) if config.sensors.enabled else None
        )
        self.controller_input_health = (
            "ground-truth" if not self.sensor_suite else "pending"
        )
        self.controller_input_speed_ms = None
        self.controller_input_gap_m = None
        self.controller_input_age_s = None
        self.applied_input_health = "inactive"
        self._update_sensors()

    def advance(self) -> dict:
        """Advance one dashboard frame, preserving the original ten-tick API."""
        for _ in range(self.steps_per_frame):
            self.step()
            if self.status != "running":
                break
        return self.telemetry()

    def step(self) -> dict:
        """Advance exactly one physics tick; offline runners record every event."""
        if self.status != "running":
            return self.telemetry()
        modes = {
            "acceleration": Controls(throttle=1),
            "braking": Controls(brake=1),
            "coast": Controls(),
        }
        controls = modes.get(self.config.mode, self.controls)
        torque = (
            0 if controls.brake > 0 else controls.throttle * self.config.max_torque_nm
        )
        brake_n = controls.brake * self.config.mass_kg * 9.81
        self.sim.transmission.current_gear = 1 if self.state.velocity_ms > 27.7 else 0
        if self.controller:
            torque, brake_n = self._controller_inputs()
        self._energy_step(torque, brake_n)
        self.ticks += 1
        self.state = VehicleState(
            self.ticks * self.dt_s,
            self.last.state.position_m,
            self.last.state.velocity_ms,
        )
        self._update_sensors()
        if self.has_lead:
            gap = self._observation().gap_m
            self.minimum_gap = min(self.minimum_gap, gap)
            if gap <= 0:
                self.collision = True
                self.status = "collision"
        if self.status == "running" and self.ticks >= round(
            self.config.duration_s / self.dt_s
        ):
            self.status = "completed"
        return self.telemetry()

    def _lead_state(self, time_s: float) -> tuple[float, float]:
        speed = self.config.lead_speed_kmh / 3.6
        if self.config.mode != "aeb" or time_s <= self.config.lead_brake_start_s:
            return self.config.initial_gap_m + speed * time_s, speed
        elapsed = min(
            time_s - self.config.lead_brake_start_s,
            speed / self.config.lead_deceleration_ms2,
        )
        position = (
            self.config.initial_gap_m
            + speed * self.config.lead_brake_start_s
            + speed * elapsed
            - 0.5 * self.config.lead_deceleration_ms2 * elapsed**2
        )
        return position, max(0.0, speed - self.config.lead_deceleration_ms2 * elapsed)

    def _observation(self) -> Observation:
        lead_position, lead_speed = self._lead_state(self.state.time_s)
        return Observation(
            self.state.velocity_ms,
            lead_position - self.state.position_m if self.has_lead else None,
            lead_speed if self.has_lead else 0.0,
        )

    def _update_sensors(self):
        if self.sensor_suite:
            truth = self._observation()
            self.sensor_suite.update(
                self.ticks,
                truth.speed_ms,
                truth.gap_m,
                truth.speed_ms - truth.lead_speed_ms if self.has_lead else None,
            )

    def _sensor_observation(self):
        if not self.sensor_suite:
            return self._observation(), "ground-truth"
        views = self.sensor_suite.views()
        required = [views["speed"]] + ([views["radar"]] if self.has_lead else [])
        if not all(v["valid"] for v in required):
            return None, "stale" if any(
                v["status"] == "stale" for v in required
            ) else "unavailable"
        speed = views["speed"]["values"]["speed_ms"]
        gap = views["radar"]["values"].get("distance_m") if self.has_lead else None
        lead = (
            speed - views["radar"]["values"]["closing_speed_ms"]
            if self.has_lead
            else 0.0
        )
        if lead < 0:
            return None, "inconsistent-measurements"
        health = next(
            (v["status"] for v in required if v["status"] != "valid"), "valid"
        )
        return Observation(speed, gap, lead), health

    def _controller_inputs(self) -> tuple[float, float]:
        observation, health = self._sensor_observation()
        expiry = None
        source = None
        if self.sensor_suite:
            views = self.sensor_suite.views()
            required = ["speed"] + (["radar"] if self.has_lead else [])
            times = [views[n]["sample_time_s"] for n in required]
            if all(t is not None for t in times):
                source = min(times)
                expiry = min(
                    views[n]["sample_time_s"]
                    + getattr(self.config.sensors, n).stale_after_s
                    for n in required
                )
        self.observations.append((observation, health, expiry, source))
        delayed, health, expiry, source = self.observations[0]
        self.controller_input_age_s = (
            self.state.time_s - source if source is not None else None
        )
        if (
            delayed is not None
            and expiry is not None
            and self.state.time_s > expiry + 1e-9
        ):
            delayed = None
            health = "stale"
        self.controller_input_health = health
        self.controller_input_speed_ms = delayed.speed_ms if delayed else None
        self.controller_input_gap_m = delayed.gap_m if delayed else None
        if delayed is None:
            command = (
                Command(-9.81, "emergency_braking")
                if self.controller.emergency_latched
                else Command(
                    -self.config.comfort_deceleration_ms2, "sensor_fallback_braking"
                )
            )
        else:
            command = self.controller.update(delayed)
        if command.state == "emergency_braking" and self.aeb_trigger_time_s is None:
            self.aeb_trigger_time_s = self.state.time_s
        self.commands.append((command, health))
        applied, self.applied_input_health = (
            self.commands[0]
            if len(self.commands) > self.actuator_delay_ticks
            else (Command(0.0, "actuator_wait"), "actuator_wait")
        )
        self.controller_state = applied.state
        self.requested_acceleration = applied.acceleration_ms2
        # Feed-forward road load converts desired acceleration to wheel force.
        v = self.sim.vehicle
        road = (
            0.5
            * self.sim.air_density_kg_m3
            * v.cd
            * v.frontal_area_m2
            * (
                self.controller_input_speed_ms
                if self.sensor_suite and self.controller_input_speed_ms is not None
                else self.state.velocity_ms
            )
            ** 2
            + v.rr_coeff * v.mass_kg * 9.81 * math.cos(self.sim.gradient_rad)
            + v.mass_kg * 9.81 * math.sin(self.sim.gradient_rad)
        )
        force = v.mass_kg * applied.acceleration_ms2 + road
        if applied.state in {
            "emergency_braking",
            "actuator_wait",
            "sensor_fallback_braking",
        }:
            # Full emergency brake demand; tyre limit sets achievable deceleration.
            force = (
                -v.mass_kg * 9.81
                if applied.state == "emergency_braking"
                else -v.mass_kg * self.config.comfort_deceleration_ms2
                if applied.state == "sensor_fallback_braking"
                else 0.0
            )
        tr = self.sim.transmission
        if force >= 0:
            return force * v.wheel_radius_m / (
                tr.active_ratio * tr.mechanical_efficiency
            ), 0.0
        return 0.0, -force

    def _work_distance(self, result) -> float:
        # Integrate the held acceleration over the moving part of the interval.
        moving_dt = self.dt_s
        if result.acceleration_ms2 < 0:
            moving_dt = min(
                moving_dt, -self.state.velocity_ms / result.acceleration_ms2
            )
        return 0.5 * (self.state.velocity_ms + result.state.velocity_ms) * moving_dt

    def _energy_step(self, torque: float, brake_n: float) -> None:
        discharge_w, charge_w = self.battery.power_limits(self.dt_s)
        drive_efficiency = (
            self.config.drive_efficiency * self.sim.transmission.mechanical_efficiency
        )
        regen_efficiency = (
            self.config.regen_efficiency * self.sim.transmission.mechanical_efficiency
        )
        result = self.sim.step(self.state, torque, brake_n, self.dt_s)

        def demand(r):
            return (
                r.drive_force_n
                * self._work_distance(r)
                / (drive_efficiency * self.dt_s)
            )

        self.battery_limited = demand(result) > discharge_w + 1e-7
        if self.battery_limited:
            lo, hi = 0.0, torque
            for _ in range(40):
                mid = (lo + hi) / 2
                candidate = self.sim.step(self.state, mid, brake_n, self.dt_s)
                if demand(candidate) <= discharge_w:
                    lo = mid
                else:
                    hi = mid
            result = self.sim.step(self.state, lo, brake_n, self.dt_s)
        distance = self._work_distance(result)
        drive_j = result.drive_force_n * distance
        brake_j = result.brake_force_n * distance
        regen_j = 0.0
        self.regen_force_n = 0.0
        if (
            self.config.regen_enabled
            and distance > 0
            and result.motor_rpm < self.sim.motor.max_rpm
        ):
            tr = self.sim.transmission
            motor_force = (
                self.sim.motor.max_available_torque(result.motor_rpm)
                * tr.active_ratio
                / (tr.mechanical_efficiency * self.sim.vehicle.wheel_radius_m)
            )
            regen_j = min(
                brake_j,
                motor_force * distance,
                self.config.max_power_kw * 1000 * self.dt_s / tr.mechanical_efficiency,
                charge_w * self.dt_s / regen_efficiency,
            )
            self.regen_force_n = regen_j / distance
        terminal_j = drive_j / drive_efficiency - regen_j * regen_efficiency
        self.electrical = self.battery.exchange(terminal_j / self.dt_s, self.dt_s)
        self.energy["consumed_j"] += max(0, terminal_j)
        self.energy["recovered_j"] += max(0, -terminal_j)
        self.energy["battery_heat_j"] += self.electrical["heat_w"] * self.dt_s
        self.energy["conversion_loss_j"] += drive_j * (
            1 / drive_efficiency - 1
        ) + regen_j * (1 - regen_efficiency)
        self.energy["friction_heat_j"] += brake_j - regen_j
        self.energy["road_work_j"] += result.resistance_force_n * distance
        self.last = result

    def sensor_telemetry(self) -> dict:
        truth = self._observation()
        data = dict(
            sensors_enabled=bool(self.sensor_suite),
            actual_speed_ms=truth.speed_ms,
            actual_gap_m=truth.gap_m,
            actual_closing_speed_ms=truth.speed_ms - truth.lead_speed_ms
            if self.has_lead
            else None,
            controller_input_health=self.controller_input_health,
            applied_input_health=self.applied_input_health,
            controller_input_age_s=self.controller_input_age_s,
            controller_measured_speed_ms=self.controller_input_speed_ms,
            controller_measured_gap_m=self.controller_input_gap_m,
            active_sensor_faults=";".join(f.id for f in self.sensor_suite.active)
            if self.sensor_suite
            else "",
        )
        views = self.sensor_suite.views() if self.sensor_suite else {}
        for name in ("speed", "radar"):
            view = views.get(name, {})
            for key, default in [
                ("valid", False),
                ("status", "disabled"),
                ("age_s", None),
                ("sample_time_s", None),
                ("delivery_time_s", None),
                ("frozen", False),
                ("discarded_packets", 0),
            ]:
                data[name + "_sensor_" + key] = view.get(key, default)
        speed = views.get("speed", {}).get("values", {}).get("speed_ms")
        radar = views.get("radar", {}).get("values", {})
        distance = radar.get("distance_m")
        closing = radar.get("closing_speed_ms")
        data.update(
            measured_speed_ms=speed,
            measured_gap_m=distance,
            measured_closing_speed_ms=closing,
            speed_measurement_error_ms=speed - truth.speed_ms
            if data["speed_sensor_valid"]
            else None,
            radar_distance_error_m=distance - truth.gap_m
            if data["radar_sensor_valid"] and truth.gap_m is not None
            else None,
            radar_closing_speed_error_ms=closing
            - (truth.speed_ms - truth.lead_speed_ms)
            if data["radar_sensor_valid"] and truth.gap_m is not None
            else None,
        )
        return data

    def telemetry(self) -> dict:
        result = self.last
        shaft_torque = result.delivered_motor_torque_nm if result else 0.0
        if self.regen_force_n > 0:
            shaft_torque = (
                -self.regen_force_n
                * self.sim.vehicle.wheel_radius_m
                * self.sim.transmission.mechanical_efficiency
                / self.sim.transmission.active_ratio
            )
        observation = self._observation()
        return {
            **self.sensor_telemetry(),
            "controller_state": self.controller_state,
            "requested_acceleration_ms2": self.requested_acceleration,
            "target_speed_kmh": self.config.target_speed_kmh
            if self.controller
            else None,
            "lead_speed_kmh": observation.lead_speed_ms * 3.6
            if self.has_lead
            else None,
            "gap_m": observation.gap_m,
            "desired_gap_m": self.config.standstill_gap_m
            + self.config.time_headway_s * self.state.velocity_ms
            if self.has_lead
            else None,
            "ttc_s": observation.ttc_s if self.has_lead else None,
            "collision": self.collision,
            "minimum_gap_m": self.minimum_gap,
            "aeb_trigger_time_s": self.aeb_trigger_time_s,
            "type": "state",
            "status": self.status,
            "time_s": self.state.time_s,
            "position_m": self.state.position_m,
            "velocity_kmh": self.state.velocity_ms * 3.6,
            "acceleration_ms2": result.acceleration_ms2 if result else 0,
            "motor_rpm": result.motor_rpm if result else 0,
            "motor_torque_nm": shaft_torque,
            "motor_power_kw": (
                shaft_torque * result.motor_rpm * math.pi / 30 / 1000 if result else 0
            ),
            "drive_force_n": result.drive_force_n if result else 0,
            "brake_force_n": result.brake_force_n if result else 0,
            "resistance_force_n": result.resistance_force_n if result else 0,
            "traction_limited": result.traction_limited if result else False,
            "torque_limited": result.torque_limited if result else False,
            "soc": self.battery.soc,
            "battery_power_kw": self.electrical["terminal_power_w"] / 1000,
            "battery_voltage_v": self.electrical["voltage_v"],
            "battery_current_a": self.electrical["current_a"],
            "energy_consumed_kwh": self.energy["consumed_j"] / 3_600_000,
            "energy_recovered_kwh": self.energy["recovered_j"] / 3_600_000,
            "battery_heat_kwh": self.energy["battery_heat_j"] / 3_600_000,
            "conversion_loss_kwh": self.energy["conversion_loss_j"] / 3_600_000,
            "friction_heat_kwh": self.energy["friction_heat_j"] / 3_600_000,
            "road_work_kwh": self.energy["road_work_j"] / 3_600_000,
            "regen_force_n": self.regen_force_n,
            "friction_brake_force_n": max(0, result.brake_force_n - self.regen_force_n)
            if result
            else 0,
            "battery_limited": self.battery_limited,
            "energy_balance_error_j": (
                self.initial_energy_j
                - self.battery.energy_j
                + self.initial_kinetic_j
                - 0.5 * self.config.mass_kg * self.state.velocity_ms**2
                - self.energy["battery_heat_j"]
                - self.energy["conversion_loss_j"]
                - self.energy["friction_heat_j"]
                - self.energy["road_work_j"]
            ),
            "current_gear": self.sim.transmission.current_gear + 1,
        }
