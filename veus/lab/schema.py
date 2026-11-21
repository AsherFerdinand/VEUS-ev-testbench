"""Versioned laboratory request contracts, SI units and explicit operating policy."""

from typing import Literal
from pydantic import Field, model_validator, field_validator, model_serializer
from veus.contracts import StrictModel
from veus.workbench.design import VehicleDesignV2
from veus.workbench.engineering import explicit_snapshot
from .profiles import ProfileData, RouteData


class ExperimentConfig(StrictModel):
    kind: Literal[
        "constant_speed", "acceleration", "braking", "gradient", "coast", "profile"
    ] = "acceleration"
    mode: Literal["predictive", "prescribed"] = "predictive"
    duration_s: float = Field(default=20, gt=0, le=1800)
    dt_s: float = Field(default=0.05, ge=0.01, le=0.25)
    initial_speed_ms: float = Field(default=0, ge=0, le=100)
    target_speed_ms: float = Field(default=27.7777777778, ge=0, le=100)
    grade_percent: float = Field(default=0, ge=-30, le=30)
    regen_enabled: bool = True
    brake_deceleration_ms2: float = Field(default=3, gt=0, le=12)
    tracking_time_constant_s: float = Field(default=0.8, ge=0.2, le=10)
    power_policy: Literal["continuous", "acknowledged_peak"] = "continuous"
    route_grade_policy: Literal["require", "experiment_constant_assumption"] = "require"

    @model_validator(mode="after")
    def bound_steps(self):
        ticks = self.duration_s / self.dt_s
        if ticks > 12000 + 1e-8:
            raise ValueError(
                "Experiment exceeds 12000 steps; choose an explicit coarser dt or shorter duration"
            )
        if abs(ticks - round(ticks)) > 1e-7:
            raise ValueError("Duration must be an integer multiple of dt")
        if (
            self.kind in ["acceleration", "braking", "coast"]
            and self.mode == "prescribed"
        ):
            raise ValueError(
                "Acceleration, braking and coast experiments use predictive achieved movement"
            )
        return self


class LabRequest(StrictModel):
    schema_version: Literal[1] = 1
    vehicle: VehicleDesignV2
    experiment: ExperimentConfig = Field(default_factory=ExperimentConfig)
    acknowledgements: list[str] = Field(default_factory=list, max_length=8)
    profile: ProfileData | None = None
    route: RouteData | None = None
    efficiency_model: Literal["illustrative_map"] | None = None

    @model_serializer(mode="wrap")
    def omit_legacy_efficiency_option(self, handler):
        values = handler(self)
        if values.get("efficiency_model") is None:
            values.pop("efficiency_model", None)
        return values

    @field_validator("vehicle", mode="before")
    @classmethod
    def complete_vehicle(cls, value):
        return value if isinstance(value, VehicleDesignV2) else explicit_snapshot(value)
