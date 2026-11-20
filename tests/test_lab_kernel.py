"""Analytical and coupled-limit checks. These do not establish vehicle validation."""

import copy
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from veus.workbench.design import VehicleDesignV2
from veus.workbench.adapter import ACKNOWLEDGEMENTS
from veus.lab.schema import LabRequest, ExperimentConfig
from veus.lab.runner import run
from veus.lab.api import router


def request(kind="acceleration", **changes):
    d = VehicleDesignV2().model_dump(mode="json")
    for group, value in changes.pop("vehicle", {}).items():
        d[group].update(value)
    exp = dict(kind=kind, duration_s=5, dt_s=0.05)
    exp.update(changes)
    return LabRequest(vehicle=d, experiment=exp, acknowledgements=ACKNOWLEDGEMENTS)


def test_selected_geometry_and_rating_policy_are_used_not_legacy_vehicle():
    d = {
        "body": {
            "mass_excluding_components_kg": 1000,
            "drag_coefficient": 0,
            "rolling_resistance_coefficient": 0,
            "frontal_area_m2": 2,
            "wheel_radius_m": 0.5,
        },
        "gearbox": {"reduction_ratio": 5, "mechanical_efficiency": 1},
        "motor": {"rated_torque_nm": 100, "rated_power_kw": 120},
        "battery": {"resistance_ohm": 0},
        "inverter": {"efficiency_assumption": 1},
    }
    r = run(request(vehicle=d, duration_s=2, dt_s=0.01))
    mass = 1548
    # 100 Nm × 5 / .5 = 1000 N, no road losses, constant force.
    assert r["trace"][-1]["speed_ms"] == pytest.approx(1000 / mass * 2, abs=1e-10)
    assert r["trace"][1]["motor_torque_nm"] == pytest.approx(100)
    assert max(abs(x["energy_balance_error_j"]) for x in r["trace"]) < 1e-5
    assert r == run(request(vehicle=d, duration_s=2, dt_s=0.01))


def test_five_experiments_and_target_only_when_achieved():
    for kind in ["constant_speed", "acceleration", "braking", "gradient", "coast"]:
        r = run(
            request(
                kind,
                initial_speed_ms=20,
                target_speed_ms=20,
                grade_percent=3 if kind == "gradient" else 0,
            )
        )
        assert len(r["trace"]) == 101 and r["trace"][0]["time_s"] == 0
        assert r["summary"]["maximum_energy_balance_error_j"] < 1e-4
        assert 0 <= r["summary"]["final_soc"] <= 1
    r = run(request(target_speed_ms=100, duration_s=1))
    assert r["summary"]["time_to_target_s"] is None


def test_braking_regen_fallback_full_soc_zero_acceptance_and_empty_pack():
    on = run(request("braking", initial_speed_ms=15, duration_s=8))
    off = run(
        request("braking", initial_speed_ms=15, duration_s=8, regen_enabled=False)
    )
    assert on["summary"]["energy_recovered_kwh"] > 0
    regenerative = [r for r in on["trace"] if r["regen_power_w"] > 0]
    assert regenerative and all(
        r["motor_power_w"] < 0 and r["motor_torque_nm"] < 0 for r in regenerative
    )
    assert all(
        r["regen_power_w"] == pytest.approx(-r["battery_power_w"]) for r in regenerative
    )
    assert all(r["regen_wheel_power_w"] >= r["regen_power_w"] for r in regenerative)
    assert off["summary"]["energy_recovered_kwh"] == 0
    assert on["summary"]["stopping_distance_m"] == pytest.approx(
        off["summary"]["stopping_distance_m"]
    )
    for battery, assumptions in [({"charge_limit_a": 0}, {}), ({}, {"initial_soc": 1})]:
        r = run(
            request(
                "braking",
                initial_speed_ms=15,
                duration_s=8,
                vehicle={"battery": battery, "assumptions": assumptions},
            )
        )
        assert r["summary"]["energy_recovered_kwh"] == 0
        assert r["summary"]["friction_energy_kwh"] > 0
        assert r["summary"]["maximum_energy_balance_error_j"] < 1e-4
    r = run(request(vehicle={"assumptions": {"initial_soc": 0}}))
    assert (
        r["summary"]["final_speed_ms"] == 0 and r["summary"]["energy_consumed_kwh"] == 0
    )
    r = run(
        request(
            "coast", initial_speed_ms=20, vehicle={"battery": {"discharge_limit_a": 0}}
        )
    )
    assert r["summary"]["final_speed_ms"] < 20


def test_current_voltage_and_mean_shaft_power_limits_are_enforced():
    r = run(
        request(
            initial_speed_ms=20,
            vehicle={
                "battery": {"discharge_limit_a": 40, "minimum_voltage_v": 399},
                "inverter": {"maximum_dc_current_a": 30},
            },
        )
    )
    for row in r["trace"]:
        assert (
            row["battery_current_a"] <= 20 + 1e-6
        )  # (400-399)/.05 A window is tighter.
        assert row["battery_voltage_v"] >= 399 - 1e-6
        assert row["motor_power_w"] <= 120000 + 1e-4
    assert any(
        "battery_or_inverter_electrical_envelope" in r["limits"] for r in r["trace"]
    )


