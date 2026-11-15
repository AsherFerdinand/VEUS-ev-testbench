import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from veus.testing.schema import Scenario
from veus.testing.runner import run_scenario
from veus.testing.__main__ import main
from veus.sim.session import RunConfig, SimulationSession

ROOT = Path(__file__).resolve().parents[1]


def scenario(**kwargs):
    return Scenario(
        id="test-case", description="Test fixture", config=RunConfig(**kwargs)
    )


def test_scenario_determinism_and_frame_compatibility():
    s = scenario(mode="acceleration", duration_s=1)
    result = run_scenario(s)
    assert result == run_scenario(s)
    assert len(result.telemetry) == 101
    assert result.status == "INCONCLUSIVE"  # no requirements is never a vacuous pass
    session = SimulationSession(s.config)
    session.status = "running"
    for index in range(1, 11):
        frame = session.advance()
        assert all(
            result.telemetry[index * 10][key] == value for key, value in frame.items()
        )


def test_manual_events_and_brake_distance_definition():
    s = Scenario(
        id="pedals",
        description="Pulse braking",
        config=RunConfig(mode="manual", initial_speed_kmh=36, duration_s=3),
        controls=[dict(time_s=1, controls=dict(brake=1, throttle=0))],
    )
    result = run_scenario(s)
    assert result.metrics.brake_onset_time_s == 1
    assert result.metrics.braking_distance_m > 0
    assert result.metrics.stop_time_s > 1
    assert result.telemetry[100]["manual_brake_command"] == 0
    assert result.telemetry[101]["manual_brake_command"] == 1
    assert all(f["drive_force_n"] == 0 for f in result.telemetry[101:])


def test_collision_metrics_and_inconclusive_non_events():
    s = Scenario.model_validate_json(
        (ROOT / "scenarios/lead_braking_low_grip.json").read_text()
    )
    result = run_scenario(s)
    assert result.status == "FAIL"
    assert result.metrics.collision_count == 1
    assert result.metrics.impact_ego_speed_kmh > 0
    assert result.metrics.impact_closing_speed_kmh > 0
    assert result.metrics.braking_distance_m is None  # collision is not a stop
    assert result.metrics.minimum_ttc_s == 0
    assert next(r for r in result.requirements if r.id == "AVOID-01").status == "FAIL"
    assert next(r for r in result.requirements if r.id == "REPRO-01").status == "PASS"
    s = scenario(mode="coast", duration_s=1)
    from veus.testing.schema import Criterion

    s.criteria = [
        Criterion(
            id="STOP",
            description="Stop",
            metric="braking_distance_m",
            operator="<=",
            threshold=10,
            rationale="Test missing stop event",
        )
    ]
    result = run_scenario(s)
    assert (
        result.status == "INCONCLUSIVE" and result.metrics.impact_ego_speed_kmh is None
    )


def test_example_suite_explicit_outcomes():
    outcomes = {}
    for path in sorted((ROOT / "scenarios").glob("*.json")):
        s = Scenario.model_validate_json(path.read_text())
        result = run_scenario(s)
        outcomes[s.id] = result.status
        assert result.metrics.max_energy_balance_error_j < 0.001
    assert outcomes["lead_braking_dry"] == "PASS"
    assert outcomes["acc_following"] == "PASS"
    assert outcomes["lead_braking_low_grip"] == "FAIL"
    assert len(outcomes) == 8


@pytest.mark.parametrize(
    "update",
    [
        {"id": "../escape"},
        {"extra": 1},
        {"controls": [{"time_s": 0.001, "controls": {}}]},
        {"controls": [{"time_s": 2, "controls": {}}, {"time_s": 1, "controls": {}}]},
        {"controls": [{"time_s": 1, "controls": {}}, {"time_s": 1, "controls": {}}]},
        {"config": {"duration_s": 1}, "controls": [{"time_s": 1, "controls": {}}]},
        {"config": {"mode": "cruise"}, "controls": [{"time_s": 0, "controls": {}}]},
        {"config": {"mode": "aeb", "duration_s": 1, "lead_brake_start_s": 3}},
    ],
)
def test_invalid_scenario(update):
    data = dict(id="test", description="Invalid configuration", config={})
    data.update(update)
    with pytest.raises(ValidationError):
        Scenario.model_validate(data)


def test_cli_reports_reject_overwrite_and_escape_html(tmp_path):
    source = tmp_path / "case.json"
    item = dict(
        id="html-test",
        description="<script>alert(1)</script>",
        config=dict(mode="cruise", duration_s=1),
        criteria=[
            dict(
                id="TRACK",
                description="Tight target",
                metric="final_speed_error_kmh",
                operator="<=",
                threshold=0.01,
                rationale="Deliberate failure checks CLI exit status",
            )
        ],
    )
    source.write_text(json.dumps(item))
    output = tmp_path / "output"
    assert main(["run", str(source), "--output", str(output)]) == 1
    report = (output / "report.html").read_text()
    assert "<script>alert(1)</script>" not in report
    assert "&lt;script&gt;" in report and "data:image/png;base64," in report
    summary = json.loads((output / "summary.json").read_text())
    assert summary["status"] == "FAIL" and summary["physics_status"] == "PASS"
    assert (output / "html-test/input.json").read_text() == source.read_text()
    result = json.loads((output / "html-test/result.json").read_text())
    assert result["requirements"][0]["status"] == "FAIL"
    saved = (output / "summary.json").read_bytes()
    assert main(["run", str(source), "--output", str(output)]) == 2
    assert (output / "summary.json").read_bytes() == saved
    assert (
        main(["run", str(source), str(source), "--output", str(tmp_path / "duplicate")])
        == 2
    )
    assert not (tmp_path / "duplicate").exists()
    assert (
        main(["run", str(tmp_path / "missing.json"), "--output", str(tmp_path / "bad")])
        == 2
    )


def test_physics_cli_success_and_inconclusive_exit(tmp_path):
    assert main(["physics", "--output", str(tmp_path / "physics")]) == 0
    source = tmp_path / "no-criteria.json"
    source.write_text(scenario(mode="coast", duration_s=1).model_dump_json())
    assert (
        main(["run", str(source), "--output", str(tmp_path / "empty-requirements")])
        == 1
    )
    summary = json.loads((tmp_path / "empty-requirements/summary.json").read_text())
    assert summary["status"] == "INCONCLUSIVE"
