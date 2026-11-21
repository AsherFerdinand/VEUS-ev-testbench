"""Illustrative-map interpolation/balance and exact legacy fingerprints, not validation."""

import hashlib
import pytest
from veus.model.motor import ElectricMotor
from veus.model.efficiency_map import (
    bilinear,
    IllustrativeMotorMap,
    UnsupportedOperatingPoint,
)
from veus.workbench.design import VehicleDesignV2
from veus.workbench.adapter import ACKNOWLEDGEMENTS
from veus.workbench.insights import InsightsRequest, calculate
from veus.lab.schema import LabRequest
from veus.lab.runner import run
from veus.lab.report import export
from veus.lab.profiles import builtin_profile


def request(model="illustrative_map", kind="acceleration", **experiment):
    e = dict(kind=kind, duration_s=2, dt_s=0.05)
    e.update(experiment)
    return LabRequest(
        vehicle=VehicleDesignV2(),
        acknowledgements=ACKNOWLEDGEMENTS,
        experiment=e,
        efficiency_model=model,
    )


def test_bilinear_has_independent_arithmetic_and_no_extrapolation():
    assert bilinear(0.25, 0.5, [0, 1], [0, 1], [[0.8, 0.9], [0.9, 1]]) == pytest.approx(
        0.875
    )
    for x, y in [(-0.001, 0.5), (1.01, 0.5), (0.5, 1.01), (float("nan"), 0)]:
        with pytest.raises(UnsupportedOperatingPoint):
            bilinear(x, y, [0, 1], [0, 1], [[0.8, 0.9], [0.9, 1]])
    m = IllustrativeMotorMap(
        ElectricMotor(max_torque_nm=100, max_power_kw=200, max_rpm=12000)
    )
    assert m.efficiency(3600, 20) == pytest.approx(0.89)
    assert m.efficiency(5700, 40) == pytest.approx((0.89 + 0.94 + 0.91 + 0.955) / 4)
    assert m.efficiency(3600, 20, True) == pytest.approx(0.82)
    assert m.efficiency(0, 0) == 0.72
    with pytest.raises(UnsupportedOperatingPoint):
        m.efficiency(12001, 0)
    with pytest.raises(UnsupportedOperatingPoint):
        m.efficiency(0, 101)
    with pytest.raises(UnsupportedOperatingPoint):
        m.efficiency(3000, 71, True)


def test_retained_constant_torque_power_speed_envelope_and_map_metadata_isolation():
    motor = ElectricMotor(max_torque_nm=100, max_power_kw=50, max_rpm=12000)
    m = IllustrativeMotorMap(motor)
    assert m.torque_limit(1000) == 100
    assert m.torque_limit(30000 / (3.141592653589793)) == pytest.approx(50)
    assert m.torque_limit(12000) == 0
    assert m.torque_limit(1000, True) == 70
    with pytest.raises(UnsupportedOperatingPoint):
        m.efficiency(10000, 100)
    original = m.metadata()
    changed = m.metadata()
    changed["motoring_efficiency"][0][0] = 0.1
    changed["rpm_fraction_axis"][0] = -0.5
    assert m.metadata() == original and m.efficiency(0, 0) == 0.72


def test_mapped_drive_and_regeneration_loss_splits_preserve_power_balance():
    for kind, initial in [("acceleration", 10), ("braking", 15)]:
        r = run(request(kind=kind, initial_speed_ms=initial, duration_s=5))
        assert r["summary"]["maximum_energy_balance_error_j"] < 1e-4
        assert "powertrain_map" in r["provenance"]
        assert all(
            r["summary"][k] >= 0
            for k in ["motor_loss_kwh", "inverter_loss_kwh", "gearbox_loss_kwh"]
        )
        for row in r["trace"][1:]:
            assert (
                row["motor_loss_w"] >= 0
                and row["inverter_loss_w"] >= 0
                and row["gearbox_loss_w"] >= 0
            )
            assert row["battery_power_w"] - row["motor_ac_power_w"] == pytest.approx(
                row["inverter_loss_w"], abs=1e-7
            )
            assert row["motor_ac_power_w"] - row["motor_power_w"] == pytest.approx(
                row["motor_loss_w"], abs=1e-7
            )
        split = sum(
            r["summary"][k]
            for k in ["motor_loss_kwh", "inverter_loss_kwh", "gearbox_loss_kwh"]
        )
        assert split == pytest.approx(r["summary"]["conversion_loss_kwh"], abs=1e-10)
        if kind == "braking":
            rec = [row for row in r["trace"] if row["regen_power_w"] > 0]
            assert rec and all(
                row["motor_power_w"] < 0
                and row["motor_ac_power_w"] < 0
                and row["battery_power_w"] < 0
                for row in rec
            )
            assert all(
                row["regen_wheel_power_w"]
                >= -row["motor_power_w"]
                >= row["regen_power_w"]
                for row in rec
            )


def test_mapped_limits_soc_and_no_unsupported_peak_operation():
    req = request(initial_speed_ms=20)
    req.vehicle.battery.discharge_limit_a = 30
    req.vehicle.inverter.maximum_dc_current_a = 20
    result = run(req)
    assert all(row["battery_current_a"] <= 20 + 1e-6 for row in result["trace"])
    assert all(row["motor_power_w"] <= 120000 + 1e-5 for row in result["trace"])
    assert all(0 <= row["soc"] <= 1 for row in result["trace"])
    req = request(kind="braking", initial_speed_ms=15)
    req.vehicle.assumptions.initial_soc = 1
    result = run(req)
    assert (
        result["summary"]["energy_recovered_kwh"] == 0
        and result["summary"]["friction_energy_kwh"] > 0
    )
    req = request(power_policy="acknowledged_peak")
    req.acknowledgements.append("peak_envelope_without_thermal_model")
    with pytest.raises(ValueError, match="peak durations"):
        run(req)
    req.vehicle.motor.peak_duration_s = 1
    req.vehicle.inverter.peak_duration_s = 1
    with pytest.raises(ValueError, match="duration"):
        run(req)
    req = request(initial_speed_ms=100)
    with pytest.raises(UnsupportedOperatingPoint):
        run(req)