def test_constant_speed_requested_demand_has_independent_reference_and_no_forcing():
    d = {
        "body": {
            "drag_coefficient": 0.25,
            "frontal_area_m2": 2,
            "rolling_resistance_coefficient": 0,
        },
        "motor": {"efficiency_assumption": 1},
        "inverter": {"efficiency_assumption": 1},
        "gearbox": {"mechanical_efficiency": 1},
        "battery": {"resistance_ohm": 0},
    }
    r = run(
        request(
            "constant_speed",
            mode="prescribed",
            initial_speed_ms=20,
            target_speed_ms=20,
            vehicle=d,
        )
    )
    # 0.5 × 1.225 × .25 × 2 × 20² = 122.5 N; 2450 W at 20 m/s.
    assert r["trace"][1]["requested_dc_power_w"] == pytest.approx(2450)
    assert r["summary"]["requested_discharge_energy_kwh"] == pytest.approx(
        2450 * 5 / 3600000
    )
    assert r["summary"]["final_speed_ms"] == pytest.approx(20)
    limited = run(
        request(
            "constant_speed",
            mode="prescribed",
            initial_speed_ms=0,
            target_speed_ms=50,
            vehicle={"battery": {"discharge_limit_a": 1}},
        )
    )
    assert limited["summary"]["final_speed_ms"] < (2 * 400 * 5 / 1748) ** 0.5
    assert limited["summary"]["requested_infeasible_duration_s"] > 0
    assert (
        limited["summary"]["requested_discharge_energy_kwh"]
        > limited["summary"]["energy_consumed_kwh"]
    )


def test_grade_drag_and_mass_change_real_selected_results():
    flat = run(request("constant_speed", initial_speed_ms=20, target_speed_ms=20))
    uphill = run(
        request("gradient", initial_speed_ms=20, target_speed_ms=20, grade_percent=5)
    )
    assert (
        uphill["summary"]["energy_consumed_kwh"]
        > flat["summary"]["energy_consumed_kwh"]
    )
    assert uphill["summary"]["gradient_work_kwh"] > 0
    a = run(request())
    b = run(request(vehicle={"battery": {"mass_kg": 620}}))
    assert b["summary"]["final_speed_ms"] < a["summary"]["final_speed_ms"]


def test_unknown_inputs_peak_ack_and_execution_bounds():
    with pytest.raises(ValueError):
        run(request(vehicle={"battery": {"resistance_ohm": None}}))
    with pytest.raises(ValueError):
        run(request(power_policy="acknowledged_peak"))
    req = request(
        power_policy="acknowledged_peak",
        duration_s=5,
        vehicle={"motor": {"peak_duration_s": 2}, "inverter": {"peak_duration_s": 2}},
    )
    req.acknowledgements.append("peak_envelope_without_thermal_model")
    with pytest.raises(ValueError):
        run(req)
    with pytest.raises(ValueError):
        ExperimentConfig(duration_s=1800, dt_s=0.01)


def test_api_exports_frozen_results_without_recalculation():
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        req = request(duration_s=1)
        response = c.post("/api/lab/run", json=req.model_dump(mode="json"))
        assert response.status_code == 200
        result = response.json()
        for fmt in ["json", "csv", "html"]:
            response = c.post("/api/lab/export", json={"result": result, "format": fmt})
            assert response.status_code == 200 and response.json()["content"]
        broken = copy.deepcopy(result)
        broken["summary"]["distance_m"] += 1
        assert (
            c.post(
                "/api/lab/export", json={"result": broken, "format": "json"}
            ).status_code
            == 422
        )
        assert c.post("/api/lab/run", json={"bad": 1}).status_code == 422


def test_external_request_requires_complete_vehicle_snapshot():
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        assert (
            c.post(
                "/api/lab/run",
                json={"vehicle": {}, "acknowledgements": ACKNOWLEDGEMENTS},
            ).status_code
            == 422
        )


def profile(times, speeds, grades=None):
    from veus.lab.profiles import ProfileData, Source

    return ProfileData(
        id="analytic-profile",
        name="Explicit synthetic test profile",
        source=Source(
            kind="illustrative",
            source_url="synthetic://unit-test",
            licence="Synthetic unit test",
            sha256="0" * 64,
            units={"time": "s", "speed": "m/s"},
        ),
        time_s=times,
        speed_ms=speeds,
        grade_percent=grades,
    )


def route(distances, grades=None, elevation=None):
    from veus.lab.profiles import RouteData, Source

    return RouteData(
        id="analytic-route",
        name="Explicit synthetic test route",
        source=Source(
            kind="illustrative",
            source_url="synthetic://unit-test",
            licence="Synthetic unit test",
            sha256="0" * 64,
            units={"distance": "m"},
        ),
        s_m=distances,
        grade_percent=grades,
        elevation_m=elevation,
    )


