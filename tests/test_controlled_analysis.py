"""Matched scenario hashes, arithmetic, explicit mass scaling and bounded failures."""

import copy
import pytest
from veus.workbench.design_analysis import (
    StudyRequest,
    run_study,
    study_export,
    delta,
    variants,
)
from veus.workbench.presets import vehicle_presets
from veus.workbench.adapter import ACKNOWLEDGEMENTS


def req(**changes):
    v = vehicle_presets()["presets"][0]["design"]
    data = dict(
        baseline=v,
        modified=v,
        conditions=dict(
            acknowledgements=ACKNOWLEDGEMENTS, profile_id="urban", dt_s=0.2
        ),
    )
    data.update(changes)
    return StudyRequest(**data)


def test_identical_design_zero_deltas_and_determinism():
    r = run_study(req())
    assert r == run_study(req())
    assert r["matched_conditions"]
    assert all(d["absolute"] in [0, None] for d in r["rows"][1]["differences"].values())
    for fmt in ["json", "csv", "html"]:
        assert study_export(r, fmt)["content"]
    bad = copy.deepcopy(r)
    bad["matched_conditions"] = False
    with pytest.raises(ValueError):
        study_export(bad, "json")


def test_percentage_and_missing_reference():
    assert delta(20, 15)["percent"] == -25
    assert delta(0, 5) == dict(
        absolute=5, percent=None, reason="Zero baseline: percentage undefined"
    )
    assert delta(None, 5)["absolute"] is None


def test_bounded_drag_sweep_uses_same_scenario_and_saved_snapshot_unchanged():
    request = req(
        kind="sensitivity", parameter="body.drag_coefficient", values=[0.2, 0.3]
    )
    before = request.model_dump(mode="json")
    r = run_study(request)
    assert request.model_dump(mode="json") == before
    assert r["matched_conditions"] and len(r["rows"]) == 3
    low, high = [
        p["analysis"]["metrics"]["modelled_consumption_kwh_100km"]["value"]
        for p in r["rows"][1:]
    ]
    assert low < high
    assert len({p["configuration_sha256"] for p in r["rows"]}) == 3
    with pytest.raises(ValueError):
        req(kind="sensitivity", values=list(range(6)))


def test_battery_mass_scaling_and_invalid_points_retained():
    request = req(
        kind="battery_size", values=[50, 80], battery_mass_kg_per_usable_kwh=7
    )
    points = variants(request)
    assert (
        points[1][2]["battery"]["mass_kg"] == 350
        and points[2][2]["battery"]["mass_kg"] == 560
    )
    assert points[1][2]["battery"]["gross_capacity_kwh"] == pytest.approx(50 * 64 / 60)
    with pytest.raises(ValueError):
        req(kind="battery_size", values=[50, 80])
    r = run_study(
        req(kind="sensitivity", parameter="motor.rated_power_kw", values=[100, 1000])
    )
    assert r["rows"][-1]["status"] == "inconclusive" and r["rows"][-1]["error"]


def test_changed_initial_soc_warns_and_suppresses_controlled_differences():
    request = req()
    d = request.modified.model_copy(deep=True)
    d.assumptions.initial_soc = 0.6
    request.modified = d
    r = run_study(request)
    assert not r["matched_conditions"] and r["warnings"]
    assert not r["rows"][1]["differences"]


def test_drag_sensitivity_matches_independent_steady_force_reference():
    from veus.lab.schema import LabRequest
    from veus.lab.runner import run

    request = req(
        kind="sensitivity", parameter="body.drag_coefficient", values=[0.2, 0.3]
    )
    points = variants(request)[1:]
    results = []
    for _, _, vehicle in points:
        results.append(
            run(
                LabRequest(
                    vehicle=vehicle,
                    acknowledgements=ACKNOWLEDGEMENTS,
                    experiment=dict(
                        kind="constant_speed",
                        duration_s=2,
                        dt_s=0.2,
                        initial_speed_ms=20,
                        target_speed_ms=20,
                    ),
                )
            )
        )
    # Difference .5*rho*DeltaCd*A*v^3 divided by declared forward efficiencies.
    expected = 0.5 * 1.225 * 0.1 * 2.2 * 20**3 / (0.94 * 0.97 * 0.97)
    actual = (
        (
            results[1]["summary"]["net_battery_energy_kwh"]
            - results[0]["summary"]["net_battery_energy_kwh"]
        )
        * 3.6e6
        / 2
    )
    assert actual == pytest.approx(expected, abs=1e-7)
