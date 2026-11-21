"""Coupling adapter around SimulationSession's authoritative energy integration."""

from types import SimpleNamespace
import math
from veus.sim.session import SimulationSession
from veus.sim.dynamics import VehicleState, road_loads
from veus.model.energy_battery import EnergyBattery
from veus.workbench.engineering import evaluate
from veus.workbench.adapter import mapped_parameters, ACKNOWLEDGEMENTS
from veus.model.vehicle import HighPerformanceVehicle
from veus.model.motor import ElectricMotor
from veus.model.transmission import Transmission
from veus.sim.dynamics import LongitudinalSimulator
from veus.model.efficiency_map import IllustrativeMotorMap


class BoundedBattery(EnergyBattery):
    def power_limits(self, dt_s):
        return super().power_limits(dt_s, **getattr(self, "envelope", {}))


class CoupledKernel(SimulationSession):
    """No legacy controller, sensor, WebSocket or automatic two-speed selection."""

    def __init__(self, design, experiment, acknowledgements, efficiency_model=None):
        if efficiency_model not in [None, "illustrative_map"]:
            raise ValueError("Unsupported powertrain efficiency model")
        self.efficiency_map = None
        result = evaluate(design)
        checks = [c for c in result["checks"] if c["status"] == "incompatible"]
        # The separate design operating point does not describe the selected experiment.
        checks = [
            c
            for c in checks
            if not c["id"].startswith("operating_") and c["id"] != "inverter_dc_current"
        ]
        if checks:
            raise ValueError(
                "Incompatible design: " + ", ".join(c["id"] for c in checks)
            )
        if not set(ACKNOWLEDGEMENTS) <= set(acknowledgements):
            raise ValueError(
                "Acknowledge all adapter model assumptions before execution"
            )
        missing = [
            k
            for k in result["simulation_readiness"]["missing_inputs"]
            if k != "nonzero_discharge_capability"
        ]
        if experiment.power_policy == "continuous":
            missing = [
                k for k in missing if k not in ["motor_peak_power", "motor_peak_torque"]
            ]
        if missing:
            raise ValueError("Missing essential simulation data: " + ", ".join(missing))
        if (
            design.inverter.minimum_dc_voltage_v is None
            or design.inverter.maximum_dc_current_a is None
        ):
            raise ValueError("Inverter voltage/current envelope required")
        if (
            experiment.power_policy == "acknowledged_peak"
            and "peak_envelope_without_thermal_model" not in acknowledgements
        ):
            raise ValueError(
                "Peak operation requires peak_envelope_without_thermal_model acknowledgement"
            )
        if experiment.power_policy == "acknowledged_peak":
            if efficiency_model and (
                design.motor.peak_duration_s is None
                or design.inverter.peak_duration_s is None
            ):
                raise ValueError(
                    "Mapped peak operation requires declared motor and inverter peak durations; select continuous policy"
                )
            if design.inverter.peak_power_kw is None:
                raise ValueError("Peak inverter power is required for peak policy")
            durations = [
                v
                for v in [design.motor.peak_duration_s, design.inverter.peak_duration_s]
                if v is not None
            ]
            if durations and experiment.duration_s > min(durations) + 1e-9:
                raise ValueError(
                    "Peak experiment exceeds a declared motor/inverter peak duration; use continuous policy or shorten run"
                )
        mass = result["specifications"]["total_mass_kg"]["value"]
        p = mapped_parameters(design, mass)
        eta = design.motor.efficiency_assumption * design.inverter.efficiency_assumption
        shaft_power = (
            design.motor.rated_power_kw
            if experiment.power_policy == "continuous"
            else design.motor.peak_power_kw
        )
        shaft_torque = (
            design.motor.rated_torque_nm
            if experiment.power_policy == "continuous"
            else design.motor.peak_torque_nm
        )
        ac_power = (
            design.inverter.continuous_power_kw
            if experiment.power_policy == "continuous"
            else design.inverter.peak_power_kw
        )
        if efficiency_model is None:
            shaft_power = min(
                shaft_power, ac_power * design.motor.efficiency_assumption
            )
        p["motor"]["max_power_kw"] = shaft_power
        p["motor"]["max_torque_nm"] = shaft_torque
        self.sim = LongitudinalSimulator(
            vehicle=HighPerformanceVehicle(**p["vehicle"]),
            motor=ElectricMotor(**p["motor"]),
            transmission=Transmission(**p["transmission"]),
            **(p["road"] | {"gradient_rad": math.atan(experiment.grade_percent / 100)}),
        )
        if efficiency_model:
            self.efficiency_map = IllustrativeMotorMap(self.sim.motor)
        self.battery = BoundedBattery(**p["battery"])
        self.battery.envelope = dict(
            terminal_minimum_v=max(
                design.battery.minimum_voltage_v, design.inverter.minimum_dc_voltage_v
            ),
            terminal_maximum_v=min(
                design.battery.maximum_voltage_v, design.inverter.maximum_dc_voltage_v
            ),
            terminal_current_limit_a=design.inverter.maximum_dc_current_a,
            discharge_power_limit_w=min(
                ac_power * 1000 / design.inverter.efficiency_assumption,
                shaft_power * 1000 / eta,
            ),
            charge_power_limit_w=ac_power
            * 1000
            * design.inverter.efficiency_assumption,
        )
        if self.efficiency_map:
            self.battery.envelope["discharge_power_limit_w"] = (
                ac_power * 1000 / design.inverter.efficiency_assumption
            )
        self.config = SimpleNamespace(
            drive_efficiency=eta,
            regen_efficiency=design.assumptions.regen_efficiency,
            regen_enabled=experiment.regen_enabled,
            max_power_kw=shaft_power,
            mass_kg=mass,
        )
        self.dt_s = experiment.dt_s
        self.state = VehicleState(velocity_ms=experiment.initial_speed_ms)
        self.initial_energy_j = self.battery.energy_j
        self.initial_kinetic_j = 0.5 * mass * self.state.velocity_ms**2
        self.energy = {
            k: 0.0
            for k in [
                "consumed_j",
                "recovered_j",
                "battery_heat_j",
                "conversion_loss_j",
                "friction_heat_j",
                "road_work_j",
            ]
        }
        self.electrical = dict(
            terminal_power_w=0.0, current_a=0.0, voltage_v=self.battery.voltage_v
        )
        self.regen_force_n = 0.0
        self.battery_limited = False
        self.last = None
        self.inverter_ac_cap_w = ac_power * 1000
        self.mass = mass
        self.design = design
        self.experiment = experiment
        self.road_energy = dict(aerodynamic_j=0.0, rolling_j=0.0, gradient_j=0.0)
        if self.efficiency_map:
            initial_rpm = (
                self.state.velocity_ms
                / self.sim.vehicle.wheel_radius_m
                * self.sim.transmission.active_ratio
                * 30
                / math.pi
            )
            self.efficiency_map.efficiency(initial_rpm, 0)
            self.map_losses = {
                key: 0.0
                for key in ["motor_loss_j", "inverter_loss_j", "gearbox_loss_j"]
            }

    def step_lab(self, torque, brake, grade_percent):
        self.sim.gradient_rad = math.atan(grade_percent / 100)
        self._energy_step(torque, brake)
        result = self.last
        distance = self._work_distance(result)
        road = road_loads(
            self.sim.vehicle,
            self.state.velocity_ms,
            self.sim.gradient_rad,
            self.sim.air_density_kg_m3,
        )
        for kind in ["aerodynamic", "rolling", "gradient"]:
            self.road_energy[kind + "_j"] += road[kind + "_n"] * distance
        regen_j = self.regen_force_n * distance
        motor_power = (
            result.drive_force_n
            * distance
            / self.sim.transmission.mechanical_efficiency
            - regen_j * self.sim.transmission.mechanical_efficiency
        ) / self.dt_s
        shaft_torque = (
            result.delivered_motor_torque_nm
            - self.regen_force_n
            * self.sim.vehicle.wheel_radius_m
            * self.sim.transmission.mechanical_efficiency
            / self.sim.transmission.active_ratio
        )
        friction_j = (result.brake_force_n - self.regen_force_n) * distance
        limits = []
        if self.battery_limited:
            limits.append("battery_or_inverter_electrical_envelope")
            current = self.electrical["current_a"]
            voltage = self.electrical["voltage_v"]
            if self.battery.soc <= 1e-10:
                limits.append("battery_SOC")
            if current >= self.battery.discharge_limit_a - 1e-6:
                limits.append("battery_discharge_current")
            if current >= self.design.inverter.maximum_dc_current_a - 1e-6:
                limits.append("inverter_DC_current")
            if (
                self.battery.resistance_ohm > 0
                and current > 1e-8
                and voltage <= self.battery.envelope["terminal_minimum_v"] + 1e-6
            ):
                limits.append("battery_inverter_terminal_voltage")
            if motor_power >= self.sim.motor.max_power_kw * 1000 - 1e-4:
                limits.append("motor_average_shaft_power")
            if (
                self.electrical["terminal_power_w"]
                * self.design.inverter.efficiency_assumption
                >= self.inverter_ac_cap_w - 1e-4
            ):
                limits.append("inverter_AC_output_power")
        if result.torque_limited:
            limits.append("motor_torque_power_or_speed")
        if result.traction_limited:
            limits.append("tyre_traction")
        if brake > 0 and friction_j > 1e-8 and self.experiment.regen_enabled:
            limits.append("regen_acceptance_or_motor_limit")
            if (
                self.battery.soc >= 1 - 1e-10
                or self.battery.charge_limit_a == 0
                or -self.electrical["current_a"] >= self.battery.charge_limit_a - 1e-6
            ):
                limits.append("battery_charge_acceptance")
        self.state = result.state
        residual = (
            self.initial_energy_j
            - self.battery.energy_j
            + self.initial_kinetic_j
            - 0.5 * self.mass * self.state.velocity_ms**2
            - self.energy["battery_heat_j"]
            - self.energy["conversion_loss_j"]
            - self.energy["friction_heat_j"]
            - self.energy["road_work_j"]
        )
        row = dict(
            time_s=self.state.time_s,
            position_m=self.state.position_m,
            speed_ms=self.state.velocity_ms,
            soc=self.battery.soc,
            battery_power_w=self.electrical["terminal_power_w"],
            motor_power_w=motor_power,
            motor_torque_nm=shaft_torque,
            acceleration_ms2=result.acceleration_ms2,
            battery_current_a=self.electrical["current_a"],
            battery_voltage_v=self.electrical["voltage_v"],
            regen_power_w=max(0, -self.electrical["terminal_power_w"]),
            regen_wheel_power_w=regen_j / self.dt_s,
            friction_power_w=friction_j / self.dt_s,
            grade_percent=grade_percent,
            limits=limits,
            energy_balance_error_j=residual,
            road_force_n=result.resistance_force_n,
            **road,
            battery_discharge_energy_j=self.energy["consumed_j"],
            battery_received_energy_j=self.energy["recovered_j"],
            battery_heat_j=self.energy["battery_heat_j"],
            conversion_loss_j=self.energy["conversion_loss_j"],
            friction_energy_j=self.energy["friction_heat_j"],
            **self.road_energy,
        )

        if self.efficiency_map:
            regenerative = regen_j > 0
            if motor_power == 0 and shaft_torque == 0:
                # No conversion occurs; an overspeed coast needs no extrapolation.
                eta_motor = None
                ac_power = 0.0
                if result.motor_rpm > self.sim.motor.max_rpm:
                    row["limits"].append(
                        "zero_power_outside_map_efficiency_unavailable"
                    )
            else:
                eta_motor = self.efficiency_map.efficiency(
                    result.motor_rpm, abs(shaft_torque), regenerative
                )
                ac_power = (
                    motor_power * eta_motor if regenerative else motor_power / eta_motor
                )
            wheel_power = (result.drive_force_n * distance - regen_j) / self.dt_s
            losses = dict(
                motor_loss_w=max(0, ac_power - motor_power),
                inverter_loss_w=max(0, self.electrical["terminal_power_w"] - ac_power),
                gearbox_loss_w=max(0, motor_power - wheel_power),
            )
            for key, value in losses.items():
                self.map_losses[key.replace("_w", "_j")] += value * self.dt_s
            row.update(
                motor_rpm=result.motor_rpm,
                motor_efficiency=eta_motor,
                inverter_efficiency=self.design.inverter.efficiency_assumption,
                motor_ac_power_w=ac_power,
                **losses,
                **self.map_losses,
            )
        return row

    def _drive_conversion_efficiency(self, result):
        if not self.efficiency_map:
            return super()._drive_conversion_efficiency(result)
        if result.delivered_motor_torque_nm == 0:
            # Neutral algebraic divisor for zero work, not an efficiency estimate.
            return 1.0
        eta = self.efficiency_map.efficiency(
            result.motor_rpm, result.delivered_motor_torque_nm
        )
        return (
            eta
            * self.design.inverter.efficiency_assumption
            * self.sim.transmission.mechanical_efficiency
        )

    def _drive_power_limit(self, result, discharge_w):
        if not self.efficiency_map:
            return super()._drive_power_limit(result, discharge_w)
        if result.delivered_motor_torque_nm == 0:
            return discharge_w
        eta = self.efficiency_map.efficiency(
            result.motor_rpm, result.delivered_motor_torque_nm
        )
        return min(
            discharge_w,
            self.sim.motor.max_power_kw
            * 1000
            / (eta * self.design.inverter.efficiency_assumption),
        )

    def _regenerative_recovery(self, result, distance, brake_j, charge_w):
        if not self.efficiency_map:
            return super()._regenerative_recovery(result, distance, brake_j, charge_w)
        rpm = result.motor_rpm
        tr = self.sim.transmission
        radius = self.sim.vehicle.wheel_radius_m

        def eta(joules):
            torque = (
                joules / distance * radius * tr.mechanical_efficiency / tr.active_ratio
                if distance > 0
                else 0
            )
            return (
                self.efficiency_map.efficiency(rpm, torque, True)
                * self.design.inverter.efficiency_assumption
                * tr.mechanical_efficiency
            )

        if (
            not self.config.regen_enabled
            or distance <= 0
            or rpm >= self.sim.motor.max_rpm
        ):
            return 0.0, 1.0
        maximum = min(
            brake_j,
            self.efficiency_map.torque_limit(rpm, True)
            * tr.active_ratio
            / (tr.mechanical_efficiency * radius)
            * distance,
            self.sim.motor.max_power_kw * 1000 * self.dt_s / tr.mechanical_efficiency,
        )
        budget = charge_w * self.dt_s
        if maximum * eta(maximum) <= budget:
            return maximum, eta(maximum)
        lo, hi = 0.0, maximum
        for _ in range(40):
            mid = (lo + hi) / 2
            if mid * eta(mid) <= budget:
                lo = mid
            else:
                hi = mid
        return lo, eta(lo)