def test_representative_cycle_is_deterministic_and_operating_points_are_exported():
    p = builtin_profile("urban")
    req = request(kind="profile", mode="prescribed", duration_s=p.time_s[-1], dt_s=0.2)
    req.profile = p
    a = run(req)
    b = run(req)
    assert a == b
    assert len(a["trace"]) == 601
    assert a["summary"]["maximum_energy_balance_error_j"] < 1e-4
    assert max(row["motor_efficiency"] or 0 for row in a["trace"]) <= 0.955
    assert a["summary"]["requested_motion_infeasible_duration_s"] == 0
    assert "motor_efficiency" in export(a, "csv")["content"].split("\n")[0]
    assert export(a, "html")["content"]
    legacy = run(req.model_copy(update={"efficiency_model": None}))
    assert a["run_sha256"] != legacy["run_sha256"]
    assert (
        a["summary"]["net_battery_energy_kwh"]
        != legacy["summary"]["net_battery_energy_kwh"]
    )


def test_optional_mode_does_not_change_legacy_requests_results_or_export_bytes():
    req = request(None, kind="braking", initial_speed_ms=10, duration_s=1)
    assert "efficiency_model" not in req.model_dump(mode="json")
    assert "efficiency_model" not in InsightsRequest(
        vehicle=VehicleDesignV2(), acknowledgements=ACKNOWLEDGEMENTS
    ).model_dump(mode="json")
    old = run(req)
    assert (
        old["run_sha256"]
        == "c666acf6ee4ede4e87c358cad2324cfaedb91b3970001a1d0dfadcc50a73a42e"
    )
    expected = {
        "json": "dae9f1bbd15b2177705ea2e75c9a01e24119682e7340212433bf0389a49285a8",
        "csv": "419b66477779ff9656847e79143dfc4c1e52e64223800458a7e7c456a0846cde",
        "html": "0bcc3d49338dbe900a5d1f20a1e14a674deb881a3d83623a758d5e1e83f5bbf5",
    }
    for fmt, sha in expected.items():
        assert hashlib.sha256(export(old, fmt)["content"].encode()).hexdigest() == sha
    assert (
        "motor_efficiency" not in old["trace"][-1]
        and "powertrain_map" not in old["provenance"]
    )


def test_insights_map_passthrough_preserves_same_cycle_conditions():
    req = InsightsRequest(
        vehicle=VehicleDesignV2(),
        acknowledgements=ACKNOWLEDGEMENTS,
        acceleration_duration_s=1,
    )
    old = calculate(req)
    mapped = calculate(req.model_copy(update={"efficiency_model": "illustrative_map"}))
    assert old["cycle"]["scenario_sha256"] == mapped["cycle"]["scenario_sha256"]
    assert "motor_rpm" not in old["cycle"]["preview_fields"]
    assert (
        "motor_rpm" in mapped["cycle"]["preview_fields"]
        and "motor_torque_nm" in mapped["cycle"]["preview_fields"]
    )
    assert mapped["cycle"]["powertrain_map"]["classification"] == "illustrative"
    assert mapped["request"]["efficiency_model"] == "illustrative_map"


def test_map_load_power_monotonicity_supports_bounded_coupling_searches():
    m = IllustrativeMotorMap(
        ElectricMotor(max_torque_nm=100, max_power_kw=50, max_rpm=12000)
    )
    for rpm in [1, 3000, 7000, 11999]:
        for regenerative in [False, True]:
            maximum = m.torque_limit(rpm, regenerative)
            torques = [maximum * i / 100 for i in range(101)]
            powers = [
                t * m.efficiency(rpm, t, True)
                if regenerative
                else t / m.efficiency(rpm, t)
                for t in torques
            ]
            assert all(b >= a - 1e-12 for a, b in zip(powers, powers[1:]))


def test_all_presets_complete_default_cycle_and_thirty_second_acceleration():
    from veus.workbench.presets import vehicle_presets

    results = []
    for preset in vehicle_presets()["presets"]:
        result = calculate(
            InsightsRequest(
                vehicle=preset["design"],
                acknowledgements=ACKNOWLEDGEMENTS,
                efficiency_model="illustrative_map",
            )
        )
        assert result["cycle"]["samples_simulated"] == 601
        assert (
            result["acceleration"]["summary"]["maximum_energy_balance_error_j"] < 0.01
        )
        results.append(result)
    # Inspect the full trace: unavailable efficiency is explicit, never extrapolated.
    direct = run(
        LabRequest(
            vehicle=vehicle_presets()["presets"][0]["design"],
            acknowledgements=ACKNOWLEDGEMENTS,
            efficiency_model="illustrative_map",
            experiment={"kind": "acceleration", "duration_s": 30, "dt_s": 0.2},
        )
    )
    outside = [
        row
        for row in direct["trace"]
        if "zero_power_outside_map_efficiency_unavailable" in row["limits"]
    ]
    assert outside
    assert all(
        row["motor_efficiency"] is None
        and row["motor_ac_power_w"] == 0
        and row["motor_power_w"] == 0
        for row in outside
    )
