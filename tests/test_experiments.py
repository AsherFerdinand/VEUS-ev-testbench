import base64
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from veus.studio.main import app
from veus.validation.experiments import (
    Experiment,
    ModelParameters,
    evaluate,
    error_metrics,
)
from veus.validation.measurements import load_csv
from veus.validation.calibration import (
    CalibrationConfig,
    ParameterRange,
    calibrate,
    guard_holdout,
    sensitivity,
)
from veus.validation.report import analyse
from veus.validation.__main__ import main

ROOT = Path(__file__).resolve().parents[1]


def pair(name):
    exp = Experiment.model_validate_json(
        (ROOT / "examples/validation" / f"{name}.json").read_text()
    )
    path = (
        ROOT
        / ("datasets/ved" if name.startswith("ved-") else "examples/validation")
        / (name + ".csv")
    )
    raw = path.read_bytes()
    return exp, load_csv(raw, exp.source, exp.preprocessing), raw


def settings():
    return CalibrationConfig.model_validate_json(
        (ROOT / "examples/validation/battery-calibration.json").read_text()
    )


def test_metrics_independent_calculation_missing_and_zero_reference():
    m = error_metrics([0, 2, None, 4], [1, 0, 999, 7])
    assert m["mae"] == 2
    assert m["rmse"] == pytest.approx((14 / 3) ** 0.5)
    assert m["bias"] == pytest.approx(2 / 3)
    assert m["max_abs_error"] == 3 and m["coverage"] == 0.75
    assert error_metrics([None], [0])["mae"] is None
    assert not any("percent" in key for key in m)
    with pytest.raises(ValueError):
        error_metrics([1], [1, 2])
    with pytest.raises(ValueError):
        error_metrics([1], [float("nan")])


def test_role_guards_and_no_forced_speed():
    exp, data, _ = pair("synthetic-coast-holdout")
    before = evaluate(exp, data)
    wrong = exp.parameters.model_copy(update={"rolling_resistance": 0.04})
    after = evaluate(exp, data, wrong)
    assert (
        after["metrics"]["vehicle_speed_ms"]["rmse"]
        > before["metrics"]["vehicle_speed_ms"]["rmse"]
    )
    assert (
        before["predictions"][0]["vehicle_speed_ms"]
        == data.signals["vehicle_speed_ms"][0]
    )
    assert before["predictions"][100]["vehicle_speed_ms"] != data.at(
        "vehicle_speed_ms", 1
    )
    with pytest.raises(ValueError):
        calibrate(exp, data, settings())
    config = exp.model_dump()
    config["kind"] = "energy_replay"
    with pytest.raises(ValueError):
        Experiment.model_validate(config)
    data.signals.pop("motor_torque_nm")
    with pytest.raises(ValueError, match="independent input"):
        evaluate(exp, data)


def test_calibration_reproducibility_bounds_and_independent_holdout():
    train, data, _ = pair("synthetic-battery-train")
    original = train.model_dump()
    artifact = calibrate(train, data, settings())
    assert artifact == calibrate(train, data, settings())
    assert train.model_dump() == original
    assert artifact["calibrated_parameters"]["battery_voltage_v"] == pytest.approx(390)
    assert artifact["calibrated_parameters"]["battery_resistance_ohm"] == pytest.approx(
        0.12
    )
    holdout, test, _ = pair("synthetic-battery-holdout")
    guard_holdout(artifact, holdout)
    calibrated = evaluate(
        holdout, test, ModelParameters.model_validate(artifact["calibrated_parameters"])
    )
    assert calibrated["metrics"]["battery_voltage_v"]["rmse"] < 1e-8
    with pytest.raises(ValueError):
        guard_holdout(artifact, train)
    duplicate = holdout.model_copy(deep=True)
    duplicate.source.expected_sha256 = train.source.expected_sha256
    with pytest.raises(ValueError, match="leakage"):
        guard_holdout(artifact, duplicate)
    duplicate = holdout.model_copy(deep=True)
    duplicate.source.run_id = train.source.run_id
    with pytest.raises(ValueError, match="leakage"):
        guard_holdout(artifact, duplicate)
    with pytest.raises(ValueError):
        ParameterRange(name="rolling_resistance", low=-1, high=0.1)


def test_unexcited_parameters_not_misrepresented():
    exp, data, _ = pair("synthetic-battery-train")
    data.signals["battery_current_a"] = [10] * len(data.times)
    data.signals["battery_voltage_v"] = [389] * len(data.times)
    result = calibrate(exp, data, settings())
    assert result["status"] == "NOT_IDENTIFIABLE"
    assert result["calibrated_parameters"] is None


