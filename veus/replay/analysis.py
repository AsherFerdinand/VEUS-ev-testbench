"""Deterministic full-resolution recorded-data analysis. No vehicle model runs."""

import hashlib
import json
import platform
from importlib.metadata import version
from typing import Literal
from pydantic import Field, model_validator
from veus.contracts import StrictModel
from veus.validation.measurements import (
    DataSource,
    ImportConfig,
    load_csv,
    derive_acceleration,
    CANONICAL,
)

VERSION = "veus-replay-v1"


class EventSettings(StrictModel):
    acceleration_ms2: float = Field(default=2.0, gt=0, le=20)
    deceleration_ms2: float = Field(default=2.5, gt=0, le=20)
    power_magnitude_w: float = Field(default=50000.0, gt=0, le=2_000_000)
    standstill_ms: float = Field(default=0.1, ge=0, le=2)
    minimum_duration_s: float = Field(default=0.5, ge=0, le=30)
    regen_power_w: float = Field(default=1000.0, gt=0)
    regen_deceleration_ms2: float = Field(default=0.1, gt=0)


class SanityLimits(StrictModel):
    speed_ms: float = Field(default=120.0, gt=0, le=500)
    voltage_v: float = Field(default=2000.0, gt=0, le=10000)
    current_a: float = Field(default=5000.0, gt=0, le=100000)
    measured_acceleration_ms2: float = Field(default=100.0, gt=0, le=1000)


class ReplayConfig(StrictModel):
    schema_version: Literal[1] = 1
    source: DataSource
    preprocessing: ImportConfig
    current_sign: Literal["unknown", "discharge_positive", "charge_positive"] = (
        "unknown"
    )
    sign_evidence: str | None = None
    thresholds: EventSettings = Field(default_factory=EventSettings)
    sanity_limits: SanityLimits = Field(default_factory=SanityLimits)
    limitations: list[str] = Field(min_length=1)
    provenance: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def evidence(self):
        if self.current_sign != "unknown" and (
            not self.sign_evidence or len(self.sign_evidence.strip()) < 10
        ):
            raise ValueError(
                "Known current sign requires explicit evidence; this assertion is not authenticated"
            )
        if "vehicle_speed_ms" not in self.preprocessing.columns:
            raise ValueError("Replay requires a measured speed column")
        return self


