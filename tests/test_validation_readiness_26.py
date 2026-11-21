"""Numerical statistics and disjoint-interval guards do not authenticate VED."""

import math
import pytest
from veus.workbench.validation_readiness import (
    error_metrics,
    heldout,
    Assessment,
    assess_validation,
)
from veus.investigation.catalogue import payload
from veus.workbench.presets import vehicle_presets


def test_independent_error_reference_and_coverage():
    r = error_metrics(
        [1, 2, 3, None],
        [2, 2, 1, 4],
        unit="m/s",
        alignment_verified=True,
        mapping_verified=True,
        uncertainty=0.1,
    )
    assert (
        r["mae"] == 1
        and r["rmse"] == pytest.approx(math.sqrt(5 / 3))
        and r["bias"] == pytest.approx(-1 / 3)
    )
    assert r["valid_sample_coverage"] == 0.75 and r["residuals"] == [1, 0, -2, None]
    assert r["error_distribution"] == dict(minimum=-2, median=0, maximum=1)
    assert (
        r["supplied_measurement_uncertainty"] == 0.1
        and r["physical_validation"] == "INCONCLUSIVE"
    )
    with pytest.raises(ValueError):
        error_metrics([1], [2], unit="m/s")
    with pytest.raises(ValueError):
        error_metrics(
            [1], [2], unit="W", alignment_verified=True, mapping_verified=True
        )


def test_heldout_overlap_and_boundary_leakage_rejected():
    assert heldout([0, 10], [11, 20], 30)["no_sample_overlap"]
    for a, b in [([0, 10], [10, 20]), ([0, 11], [10, 20]), ([0, 30], [31, 40])]:
        with pytest.raises(ValueError):
            heldout(a, b, 30)


def test_real_ved_assessment_reproducible_no_calibration_or_fake_residual():
    p = payload("ved-10-1561-full")
    request = Assessment(
        recording=dict(
            configuration=p["configuration"],
            csv_base64=p["csv_base64"],
            mappings_confirmed=True,
        ),
        vehicle=vehicle_presets()["presets"][0]["design"],
        calibration_interval_s=[0, 150],
        evaluation_interval_s=[200, 350],
    )
    r = assess_validation(request)
    assert r == assess_validation(request)
    assert (
        r["status"] == "INCONCLUSIVE"
        and r["metrics"] is None
        and r["residuals"] is None
    )
    assert r["source_sha256"] == p["configuration"]["source"]["expected_sha256"]
    assert all(
        v["calibrated_value"] is None
        and v["heldout_error"] is None
        and v["status"] == "BLOCKED"
        for v in r["calibration"].values()
    )
    assert (
        next(c for c in r["checks"] if c["item"] == "current_polarity")["status"]
        == "UNAVAILABLE"
    )
    assert any("binned" in c["missing_evidence"] for c in r["checks"])
    from veus.workbench.validation_readiness import readiness_report

    assert "INCONCLUSIVE" in readiness_report(r, "html")["content"]
    assert "assessment_sha256" in readiness_report(r, "json")["content"]
    r["status"] = "VALIDATED"
    with pytest.raises(ValueError):
        readiness_report(r, "html")
