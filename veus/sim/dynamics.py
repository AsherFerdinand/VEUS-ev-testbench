"""Forward-only longitudinal dynamics; SI units, explicit Euler integration."""
from dataclasses import dataclass, field
import math

from veus.model.motor import ElectricMotor
from veus.model.transmission import Transmission
from veus.model.vehicle import HighPerformanceVehicle


def _finite(**values: float) -> None:
    if any(not math.isfinite(value) for value in values.values()):
        raise ValueError(f"Values must be finite: {', '.join(values)}")


@dataclass(frozen=True)
class VehicleState:
    time_s: float = 0.0
    position_m: float = 0.0
    velocity_ms: float = 0.0

    def __post_init__(self):
        _finite(time=self.time_s, position=self.position_m, velocity=self.velocity_ms)
        if self.time_s < 0 or self.velocity_ms < 0:
            raise ValueError("Time and forward velocity must be nonnegative")


@dataclass(frozen=True)
class StepResult:
    state: VehicleState
    acceleration_ms2: float
    motor_rpm: float
    delivered_motor_torque_nm: float
    drive_force_n: float
    brake_force_n: float
    resistance_force_n: float
    torque_limited: bool
    traction_limited: bool


@dataclass
class LongitudinalSimulator:
    vehicle: HighPerformanceVehicle = field(default_factory=HighPerformanceVehicle)
    motor: ElectricMotor = field(default_factory=ElectricMotor)
    transmission: Transmission = field(default_factory=Transmission)
    friction_coefficient: float = 1.0
    gradient_rad: float = 0.0
    air_density_kg_m3: float = 1.225

    def step(self, state: VehicleState, motor_torque_nm: float,
             brake_force_n: float, dt_s: float) -> StepResult:
        """Hold one gear per step; brake command is friction braking, not regen.

        Acceleration and forces describe the beginning of the step. A stopping
        event truncates the step at zero speed and holds the vehicle thereafter.
        """
        v, m, tr = self.vehicle, self.motor, self.transmission
        _finite(torque=motor_torque_nm, brake=brake_force_n, dt=dt_s,
                friction=self.friction_coefficient, gradient=self.gradient_rad,
                density=self.air_density_kg_m3, mass=v.mass_kg, radius=v.wheel_radius_m,
                cd=v.cd, area=v.frontal_area_m2, rolling=v.rr_coeff,
                efficiency=tr.mechanical_efficiency, max_torque=m.max_torque_nm,
                max_power=m.max_power_kw, max_rpm=m.max_rpm)
        if dt_s <= 0 or motor_torque_nm < 0 or brake_force_n < 0:
            raise ValueError("Positive timestep and nonnegative drive/brake commands required")
        if (v.mass_kg <= 0 or v.wheel_radius_m <= 0 or v.frontal_area_m2 <= 0
                or min(v.cd, v.rr_coeff, self.friction_coefficient, self.air_density_kg_m3) < 0
                or not 0 < tr.mechanical_efficiency <= 1
                or min(m.max_torque_nm, m.max_power_kw, m.max_rpm) <= 0
                or abs(self.gradient_rad) >= math.pi / 2):
            raise ValueError("Invalid vehicle, motor, road or transmission configuration")
        if not tr.gear_ratios or any(not math.isfinite(r) or r <= 0 for r in tr.gear_ratios):
            raise ValueError("Gear ratios must be positive and finite")
        if not 0 <= tr.current_gear < len(tr.gear_ratios):
            raise ValueError("Invalid selected gear")
        ratio = tr.active_ratio
        rpm = state.velocity_ms / v.wheel_radius_m * ratio * 30 / math.pi
        available = 0.0 if rpm >= m.max_rpm else m.max_available_torque(rpm)
        torque = min(motor_torque_nm, available)
        normal = v.mass_kg * 9.81 * math.cos(self.gradient_rad)
        limit = self.friction_coefficient * normal
        raw_drive = torque * ratio * tr.mechanical_efficiency / v.wheel_radius_m
        drive = min(raw_drive, limit)
        # A single lumped contact patch: braking uses remaining force capacity.
        brake = min(brake_force_n, max(0.0, limit - drive))
        grade = v.mass_kg * 9.81 * math.sin(self.gradient_rad)
        aero = 0.5 * self.air_density_kg_m3 * v.cd * v.frontal_area_m2 * state.velocity_ms**2
        rolling = v.rr_coeff * normal
        if state.velocity_ms == 0:
            # Static holding prevents spontaneous rollback in this forward-only model.
            rolling = min(rolling, max(0.0, drive - grade - brake))
        resistance = grade + aero + rolling
        acceleration = (drive - brake - resistance) / v.mass_kg
        if state.velocity_ms == 0 and acceleration < 0:
            acceleration = 0.0
        moving_dt = dt_s
        if acceleration < 0 and state.velocity_ms + acceleration * dt_s < 0:
            moving_dt = -state.velocity_ms / acceleration
        # Explicit Euler position; use the exact constant-acceleration stopping
        # distance only for a step that ends at the zero-speed boundary.
        distance = state.velocity_ms * moving_dt
        if moving_dt < dt_s:
            distance += 0.5 * acceleration * moving_dt**2
        next_state = VehicleState(state.time_s + dt_s, state.position_m + distance,
                                  max(0.0, state.velocity_ms + acceleration * moving_dt))
        return StepResult(next_state, acceleration, rpm,
                          drive * v.wheel_radius_m / (ratio * tr.mechanical_efficiency),
                          drive, brake, resistance, torque < motor_torque_nm,
                          raw_drive > limit or brake < brake_force_n)
