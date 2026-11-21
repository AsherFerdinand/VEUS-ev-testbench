"""Illustrative class envelopes and appearance compatibility; no new model physics."""

import hashlib
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from veus.lab.report import export
from veus.lab.runner import run
from veus.lab.schema import LabRequest
from veus.replay.analysis import canonical
from veus.workbench.adapter import ACKNOWLEDGEMENTS, build_models
from veus.workbench.catalogue import catalogue
from veus.workbench.design import VehicleDesignV2
from veus.workbench.engineering import evaluate, explicit_snapshot, router
from veus.workbench.presets import vehicle_presets


def test_three_fictional_presets_match_supported_explicit_specs():
    result = vehicle_presets()
    assert result["schema_version"] == 1
    assert [p["id"] for p in result["presets"]] == ["s1", "r1", "x1"]
    expected = {
        "s1": ("sedan", 60, 180, 1750, 0.25, 400),
        "r1": ("performance", 90, 450, 1950, 0.30, 800),
        "x1": ("suv", 100, 250, 2450, 0.32, 450),
    }
    records = {c["id"]: c for c in catalogue()["components"]}
    for preset in result["presets"]:
        appearance, energy, power, mass, cd, voltage = expected[preset["id"]]
        d = VehicleDesignV2.model_validate(explicit_snapshot(preset["design"]))
        assert d.appearance == appearance and preset["classification"] == "illustrative"
        assert (
            d.battery.usable_capacity_kwh == energy and d.motor.peak_power_kw == power
        )
        assert d.body.drag_coefficient == cd and d.battery.nominal_voltage_v == voltage
        assert preset["specifications"]["total_mass_kg"]["value"] == mass
        assert all(c["status"] != "incompatible" for c in preset["checks"])
        assert preset["simulation_readiness"]["status"] == "requires_acknowledgement"
        assert set(preset["simulation_readiness"]["required_acknowledgements"]) == set(
            ACKNOWLEDGEMENTS
        )
        for kind, id in d.component_ids.items():
            assert getattr(d, kind).model_dump(mode="json") == records[id]["parameters"]
        assert (
            "downforce" not in preset["specifications"]
            and "range" not in preset["specifications"]
        )


@pytest.mark.parametrize("id", ["s1", "r1", "x1"])
def test_each_class_passes_adapter_and_finite_coupled_lab_without_default_fallback(id):
    p = next(x for x in vehicle_presets()["presets"] if x["id"] == id)
    d = VehicleDesignV2.model_validate(p["design"])
    evaluated = evaluate(d)
    models = build_models(
        d,
        evaluated["checks"],
        evaluated["specifications"]["total_mass_kg"]["value"],
        ACKNOWLEDGEMENTS,
    )
    assert (
        models.dynamics.vehicle.mass_kg == p["specifications"]["total_mass_kg"]["value"]
    )
    assert models.dynamics.vehicle.cd == d.body.drag_coefficient
    assert models.dynamics.motor.max_power_kw == d.motor.peak_power_kw
    req = LabRequest(
        vehicle=d,
        experiment={"kind": "acceleration", "duration_s": 1, "dt_s": 0.05},
        acknowledgements=ACKNOWLEDGEMENTS,
    )
    result = run(req)
    assert result["vehicle"]["appearance"] == p["appearance"]
    assert result["summary"]["final_speed_ms"] > 0
    assert result["summary"]["maximum_energy_balance_error_j"] < 1e-4
    assert result["trace"][-1]["soc"] < d.assumptions.initial_soc
    assert result == run(req)
    assert all(
        row["battery_current_a"] <= d.battery.discharge_limit_a + 1e-6
        for row in result["trace"]
    )
    assert all(
        row["battery_voltage_v"] >= d.battery.minimum_voltage_v - 1e-6
        for row in result["trace"]
    )


