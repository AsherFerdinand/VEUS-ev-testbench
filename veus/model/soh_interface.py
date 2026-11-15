"""Future SOH exchange contracts only: never infer electrical limits from SOH."""

from datetime import datetime
from typing import Literal, Protocol
from pydantic import Field, model_validator
from veus.contracts import StrictModel


class CapacitySOHEstimate(StrictModel):
    schema_version: Literal[1] = 1
    battery_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    estimator_version: str = Field(min_length=1)
    measured_at: datetime
    cycle_index: int = Field(ge=0)
    capacity_soh_fraction: float = Field(gt=0, le=1.5)
    reference_capacity_ah: float = Field(gt=0)
    test_temperature_c: float
    test_discharge_rate_c: float = Field(gt=0)
    interval_low: float | None = Field(default=None, gt=0, le=1.5)
    interval_high: float | None = Field(default=None, gt=0, le=1.5)

    @model_validator(mode="after")
    def consistent(self):
        if self.measured_at.tzinfo is None:
            raise ValueError("SOH measurement timestamp must include timezone")
        if (self.interval_low is None) != (self.interval_high is None):
            raise ValueError("Provide both uncertainty interval bounds or neither")
        if (
            self.interval_low is not None
            and not self.interval_low
            <= self.capacity_soh_fraction
            <= self.interval_high
        ):
            raise ValueError("SOH estimate must lie within its uncertainty interval")
        return self


class BatteryOperatingContext(StrictModel):
    soc: float = Field(ge=0, le=1)
    temperature_c: float
    requested_current_a: float
    pack_series_cells: int = Field(gt=0)
    pack_parallel_cells: int = Field(gt=0)


class CalibratedBatteryParameters(StrictModel):
    capacity_kwh: float = Field(gt=0)
    ocv_v: float = Field(gt=0)
    resistance_ohm: float = Field(ge=0)
    discharge_limit_a: float = Field(ge=0)
    charge_limit_a: float = Field(ge=0)
    calibration_id: str = Field(min_length=1)
    evidence_reference: str = Field(min_length=1)


class BatteryParameterProvider(Protocol):
    def parameters(
        self, estimate: CapacitySOHEstimate, context: BatteryOperatingContext
    ) -> CalibratedBatteryParameters:
        """Requires calibrated mappings and independent electrical-limit evidence."""
        ...
