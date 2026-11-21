"""Independent specification references and retained-model adapter checks, not physical validation."""

import copy
import math
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from veus.workbench.catalogue import catalogue, Component
from veus.workbench.design import VehicleDesignV2
from veus.workbench.engineering import evaluate, router
from veus.workbench.adapter import build_models, ACKNOWLEDGEMENTS
from veus.sim.dynamics import VehicleState


def design(**groups):
    d = VehicleDesignV2().model_dump(mode="json")
    for key, value in groups.items():
        if isinstance(value, dict):
            d[key].update(value)
        else:
            d[key] = value
    return VehicleDesignV2.model_validate(d)


def check(result, key):
    return next(c for c in result["checks"] if c["id"] == key)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        yield c


def test_representative_catalogue_types_units_and_consolidated_source():
    c = catalogue()
    assert c["version"] == "representative-v1"
    original_ids = {
        "battery-64",
        "battery-80",
        "motor-150",
        "motor-220",
        "inverter-180",
        "inverter-260",
        "charger-11",
        "charger-22",
        "dcdc-2",
        "gearbox-9",
        "gearbox-11",
        "body-sedan",
        "body-compact",
    }
    class_ids = {
        "battery-s1",
        "motor-s1",
        "body-s1",
        "battery-r1",
        "motor-r1",
        "inverter-r1",
        "body-r1",
        "battery-x1",
        "motor-x1",
        "inverter-x1",
        "body-x1",
        "charger-wide-22",
        "dcdc-wide-2",
        "gearbox-heavy-9",
    }
    assert {record["id"] for record in c["components"]} == original_ids | class_ids
    assert len(c["components"]) == 27 and len(c["sources"]) == 2
    assert {source["id"] for source in c["sources"]} == {
        "veus-representative",
        "veus-classes-2.3.2",
    }
    assert {r["kind"] for r in c["components"]} == {
        "battery",
        "motor",
        "inverter",
        "body",
        "gearbox",
        "charging",
        "dcdc",
    }
    assert len({r["id"] for r in c["components"]}) == len(c["components"])
    for record in c["components"]:
        Component.model_validate(record)
        assert record["manufacturer"] is None and record["model"] is None
        assert record["parameter_metadata"].keys() == record["parameters"].keys()
        for key, meta in record["parameter_metadata"].items():
            assert meta["classification"] == "illustrative"
            assert meta["source_id"] == (
                "veus-representative"
                if record["id"] in original_ids
                else "veus-classes-2.3.2"
            )
            assert meta["unit"] and meta["uncertainty"] and meta["operating_conditions"]
        if record["kind"] == "motor":
            assert record["parameters"]["peak_duration_s"] is None
    inv = [r for r in c["components"] if r["kind"] == "inverter"]
    assert (
        inv[0]["parameters"]["efficiency_assumption"]
        == inv[1]["parameters"]["efficiency_assumption"]
    )


def test_independent_analytical_specifications_and_explicit_mass_accounting():
    d = design(
        body={
            "mass_excluding_components_kg": 1000,
            "drag_coefficient": 0.25,
            "frontal_area_m2": 2,
        },
        battery={
            "gross_capacity_kwh": 80,
            "usable_capacity_kwh": 72,
            "nominal_voltage_v": 400,
            "mass_kg": 400,
        },
        motor={"mass_kg": 60, "peak_power_kw": 160},
        inverter={"mass_kg": 20},
        charging={"mass_kg": 10},
        dcdc={"mass_kg": 2},
        gearbox={"mass_kg": 8, "reduction_ratio": 10, "mechanical_efficiency": 0.9},
        operating_point={
            "dc_voltage_v": 400,
            "dc_power_kw": 80,
            "motor_torque_nm": 100,
        },
    )
    r = evaluate(d)
    s = r["specifications"]
    # 1000 residual + 400+60+20+10+2+8 listed masses = 1500 kg exactly.
    expected = {
        "total_mass_kg": 1500,
        "gross_energy_kwh": 80,
        "usable_energy_kwh": 72,
        "gross_nominal_capacity_ah": 200,
        "usable_nominal_capacity_ah": 180,
        "peak_power_to_weight_kw_per_tonne": 160 / 1.5,
        "required_dc_current_a": 200,
        "wheel_torque_nm": 900,
        "drag_area_m2": 0.5,
    }
    for key, value in expected.items():
        assert s[key]["value"] == pytest.approx(value)
        assert s[key]["unit"] and s[key]["equation"] and s[key]["assumptions"]
    assert evaluate(d) == r
    assert (
        VehicleDesignV2.model_validate_json(d.model_dump_json()).model_dump()
        == d.model_dump()
    )
    assert "range" in r["unavailable"] and "range_km" not in s
    changed = evaluate(design(body={"mass_excluding_components_kg": 1001}))
    default = evaluate(VehicleDesignV2())
    assert (
        changed["specifications"]["total_mass_kg"]["value"]
        - default["specifications"]["total_mass_kg"]["value"]
        == -199
    )