def test_appearance_omission_preserves_old_default_snapshot_and_evaluation_hash():
    old = VehicleDesignV2().model_dump(mode="json")
    assert "appearance" not in old
    assert "appearance" not in json.loads(VehicleDesignV2().model_dump_json())
    assert (
        hashlib.sha256(canonical(old)).hexdigest()
        == "b1e9f7779b949765c709924ed227444d82ab3de35f156401d521fc6b06c2c324"
    )
    assert (
        evaluate(VehicleDesignV2())["configuration_sha256"]
        == "b1e9f7779b949765c709924ed227444d82ab3de35f156401d521fc6b06c2c324"
    )
    assert (
        VehicleDesignV2.model_validate(explicit_snapshot(old)).model_dump(mode="json")
        == old
    )
    assert (
        VehicleDesignV2.model_validate(old | {"appearance": None}).model_dump(
            mode="json"
        )
        == old
    )
    with pytest.raises(ValidationError):
        VehicleDesignV2.model_validate(old | {"appearance": "invented"})


def test_appearance_changes_no_numerical_parameters_or_results():
    d = VehicleDesignV2()
    req = LabRequest(
        vehicle=d,
        experiment={"kind": "braking", "initial_speed_ms": 10, "duration_s": 1},
        acknowledgements=ACKNOWLEDGEMENTS,
    )
    old = run(req)
    assert (
        old["run_sha256"]
        == "c666acf6ee4ede4e87c358cad2324cfaedb91b3970001a1d0dfadcc50a73a42e"
    )
    for appearance in ["sedan", "performance", "suv"]:
        changed = VehicleDesignV2.model_validate(
            d.model_dump(mode="json") | {"appearance": appearance}
        )
        result = run(req.model_copy(update={"vehicle": changed}))
        assert result["summary"] == old["summary"] and result["trace"] == old["trace"]
        assert result["vehicle"]["appearance"] == appearance
        assert (
            result["run_sha256"] != old["run_sha256"]
        )  # snapshot identity is preserved in provenance.


def test_old_frozen_json_csv_and_html_exports_remain_byte_equivalent():
    req = LabRequest(
        vehicle=VehicleDesignV2(),
        experiment={"kind": "braking", "initial_speed_ms": 10, "duration_s": 1},
        acknowledgements=ACKNOWLEDGEMENTS,
    )
    result = run(req)
    expected = {
        # Pre-change fingerprints captured from commit 0345540; no temporary file dependency.
        "json": "dae9f1bbd15b2177705ea2e75c9a01e24119682e7340212433bf0389a49285a8",
        "csv": "419b66477779ff9656847e79143dfc4c1e52e64223800458a7e7c456a0846cde",
        "html": "0bcc3d49338dbe900a5d1f20a1e14a674deb881a3d83623a758d5e1e83f5bbf5",
    }
    for format, digest in expected.items():
        assert (
            hashlib.sha256(export(result, format)["content"].encode()).hexdigest()
            == digest
        )


def test_preset_api_complete_roundtrip_isolation_and_optional_appearance_schema():
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        a = c.get("/api/workbench/v2/presets")
        assert a.status_code == 200
        records = a.json()["presets"]
        assert len(records) == 3
        for p in records:
            response = c.post("/api/workbench/v2/evaluate", json=p["design"])
            assert response.status_code == 200
            assert response.json()["design"] == p["design"]
            assert (
                c.post(
                    "/api/workbench/v2/adapter",
                    json={"design": p["design"], "acknowledgements": ACKNOWLEDGEMENTS},
                ).status_code
                == 200
            )
        schema = c.get("/api/workbench/v2/schema").json()
        assert (
            "appearance" in schema["properties"]
            and "appearance" not in schema["required"]
        )
        old = VehicleDesignV2().model_dump(mode="json")
        assert c.post("/api/workbench/v2/evaluate", json=old).json()["design"] == old
        records[0]["design"]["battery"]["mass_kg"] = 1
        assert (
            c.get("/api/workbench/v2/presets").json()["presets"][0]["design"][
                "battery"
            ]["mass_kg"]
            == 420
        )
