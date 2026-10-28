"""Versioned measurement experiments and independent-input model adapters."""

import math
from pydantic import Field, model_validator
from typing import Literal
from veus.contracts import StrictModel
from veus.validation.measurements import (
    DataSource,
    ImportConfig,
    Measurements,
    Signal,
    interpolate,
    derive_acceleration,
)
from veus.sim.session import SimulationSession, RunConfig
from veus.sim.dynamics import VehicleState
from veus.model.vehicle import HighPerformanceVehicle
from veus.model.transmission import Transmission
from veus.model.energy_battery import EnergyBattery


class ModelParameters(StrictModel):
    mass_kg: float = Field(default=1800, ge=500, le=5000)
    drag_area_m2: float = Field(default=0.564, ge=0.1, le=2)
    rolling_resistance: float = Field(default=0.015, ge=0, le=0.05)
    wheel_radius_m: float = Field(default=0.355, ge=0.2, le=0.6)
    air_density_kg_m3: float = Field(default=1.225, ge=0.8, le=1.5)
    gear_ratio: float = Field(default=15, ge=1, le=25)
    road_gradient_offset_rad: float = Field(default=0, ge=-0.2, le=0.2)
    transmission_efficiency: float = Field(default=0.97, gt=0, le=1)
    drive_efficiency: float = Field(default=0.9, ge=0.5, le=1)
    regen_efficiency: float = Field(default=0.7, ge=0.1, le=1)
    max_power_kw: float = Field(default=150, ge=10, le=1000)
    max_torque_nm: float = Field(default=300, ge=10, le=1500)
    friction: float = Field(default=0.9, ge=0, le=1.5)
    battery_capacity_kwh: float = Field(default=60, ge=1, le=200)
    battery_voltage_v: float = Field(default=400, ge=100, le=1000)
    battery_resistance_ohm: float = Field(default=0.05, ge=0, le=1)
    discharge_limit_a: float = Field(default=500, ge=0, le=2000)
    charge_limit_a: float = Field(default=200, ge=0, le=1000)


class Comparison(StrictModel):
    signal: Signal
    metric: Literal["mae", "rmse", "max_abs_error", "abs_bias"] = "rmse"
    threshold: float = Field(ge=0)
    rationale: str = Field(min_length=1)
    uncertainty: float | None = Field(default=None, ge=0)


class Experiment(StrictModel):
    schema_version: Literal[1] = 1
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    objective: str = Field(min_length=1)
    source: DataSource
    preprocessing: ImportConfig
    kind: Literal["dynamics", "battery_current", "energy_replay"]
    parameters: ModelParameters = Field(default_factory=ModelParameters)
    dt_s: Literal[0.005, 0.01, 0.02, 0.05, 0.1] = 0.01
    initial_soc: float = Field(default=0.8, ge=0, le=1)
    initial_speed_ms: float | None = Field(default=None, ge=0, le=100)
    road_grade_policy: Literal["measured", "level_assumed"] = "measured"
    assumptions: list[str] = Field(min_length=1)
    derive_acceleration: bool = False
    minimum_coverage: float = Field(default=0.95, gt=0, le=1)
    comparisons: list[Comparison] = Field(min_length=1)

    @model_validator(mode="after")
    def roles(self):
        allowed = {
            "dynamics": {
                "vehicle_speed_ms",
                "longitudinal_acceleration_ms2",
                "position_m",
                "battery_voltage_v",
                "battery_current_a",
                "battery_soc",
                "battery_power_w",
                "energy_wh",
            },
            "battery_current": {
                "battery_voltage_v",
                "battery_soc",
                "battery_power_w",
                "energy_wh",
            },
            "energy_replay": {
                "battery_current_a",
                "battery_voltage_v",
                "battery_soc",
                "battery_power_w",
                "energy_wh",
            },
        }
        if any(c.signal not in allowed[self.kind] for c in self.comparisons):
            raise ValueError(
                "Comparison is not an independent output of this experiment"
            )
        if len({c.signal for c in self.comparisons}) != len(self.comparisons):
            raise ValueError("Duplicate comparison signal")
        if self.derive_acceleration and self.kind != "dynamics":
            raise ValueError(
                "Derived acceleration is only an output reference for dynamics"
            )
        return self