def test_sensitivity_is_deterministic_and_separate():
    exp, data, _ = pair("synthetic-battery-holdout")
    ranges = [ParameterRange(name="battery_voltage_v", low=390, high=410)]
    a = sensitivity(exp, data, ranges, "battery_voltage_v")
    assert a == sensitivity(exp, data, ranges, "battery_voltage_v")
    assert a["rows"][0]["final_prediction_span"] == pytest.approx(20)
    assert exp.parameters.battery_voltage_v == 400


def test_output_uncertainty_can_make_outcome_inconclusive():
    exp, data, _ = pair("synthetic-battery-holdout")
    value = evaluate(exp, data)["metrics"]["battery_voltage_v"]["rmse"]
    exp.comparisons[0].threshold = value
    exp.comparisons[0].uncertainty = 1
    result = evaluate(exp, data)
    assert result["status"] == "INCONCLUSIVE"
    assert result["metrics"]["battery_voltage_v"][
        "uncertainty_interval"
    ] == pytest.approx([value - 1, value + 1])


def test_measurement_report_and_api_do_not_claim_validation(tmp_path):
    exp, data, raw = pair("synthetic-battery-holdout")
    result = analyse(exp, raw)
    assert result["summary"]["label"] == "Synthetic pipeline demonstration"
    assert result["summary"]["provenance"]["validation_scope"].startswith(
        "Synthetic pipeline demonstration"
    )
    assert "Synthetic pipeline demonstration" in result["html"]
    measured, _, measured_raw = pair("ved-10-1561")
    real = analyse(measured, measured_raw)
    assert real["summary"]["status"] == "INCONCLUSIVE"
    assert real["summary"]["evidence_status"] == "CONDITIONS_UNVERIFIED"
    assert real["summary"]["numerical_status"] == "FAIL"
    with TestClient(app) as client:
        assert client.get("/api/validation/examples/../../missing").status_code != 200
        response = client.post(
            "/api/validation/analyse",
            json=dict(
                experiment=exp.model_dump(mode="json"),
                csv_base64=base64.b64encode(raw).decode(),
            ),
        )
        assert response.status_code == 200
        assert response.json()["summary"]["evidence_status"] == "SYNTHETIC_ONLY"
        bad = client.post(
            "/api/validation/analyse",
            json=dict(
                experiment=exp.model_dump(mode="json"),
                csv_base64=base64.b64encode(raw + b"\n").decode(),
            ),
        )
        assert bad.status_code == 422
    output = tmp_path / "report"
    assert (
        main(
            [
                "evaluate",
                str(ROOT / "examples/validation/synthetic-battery-holdout.json"),
                str(ROOT / "examples/validation/synthetic-battery-holdout.csv"),
                "--output",
                str(output),
            ]
        )
        == 1
    )
    assert (output / "original.csv").read_bytes() == raw
    assert (output / "original-residuals.csv").exists()
    assert (
        main(
            [
                "evaluate",
                str(ROOT / "examples/validation/synthetic-battery-holdout.json"),
                str(ROOT / "examples/validation/synthetic-battery-holdout.csv"),
                "--output",
                str(output),
            ]
        )
        == 2
    )


def make_experiment(raw, kind, columns, comparisons, parameters=None):
    import hashlib
    from veus.validation.measurements import DataSource, ImportConfig

    exp = Experiment(
        id="custom-fixture",
        objective="Synthetic software fixture",
        kind=kind,
        source=DataSource(
            dataset="test",
            source_url="test fixture",
            licence="test fixture",
            kind="synthetic",
            run_id="custom",
            role="exploration",
            expected_sha256=hashlib.sha256(raw).hexdigest(),
            provenance_evidence="Synthetic fixture",
        ),
        preprocessing=ImportConfig(
            columns={k: dict(column=k, unit=u) for k, u in columns.items()}
        ),
        parameters=ModelParameters(**(parameters or {})),
        assumptions=["Isolated synthetic case, not physical validation"],
        comparisons=comparisons,
    )
    return exp, load_csv(raw, exp.source, exp.preprocessing)


def test_energy_replay_is_not_a_speed_validation_and_signed_regen():
    raw = b"time_s,motor_torque_nm,motor_speed_rad_s,battery_voltage_v,battery_current_a\n0,10,100,400,3.125\n1,10,100,400,3.125\n2,10,100,400,3.125\n"
    cols = dict(
        time_s="s",
        motor_torque_nm="Nm",
        motor_speed_rad_s="rad/s",
        battery_voltage_v="V",
        battery_current_a="A",
    )
    exp, data = make_experiment(
        raw,
        "energy_replay",
        cols,
        [
            dict(
                signal="battery_power_w",
                threshold=1e-6,
                rationale="Known 1000 W shaft / eta 0.8",
            ),
            dict(
                signal="energy_wh",
                threshold=1e-6,
                rationale="Constant-power energy integral",
            ),
        ],
        dict(drive_efficiency=0.8, battery_resistance_ohm=0),
    )
    result = evaluate(exp, data)
    assert result["status"] == "PASS"
    assert result["predictions"][-1]["energy_wh"] == pytest.approx(1250 * 2 / 3600)
    negative = raw.replace(b"10,100,400,3.125", b"-5,100,400,-0.875")
    exp, data = make_experiment(
        negative,
        "energy_replay",
        cols,
        [
            dict(
                signal="battery_power_w",
                threshold=1e-6,
                rationale="500 W mechanical regen * 0.7",
            )
        ],
        dict(regen_efficiency=0.7, battery_resistance_ohm=0),
    )
    assert evaluate(exp, data)["status"] == "PASS"
    assert evaluate(exp, data)["predictions"][-1]["energy_wh"] < 0


