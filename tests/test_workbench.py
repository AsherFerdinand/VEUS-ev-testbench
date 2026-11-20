"""Foundation contracts: real configuration checks and honest presentation boundaries."""

import hashlib
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from veus.studio.main import app
from veus.workbench.schema import VehicleDesign
from veus.workbench.api import content_data

ROOT = Path(__file__).resolve().parents[1]


def test_new_root_isolated_from_legacy_shell_and_migration_preserved():
    with TestClient(app) as client:
        root = client.get("/")
        assert root.status_code == 200
        assert "Electric Vehicle Engineering Workbench" in root.text
        assert "/static/workbench/app.js" in root.text
        for name in [
            "drive.js",
            "scene.js",
            "dashboard.js",
            "workspaces.js",
            "/ws/simulation",
        ]:
            assert name not in root.text
        for path in ["/engineering", "/engineering/"]:
            old = client.get(path)
            assert old.status_code == 200 and "VEUS Studio Telemetry" in old.text
            assert "drive.js" in old.text and "investigation.js" in old.text
        assert client.get("/engineering-docs/engineering.md").status_code == 200


def test_content_has_ten_components_eight_challenges_and_resolvable_sources():
    with TestClient(app) as client:
        data = client.get("/api/workbench/content").json()
    assert len(data["components"]) == 10 and len(data["challenges"]) == 8
    assert len({c["id"] for c in data["components"]}) == 10
    sources = {s["id"] for s in data["sources"]}
    for component in data["components"]:
        assert component["sources"] and set(component["sources"]) <= sources
        for key in ["function", "parameters", "relationships", "limitation"]:
            assert component[key]
    for challenge in data["challenges"]:
        assert set(challenge["sources"]) <= sources
        for key in [
            "problem",
            "physics",
            "technologies",
            "experiment",
            "classification",
        ]:
            assert challenge[key]
    assert "not yet populated" in data["catalogue_policy"]["status"]
    assert content_data()["schema_version"] == 1


def test_design_validation_is_deterministic_roundtrip_not_simulation():
    with TestClient(app) as client:
        value = client.get("/api/workbench/design").json()
        first = client.post("/api/workbench/design/validate", json=value)
        second = client.post("/api/workbench/design/validate", json=value)
        assert first.status_code == 200 and first.json() == second.json()
        result = first.json()
        assert result["design"] == VehicleDesign().model_dump(mode="json")
        assert len(result["configuration_sha256"]) == 64
        assert "no simulation" in result["status"]
        assert "range_km" not in result and "efficiency" not in result
        schema = client.get("/api/workbench/design/schema").json()
        assert schema["properties"]["schema_version"]["const"] == 1
        assert schema["additionalProperties"] is False


@pytest.mark.parametrize(
    "change",
    [
        {"schema_version": 2},
        {"classification": "manufacturer_specified"},
        {"battery": {"usable_capacity_kwh": 70}},
        {"battery": {"minimum_voltage_v": 460}},
        {"inverter": {"maximum_dc_voltage_v": 400}},
        {"inverter": {"continuous_power_kw": 100}},
        {"motor": {"rated_dc_maximum_v": 440}},
        {"motor": {"rated_dc_minimum_v": 350}},
        {"charging": {"charger_dc_maximum_v": 400}},
        {"body": {"mass_excluding_battery_kg": -1}},
        {"tariffs": {"charging_efficiency": 1.1}},
        {"battery": {"chemistry": "fictional"}},
        {"unexpected_result": 1000},
        {"body": {"drag_coefficient": float("inf")}},
    ],
)
def test_design_rejects_invalid_envelopes_and_nonfinite_values(change):
    cfg = VehicleDesign().model_dump()
    for key, value in change.items():
        if isinstance(value, dict):
            cfg[key].update(value)
        else:
            cfg[key] = value
    with pytest.raises(ValidationError):
        VehicleDesign.model_validate(cfg)


def test_design_api_rejects_oversize_and_invalid_inputs():
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/workbench/design/validate", content=b" " * 64001
            ).status_code
            == 413
        )
        assert (
            client.post(
                "/api/workbench/design/validate", content=b"not json"
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/workbench/design/validate",
                json={"battery": {"usable_capacity_kwh": 90}},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/workbench/design/validate", json={"name": "<script>name</script>"}
            ).status_code
            == 200
        )


def test_no_implicit_technology_performance_mapping_or_model_adapter():
    cfg = VehicleDesign().model_dump()
    cfg["battery"]["chemistry"] = "LFP"
    cfg["inverter"]["technology"] = "SiC"
    alternative = VehicleDesign.model_validate(cfg).model_dump()
    assert alternative["battery"]["gross_capacity_kwh"] == 64
    assert alternative["inverter"]["continuous_power_kw"] == 150
    assert set(alternative) == set(VehicleDesign().model_dump())
    assert not any(
        "cost" in k or "range" in k or "prediction" in k for k in alternative
    )


def test_genuine_recordings_and_existing_measurement_gates_remain_accessible():
    with TestClient(app) as client:
        entries = client.get("/api/investigation/catalogue").json()
        full = next(e for e in entries if e["id"] == "ved-10-1561-full")
        assert full["sample_count"] == 534 and full["duration_s"] == pytest.approx(
            460.4
        )
        raw = client.get("/api/investigation/recordings/ved-10-1561-full").json()
        request = {k: raw[k] for k in ["configuration", "csv_base64"]}
        request["mappings_confirmed"] = True
        result = client.post(
            "/api/investigation/case-study", json={"first": request}
        ).json()["recordings"][0]
        assert result["metrics"]["distance_m"]["value"] is None
        assert result["metrics"]["electrical_energy_used_wh"]["value"] is None
        assert not result["analysis"]["investigation_energy_gate"]["available"]
        p = ROOT / "datasets/ved/ved-10-1561-full.csv"
        assert hashlib.sha256(p.read_bytes()).hexdigest() == full["source_sha256"]