def prepare(data: Measurements, experiment: Experiment) -> Measurements:
    # Copy derived channels; never mutate caller's source representation.
    from dataclasses import replace

    signals = {k: list(v) for k, v in data.signals.items()}
    data = replace(data, signals=signals)
    if experiment.derive_acceleration:
        signals["longitudinal_acceleration_ms2"] = derive_acceleration(data)
    if (
        "battery_power_w" not in signals
        and {"battery_voltage_v", "battery_current_a"} <= signals.keys()
    ):
        signals["battery_power_w"] = [
            v * i if v is not None and i is not None else None
            for v, i in zip(signals["battery_voltage_v"], signals["battery_current_a"])
        ]
    if "energy_wh" not in signals and "battery_power_w" in signals:
        energy = [0.0]
        power = signals["battery_power_w"]
        for i in range(1, len(data.times)):
            good = (
                energy[-1] is not None
                and power[i - 1] is not None
                and power[i] is not None
                and data.times[i] - data.times[i - 1] <= data.max_gap_s
            )
            energy.append(
                energy[-1]
                + 0.5
                * (power[i - 1] + power[i])
                * (data.times[i] - data.times[i - 1])
                / 3600
                if good
                else None
            )
        signals["energy_wh"] = energy
    for c in experiment.comparisons:
        if c.signal not in signals:
            raise ValueError(f"Missing reference output: {c.signal}")
    return data


def require(data, signal, time, experiment):
    value = data.at(signal, time, experiment.preprocessing.input_interpolation)
    if value is None:
        raise ValueError(
            f"Required independent input {signal} unavailable at {time:.4f} s; no imputation allowed"
        )
    return value


