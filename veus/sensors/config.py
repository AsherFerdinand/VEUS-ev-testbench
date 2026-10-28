"""Sampling and scheduled fault contracts; all times use the 0.01 s grid."""

from typing import Literal
from pydantic import Field, model_validator
from veus.contracts import StrictModel


def on_grid(value: float) -> bool:
    return abs(value / 0.01 - round(value / 0.01)) < 1e-7


class SensorTiming(StrictModel):
    sampling_hz: float = Field(default=100, ge=1, le=100)
    latency_s: float = Field(default=0, ge=0, le=10)
    stale_after_s: float = Field(default=0.3, ge=0.01, le=20)

    @model_validator(mode="after")
    def timing(self):
        if not all(
            on_grid(v)
            for v in (1 / self.sampling_hz, self.latency_s, self.stale_after_s)
        ):
            raise ValueError(
                "Sampling periods, latency and staleness must align to 0.01 s"
            )
        return self


class SpeedSensorConfig(SensorTiming):
    noise_std_ms: float = Field(default=0, ge=0, le=20)
    bias_ms: float = Field(default=0, ge=-100, le=100)


class RadarSensorConfig(SensorTiming):
    distance_noise_std_m: float = Field(default=0, ge=0, le=100)
    relative_speed_noise_std_ms: float = Field(default=0, ge=0, le=30)
    distance_bias_m: float = Field(default=0, ge=-300, le=300)
    relative_speed_bias_ms: float = Field(default=0, ge=-100, le=100)


class SensorFault(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    sensor: Literal["speed", "radar"]
    fault: Literal["noise", "bias", "latency", "dropout", "freeze"]
    start_time_s: float = Field(ge=0, le=120)
    duration_s: float = Field(gt=0, le=120)
    parameters: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def parameters_match(self):
        if not on_grid(self.start_time_s) or not on_grid(self.duration_s):
            raise ValueError("Fault times must align to 0.01 s")
        keys = {
            ("speed", "noise"): {"noise_std_ms": (0, 20)},
            ("radar", "noise"): {
                "distance_noise_std_m": (0, 100),
                "relative_speed_noise_std_ms": (0, 30),
            },
            ("speed", "bias"): {"bias_ms": (-100, 100)},
            ("radar", "bias"): {
                "distance_bias_m": (-300, 300),
                "relative_speed_bias_ms": (-100, 100),
            },
        }.get(
            (self.sensor, self.fault),
            {"latency_s": (0, 10)} if self.fault == "latency" else {},
        )
        if not set(self.parameters) <= set(keys) or (keys and not self.parameters):
            raise ValueError("Provide only the parameters for this sensor/fault type")
        for key, value in self.parameters.items():
            low, high = keys[key]
            if not low <= value <= high:
                raise ValueError(f"{key} out of range")
            if key == "latency_s" and not on_grid(value):
                raise ValueError("Latency must align to 0.01 s")
        return self


class SensorSuiteConfig(StrictModel):
    enabled: bool = False
    mode: Literal["ideal", "configured"] = "configured"
    seed: int = Field(default=42, ge=0, le=2**32 - 1)
    speed: SpeedSensorConfig = Field(default_factory=SpeedSensorConfig)
    radar: RadarSensorConfig = Field(default_factory=RadarSensorConfig)
    faults: list[SensorFault] = Field(default_factory=list, max_length=128)

    @model_validator(mode="after")
    def consistent(self):
        if len({f.id for f in self.faults}) != len(self.faults):
            raise ValueError("Fault IDs must be unique")
        if self.mode == "ideal" and (
            self.faults
            or self.speed != SpeedSensorConfig()
            or self.radar != RadarSensorConfig()
        ):
            raise ValueError(
                "Ideal mode requires default characteristics and no faults; use configured mode otherwise"
            )
        return self
