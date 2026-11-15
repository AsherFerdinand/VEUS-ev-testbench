import csv
from pathlib import Path
import pytest
from pydantic import ValidationError
from veus.sensors.config import SensorSuiteConfig
from veus.sensors.virtual import SensorSuite
from veus.sim.session import RunConfig, SimulationSession


def suite(**kwargs):
    return SensorSuite(SensorSuiteConfig(enabled=True, **kwargs))


def update(sensor, tick):
    sensor.update(tick, 10 + tick * 0.1, 50 - tick * 0.1, 2.0)
    return sensor.views()


def fault(kind, **kwargs):
    return dict(
        id="event",
        sensor="radar",
        fault=kind,
        start_time_s=0.02,
        duration_s=0.03,
        **kwargs,
    )


def test_ideal_measurements_timestamps():
    sensor = suite(mode="ideal")
    for tick in range(10):
        views = update(sensor, tick)
        assert views["speed"]["values"]["speed_ms"] == 10 + tick * 0.1
        assert views["radar"]["values"] == dict(
            distance_m=50 - tick * 0.1, closing_speed_ms=2.0
        )
        assert views["radar"]["valid"] and views["radar"]["age_s"] == 0
        assert views["radar"]["sample_time_s"] == tick * 0.01


def test_bias_and_overlapping_noise_bias():
    sensor = suite(
        radar=dict(distance_bias_m=2),
        faults=[fault("bias", parameters={"distance_bias_m": 3})],
    )
    assert update(sensor, 0)["radar"]["values"]["distance_m"] == 52
    assert update(sensor, 2)["radar"]["values"]["distance_m"] == 54.8
    assert update(sensor, 5)["radar"]["values"]["distance_m"] == 51.5
    assert sensor.events == [
        dict(id="event", sensor="radar", fault="bias", event="activated", time_s=0.02),
        dict(
            id="event", sensor="radar", fault="bias", event="deactivated", time_s=0.05
        ),
    ]


def test_seed_reset_and_independent_streams():
    def sequence(seed):
        s = suite(
            seed=seed, radar={"distance_noise_std_m": 1}, speed={"noise_std_ms": 0.1}
        )
        return [update(s, i)["radar"]["values"]["distance_m"] for i in range(20)]

    assert sequence(42) == sequence(42)
    assert sequence(42) != sequence(43)


def test_sampling_hold_and_latency():
    s = suite(radar={"sampling_hz": 20, "latency_s": 0.02})
    assert not update(s, 0)["radar"]["valid"]
    assert not update(s, 1)["radar"]["valid"]
    assert update(s, 2)["radar"]["values"]["distance_m"] == 50
    for tick in range(3, 7):
        update(s, tick)
    assert s.views()["radar"]["sample_time_s"] == 0
    assert update(s, 7)["radar"]["sample_time_s"] == 0.05
    assert s.views()["radar"]["age_s"] == 0.02


def test_dropout_priority_freeze_and_staleness():
    s = suite(radar={"stale_after_s": 0.02}, faults=[fault("freeze")])
    for t in range(5):
        v = update(s, t)
    assert v["radar"]["values"]["distance_m"] == 49.9
    assert v["radar"]["sample_time_s"] == 0.01
    assert v["radar"]["frozen"]
    assert v["radar"]["status"] == "stale" and not v["radar"]["valid"]
    assert update(s, 5)["radar"]["valid"]
    f = fault("dropout")
    f["id"] = "drop"
    s = suite(faults=[fault("freeze"), f])
    update(s, 0)
    update(s, 1)
    assert update(s, 2)["radar"]["values"]["distance_m"] is None
    assert not s.views()["radar"]["valid"]
    assert update(s, 5)["radar"]["valid"]


def test_freeze_without_prior_measurement_and_variable_latency():
    f = fault("freeze")
    f["start_time_s"] = 0
    s = suite(faults=[f])
    assert not update(s, 0)["radar"]["valid"]
    assert update(s, 3)["radar"]["valid"]
    f = fault("latency", parameters={"latency_s": 0.1})
    f["start_time_s"] = 0
    s = suite(faults=[f])
    for i in range(15):
        update(s, i)
    assert s.views()["radar"]["sample_time_s"] == 0.14
    assert s.views()["radar"]["discarded_packets"] > 0


@pytest.mark.parametrize(
    "config",
    [
        {"speed": {"sampling_hz": 30}},
        {"radar": {"latency_s": -0.1}},
        {"speed": {"noise_std_ms": -1}},
        {"seed": -1},
        {"faults": [fault("noise", parameters={"unknown": 1})]},
        {"faults": [fault("bias", parameters={"distance_bias_m": float("nan")})]},
        {"faults": [fault("latency", parameters={"latency_s": 0.001})]},
        {"faults": [fault("dropout", parameters={"distance_bias_m": 1})]},
        {"faults": [fault("bias", parameters={})]},
        {"mode": "ideal", "speed": {"bias_ms": 1}},
        {"faults": [fault("freeze"), fault("freeze")]},
    ],
)
def test_invalid_sensor_configs(config):
    with pytest.raises(ValidationError):
        SensorSuiteConfig(**config)


