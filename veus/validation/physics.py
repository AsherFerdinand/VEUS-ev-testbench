"""Independent analytical trajectory references and first-order error bounds."""

from dataclasses import dataclass
import math
from veus.model.vehicle import HighPerformanceVehicle
from veus.model.transmission import Transmission
from veus.model.energy_battery import EnergyBattery
from veus.sim.dynamics import LongitudinalSimulator, VehicleState


@dataclass
class ReferenceTrace:
    name: str
    unit: str
    equation: str
    tolerance: float
    times_s: list[float]
    reference: list[float]
    simulated: list[float]

    @property
    def max_error(self) -> float:
        return max(abs(a - b) for a, b in zip(self.reference, self.simulated))

    def summary(self) -> dict:
        return dict(
            name=self.name,
            unit=self.unit,
            equation=self.equation,
            tolerance=self.tolerance,
            max_absolute_error=self.max_error,
            status="PASS" if self.max_error <= self.tolerance else "FAIL",
        )


def physics_references(dt_s: float = 0.01) -> list[ReferenceTrace]:
    if (
        not math.isfinite(dt_s)
        or dt_s <= 0
        or dt_s > 0.1
        or abs(10 / dt_s - round(10 / dt_s)) > 1e-8
    ):
        raise ValueError("Use a timestep <= 0.1 s that exactly divides 10 s")
    traces = []
    for name, v0, torque, brake, grade, cd, duration in (
        ("acceleration", 0.0, 500.0, 0.0, 0.0, 0.0, 4.0),
        ("braking", 10.0, 0.0, 2000.0, 0.0, 0.0, 6.0),
        ("gradient", 20.0, 0.0, 0.0, 0.1, 0.0, 4.0),
        ("coasting", 20.0, 0.0, 0.0, 0.0, 0.3, 10.0),
    ):
        if abs(duration / dt_s - round(duration / dt_s)) > 1e-8:
            raise ValueError("Timestep must divide all reference durations")
        sim = LongitudinalSimulator(
            vehicle=HighPerformanceVehicle(
                mass_kg=1000, wheel_radius_m=0.5, cd=cd, frontal_area_m2=2, rr_coeff=0
            ),
            transmission=Transmission(gear_ratios=[1.0], mechanical_efficiency=1.0),
            gradient_rad=grade,
        )
        state = VehicleState(velocity_ms=v0)
        times = [0.0]
        velocities = [v0]
        positions = [0.0]
        for tick in range(round(duration / dt_s)):
            state = sim.step(state, torque, brake, dt_s).state
            times.append((tick + 1) * dt_s)
            velocities.append(state.velocity_ms)
            positions.append(state.position_m)
        a = torque / 0.5 / 1000 - brake / 1000 - 9.81 * math.sin(grade)
        if name == "coasting":
            k = 0.5 * 1.225 * cd * 2 / 1000
            ref_v = [v0 / (1 + k * v0 * t) for t in times]
            ref_x = [math.log1p(k * v0 * t) / k for t in times]
            # f' <= 0 and |f' dt| < 1: non-expansive Euler. Bound accumulated
            # local speed error by T*max(|v''|)/2*dt, |v''| <= 2 k² v0³.
            vtol = duration * k * k * v0**3 * dt_s + 1e-9
            xtol = dt_s * (v0 - ref_v[-1]) + duration * vtol + 1e-9
            equation = "v=v0/(1+k*v0*t); x=ln(1+k*v0*t)/k; k=rho*Cd*A/(2m)"
        else:
            moving = [min(t, -v0 / a) if a < 0 and v0 + a * t < 0 else t for t in times]
            ref_v = [max(0.0, v0 + a * t) for t in times]
            ref_x = [v0 * t + 0.5 * a * t * t for t in moving]
            vtol = 1e-9
            xtol = (
                0.5 * v0 * dt_s + 0.5 * abs(a) * dt_s**2 + 1e-9
                if name == "braking"
                else 0.5 * abs(a) * duration * dt_s + 1e-9
            )
            equation = "v=max(0,v0+a*t); x=v0*t_moving+0.5*a*t_moving²; a=(Fdrive-Fbrake)/m-g*sin(grade)"
        traces.extend(
            [
                ReferenceTrace(
                    name + "_speed", "m/s", equation, vtol, times, ref_v, velocities
                ),
                ReferenceTrace(
                    name + "_position", "m", equation, xtol, times, ref_x, positions
                ),
            ]
        )
    battery = EnergyBattery()
    initial = battery.energy_j
    power = 20000.0
    duration = 10.0
    # Direct quadratic root is deliberately distinct from the implementation's
    # cancellation-resistant rationalized root.
    current = (400 - math.sqrt(400**2 - 4 * 0.05 * power)) / (2 * 0.05)
    times = [0.0]
    simulated = [0.0]
    for tick in range(round(duration / dt_s)):
        battery.exchange(power, dt_s)
        times.append((tick + 1) * dt_s)
        simulated.append(initial - battery.energy_j)
    traces.append(
        ReferenceTrace(
            "battery_chemical_energy",
            "J",
            "I=(Voc-sqrt(Voc²-4*R*P))/(2R); E_drawn=Voc*I*t",
            1e-4,
            times,
            [400 * current * t for t in times],
            simulated,
        )
    )
    # Coupled acceleration-to-battery reference, not just a battery identity.
    from veus.sim.session import RunConfig, SimulationSession

    session = SimulationSession(
        RunConfig(
            mode="acceleration",
            duration_s=4,
            mass_kg=1000,
            max_torque_nm=300,
            drive_efficiency=0.8,
            battery_resistance_ohm=0,
        )
    )
    session.sim.vehicle = HighPerformanceVehicle(
        mass_kg=1000, wheel_radius_m=0.5, cd=0, rr_coeff=0
    )
    session.sim.transmission = Transmission(
        gear_ratios=[1.0, 1.0], mechanical_efficiency=1.0
    )
    session.dt_s = dt_s
    session.status = "running"
    times = [0.0]
    observed = [0.0]
    for tick in range(round(4 / session.dt_s)):
        frame = session.step()
        times.append(frame["time_s"])
        observed.append(frame["energy_consumed_kwh"] * 3_600_000)
    traces.append(
        ReferenceTrace(
            "coupled_drive_energy",
            "J",
            "a=T/(r*m)=0.6 m/s²; E_terminal=0.5*m*(a*t)²/eta; eta=0.8, R=0",
            1e-4,
            times,
            [0.5 * 1000 * (0.6 * t) ** 2 / 0.8 for t in times],
            observed,
        )
    )
    # Independent kinetic-energy recovery reference under constant brake force.
    from veus.sim.session import Controls

    regen = SimulationSession(
        RunConfig(
            mode="manual",
            duration_s=2,
            initial_speed_kmh=36,
            mass_kg=1000,
            max_torque_nm=300,
            regen_efficiency=0.7,
            battery_resistance_ohm=0,
        )
    )
    regen.dt_s = dt_s
    regen.sim.vehicle = HighPerformanceVehicle(
        mass_kg=1000, wheel_radius_m=0.5, cd=0, rr_coeff=0
    )
    regen.sim.transmission = Transmission(
        gear_ratios=[1.0, 1.0], mechanical_efficiency=1.0
    )
    regen.controls = Controls(brake=0.05)
    regen.status = "running"
    times = [0.0]
    observed = [0.0]
    for tick in range(round(2 / dt_s)):
        frame = regen.step()
        times.append(frame["time_s"])
        observed.append(frame["energy_recovered_kwh"] * 3_600_000)
    traces.append(
        ReferenceTrace(
            "regenerative_energy",
            "J",
            "a=-0.05*g; E_recovered=eta*0.5*m*(v0²-(v0+a*t)²); eta=0.7, R=0",
            1e-4,
            times,
            [0.7 * 0.5 * 1000 * (10**2 - (10 - 0.05 * 9.81 * t) ** 2) for t in times],
            observed,
        )
    )
    return traces
