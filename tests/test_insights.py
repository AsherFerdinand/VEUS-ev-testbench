"""Independent insight arithmetic and conservative extrapolation gates, not certification."""

import copy
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from veus.lab.profiles import ProfileData, Source
from veus.lab.schema import LabRequest
from veus.lab.runner import run
from veus.replay.analysis import canonical
from veus.workbench.adapter import ACKNOWLEDGEMENTS
from veus.workbench.design import VehicleDesignV2
from veus.workbench.insights import (
    InsightsRequest,
    calculate,
    cycle_range_km,
    energy_economics,
    cycle_eligibility,
    compact_run,
    insights_export,
    router,
)


def request(**updates):
    values = dict(
        vehicle=VehicleDesignV2(),
        acknowledgements=ACKNOWLEDGEMENTS,
        acceleration_duration_s=1,
    )
    values.update(updates)
    return InsightsRequest(**values)


@pytest.fixture(scope="module")
def insight():
    return calculate(request())


def test_range_and_economics_independent_analytical_reference():
    assert cycle_range_km(60, 15) == 400
    money = energy_economics(15, 40, 0.3, 0.8, 20)
    # 40 km ×15/100 =6kWh battery; /0.8=7.5kWh grid; ×.3=2.25EUR daily.
    assert money["daily_battery_energy_kwh"] == 6
    assert money["daily_grid_energy_kwh"] == 7.5
    assert money["daily_electricity_cost_eur"] == 2.25
    assert money["daily_battery_energy_cost_eur"] == pytest.approx(1.8)
    assert money["monthly_grid_energy_kwh"] == 150
    assert money["monthly_electricity_cost_eur"] == 45
    absent = energy_economics(15, 40, 0.3, None, None)
    assert absent["daily_battery_energy_cost_eur"] == pytest.approx(1.8)
    assert (
        absent["daily_grid_energy_kwh"] is None
        and absent["daily_electricity_cost_eur"] is None
    )
    assert absent["monthly_battery_energy_kwh"] is None
    zero = energy_economics(15, 0, 0, 0.8, 0)
    assert all(x == 0 for x in zero.values())
    for args in [(0, 15), (60, 0), (60, -1), (float("inf"), 15)]:
        with pytest.raises(ValueError):
            cycle_range_km(*args)
    for efficiency in [0, -0.1, 1.1, float("nan")]:
        with pytest.raises(ValueError):
            energy_economics(15, 40, 0.3, efficiency)


def reference_cycle():
    p = ProfileData(
        id="analytic",
        name="Synthetic analytical gate fixture",
        source=Source(
            kind="illustrative",
            source_url="synthetic://test",
            licence="Test fixture",
            sha256="0" * 64,
            units={"time": "s", "speed": "m/s"},
        ),
        time_s=[0, 1],
        speed_ms=[20, 20],
        grade_percent=[0, 0],
    )
    result = {
        "summary": dict(
            duration_s=1,
            distance_m=1000,
            net_battery_energy_kwh=0.13,
            battery_heat_kwh=0.02,
            requested_motion_infeasible_duration_s=0,
            initial_soc=0.8,
            final_soc=0.7975,
            maximum_tracking_error_ms=0,
        ),
        "trace": [dict(time_s=0, soc=0.8), dict(time_s=1, soc=0.7975)],
    }
    return result, p


def test_range_gate_uses_stored_depletion_not_terminal_energy_and_allows_regen_clipping():
    r, p = reference_cycle()
    # .13 terminal + .02 heat=.15 kWh over1km ->15kWh/100km ->400km model reservoir.
    g = cycle_eligibility(r, p, 60)
    assert g["status"] == "available"
    assert g["stored_consumption_kwh_100km"] == pytest.approx(15)
    assert cycle_range_km(60, g["stored_consumption_kwh_100km"]) == pytest.approx(400)
    r["summary"]["requested_infeasible_duration_s"] = (
        1  # Could be recovery-only, not impossible braking.
    )
    r["trace"][-1]["requested_regen_recovery_limited"] = True
    assert cycle_eligibility(r, p, 60)["status"] == "available"