def test_disabled_baseline_exact_and_ideal_close():
    from veus.testing.runner import run_scenario
    from veus.testing.schema import Scenario

    path = Path(__file__).resolve().parents[1] / "scenarios/lead_braking_dry.json"
    original = Scenario.model_validate_json(path.read_text())
    disabled = run_scenario(original)
    config = original.config.model_copy(
        update={"sensors": SensorSuiteConfig(enabled=True, mode="ideal")}
    )
    ideal = run_scenario(original.model_copy(update={"config": config}))
    assert ideal.metrics.minimum_separation_m == pytest.approx(
        disabled.metrics.minimum_separation_m, abs=1e-9
    )
    assert ideal.metrics.aeb_detection_time_s == disabled.metrics.aeb_detection_time_s
    assert ideal.metrics.radar_distance_mae_m == 0
    golden = list(
        csv.DictReader((path.parents[1] / "docs/verification/summary.csv").open())
    )
    row = next(r for r in golden if r["scenario_id"] == original.id)
    assert disabled.metrics.minimum_separation_m == float(row["minimum_separation_m"])


def test_controller_fallback_no_truth_substitution_and_emergency_latch():
    sensors = SensorSuiteConfig(
        enabled=True,
        faults=[
            dict(
                id="lost", sensor="radar", fault="dropout", start_time_s=0, duration_s=1
            )
        ],
    )
    s = SimulationSession(
        RunConfig(
            mode="aeb",
            initial_speed_kmh=80,
            sensors=sensors,
            duration_s=2,
            lead_brake_start_s=1,
        )
    )
    s.status = "running"
    f = s.step()
    assert f["controller_state"] == "sensor_fallback_braking"
    assert f["controller_measured_gap_m"] is None
    assert f["gap_m"] is not None and f["measured_gap_m"] is None
    assert f["brake_force_n"] > 0
    s.controller.emergency_latched = True
    assert s.step()["controller_state"] == "emergency_braking"


def test_detection_delay_age_and_reset_rng():
    config = RunConfig(
        mode="cruise",
        initial_speed_kmh=36,
        sensors=SensorSuiteConfig(
            enabled=True, speed={"noise_std_ms": 0.01, "stale_after_s": 0.02}
        ),
        detection_delay_s=0.1,
    )
    s = SimulationSession(config)
    s.status = "running"
    first = s.step()
    for _ in range(10):
        f = s.step()
    assert f["controller_input_health"] == "stale"
    assert f["controller_state"] == "sensor_fallback_braking"
    s.reset(config)
    s.status = "running"
    assert s.step() == first
    assert not s.sensor_suite.events


def test_sensor_horizon_and_negative_reading_validation():
    with pytest.raises(ValidationError):
        RunConfig(
            duration_s=1,
            sensors=SensorSuiteConfig(faults=[fault("freeze") | {"duration_s": 2}]),
        )
    s = suite(speed={"bias_ms": -100})
    assert not update(s, 0)["speed"]["valid"]


def test_overlap_rules_noise_and_latency_fault_boundaries():
    noise = fault("noise", parameters={"distance_noise_std_m": 1})
    noise2 = noise | dict(id="other", parameters={"distance_noise_std_m": 2})
    a = suite(seed=1, faults=[noise, noise2])
    b = suite(seed=1, faults=[noise, noise2])
    values = []
    for tick in range(7):
        va = update(a, tick)
        vb = update(b, tick)
        assert va == vb
        values.append(va["radar"]["values"]["distance_m"])
    assert values[0] == 50 and values[2] != 49.8 and values[5] == 49.5
    latency = fault("latency", parameters={"latency_s": 0.02})
    s = suite(radar={"latency_s": 0.01}, faults=[latency])
    for tick in range(5):
        update(s, tick)
    assert s.views()["radar"]["sample_time_s"] == 0.01
    for tick in range(5, 8):
        update(s, tick)
    assert (
        s.views()["radar"]["sample_time_s"] == 0.06
    )  # old late packet must not overwrite


def test_missing_measurements_not_zeroed_in_error_statistics():
    from veus.testing.schema import Scenario
    from veus.testing.runner import run_scenario

    s = Scenario(
        id="drop-stats",
        description="Only first half has radar data",
        config=RunConfig(
            mode="acc",
            initial_speed_kmh=36,
            lead_speed_kmh=36,
            initial_gap_m=100,
            duration_s=2,
            sensors=SensorSuiteConfig(
                enabled=True,
                radar={"distance_bias_m": 5},
                faults=[
                    dict(
                        id="drop",
                        sensor="radar",
                        fault="dropout",
                        start_time_s=1,
                        duration_s=1,
                    )
                ],
            ),
        ),
    )
    r = run_scenario(s)
    assert r.metrics.radar_distance_mae_m == pytest.approx(5)
    assert r.metrics.radar_unavailable_fraction > 0
    assert r.metrics.fault_activation_count == 1
    assert r.ideal_baseline.config.sensors.mode == "ideal"
    assert r.ideal_baseline.metrics.radar_distance_mae_m == 0
    assert r.sensor_fault_events[-1]["event"] == "deactivated"