def test_profile_prescribed_demand_and_predictive_motion_share_kernel_without_forcing():
    p = profile([0, 1, 2], [0, 20, 20], [0, 0, 0])
    req = request("profile", duration_s=2, dt_s=0.05)
    req.profile = p
    predictive = run(req)
    req.experiment.mode = "prescribed"
    prescribed = run(req)
    for r in [predictive, prescribed]:
        assert r["summary"]["final_speed_ms"] < 20
        assert r["summary"]["requested_infeasible_duration_s"] > 0
        assert (
            r["summary"]["requested_discharge_energy_kwh"]
            > r["summary"]["energy_consumed_kwh"]
        )
        assert r["summary"]["maximum_energy_balance_error_j"] < 1e-4
        assert r["provenance"]["profile"]["source"]["kind"] == "illustrative"
        assert all(
            row["speed_ms"] != row["target_speed_ms"] for row in r["trace"][1:10]
        )
    assert predictive["run_sha256"] != prescribed["run_sha256"]


def test_profile_gaps_and_missing_grade_are_not_silently_completed():
    req = request("profile", duration_s=2, dt_s=0.05)
    req.profile = profile([0, 1, 2], [5, 5, 5])
    with pytest.raises(ValueError, match="grade"):
        run(req)
    req.experiment.route_grade_policy = "experiment_constant_assumption"
    out = run(req)
    assert all(
        r["grade_source"] == "experiment_constant_assumption" for r in out["trace"]
    )
    req.profile = profile([0, 5], [5, 5], [0, 0])
    with pytest.raises(ValueError, match="gap"):
        run(req)
    req.profile = profile([0, 1], [5, 5], [0, 0])
    with pytest.raises(ValueError, match="coverage"):
        run(req)


def test_route_grade_uses_declared_distance_basis_and_preserves_missing_geometry():
    req = request("profile", duration_s=2, dt_s=0.05, initial_speed_ms=0)
    req.profile = profile([0, 1, 2], [20, 20, 20], [0, 0, 0])
    req.route = route([0, 25, 100], [0, 10, 10])
    a = run(req)
    req.experiment.mode = "prescribed"
    b = run(req)
    assert a["trace"][-1]["route_position_m"] == pytest.approx(
        a["trace"][-1]["position_m"]
    )
    assert b["trace"][-1]["route_position_m"] == pytest.approx(
        b["summary"]["requested_distance_m"]
    )
    assert b["trace"][-1]["route_position_m"] > a["trace"][-1]["route_position_m"]
    assert b["trace"][-1]["grade_percent"] > a["trace"][-1]["grade_percent"]
    assert all(r["latitude"] is None and r["longitude"] is None for r in b["trace"])
    req.route = route([0, 100])
    with pytest.raises(ValueError, match="grade/coverage"):
        run(req)
    req.experiment.route_grade_policy = "experiment_constant_assumption"
    c = run(req)
    assert all(r["grade_percent"] == 0 for r in c["trace"])


def test_route_coverage_exhaustion_fails_without_clamping():
    req = request(
        "constant_speed", duration_s=2, initial_speed_ms=20, target_speed_ms=20
    )
    req.route = route([0, 5], [0, 0])
    with pytest.raises(ValueError, match="coverage"):
        run(req)


def test_combined_route_timed_profile_uses_same_explicit_runner():
    req = request("profile", duration_s=2, dt_s=0.05)
    req.route = route([0, 10, 20], [0, 0, 0]).model_copy(
        update={"time_s": [0, 1, 2], "speed_ms": [0, 5, 5]}
    )
    out = run(req)
    assert out["request"]["profile"]["speed_ms"] == [0, 5, 5]
    assert out["provenance"]["profile"]["source"]["kind"] == "illustrative"
    req.route = route([0, 10, 20], [0, 0, 0])
    with pytest.raises(ValueError, match="timed speed"):
        run(req)


def test_regen_recovery_constraint_does_not_claim_braking_motion_is_infeasible():
    req = request("profile", duration_s=2, initial_speed_ms=10)
    req.profile = profile([0, 1, 2], [10, 8, 6], [0, 0, 0])
    req.vehicle.battery.charge_limit_a = 0
    r = run(req)
    assert any(row["requested_regen_recovery_limited"] for row in r["trace"][1:])
    assert all(row["requested_motion_feasible"] for row in r["trace"][1:])
    assert r["summary"]["requested_motion_infeasible_duration_s"] == 0
    assert r["summary"]["rms_tracking_error_ms"] is not None
    assert r["summary"]["energy_recovered_kwh"] == 0
    assert r["limit_duration_s"]["requested_regen_recovery_limited"] > 0
    assert all("value" in f and "unit" in f for f in r["findings"])
    assert sum(
        i["duration_s"]
        for i in r["limit_intervals"]
        if i["limit"] == "requested_regen_recovery_limited"
    ) == pytest.approx(r["limit_duration_s"]["requested_regen_recovery_limited"])