@pytest.mark.parametrize(
    "change",
    [
        {"summary": {"requested_motion_infeasible_duration_s": 0.2}},
        {"summary": {"maximum_tracking_error_ms": 0.2}},
        {"summary": {"duration_s": 0.5}},
        {"summary": {"distance_m": 0}},
        {"summary": {"net_battery_energy_kwh": -0.02}},
        {"summary": {"final_soc": 0.7}},
        {"trace": [dict(time_s=0, soc=0.8), dict(time_s=1, soc=0)]},
        {"trace": [dict(time_s=0, soc=1), dict(time_s=1, soc=0.9975)]},
    ],
)
def test_range_gate_marks_incomplete_infeasible_soc_or_energy_cases_inconclusive(
    change,
):
    r, p = reference_cycle()
    if "summary" in change:
        r["summary"].update(change["summary"])
    else:
        r.update(change)
    g = cycle_eligibility(r, p, 60)
    assert g["status"] == "inconclusive" and g["reasons"]


def test_actual_cycle_insights_reproducibility_full_run_hash_and_bounded_preview(
    insight,
):
    assert insight == calculate(request())
    assert insight["cycle"]["eligibility"]["status"] == "available"
    assert insight["cycle"]["samples_simulated"] > 400
    assert len(insight["cycle"]["preview_trace"]) <= 400
    assert "preview_only" in insight["cycle"]["trace_scope"]
    assert (
        insight["metrics"]["modelled_consumption_kwh_100km"]["value"]
        > insight["metrics"]["terminal_consumption_kwh_100km"]["value"]
    )
    frozen = LabRequest.model_validate(insight["provenance"]["cycle_request"])
    full = run(frozen)
    assert full["run_sha256"] == insight["cycle"]["run_sha256"]
    assert insight["cycle"]["preview_trace"][0]["time_s"] == 0
    assert (
        insight["cycle"]["preview_trace"][-1]["time_s"] == full["trace"][-1]["time_s"]
    )
    assert insight["metrics"]["daily_grid_energy_kwh"]["value"] is None
    assert insight["metrics"]["daily_battery_energy_cost_eur"]["value"] > 0
    assert insight["metrics"]["modelled_acceleration_time_s"]["value"] is None
    assert insight["metrics"]["acceleration_final_speed_ms"]["value"] > 0
    assert (
        insight["provenance"]["cycle_request"]["experiment"]["power_policy"]
        == "continuous"
    )
    assert (
        insight["provenance"]["acceleration_request"]["experiment"]["power_policy"]
        == "continuous"
    )


def test_scenario_hash_includes_profile_source_but_excludes_vehicle_geometry(insight):
    full = run(LabRequest.model_validate(insight["provenance"]["cycle_request"]))
    a = compact_run(full)["scenario_sha256"]
    changed = copy.deepcopy(full)
    changed["request"]["profile"]["source"]["sha256"] = "1" * 64
    assert compact_run(changed)["scenario_sha256"] != a
    changed = copy.deepcopy(full)
    changed["vehicle"]["body"]["drag_coefficient"] = 0.9
    assert compact_run(changed)["scenario_sha256"] == a
    changed = copy.deepcopy(full)
    changed["vehicle"]["assumptions"]["initial_soc"] = 0.7
    assert compact_run(changed)["scenario_sha256"] != a


