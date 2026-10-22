"""Per-client interactive mechanical runs; independent of transport and UI."""
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
            self.last = self.sim.step(self.state, torque, brake_n, self.dt_s)
            self.ticks += 1
            self.state = VehicleState(self.ticks*self.dt_s, self.last.state.position_m,
                                      self.last.state.velocity_ms)
        if self.ticks >= round(self.config.duration_s/self.dt_s):
            self.status = 'completed'
        return self.telemetry()

    def telemetry(self) -> dict:
        result = self.last
        return {
            'type': 'state', 'status': self.status,
            'time_s': self.state.time_s, 'position_m': self.state.position_m,
            'velocity_kmh': self.state.velocity_ms*3.6,
            'acceleration_ms2': result.acceleration_ms2 if result else 0,
            'motor_rpm': result.motor_rpm if result else 0,
            'motor_torque_nm': result.delivered_motor_torque_nm if result else 0,
            'motor_power_kw': (result.delivered_motor_torque_nm*result.motor_rpm*math.pi/30/1000
                               if result else 0),
            'drive_force_n': result.drive_force_n if result else 0,
            'brake_force_n': result.brake_force_n if result else 0,
            'resistance_force_n': result.resistance_force_n if result else 0,
            'traction_limited': result.traction_limited if result else False,
            'torque_limited': result.torque_limited if result else False,
            'current_gear': self.sim.transmission.current_gear+1,
        }