def predict(
    experiment: Experiment,
    data: Measurements,
    parameters: ModelParameters | None = None,
) -> list[dict]:
    p = parameters or experiment.parameters
    dt = experiment.dt_s
    horizon = data.times[-1]
    if not 1 <= horizon <= 120:
        raise ValueError("Select a measurement window of 1..120 s")
    steps = round(horizon / dt)
    if abs(steps * dt - horizon) > 1e-7:
        raise ValueError("Final timestamp must align with the simulation timestep")
    soc = (
        data.signals["battery_soc"][0]
        if data.signals.get("battery_soc", [None])[0] is not None
        else experiment.initial_soc
    )
    if experiment.kind == "dynamics":
        speed = experiment.initial_speed_ms
        if speed is None:
            speed = data.signals.get("vehicle_speed_ms", [None])[0]
        if speed is None:
            raise ValueError("Dynamics needs an independent initial speed")
        cfg = RunConfig(
            mode="manual",
            duration_s=horizon,
            initial_speed_kmh=speed * 3.6,
            mass_kg=p.mass_kg,
            max_power_kw=p.max_power_kw,
            max_torque_nm=p.max_torque_nm,
            friction=p.friction,
            drive_efficiency=p.drive_efficiency,
            regen_efficiency=p.regen_efficiency,
            battery_capacity_kwh=p.battery_capacity_kwh,
            initial_soc=soc,
            battery_voltage_v=p.battery_voltage_v,
            battery_resistance_ohm=p.battery_resistance_ohm,
            discharge_limit_a=p.discharge_limit_a,
            charge_limit_a=p.charge_limit_a,
        )
        session = SimulationSession(cfg)
        session.dt_s = dt
        session.sim.vehicle = HighPerformanceVehicle(
            mass_kg=p.mass_kg,
            cd=p.drag_area_m2,
            frontal_area_m2=1,
            wheel_radius_m=p.wheel_radius_m,
            rr_coeff=p.rolling_resistance,
        )
        session.sim.transmission = Transmission(
            gear_ratios=[p.gear_ratio, p.gear_ratio],
            mechanical_efficiency=p.transmission_efficiency,
        )
        session.sim.air_density_kg_m3 = p.air_density_kg_m3
        position = data.signals.get("position_m", [0])[0] or 0
        session.state = VehicleState(position_m=position, velocity_ms=speed)
        session.status = "running"
        frames = [
            dict(
                time_s=0.0,
                vehicle_speed_ms=speed,
                position_m=position,
                longitudinal_acceleration_ms2=0.0,
                battery_soc=soc,
                battery_voltage_v=p.battery_voltage_v,
                battery_power_w=0.0,
                battery_current_a=0.0,
                energy_wh=0.0,
            )
        ]
        for tick in range(steps):
            time = tick * dt
            torque = require(data, "motor_torque_nm", time, experiment)
            brake = require(data, "brake_force_n", time, experiment)
            if torque < 0:
                raise ValueError(
                    "Dynamics requires nonnegative drive torque and separate positive brake force; signed torque replay is not supported"
                )
            session.sim.gradient_rad = (
                require(data, "road_gradient_rad", time, experiment)
                if experiment.road_grade_policy == "measured"
                else 0.0
            )
            session.sim.gradient_rad += p.road_gradient_offset_rad
            frame = session.step(motor_torque_nm=torque, brake_force_n=brake)
            frames.append(
                dict(
                    time_s=frame["time_s"],
                    vehicle_speed_ms=frame["velocity_kmh"] / 3.6,
                    position_m=frame["position_m"],
                    longitudinal_acceleration_ms2=frame["acceleration_ms2"],
                    battery_soc=frame["soc"],
                    battery_voltage_v=frame["battery_voltage_v"],
                    battery_power_w=frame["battery_power_kw"] * 1000,
                    battery_current_a=frame["battery_current_a"],
                    energy_wh=(
                        frame["energy_consumed_kwh"] - frame["energy_recovered_kwh"]
                    )
                    * 1000,
                )
            )
        return frames
    battery = EnergyBattery(
        p.battery_capacity_kwh,
        soc,
        p.battery_voltage_v,
        p.battery_resistance_ohm,
        p.discharge_limit_a,
        p.charge_limit_a,
    )
    frames = []
    net_wh = 0.0
    for tick in range(steps + 1):
        time = tick * dt
        if experiment.kind == "battery_current":
            current = require(data, "battery_current_a", time, experiment)
            if p.battery_resistance_ohm and current > p.battery_voltage_v / (
                2 * p.battery_resistance_ohm
            ):
                raise ValueError("Current exceeds stable battery model branch")
            power = (p.battery_voltage_v - current * p.battery_resistance_ohm) * current
        else:
            mechanical = require(data, "motor_torque_nm", time, experiment) * require(
                data, "motor_speed_rad_s", time, experiment
            )
            power = (
                mechanical / p.drive_efficiency
                if mechanical >= 0
                else mechanical * p.regen_efficiency
            )
        discharge, charge = battery.power_limits(dt)
        if power > discharge + 1e-6 or power < -charge - 1e-6:
            raise ValueError(
                "Measured demand is outside configured battery limits; no silent clipping"
            )
        # Evaluate voltage at the sample, then advance the left-held input interval.
        import copy

        evaluation = copy.copy(battery).exchange(power, dt)
        frames.append(
            dict(
                time_s=time,
                battery_voltage_v=evaluation["voltage_v"],
                battery_current_a=evaluation["current_a"],
                battery_power_w=power,
                battery_soc=battery.soc,
                energy_wh=net_wh,
            )
        )
        if tick < steps:
            battery.exchange(power, dt)
            net_wh += power * dt / 3600
    return frames


def error_metrics(reference: list, predicted: list) -> dict:
    pairs = [
        (a, b) for a, b in zip(reference, predicted) if a is not None and b is not None
    ]
    if len(reference) != len(predicted):
        raise ValueError("Signal lengths differ")
    if any(not math.isfinite(x) for pair in pairs for x in pair):
        raise ValueError("Nonfinite metric input")
    if not pairs:
        return dict(
            count=0,
            total=len(reference),
            coverage=0.0,
            mae=None,
            rmse=None,
            max_abs_error=None,
            bias=None,
            abs_bias=None,
        )
    residuals = [b - a for a, b in pairs]
    n = len(pairs)
    bias = sum(residuals) / n
    return dict(
        count=n,
        total=len(reference),
        coverage=n / len(reference),
        mae=sum(abs(x) for x in residuals) / n,
        rmse=math.sqrt(sum(x * x for x in residuals) / n),
        max_abs_error=max(abs(x) for x in residuals),
        bias=bias,
        abs_bias=abs(bias),
    )