def test_missing_parameters_are_not_filled_or_zeroed():
    r = evaluate(
        design(
            motor={"mass_kg": None, "peak_power_kw": None},
            gearbox={"mechanical_efficiency": None},
            battery={"resistance_ohm": None},
        )
    )
    for key in [
        "total_mass_kg",
        "peak_power_to_weight_kw_per_tonne",
        "wheel_torque_nm",
    ]:
        assert r["specifications"][key]["value"] is None
        assert r["specifications"][key]["unavailable_reason"]
    assert r["specifications"]["required_dc_current_a"]["value"] == 200
    assert r["simulation_readiness"]["status"] == "insufficient_data"
    assert "battery_resistance" in r["simulation_readiness"]["missing_inputs"]


@pytest.mark.parametrize(
    "groups,key",
    [
        ({"battery": {"usable_capacity_kwh": 90}}, "battery_energy"),
        ({"battery": {"minimum_voltage_v": 500}}, "battery_voltage_order"),
        ({"inverter": {"maximum_dc_voltage_v": 400}}, "battery_inverter_voltage"),
        ({"motor": {"drive_dc_minimum_v": 350}}, "motor_drive_voltage"),
        ({"inverter": {"continuous_power_kw": 100}}, "rated_motor_inverter_power"),
        ({"inverter": {"peak_power_kw": 155}}, "peak_motor_inverter_power"),
        ({"gearbox": {"maximum_input_torque_nm": 250}}, "gearbox_torque"),
        ({"charging": {"maximum_dc_voltage_v": 400}}, "charging_voltage"),
        ({"dcdc": {"input_maximum_v": 400}}, "dcdc_voltage"),
        ({"operating_point": {"dc_voltage_v": 200}}, "operating_voltage"),
        ({"battery": {"discharge_limit_a": 100}}, "operating_discharge_current"),
        ({"inverter": {"maximum_dc_current_a": 100}}, "inverter_dc_current"),
        (
            {
                "battery": {"discharge_limit_a": 1000},
                "inverter": {"maximum_dc_current_a": 1000},
                "operating_point": {"dc_power_kw": 200},
            },
            "operating_inverter_power",
        ),
    ],
)
def test_incompatible_envelopes_are_structured_and_cannot_prepare(groups, key):
    d = design(**groups)
    r = evaluate(d)
    assert check(r, key)["status"] == "incompatible"
    assert r["compatibility_status"] == "incompatible"
    with pytest.raises(ValueError):
        build_models(
            d,
            r["checks"],
            r["specifications"]["total_mass_kg"]["value"],
            ACKNOWLEDGEMENTS,
        )


def test_compatible_warning_and_insufficient_evidence_are_distinguished():
    r = evaluate(VehicleDesignV2())
    assert check(r, "battery_energy")["status"] == "compatible_within_checked_limits"
    assert check(r, "charging_acceptance")["status"] == "warning"
    assert check(r, "peak_duration")["status"] == "insufficient_data"
    assert check(r, "phase_current")["status"] == "insufficient_data"
    assert r["compatibility_status"] == "insufficient_data"
    r = evaluate(
        design(
            inverter={"maximum_dc_current_a": None}, battery={"charge_limit_a": None}
        )
    )
    assert check(r, "inverter_dc_current")["status"] == "insufficient_data"
    assert check(r, "charging_acceptance")["status"] == "insufficient_data"


@pytest.mark.parametrize(
    "group,field,value",
    [
        ("body", "wheel_radius_m", 0),
        ("body", "mass_excluding_components_kg", -1),
        ("gearbox", "reduction_ratio", 0),
        ("battery", "mass_kg", float("nan")),
        ("motor", "efficiency_assumption", 1.1),
        ("inverter", "maximum_dc_current_a", -1),
    ],
)
def test_structural_invalid_values_reject(group, field, value):
    with pytest.raises(ValidationError):
        design(**{group: {field: value}})


def test_catalogue_references_and_resolved_overrides_are_explicit():
    r = evaluate(design(component_ids={"motor": "custom"}))
    assert (
        check(r, "catalogue_references")["status"] == "compatible_within_checked_limits"
    )
    r = evaluate(design(component_ids={"motor": "battery-64"}))
    assert check(r, "catalogue_references")["status"] == "incompatible"
    r = evaluate(design(motor={"rated_power_kw": 100}))
    assert "rated_power_kw" in r["catalogue_overrides"]["motor"]
    with pytest.raises(ValidationError):
        design(catalogue_version="unknown")
    with pytest.raises(ValidationError):
        design(schema_version=3)