def canonical(value):
    # JavaScript serializes 0.0 as 0 in opaque provenance. Hash the same numeric
    # content consistently after a browser round trip, including negative zero.
    def normal(item):
        if isinstance(item, float) and item.is_integer():
            return int(item)
        if isinstance(item, dict):
            return {key: normal(child) for key, child in item.items()}
        if isinstance(item, list):
            return [normal(child) for child in item]
        return item

    return (
        json.dumps(normal(value), sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()


def positive_integral(a, b, dt):
    """Exact positive area for a linearly interpolated pair, including sign crossing."""
    if a >= 0 and b >= 0:
        return (a + b) * dt / 2
    if a <= 0 and b <= 0:
        return 0.0
    fraction = abs(a) / (abs(a) + abs(b))
    return a * dt * fraction / 2 if a > 0 else b * dt * (1 - fraction) / 2


def analyse(raw: bytes, config: ReplayConfig):
    if len(raw) > 2_000_000:
        raise ValueError("Replay supports CSV windows up to 2 MB and 5000 rows")
    data = load_csv(raw, config.source, config.preprocessing)
    if len(data.times) > 5000:
        raise ValueError(
            "Replay supports at most 5000 full-resolution rows; select a documented window"
        )
    times, measured = data.times, data.signals
    if times[-1] > 86400:
        raise ValueError(
            "Replay window exceeds one day; select a documented smaller window"
        )
    limits = config.sanity_limits
    for key, bound in [
        ("vehicle_speed_ms", limits.speed_ms),
        ("battery_voltage_v", limits.voltage_v),
        ("battery_current_a", limits.current_a),
        ("longitudinal_acceleration_ms2", limits.measured_acceleration_ms2),
    ]:
        if any(v is not None and abs(v) > bound for v in measured.get(key, [])):
            raise ValueError(
                f"{key} exceeds the declared broad sanity limit {bound}; inspect units/source or explicitly configure appropriate limits"
            )
    if any(
        v is not None and not -100 <= v <= 100
        for v in measured.get("ambient_temperature_c", [])
    ):
        raise ValueError("Ambient temperature outside broad -100..100 °C sanity range")
    if any(
        v is not None and abs(v) > 10_000_000
        for v in measured.get("battery_power_w", [])
    ):
        raise ValueError(
            "Recorded power exceeds broad 10 MW sanity limit; inspect units"
        )
    speed = measured["vehicle_speed_ms"]
    voltage, current = (
        measured.get("battery_voltage_v"),
        measured.get("battery_current_a"),
    )
    derived = {"acceleration_ms2": derive_acceleration(data)}
    if voltage is not None and current is not None:
        derived["electrical_power_w"] = [
            v * i if v is not None and i is not None else None
            for v, i in zip(voltage, current)
        ]
    # Derived electrical quantities use V*I only, not an undocumented measured power sign.
    power = derived.get("electrical_power_w")
    distance = [0.0]
    valid_speed = []
    covered_s = 0.0
    for i, (left, right) in enumerate(zip(times, times[1:])):
        dt = right - left
        valid = (
            dt <= data.max_gap_s and speed[i] is not None and speed[i + 1] is not None
        )
        valid_speed.append(valid)
        area = (speed[i] + speed[i + 1]) * dt / 2 if valid else 0.0
        distance.append(distance[-1] + area)
        if valid:
            covered_s += dt
    derived["known_segment_distance_m"] = distance
    duration = times[-1]
    full_speed = all(valid_speed)
    energy_used, energy_received = [0.0], [0.0]
    sign = 1 if config.current_sign == "discharge_positive" else -1
    energy_valid = (
        config.current_sign != "unknown"
        and power is not None
        and all(v is not None for v in power)
        and not data.metadata["gaps"]
    )
    if energy_valid:
        for i, (left, right) in enumerate(zip(times, times[1:])):
            a, b, dt = power[i] * sign, power[i + 1] * sign, right - left
            energy_used.append(energy_used[-1] + positive_integral(a, b, dt) / 3600)
            energy_received.append(
                energy_received[-1] + positive_integral(-a, -b, dt) / 3600
            )
        derived["electrical_energy_used_wh"] = energy_used
        derived["electrical_energy_received_wh"] = energy_received
    energy_reason = (
        "Current polarity is unverified; signed V×I does not establish discharge or charging."
        if config.current_sign == "unknown"
        else "Voltage/current missing or timestamp gaps prevent complete energy integration."
    )
    events = []

    def add(kind, start, end, signals, rule, qualification, classification):
        events.append(
            dict(
                type=kind,
                start_s=start,
                end_s=end,
                source_start_s=start + data.metadata["time_origin_s"],
                source_end_s=end + data.metadata["time_origin_s"],
                signals=signals,
                rule=rule,
                qualification=qualification,
                classification=classification,
            )
        )

    def runs(kind, values, predicate, signals, rule, classification):
        start = None
        last = None
        for i in range(len(times) + 1):
            match = i < len(times) and values[i] is not None and predicate(values[i], i)
            if start is not None and (
                not match or times[i] - times[i - 1] > data.max_gap_s
            ):
                if (
                    times[last] - times[start] + 1e-9
                    >= config.thresholds.minimum_duration_s
                ):
                    add(
                        kind,
                        times[start],
                        times[last],
                        signals,
                        rule,
                        "Threshold episode on recorded samples; timing/derivatives depend on sampling and noise, not a diagnosed cause.",
                        classification,
                    )
                start = None
            if match:
                if start is None:
                    start = i
                last = i

    t = config.thresholds
    runs(
        "strong_acceleration",
        derived["acceleration_ms2"],
        lambda v, i: v >= t.acceleration_ms2,
        ["vehicle_speed_ms", "acceleration_ms2"],
        f"derived acceleration >= {t.acceleration_ms2} m/s²",
        "inferred",
    )
    runs(
        "strong_deceleration",
        derived["acceleration_ms2"],
        lambda v, i: v <= -t.deceleration_ms2,
        ["vehicle_speed_ms", "acceleration_ms2"],
        f"derived acceleration <= {-t.deceleration_ms2} m/s²",
        "inferred",
    )
    runs(
        "standstill",
        speed,
        lambda v, i: v <= t.standstill_ms,
        ["vehicle_speed_ms"],
        f"measured speed <= {t.standstill_ms} m/s",
        "observed sample threshold",
    )
    observed_power = power if power is not None else measured.get("battery_power_w")
    if observed_power is not None:
        runs(
            "high_electrical_magnitude",
            observed_power,
            lambda v, i: abs(v) >= t.power_magnitude_w,
            ["battery_voltage_v", "battery_current_a", "electrical_power_w"]
            if power is not None
            else ["battery_power_w"],
            f"abs(signed electrical power) >= {t.power_magnitude_w} W",
            "derived V×I magnitude"
            if power is not None
            else "observed power magnitude; polarity/propulsion origin not inferred",
        )
        if config.current_sign != "unknown" and power is not None:
            runs(
                "possible_regenerative_braking",
                power,
                lambda v, i: v * sign <= -t.regen_power_w
                and derived["acceleration_ms2"][i] is not None
                and derived["acceleration_ms2"][i] <= -t.regen_deceleration_ms2,
                ["battery_voltage_v", "battery_current_a", "vehicle_speed_ms"],
                f"discharge-positive V×I <= {-t.regen_power_w} W and acceleration <= {-t.regen_deceleration_ms2} m/s²",
                "inferred possibility; charging source is not independently established",
            )
    for gap in data.metadata["gaps"]:
        add(
            "timestamp_gap",
            gap["start_s"],
            gap["end_s"],
            ["time_s"],
            f"interval > {data.max_gap_s} s",
            "Travel and measurements inside the interval are unknown; no interpolation/integration.",
            "observed availability",
        )
    # Missing episodes are grouped by row, with the union of affected channels.
    start = None
    missing_signals = set()
    for i in range(len(times) + 1):
        missing = (
            {k for k, values in measured.items() if values[i] is None}
            if i < len(times)
            else set()
        )
        if start is not None and (
            not missing or times[i] - times[i - 1] > data.max_gap_s
        ):
            add(
                "missing_measurements",
                times[start],
                times[i - 1],
                sorted(missing_signals),
                "one or more mapped fields unavailable",
                "Missing data does not establish a sensor failure; original nulls retained.",
                "observed availability",
            )
            start, missing_signals = None, set()
        if missing:
            if start is None:
                start = i
            missing_signals |= missing
    events.sort(key=lambda e: (e["start_s"], e["end_s"], e["type"]))
    if len(events) > 10000:
        raise ValueError(
            "Too many events for an interactive window; narrow the recording or adjust thresholds"
        )
    metrics = {}

    def metric(key, value, unit, definition, classification="derived", reason=None):
        metrics[key] = dict(
            value=value,
            unit=unit,
            definition=definition,
            classification=classification,
            unavailable_reason=reason if value is None else None,
        )

    finite_speed = [v for v in speed if v is not None]
    acc = [v for v in derived["acceleration_ms2"] if v is not None]
    finite_power = [v for v in (observed_power or []) if v is not None]
    metric(
        "recording_duration_s",
        duration,
        "s",
        "Last minus first recorded timestamp.",
        config.source.kind + " timestamp statistic",
    )
    metric(
        "distance_m",
        distance[-1] if full_speed else None,
        "m",
        "Trapezoidal speed integral over the complete window; not GPS distance.",
        reason="Speed has missing endpoints or excessive timestamp gaps; total travel is unknown.",
    )
    metric(
        "known_segment_distance_m",
        distance[-1],
        "m",
        "Speed integral only over valid adjacent intervals; excludes unknown travel.",
    )
    metric(
        "speed_coverage_s",
        covered_s,
        "s",
        "Duration of adjacent valid speed intervals within the gap limit.",
    )
    metric(
        "maximum_speed_ms",
        max(finite_speed) if finite_speed else None,
        "m/s",
        "Maximum available recorded sample, not an estimate of unsampled peak.",
        config.source.kind + " sample statistic",
        "No valid speed samples.",
    )
    metric(
        "average_speed_ms",
        distance[-1] / duration if full_speed else None,
        "m/s",
        "Time-weighted trapezoidal mean over the complete window.",
        reason="Incomplete speed/time coverage prevents a full-window average.",
    )
    metric(
        "peak_acceleration_ms2",
        max(acc) if acc else None,
        "m/s²",
        "Maximum finite-difference estimate over available local windows, including endpoints.",
        reason="No complete differentiation stencil.",
    )
    metric(
        "peak_deceleration_ms2",
        min(acc) if acc else None,
        "m/s²",
        "Minimum signed finite-difference acceleration; not necessarily negative.",
        reason="No complete differentiation stencil.",
    )
    metric(
        "peak_signed_power_w",
        max(finite_power) if finite_power else None,
        "W",
        "Maximum sampled electrical power (derived V×I when available, else mapped power); no discharge interpretation without polarity.",
        reason="Neither voltage/current nor a mapped power signal is available.",
    )
    metric(
        "minimum_signed_power_w",
        min(finite_power) if finite_power else None,
        "W",
        "Minimum sampled electrical power (derived V×I when available, else mapped power); no charging interpretation without polarity.",
        reason="Neither voltage/current nor a mapped power signal is available.",
    )
    metric(
        "peak_power_magnitude_w",
        max(map(abs, finite_power)) if finite_power else None,
        "W",
        "Maximum absolute sampled electrical power, not validated propulsion demand.",
        reason="Neither voltage/current nor a mapped power signal is available.",
    )
    metric(
        "electrical_energy_used_wh",
        energy_used[-1] if energy_valid else None,
        "Wh",
        "Positive discharge-polarity-adjusted electrical power integral, with linear zero-crossing splits.",
        reason=energy_reason,
    )
    metric(
        "electrical_energy_received_wh",
        energy_received[-1] if energy_valid else None,
        "Wh",
        "Negative discharge-polarity-adjusted electrical power integral; charging, not necessarily regeneration.",
        reason=energy_reason,
    )
    metric(
        "regenerative_energy_wh",
        None,
        "Wh",
        "Regeneration-specific received energy requires evidence of the charging source.",
        reason="V/I and deceleration alone do not establish the origin of all charging energy.",
    )
    classifications = {
        k: config.source.kind + " (SI-converted source column)" for k in measured
    }
    classifications |= {k: "derived" for k in derived}
    units = {k: CANONICAL[k] for k in measured} | {
        "acceleration_ms2": "m/s²",
        "electrical_power_w": "W",
        "known_segment_distance_m": "m",
        "electrical_energy_used_wh": "Wh",
        "electrical_energy_received_wh": "Wh",
    }
    missing_predictive = sorted(
        {"motor_torque_nm", "brake_force_n", "road_gradient_rad"} - set(measured)
    )
    result = dict(
        schema_version=1,
        algorithm_version=VERSION,
        software={"python": platform.python_version(), "pydantic": version("pydantic")},
        scope="Recorded measurement replay and descriptive analysis; not predictive model validation.",
        configuration=config.model_dump(mode="json"),
        configuration_sha256=hashlib.sha256(
            canonical(config.model_dump(mode="json"))
        ).hexdigest(),
        metadata=data.metadata,
        time_s=times,
        measured=measured,
        derived=derived,
        classifications=classifications,
        units={k: units[k] for k in classifications},
        valid_speed_intervals=valid_speed,
        summary=metrics,
        events=events,
        quality=dict(
            full_speed_coverage=full_speed,
            speed_interval_coverage=covered_s / duration,
            energy_integration_available=energy_valid,
            current_sign=config.current_sign,
            data_origin=config.source.kind,
            physical_validation="PENDING; Phase 8 INCONCLUSIVE findings are unchanged.",
        ),
        methods=dict(
            distance="Piecewise-linear measured speed; trapezoidal interval integral. Gap/missing intervals are excluded and unknown, never claimed as zero travel.",
            acceleration="Two-neighbour secant (v[i+1]-v[i-1])/(t[i+1]-t[i-1]); one-sided endpoint differences; no smoothing. Irregular timestamps used directly. Missing/gap stencils unavailable; noise may be amplified.",
            power="Samplewise SI voltage × SI signed current; no polarity inference.",
            interpolation="Numeric readouts are preceding actual samples with their timestamps. Visual speed is linearly interpolated only across valid adjacent intervals. No gap bridging or extrapolation.",
            energy="Linear sampled-power integration with exact positive/negative zero-crossing splits, only for asserted known polarity and complete V/I/time coverage.",
        ),
        comparison=dict(
            enabled=False,
            missing_inputs=missing_predictive,
            reason="Recorded speed replay is not a predictive speed comparison. "
            + (
                "Missing independent inputs: " + ", ".join(missing_predictive) + ". "
                if missing_predictive
                else ""
            )
            + "An explicit Phase 8 experiment with initial conditions, model configuration, compatible inputs and documented assumptions is required; none is run by replay.",
        ),
    )
    result["analysis_sha256"] = hashlib.sha256(canonical(result)).hexdigest()
    return result
