"""Identical inputs must preserve legacy hashes, gates, events and reports."""

import base64
import hashlib
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from veus.workbench.measurements import router, ComparisonGate, comparison_gate
from veus.investigation.api import router as old_router
from veus.investigation.catalogue import payload
from veus.workbench.presets import vehicle_presets


def source(name="ved-10-1561-full"):
    p = payload(name)
    return dict(
        configuration=p["configuration"],
        csv_base64=p["csv_base64"],
        mappings_confirmed=True,
    )


def case():
    return dict(
        first=source(),
        second=source("ved-10-1567-full"),
        title="Identical migration evidence",
        axis="elapsed",
        format="json",
    )


def client():
    app = FastAPI()
    app.include_router(router)
    app.include_router(old_router)
    return TestClient(app)


def test_new_and_legacy_json_exact_parity_provenance_events_intervals():
    c = client()
    body = case()
    old = c.post("/api/investigation/case-study", json=body)
    new = c.post("/api/workbench/v2/measurements/case-study", json=body)
    assert old.status_code == new.status_code == 200 and old.json() == new.json()
    r = new.json()
    assert [len(v["analysis"]["time_s"]) for v in r["recordings"]] == [534, 367]
    for recording in r["recordings"]:
        assert recording["configuration"]["current_sign"] == "unknown"
        assert recording["metrics"]["electrical_energy_used_wh"]["value"] is None
        assert (
            recording["source_sha256"]
            == recording["configuration"]["source"]["expected_sha256"]
        )
        assert recording["selected_event_indices"] and recording["events"]
    selected = r["recordings"][0]["events"][0]["event_index"]
    body["first"]["selected_events"] = [selected]
    assert (
        c.post("/api/workbench/v2/measurements/case-study", json=body).json()
        == c.post("/api/investigation/case-study", json=body).json()
    )


def test_csv_report_exact_legacy_parity():

    for format in ["csv", "html"]:
        body = case()
        body["format"] = format
        c = client()
        old = c.post("/api/investigation/case-study", json=body)
        new = c.post("/api/workbench/v2/measurements/case-study", json=body)
        assert old.status_code == new.status_code == 200 and old.json() == new.json()
        if format == "csv":
            assert len(new.json()["content"].strip().splitlines()) == 902
        else:
            assert "No physical vehicle validation" in new.json()["content"]


def test_missing_signals_stay_unavailable_and_invalid_mapping_rejected():

    body = case()
    body["second"] = None
    first = body["first"]
    raw = b"t,v\n0,0\n1,1\n2,0\n"
    first["csv_base64"] = base64.b64encode(raw).decode()
    cfg = first["configuration"]
    cfg["source"]["expected_sha256"] = hashlib.sha256(raw).hexdigest()
    cfg["preprocessing"]["columns"] = {
        "time_s": dict(column="t", unit="s"),
        "vehicle_speed_ms": dict(column="v", unit="m/s"),
    }
    c = client()
    result = c.post("/api/workbench/v2/measurements/case-study", json=body)
    assert result.status_code == 200
    recording = result.json()["recordings"][0]
    assert "battery_voltage_v" not in recording["analysis"]["measured"]
    cfg["preprocessing"]["columns"]["time_s"]["unit"] = "unknown"
    assert (
        c.post("/api/workbench/v2/measurements/case-study", json=body).status_code
        == 422
    )


def test_measured_vs_illustrative_model_is_explicitly_gated_without_fake_residuals():
    request = ComparisonGate(
        recording=source(),
        vehicle=vehicle_presets()["presets"][0]["design"],
        interval_start_s=1,
        interval_end_s=20,
    )
    r = comparison_gate(request)
    assert r["status"] == "INCONCLUSIVE" and r["residuals"] is None
    assert any("polarity" in item for item in r["missing_inputs"])
    assert (
        r["interval_s"] == [1, 20]
        and r["measurement_source_sha256"]
        == request.recording.configuration.source.expected_sha256
    )
    with pytest.raises(ValueError):
        comparison_gate(request.model_copy(update={"interval_end_s": 99999}))