def test_all_old_scenario_metrics_match_recorded_baseline():
    from veus.testing.schema import Scenario
    from veus.testing.runner import run_scenario

    root = Path(__file__).resolve().parents[1]
    expected = {
        row["scenario_id"]: row
        for row in csv.DictReader((root / "docs/verification/summary.csv").open())
    }
    for path in (root / "scenarios").glob("*.json"):
        scenario = Scenario.model_validate_json(path.read_text())
        result = run_scenario(scenario)
        row = expected[scenario.id]
        assert result.status == row["status"]
        for name, value in result.metrics.model_dump().items():
            if name in row:
                assert value == (float(row[name]) if row[name] else None), (
                    scenario.id,
                    name,
                )


def test_sensor_report_serialization_and_websocket_events(tmp_path):
    import json
    from fastapi.testclient import TestClient
    from veus.studio.main import app
    from veus.testing.schema import Scenario
    from veus.testing.__main__ import main

    cfg = RunConfig(
        mode="acc",
        initial_speed_kmh=36,
        lead_speed_kmh=36,
        duration_s=1,
        sensors=SensorSuiteConfig(
            enabled=True,
            faults=[
                dict(
                    id="drop",
                    sensor="radar",
                    fault="dropout",
                    start_time_s=0,
                    duration_s=0.2,
                )
            ],
        ),
    )
    with TestClient(app) as client:
        with client.websocket_connect("/ws/simulation") as ws:
            ws.receive_json()
            ws.send_json(dict(action="reset", config=cfg.model_dump(mode="json")))
            ready = ws.receive_json()
            assert ready["sensor_fault_events"][0]["event"] == "activated"
            assert ready["resolved_config"]["sensors"]["enabled"]
            ws.send_json(dict(action="start"))
            ws.receive_json()
            for _ in range(2):
                frame = ws.receive_json()
            assert frame["sensor_fault_events"][-1]["event"] == "deactivated"
    source = tmp_path / "scenario.json"
    output = tmp_path / "report"
    source.write_text(
        Scenario(
            id="sensor-report", description="Sensor evidence", config=cfg
        ).model_dump_json()
    )
    assert (
        main(["run", str(source), "--output", str(output)]) == 1
    )  # no criteria -> INCONCLUSIVE
    result = json.loads((output / "sensor-report/result.json").read_text())
    assert result["sensor_fault_events"][0]["time_s"] == 0
    assert "telemetry" not in result["ideal_baseline"]
    assert (output / "sensor-report/ideal-baseline-telemetry.csv").exists()
    html = (output / "report.html").read_text()
    assert "Like-for-like ideal sensor baseline" in html
    assert "Virtual sensors and fault events" in html
    assert "radar_distance_mae_m" in html


def test_inconsistent_relative_velocity_does_not_use_true_lead_speed():
    config = RunConfig(
        mode="aeb",
        initial_speed_kmh=36,
        lead_speed_kmh=0,
        sensors=SensorSuiteConfig(enabled=True, radar={"relative_speed_bias_ms": 5}),
    )
    session = SimulationSession(config)
    session.status = "running"
    frame = session.step()
    assert frame["radar_sensor_valid"]
    assert frame["controller_input_health"] == "inconsistent-measurements"
    assert frame["controller_measured_gap_m"] is None
    assert frame["controller_state"] == "sensor_fallback_braking"


def test_sensor_scenario_outcomes_and_ideal_comparisons_are_reproducible():
    from veus.testing.schema import Scenario
    from veus.testing.runner import run_scenario

    root = Path(__file__).resolve().parents[1]
    outcomes = {}
    for path in sorted((root / "scenarios/sensors").glob("*.json")):
        scenario = Scenario.model_validate_json(path.read_text())
        result = run_scenario(scenario)
        assert result == run_scenario(scenario)
        outcomes[scenario.id] = result.status
        assert result.metrics.max_energy_balance_error_j < 0.001
        if scenario.id != "ideal-radar":
            assert result.ideal_baseline is not None
    assert outcomes == {
        "frozen-radar": "PASS",
        "ideal-radar": "PASS",
        "radar-dropout": "PASS",
        "radar-latency": "FAIL",
        "radar-noise": "PASS",
        "radar-positive-bias": "FAIL",
        "speed-sensor-bias": "FAIL",
    }


def test_repeated_read_tick_does_not_redraw_noise_and_time_cannot_reverse():
    sensor = suite(speed={"noise_std_ms": 0.1})
    first = update(sensor, 1)
    assert update(sensor, 1) == first
    with pytest.raises(ValueError):
        update(sensor, 0)
