from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from veus.model.soh_interface import CapacitySOHEstimate, CalibratedBatteryParameters


def estimate(**update):
    data = dict(
        battery_id="NASA-example-cell",
        dataset_id="external-fixture",
        estimator_version="not-trained-test-fixture",
        measured_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        cycle_index=100,
        capacity_soh_fraction=0.8,
        reference_capacity_ah=2,
        test_temperature_c=25,
        test_discharge_rate_c=1,
    )
    return CapacitySOHEstimate(**(data | update))


def test_soh_schema_roundtrip_does_not_infer_electrical_parameters():
    value = estimate(interval_low=0.75, interval_high=0.85)
    assert CapacitySOHEstimate.model_validate_json(value.model_dump_json()) == value
    with pytest.raises(ValidationError):
        CalibratedBatteryParameters.model_validate(value.model_dump())


@pytest.mark.parametrize(
    "kwargs",
    [
        {"capacity_soh_fraction": 0},
        {"interval_low": 0.7},
        {"interval_low": 0.9, "interval_high": 1.0},
        {"measured_at": datetime(2026, 1, 1)},
        {"test_temperature_c": float("nan")},
    ],
)
def test_invalid_soh_evidence(kwargs):
    with pytest.raises(ValidationError):
        estimate(**kwargs)
