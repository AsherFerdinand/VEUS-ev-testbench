"""Explicit CSV-to-SI conversion and bounded, non-extrapolating alignment."""

import bisect
import csv
from dataclasses import dataclass
import hashlib
import io
import math
from statistics import median
from typing import Literal
from pydantic import Field, model_validator
from veus.contracts import StrictModel

Signal = Literal[
    "time_s",
    "vehicle_speed_ms",
    "longitudinal_acceleration_ms2",
    "motor_torque_nm",
    "motor_speed_rad_s",
    "brake_force_n",
    "battery_voltage_v",
    "battery_current_a",
    "battery_soc",
    "road_gradient_rad",
    "position_m",
    "battery_power_w",
    "energy_wh",
    "ambient_temperature_c",
]


class Column(StrictModel):
    column: str = Field(min_length=1)
    unit: str
    sign: Literal[-1, 1] = 1


class DataSource(StrictModel):
    dataset: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    licence: str = Field(min_length=1)
    kind: Literal["synthetic", "measured"]
    run_id: str = Field(min_length=1)
    role: Literal["calibration", "validation", "exploration"]
    expected_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    provenance_evidence: str = Field(min_length=1)
    inputs_verified: bool = False
    vehicle_id: str | None = None
    vehicle_specifications: dict[str, str | float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def asserted_conditions(self):
        if (
            self.kind == "measured"
            and self.inputs_verified
            and (not self.vehicle_id or not self.vehicle_specifications)
        ):
            raise ValueError(
                "Asserted measured validation needs vehicle identity/specifications; software does not authenticate that assertion"
            )
        return self


class ImportConfig(StrictModel):
    columns: dict[Signal, Column]
    zero_time: bool = True
    max_gap_s: float = Field(default=2, gt=0, le=60)
    comparison_interpolation: Literal["linear", "none"] = "linear"
    input_interpolation: Literal["previous", "linear"] = "previous"


UNITS = {
    "time_s": {"s": 1, "ms": 0.001},
    "vehicle_speed_ms": {"m/s": 1, "km/h": 1 / 3.6, "mph": 0.44704},
    "longitudinal_acceleration_ms2": {"m/s2": 1, "m/s²": 1, "g": 9.81},
    "motor_torque_nm": {"Nm": 1},
    "motor_speed_rad_s": {"rad/s": 1, "rpm": math.pi / 30},
    "brake_force_n": {"N": 1},
    "battery_voltage_v": {"V": 1},
    "battery_current_a": {"A": 1},
    "battery_soc": {"fraction": 1, "%": 0.01},
    "road_gradient_rad": {"rad": 1, "deg": math.pi / 180, "%": None},
    "position_m": {"m": 1},
    "battery_power_w": {"W": 1, "kW": 1000},
    "energy_wh": {"Wh": 1, "kWh": 1000},
    "ambient_temperature_c": {"°C": 1, "C": 1},
}
CANONICAL = {k: next(iter(v)) for k, v in UNITS.items()}


@dataclass
class Measurements:
    times: list[float]
    signals: dict[str, list[float | None]]
    metadata: dict
    max_gap_s: float

    def at(self, signal: str, time_s: float, method="linear") -> float | None:
        if signal not in self.signals:
            return None
        return interpolate(
            self.times, self.signals[signal], time_s, self.max_gap_s, method
        )


def interpolate(times, values, time_s, max_gap_s, method="linear"):
    index = bisect.bisect_left(times, time_s)
    if index < len(times) and abs(times[index] - time_s) < 1e-8:
        return values[index]
    if index and abs(times[index - 1] - time_s) < 1e-8:
        return values[index - 1]
    if index == 0 or index == len(times) or method == "none":
        return None
    left, right = index - 1, index
    if times[right] - times[left] > max_gap_s + 1e-9:
        return None
    if values[left] is None or values[right] is None:
        return None
    if method == "previous":
        return values[left]
    if method != "linear":
        raise ValueError("Unknown interpolation policy")
    weight = (time_s - times[left]) / (times[right] - times[left])
    return values[left] + weight * (values[right] - values[left])


def load_csv(raw: bytes, source: DataSource, config: ImportConfig) -> Measurements:
    if len(raw) > 10_000_000:
        raise ValueError("CSV limit is 10 MB; select a documented short run/window")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != source.expected_sha256:
        raise ValueError("Source CSV SHA-256 does not match experiment")
    if "time_s" not in config.columns:
        raise ValueError("Map a time_s column explicitly")
    reader = csv.reader(io.StringIO(raw.decode("utf-8-sig")))
    try:
        header = next(reader)
    except StopIteration:
        raise ValueError("Empty CSV")
    if len(header) != len(set(header)):
        raise ValueError("Duplicate CSV column names")
    indices = {}
    for signal, mapping in config.columns.items():
        if mapping.column not in header:
            raise ValueError(f"Missing column: {mapping.column}")
        if mapping.unit not in UNITS[signal]:
            raise ValueError(f"Unsupported unit for {signal}: {mapping.unit}")
        if signal == "time_s" and mapping.sign != 1:
            raise ValueError("Time must have positive sign")
        indices[signal] = header.index(mapping.column)
    values = {key: [] for key in config.columns}
    for row in reader:
        if len(values["time_s"]) >= 100_000:
            raise ValueError("CSV exceeds 100000 rows")
        if len(row) != len(header):
            raise ValueError("Malformed CSV row length")
        for signal, mapping in config.columns.items():
            text = row[indices[signal]].strip()
            if text.lower() in {"", "na", "nan", "null"}:
                value = None
            else:
                value = float(text)
                if not math.isfinite(value):
                    raise ValueError("Non-finite measurement")
                value = (
                    math.atan(value / 100)
                    if signal == "road_gradient_rad" and mapping.unit == "%"
                    else value * UNITS[signal][mapping.unit]
                ) * mapping.sign
                if (
                    signal in {"vehicle_speed_ms", "motor_speed_rad_s", "brake_force_n"}
                    and value < 0
                ):
                    raise ValueError(f"Negative forward quantity: {signal}")
                if signal == "battery_voltage_v" and value <= 0:
                    raise ValueError("Voltage must be positive")
                if signal == "battery_soc" and not 0 <= value <= 1:
                    raise ValueError("SOC outside 0..1")
            values[signal].append(value)
    times = values.pop("time_s")
    if len(times) < 2 or any(t is None for t in times):
        raise ValueError("At least two finite timestamps are required")
    intervals = [b - a for a, b in zip(times, times[1:])]
    if any(d <= 0 for d in intervals):
        raise ValueError("Timestamps must increase strictly; duplicates are rejected")
    origin = times[0] if config.zero_time else 0
    times = [t - origin for t in times]
    if abs(times[0]) > 1e-9:
        raise ValueError(
            "Experiment must start at t=0; enable explicit zero_time conversion"
        )
    gaps = [
        dict(start_s=times[i], end_s=times[i + 1])
        for i, d in enumerate(intervals)
        if d > config.max_gap_s
    ]
    metadata = dict(
        source=source.model_dump(mode="json"),
        raw_sha256=digest,
        row_count=len(times),
        time_origin_s=origin,
        sampling_min_s=min(intervals),
        sampling_median_s=median(intervals),
        sampling_max_s=max(intervals),
        irregular_sampling=max(intervals) - min(intervals) > 1e-7,
        gaps=gaps,
        missing_counts={k: sum(v is None for v in data) for k, data in values.items()},
        preprocessing=config.model_dump(mode="json"),
        canonical_units={k: CANONICAL[k] for k in values},
    )
    return Measurements(times, values, metadata, config.max_gap_s)


def derive_acceleration(data: Measurements) -> list[float | None]:
    speeds = data.signals.get("vehicle_speed_ms")
    if speeds is None:
        raise ValueError("Speed is required to derive acceleration")
    result = []
    for i in range(len(speeds)):
        left = max(0, i - 1)
        right = min(len(speeds) - 1, i + 1)
        valid = all(speeds[j] is not None for j in range(left, right + 1))
        valid &= all(
            data.times[j + 1] - data.times[j] <= data.max_gap_s
            for j in range(left, right)
        )
        result.append(
            (speeds[right] - speeds[left]) / (data.times[right] - data.times[left])
            if valid
            else None
        )
    return result