def test_infeasible_and_boundary_cycles_cannot_produce_range_or_daily_extrapolation():
    d = VehicleDesignV2().model_dump(mode="json")
    d["battery"]["discharge_limit_a"] = 1
    limited = calculate(
        InsightsRequest(
            vehicle=d, acknowledgements=ACKNOWLEDGEMENTS, acceleration_duration_s=1
        )
    )
    assert limited["cycle"]["eligibility"]["status"] == "inconclusive"
    assert limited["metrics"]["cycle_equivalent_range_km"]["value"] is None
    assert limited["metrics"]["daily_battery_energy_kwh"]["value"] is None
    d = VehicleDesignV2().model_dump(mode="json")
    d["assumptions"]["initial_soc"] = 1
    full = calculate(
        InsightsRequest(
            vehicle=d, acknowledgements=ACKNOWLEDGEMENTS, acceleration_duration_s=1
        )
    )
    assert full["metrics"]["cycle_equivalent_range_km"]["value"] is None
    assert any("SOC" in reason for reason in full["cycle"]["eligibility"]["reasons"])


def test_complete_snapshot_acknowledgements_and_economic_inputs_are_enforced():
    with pytest.raises(ValidationError):
        InsightsRequest(vehicle={}, acknowledgements=ACKNOWLEDGEMENTS)
    with pytest.raises(ValidationError):
        InsightsRequest(vehicle=VehicleDesignV2())
    for fields in [
        {"charging_efficiency": 0},
        {"charging_efficiency": 1.1},
        {"tariff_eur_kwh": -1},
        {"daily_distance_km": float("inf")},
        {"driving_days": 32},
        {"profile_id": "made-up"},
        {"acceleration_duration_s": 121},
        {"dt_s": 0.001},
    ]:
        with pytest.raises(ValidationError):
            request(**fields)
    with pytest.raises(ValueError):
        calculate(request(profile_id="udds", dt_s=0.05))


def test_quantities_change_with_actual_selected_snapshot_and_explicit_daily_assumptions(
    insight,
):
    d = VehicleDesignV2().model_dump(mode="json")
    d["body"]["mass_excluding_components_kg"] += 100
    modified = calculate(
        InsightsRequest(
            vehicle=d,
            acknowledgements=ACKNOWLEDGEMENTS,
            charging_efficiency=0.8,
            driving_days=10,
            acceleration_duration_s=1,
        )
    )
    assert modified["configuration_sha256"] != insight["configuration_sha256"]
    assert modified["metrics"]["total_vehicle_mass_kg"]["value"] == 1848
    assert modified["cycle"]["scenario_sha256"] == insight["cycle"]["scenario_sha256"]
    assert (
        modified["metrics"]["modelled_consumption_kwh_100km"]["value"]
        != insight["metrics"]["modelled_consumption_kwh_100km"]["value"]
    )
    assert modified["metrics"]["daily_electricity_cost_eur"]["value"] > 0
    assert modified["metrics"]["monthly_electricity_cost_eur"][
        "value"
    ] == pytest.approx(10 * modified["metrics"]["daily_electricity_cost_eur"]["value"])


def test_insight_api_and_frozen_exports_do_not_recalculate(insight, monkeypatch):
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        response = client.post(
            "/api/workbench/v2/insights", json=request().model_dump(mode="json")
        )
        assert response.status_code == 200 and response.json() == insight
        assert (
            client.post("/api/workbench/v2/insights", json={"vehicle": {}}).status_code
            == 422
        )
        assert (
            client.post(
                "/api/workbench/v2/insights", content=b" " * 2000001
            ).status_code
            == 413
        )
        monkeypatch.setattr(
            "veus.workbench.insights.run",
            lambda _: (_ for _ in ()).throw(AssertionError("export recalculated")),
        )
        for format in ["json", "csv", "html"]:
            response = client.post(
                "/api/workbench/v2/insights/export",
                json={"result": insight, "format": format},
            )
            assert response.status_code == 200 and response.json()["content"]
        bad = copy.deepcopy(insight)
        bad["metrics"]["cycle_equivalent_range_km"]["value"] += 1
        assert (
            client.post(
                "/api/workbench/v2/insights/export",
                json={"result": bad, "format": "json"},
            ).status_code
            == 422
        )
        assert (
            insights_export(insight, "json")["content"] == canonical(insight).decode()
        )