def evaluate(
    experiment: Experiment,
    data: Measurements,
    parameters: ModelParameters | None = None,
) -> dict:
    data = prepare(data, experiment)
    frames = predict(experiment, data, parameters)
    times = [f["time_s"] for f in frames]
    metrics = {}
    residuals = []
    for comparison in experiment.comparisons:
        key = comparison.signal
        measured = data.signals[key][
            1:
        ]  # initial-state source is not validation evidence
        predictions = [
            interpolate(
                times,
                [f[key] for f in frames],
                t,
                experiment.dt_s * 1.01,
                experiment.preprocessing.comparison_interpolation,
            )
            for t in data.times[1:]
        ]
        m = error_metrics(measured, predictions)
        value = m[comparison.metric]
        uncertainty = comparison.uncertainty or 0.0
        lower = max(0.0, value - uncertainty) if value is not None else None
        upper = value + uncertainty if value is not None else None
        status = (
            "INCONCLUSIVE"
            if value is None or m["coverage"] < experiment.minimum_coverage
            else "PASS"
            if upper <= comparison.threshold
            else "FAIL"
            if lower > comparison.threshold
            else "INCONCLUSIVE"
        )
        metrics[key] = dict(
            **m,
            status=status,
            criterion=comparison.model_dump(mode="json"),
            uncertainty_interval=[lower, upper],
            uncertainty_interpretation="Uniform bounded output error allowance, not a statistical confidence interval; input uncertainty is not propagated",
        )
        for t, a, b in zip(data.times[1:], measured, predictions):
            residuals.append(
                dict(
                    time_s=t,
                    signal=key,
                    measured=a,
                    predicted=b,
                    residual=b - a if a is not None and b is not None else None,
                )
            )
    statuses = [m["status"] for m in metrics.values()]
    status = (
        "FAIL"
        if "FAIL" in statuses
        else "INCONCLUSIVE"
        if "INCONCLUSIVE" in statuses
        else "PASS"
    )
    events = {}
    if (
        experiment.kind == "dynamics"
        and "brake_force_n" in data.signals
        and "vehicle_speed_ms" in data.signals
    ):
        onset = next(
            (
                i
                for i, v in enumerate(data.signals["brake_force_n"])
                if v is not None and v > 0
            ),
            None,
        )
        stopped = (
            next(
                (
                    i
                    for i in range(onset or 0, len(data.times))
                    if data.signals["vehicle_speed_ms"][i] is not None
                    and data.signals["vehicle_speed_ms"][i] <= 0.05
                ),
                None,
            )
            if onset is not None
            else None
        )
        observed = None
        predicted = None
        if onset is not None and stopped is not None:
            if "position_m" in data.signals and all(
                data.signals["position_m"][i] is not None for i in [onset, stopped]
            ):
                observed = (
                    data.signals["position_m"][stopped]
                    - data.signals["position_m"][onset]
                )
                basis = "measured position difference"
            else:
                pieces = [
                    0.5
                    * (
                        data.signals["vehicle_speed_ms"][i]
                        + data.signals["vehicle_speed_ms"][i + 1]
                    )
                    * (data.times[i + 1] - data.times[i])
                    if data.signals["vehicle_speed_ms"][i] is not None
                    and data.signals["vehicle_speed_ms"][i + 1] is not None
                    and data.times[i + 1] - data.times[i] <= data.max_gap_s
                    else None
                    for i in range(onset, stopped)
                ]
                observed = sum(pieces) if all(v is not None for v in pieces) else None
                basis = "trapezoidal measured-speed distance, not a separate distance sensor"
            stop = next(
                (
                    f
                    for f in frames
                    if f["time_s"] >= data.times[onset]
                    and f["vehicle_speed_ms"] <= 0.05
                ),
                None,
            )
            origin = interpolate(
                times,
                [f["position_m"] for f in frames],
                data.times[onset],
                experiment.dt_s * 1.01,
            )
            predicted = (
                stop["position_m"] - origin if stop and origin is not None else None
            )
            events = dict(
                measured_braking_distance_m=observed,
                predicted_braking_distance_m=predicted,
                braking_distance_error_m=predicted - observed
                if predicted is not None and observed is not None
                else None,
                reference_basis=basis,
                stop_threshold_ms=0.05,
                limitation="Stop/onset quantized to recorded times; reaction distance excluded",
            )
    return dict(
        status=status,
        events=events,
        metrics=metrics,
        residuals=residuals,
        predictions=frames,
        initial_conditions=dict(
            initial_speed_ms=frames[0].get("vehicle_speed_ms"),
            initial_soc=frames[0]["battery_soc"],
        ),
        parameters=(parameters or experiment.parameters).model_dump(mode="json"),
    )