def test_adapter_constructs_retained_models_without_silent_default_geometry():
    d = design(
        body={
            "mass_excluding_components_kg": 1100,
            "wheel_radius_m": 0.4,
            "drag_coefficient": 0.31,
            "frontal_area_m2": 2.5,
            "rolling_resistance_coefficient": 0.02,
        },
        gearbox={"reduction_ratio": 10, "mechanical_efficiency": 0.95},
        assumptions={"grade_percent": 5, "air_density_kg_m3": 1.2},
    )
    r = evaluate(d)
    mass = r["specifications"]["total_mass_kg"]["value"]
    with pytest.raises(ValueError):
        build_models(d, r["checks"], mass, [])
    models = build_models(d, r["checks"], mass, ACKNOWLEDGEMENTS)
    sim = models.dynamics
    assert sim.vehicle.mass_kg == 1648 and sim.vehicle.wheel_radius_m == 0.4
    assert sim.vehicle.cd == 0.31 and sim.vehicle.frontal_area_m2 == 2.5
    assert (
        sim.transmission.gear_ratios == [10]
        and sim.transmission.mechanical_efficiency == 0.95
    )
    assert sim.motor.max_power_kw == 150 and sim.motor.max_rpm == 12000
    assert sim.gradient_rad == pytest.approx(math.atan(0.05))
    result = sim.step(
        VehicleState(velocity_ms=10), motor_torque_nm=100, brake_force_n=0, dt_s=0.01
    )
    expected_drive = 100 * 10 * 0.95 / 0.4
    expected_resistance = (
        0.5 * 1.2 * 0.31 * 2.5 * 100
        + 0.02 * 1648 * 9.81 * math.cos(math.atan(0.05))
        + 1648 * 9.81 * math.sin(math.atan(0.05))
    )
    assert result.drive_force_n == pytest.approx(expected_drive)
    assert result.acceleration_ms2 == pytest.approx(
        (expected_drive - expected_resistance) / 1648
    )
    assert models.battery.capacity_kwh == 60 and models.battery.voltage_v == 400
    assert (
        models.battery.resistance_ohm == 0.05 and models.battery.charge_limit_a == 200
    )
    assert models.drive_efficiency == pytest.approx(0.94 * 0.97)


def test_api_roundtrip_bounds_comparison_and_acknowledgements(client):
    d = client.get("/api/workbench/v2/design").json()
    r = client.post("/api/workbench/v2/evaluate", json=d)
    assert r.status_code == 200
    assert r.json() == client.post("/api/workbench/v2/evaluate", json=d).json()
    assert (
        client.get("/api/workbench/v2/schema").json()["properties"]["schema_version"][
            "const"
        ]
        == 2
    )
    assert (
        client.get("/api/workbench/v2/catalogue").json()["version"]
        == "representative-v1"
    )
    assert (
        client.post("/api/workbench/v2/evaluate", content=b" " * 64001).status_code
        == 413
    )
    assert (
        client.post(
            "/api/workbench/v2/evaluate", json={"schema_version": 99}
        ).status_code
        == 422
    )
    assert (
        client.post("/api/workbench/v2/evaluate", json={"surprise": 1}).status_code
        == 422
    )
    assert (
        client.post("/api/workbench/v2/adapter", json={"design": d}).status_code == 422
    )
    prepared = client.post(
        "/api/workbench/v2/adapter",
        json={"design": d, "acknowledgements": ACKNOWLEDGEMENTS},
    )
    assert prepared.status_code == 200 and prepared.json()["ready"]
    assert prepared.json()["mappings"]["vehicle"]["mass_kg"] == 1748
    modified = copy.deepcopy(d)
    modified["battery"]["mass_kg"] += 100
    comparison = client.post(
        "/api/workbench/v2/compare", json={"baseline": d, "modified": modified}
    ).json()
    mass = next(x for x in comparison["differences"] if x["key"] == "total_mass_kg")
    assert mass["delta"] == 100
    assert (
        next(
            x for x in comparison["changed_parameters"] if x["key"] == "battery.mass_kg"
        )["delta"]
        == 100
    )
    modified["motor"]["mass_kg"] = None
    comparison = client.post(
        "/api/workbench/v2/compare", json={"baseline": d, "modified": modified}
    ).json()
    assert (
        next(x for x in comparison["differences"] if x["key"] == "total_mass_kg")[
            "delta"
        ]
        is None
    )


def test_legacy_import_does_not_invent_or_double_count_component_masses(client):
    response = client.post("/api/workbench/v2/migrate", json={"schema_version": 1})
    assert response.status_code == 422
    assert "double-count mass" in response.json()["detail"]
    assert "body/residual mass" in response.json()["detail"]


@pytest.mark.parametrize("path", ["evaluate", "adapter", "compare"])
def test_api_never_substitutes_default_parameters_for_incomplete_snapshots(
    client, path
):
    value = design().model_dump(mode="json")
    del value["battery"]["resistance_ohm"]
    payload = (
        value
        if path == "evaluate"
        else (
            {"design": value}
            if path == "adapter"
            else {"baseline": value, "modified": design().model_dump(mode="json")}
        )
    )
    result = client.post("/api/workbench/v2/" + path, json=payload)
    assert result.status_code == 422
    assert "Incomplete resolved design snapshot" in result.json()["detail"]
