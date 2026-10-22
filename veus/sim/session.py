"""Per-client EV runs with mechanical dynamics and conserved energy accounting."""
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from veus.model.energy_battery import EnergyBattery
from veus.model.motor import ElectricMotor
from veus.model.vehicle import HighPerformanceVehicle
from veus.sim.dynamics import LongitudinalSimulator, VehicleState


class RunConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
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
    mode: Literal['manual', 'acceleration', 'braking', 'coast'] = 'manual'


class Controls(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
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
            motor=ElectricMotor(max_torque_nm=config.max_torque_nm,
                                max_power_kw=config.max_power_kw),
            friction_coefficient=config.friction,
            gradient_rad=math.atan(config.grade_percent / 100))
        self.state = VehicleState(velocity_ms=config.initial_speed_kmh / 3.6)
        self.controls = Controls()
        self.status = 'ready'
        self.ticks = 0
        self.last = None
        self.battery = EnergyBattery(config.battery_capacity_kwh, config.initial_soc,
                                     config.battery_voltage_v, config.battery_resistance_ohm,
                                     config.discharge_limit_a, config.charge_limit_a)
        self.initial_energy_j = self.battery.energy_j
        self.initial_kinetic_j = 0.5*config.mass_kg*self.state.velocity_ms**2
        self.energy = dict(consumed_j=0., recovered_j=0., battery_heat_j=0.,
                           conversion_loss_j=0., friction_heat_j=0., road_work_j=0.)
        self.electrical = dict(terminal_power_w=0., current_a=0.,
                               voltage_v=config.battery_voltage_v)
        self.regen_force_n = 0.
        self.battery_limited = False

    def advance(self) -> dict:
        if self.status != 'running':
            return self.telemetry()
        modes = {'acceleration': Controls(throttle=1), 'braking': Controls(brake=1),
                 'coast': Controls()}
        controls = modes.get(self.config.mode, self.controls)
        # Brake overrides throttle; no simultaneous propulsion/braking command.
        torque = 0 if controls.brake > 0 else controls.throttle*self.config.max_torque_nm
        brake_n = controls.brake*self.config.mass_kg*9.81
        for _ in range(self.steps_per_frame):
            if self.ticks >= round(self.config.duration_s/self.dt_s):
                break
            self.sim.transmission.current_gear = 1 if self.state.velocity_ms > 27.7 else 0
            self._energy_step(torque, brake_n)
            self.ticks += 1
            self.state = VehicleState(self.ticks*self.dt_s, self.last.state.position_m,
                                      self.last.state.velocity_ms)
        if self.ticks >= round(self.config.duration_s/self.dt_s):
            self.status = 'completed'
        return self.telemetry()

    def _work_distance(self, result) -> float:
        # Integrate the held acceleration over the moving part of the interval.
        moving_dt = self.dt_s
        if result.acceleration_ms2 < 0:
            moving_dt = min(moving_dt, -self.state.velocity_ms/result.acceleration_ms2)
        return 0.5*(self.state.velocity_ms+result.state.velocity_ms)*moving_dt

    def _energy_step(self, torque: float, brake_n: float) -> None:
        discharge_w, charge_w = self.battery.power_limits(self.dt_s)
        drive_efficiency = self.config.drive_efficiency*self.sim.transmission.mechanical_efficiency
        regen_efficiency = self.config.regen_efficiency*self.sim.transmission.mechanical_efficiency
        result = self.sim.step(self.state, torque, brake_n, self.dt_s)
        def demand(r):
            return r.drive_force_n*self._work_distance(r)/(drive_efficiency*self.dt_s)
        self.battery_limited = demand(result) > discharge_w+1e-7
        if self.battery_limited:
            lo, hi = 0., torque
            for _ in range(40):
                mid = (lo+hi)/2
                candidate = self.sim.step(self.state, mid, brake_n, self.dt_s)
                if demand(candidate) <= discharge_w:
                    lo = mid
                else:
                    hi = mid
            result = self.sim.step(self.state, lo, brake_n, self.dt_s)
        distance = self._work_distance(result)
        drive_j = result.drive_force_n*distance
        brake_j = result.brake_force_n*distance
        regen_j = 0.
        self.regen_force_n = 0.
        if self.config.regen_enabled and distance > 0 and result.motor_rpm < self.sim.motor.max_rpm:
            tr = self.sim.transmission
            motor_force = self.sim.motor.max_available_torque(result.motor_rpm)*tr.active_ratio/(tr.mechanical_efficiency*self.sim.vehicle.wheel_radius_m)
            regen_j = min(brake_j, motor_force*distance,
                          self.config.max_power_kw*1000*self.dt_s/tr.mechanical_efficiency,
                          charge_w*self.dt_s/regen_efficiency)
            self.regen_force_n = regen_j/distance
        terminal_j = drive_j/drive_efficiency-regen_j*regen_efficiency
        self.electrical = self.battery.exchange(terminal_j/self.dt_s, self.dt_s)
        self.energy['consumed_j'] += max(0, terminal_j)
        self.energy['recovered_j'] += max(0, -terminal_j)
        self.energy['battery_heat_j'] += self.electrical['heat_w']*self.dt_s
        self.energy['conversion_loss_j'] += drive_j*(1/drive_efficiency-1)+regen_j*(1-regen_efficiency)
        self.energy['friction_heat_j'] += brake_j-regen_j
        self.energy['road_work_j'] += result.resistance_force_n*distance
        self.last = result

    def telemetry(self) -> dict:
        result = self.last
        shaft_torque = (result.delivered_motor_torque_nm if result else 0.)
        if self.regen_force_n > 0:
            shaft_torque = -self.regen_force_n*self.sim.vehicle.wheel_radius_m*self.sim.transmission.mechanical_efficiency/self.sim.transmission.active_ratio
        return {
            'type': 'state', 'status': self.status,
            'time_s': self.state.time_s, 'position_m': self.state.position_m,
            'velocity_kmh': self.state.velocity_ms*3.6,
            'acceleration_ms2': result.acceleration_ms2 if result else 0,
            'motor_rpm': result.motor_rpm if result else 0,
            'motor_torque_nm': shaft_torque,
            'motor_power_kw': (shaft_torque*result.motor_rpm*math.pi/30/1000
                               if result else 0),
            'drive_force_n': result.drive_force_n if result else 0,
            'brake_force_n': result.brake_force_n if result else 0,
            'resistance_force_n': result.resistance_force_n if result else 0,
            'traction_limited': result.traction_limited if result else False,
            'torque_limited': result.torque_limited if result else False,
            'soc': self.battery.soc,
            'battery_power_kw': self.electrical['terminal_power_w']/1000,
            'battery_voltage_v': self.electrical['voltage_v'],
            'battery_current_a': self.electrical['current_a'],
            'energy_consumed_kwh': self.energy['consumed_j']/3_600_000,
            'energy_recovered_kwh': self.energy['recovered_j']/3_600_000,
            'battery_heat_kwh': self.energy['battery_heat_j']/3_600_000,
            'conversion_loss_kwh': self.energy['conversion_loss_j']/3_600_000,
            'friction_heat_kwh': self.energy['friction_heat_j']/3_600_000,
            'road_work_kwh': self.energy['road_work_j']/3_600_000,
            'regen_force_n': self.regen_force_n,
            'friction_brake_force_n': max(0, result.brake_force_n-self.regen_force_n) if result else 0,
            'battery_limited': self.battery_limited,
            'energy_balance_error_j': (
                self.initial_energy_j-self.battery.energy_j + self.initial_kinetic_j
                -0.5*self.config.mass_kg*self.state.velocity_ms**2
                -self.energy['battery_heat_j']-self.energy['conversion_loss_j']
                -self.energy['friction_heat_j']-self.energy['road_work_j']),
            'current_gear': self.sim.transmission.current_gear+1,
        }