def test_missing_output_is_not_silently_zeroed():
    exp, data, _ = pair("synthetic-battery-holdout")
    data.signals["battery_voltage_v"][1:] = [None] * 10
    result = evaluate(exp, data)
    assert result["status"] == "INCONCLUSIVE"
    assert result["metrics"]["battery_voltage_v"]["count"] == 0
    assert result["metrics"]["battery_voltage_v"]["mae"] is None


def test_fitted_parameters_do_not_overwrite_independent_fixed_conditions():
    train, data, _ = pair("synthetic-battery-train")
    artifact = calibrate(train, data, settings())
    holdout, _, raw = pair("synthetic-battery-holdout")
    holdout.parameters.mass_kg = 2500
    result = analyse(holdout, raw, artifact)
    assert result["summary"]["calibrated"]["parameters"]["mass_kg"] == 2500
    assert result["summary"]["status"] == "PASS"
    with TestClient(app) as client:
        body = dict(
            experiment=holdout.model_dump(mode="json"),
            csv_base64=base64.b64encode(raw).decode(),
            action="calibrate",
            calibration_settings=settings().model_dump(mode="json"),
        )
        assert client.post("/api/validation/analyse", json=body).status_code == 422


def test_bounded_coast_calibration_and_holdout_speed_error():
    train, data, _ = pair("synthetic-coast-train")
    train.parameters.drag_area_m2 = 0.62
    spec = CalibrationConfig(
        parameters=[dict(name="rolling_resistance", low=0.008, high=0.02)],
        objective_signal="vehicle_speed_ms",
        grid_points=7,
        refinements=2,
    )
    artifact = calibrate(train, data, spec)
    assert artifact["status"] == "CALIBRATED"
    assert artifact["calibrated_parameters"]["rolling_resistance"] == pytest.approx(
        0.012
    )
    assert artifact["training_rmse"] < artifact["initial_rmse"]
    holdout, test, _ = pair("synthetic-coast-holdout")
    holdout.parameters.drag_area_m2 = 0.62
    learned = ModelParameters.model_validate(artifact["calibrated_parameters"])
    assert (
        evaluate(holdout, test, learned)["metrics"]["vehicle_speed_ms"]["rmse"]
        < evaluate(holdout, test)["metrics"]["vehicle_speed_ms"]["rmse"]
    )


def test_braking_distance_error_is_separate_from_speed_fitting():
    rows = [
        "time_s,vehicle_speed_ms,motor_torque_nm,brake_force_n,road_gradient_rad,position_m"
    ]
    for t in range(11):
        rows.append(f"{t},{10 - t},0,1000,0,{10 * t - 0.5 * t * t}")
    raw = ("\n".join(rows) + "\n").encode()
    exp, data = make_experiment(
        raw,
        "dynamics",
        dict(
            time_s="s",
            vehicle_speed_ms="m/s",
            motor_torque_nm="Nm",
            brake_force_n="N",
            road_gradient_rad="rad",
            position_m="m",
        ),
        [
            dict(
                signal="vehicle_speed_ms",
                threshold=0.1,
                rationale="Known ideal constant deceleration with small model aero discrepancy",
            )
        ],
        dict(
            mass_kg=1000,
            rolling_resistance=0,
            drag_area_m2=0.1,
            wheel_radius_m=0.5,
            gear_ratio=1,
            transmission_efficiency=1,
        ),
    )
    events = evaluate(exp, data)["events"]
    assert events["measured_braking_distance_m"] == 50
    assert events["predicted_braking_distance_m"] > 0
    assert abs(events["braking_distance_error_m"]) < 1


def test_driving_app_import_does_not_require_optional_reporting_libraries():
    import subprocess, sys

    code = """import builtins
original=builtins.__import__
def blocked(name,*args,**kwargs):
    if name.split('.')[0] in {'numpy','matplotlib'}:raise ImportError('optional dependency blocked')
    return original(name,*args,**kwargs)
builtins.__import__=blocked
from veus.studio.main import app
assert any(getattr(r,'path',None)=='/ws/simulation' for r in app.routes)
"""
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
