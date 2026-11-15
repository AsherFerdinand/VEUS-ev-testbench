"""Independent analytical fixtures test replay analysis, not physical validation."""

import base64
import csv
import hashlib
import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from veus.replay.analysis import ReplayConfig, analyse, canonical, positive_integral
from veus.replay.report import save, event_csv
from veus.replay.__main__ import main
from veus.studio.main import app

ROOT = Path(__file__).resolve().parents[1]


def recording(rows, columns=None, **changes):
    columns = columns or {
        "time_s": {"column": "t", "unit": "s"},
        "vehicle_speed_ms": {"column": "v", "unit": "m/s"},
        "battery_voltage_v": {"column": "V", "unit": "V"},
        "battery_current_a": {"column": "I", "unit": "A"},
    }
    names = [v["column"] for v in columns.values()]
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(names)
    writer.writerows(rows)
    raw = out.getvalue().encode()
    config = ReplayConfig.model_validate(
        dict(
            source=dict(
                dataset="Analytical test fixture",
                source_url="synthetic://known-equations",
                licence="Test fixture",
                kind="synthetic",
                role="exploration",
                run_id="fixture",
                expected_sha256=hashlib.sha256(raw).hexdigest(),
                provenance_evidence="Explicitly synthetic independent arithmetic",
            ),
            preprocessing=dict(columns=columns, max_gap_s=2),
            limitations=["Synthetic fixture, not measured vehicle data."],
        )
        | changes
    )
    return raw, config


def test_real_ved_keeps_source_sign_and_provenance():
    cfg = ReplayConfig.model_validate_json(
        (ROOT / "examples/replay/ved-10-1561.json").read_text()
    )
    raw = (ROOT / "datasets/ved/ved-10-1561.csv").read_bytes()
    copy = bytes(raw)
    r = analyse(raw, cfg)
    assert len(r["time_s"]) == 111
    assert r["time_s"][-1] == pytest.approx(72.1)
    assert r["measured"]["battery_current_a"][0] == -22.5
    assert r["measured"]["ambient_temperature_c"][0] == 4.5
    assert r["derived"]["electrical_power_w"][0] == -8550
    assert r["quality"]["current_sign"] == "unknown"
    assert r["summary"]["electrical_energy_used_wh"]["value"] is None
    assert not any(e["type"] == "possible_regenerative_braking" for e in r["events"])
    assert not r["comparison"]["enabled"]
    assert set(r["comparison"]["missing_inputs"]) == {
        "motor_torque_nm",
        "brake_force_n",
        "road_gradient_rad",
    }
    assert "INCONCLUSIVE" in r["quality"]["physical_validation"]
    assert cfg.source.kind == "measured" and raw == copy
    assert r["summary"]["distance_m"]["value"] == pytest.approx(493.1573509971)


def test_unit_conversion_irregular_integration_and_derivative():
    columns = {
        "time_s": {"column": "t", "unit": "ms"},
        "vehicle_speed_ms": {"column": "v", "unit": "km/h"},
        "ambient_temperature_c": {"column": "T", "unit": "°C"},
    }
    raw, cfg = recording(
        [[10000, 0, 4], [10300, 2.16, 4], [11100, 7.92, 4], [12000, 14.4, 4]], columns
    )
    r = analyse(raw, cfg)
    assert r["time_s"] == pytest.approx([0, 0.3, 1.1, 2])
    assert r["metadata"]["time_origin_s"] == 10
    assert r["summary"]["distance_m"]["value"] == pytest.approx(4)
    assert r["summary"]["average_speed_ms"]["value"] == pytest.approx(2)
    assert r["derived"]["acceleration_ms2"] == pytest.approx([2] * 4)
    assert "electrical_power_w" not in r["derived"]
    assert r["summary"]["peak_signed_power_w"]["value"] is None


@pytest.mark.parametrize(
    "rows",
    [
        [[0, 1, 400, 1], [0, 2, 400, 1]],
        [[1, 1, 400, 1], [0, 2, 400, 1]],
        [["NaN", 1, 400, 1], [1, 2, 400, 1]],
        [[0, 1, 400, 1], ["inf", 2, 400, 1]],
    ],
)
def test_bad_timestamps_rejected_by_shared_importer(rows):
    raw, cfg = recording(rows)
    with pytest.raises(ValueError):
        analyse(raw, cfg)


@pytest.mark.parametrize(
    "column,value", [(1, -1), (1, 999), (2, 0), (2, 5000), (3, "inf"), (3, 100000)]
)
def test_invalid_and_nonphysical_measurements_rejected(column, value):
    rows = [[0, 0, 400, 1], [1, 1, 400, 1]]
    rows[1][column] = value
    raw, cfg = recording(rows)
    with pytest.raises(ValueError):
        analyse(raw, cfg)


def test_missing_and_gaps_never_become_zero_total_travel():
    raw, cfg = recording(
        [[0, 0, 400, 1], [1, 2, 400, 1], [3, "", 400, ""], [10, 6, 400, 1]],
        current_sign="discharge_positive",
        sign_evidence="Known synthetic discharge-positive fixture",
    )
    r = analyse(raw, cfg)
    assert r["summary"]["distance_m"]["value"] is None
    assert r["summary"]["average_speed_ms"]["value"] is None
    assert r["derived"]["known_segment_distance_m"] == [0, 1, 1, 1]
    assert r["valid_speed_intervals"] == [True, False, False]
    assert r["quality"]["speed_interval_coverage"] == pytest.approx(0.1)
    assert r["derived"]["electrical_power_w"][2] is None
    assert not r["quality"]["energy_integration_available"]
    assert {e["type"] for e in r["events"]} >= {"missing_measurements", "timestamp_gap"}
    assert all(v is None for v in r["derived"]["acceleration_ms2"][1:])


def test_power_and_energy_known_polarity_are_independent_arithmetic():
    raw, cfg = recording(
        [[0, 0, 400, -2], [0.3, 0.6, 400, -2], [1.1, 2.2, 400, -2], [2, 4, 400, -2]],
        current_sign="charge_positive",
        sign_evidence="Synthetic fixture uses negative current for discharge",
    )
    r = analyse(raw, cfg)
    assert r["derived"]["electrical_power_w"] == [-800] * 4
    assert r["summary"]["electrical_energy_used_wh"]["value"] == pytest.approx(
        800 * 2 / 3600
    )
    assert r["summary"]["electrical_energy_received_wh"]["value"] == 0
    assert r["summary"]["regenerative_energy_wh"]["value"] is None
    assert positive_integral(100, -100, 2) == 50
    assert positive_integral(-100, 100, 2) == 50
    assert positive_integral(0, 100, 2) == 100
    assert positive_integral(-100, 0, 2) == 0


def test_possible_regen_is_inferred_only_with_asserted_sign():
    rows = [[0, 4, 400, -5], [1, 2, 400, -5], [2, 0, 400, -5]]
    raw, cfg = recording(
        rows, thresholds={"minimum_duration_s": 0, "power_magnitude_w": 1000}
    )
    unknown = analyse(raw, cfg)
    assert not any(
        e["type"] == "possible_regenerative_braking" for e in unknown["events"]
    )
    known = analyse(
        raw,
        cfg.model_copy(
            update={
                "current_sign": "discharge_positive",
                "sign_evidence": "Known synthetic sign fixture",
            }
        ),
    )
    events = [
        e for e in known["events"] if e["type"] == "possible_regenerative_braking"
    ]
    assert events and events[0]["start_s"] == 0 and events[0]["end_s"] == 2
    assert "inferred" in events[0]["classification"]
    assert known["summary"]["electrical_energy_received_wh"]["value"] == pytest.approx(
        4000 / 3600
    )


def test_standstill_and_events_do_not_bridge_gaps():
    raw, cfg = recording(
        [[0, 0, 400, 0], [1, 0, 400, 0], [8, 0, 400, 0], [9, 0, 400, 0]]
    )
    r = analyse(raw, cfg)
    stops = [e for e in r["events"] if e["type"] == "standstill"]
    assert [(e["start_s"], e["end_s"]) for e in stops] == [(0, 1), (8, 9)]


def test_recorded_power_without_vi_is_available_but_not_energy():
    columns = {
        "time_s": {"column": "t", "unit": "s"},
        "vehicle_speed_ms": {"column": "v", "unit": "m/s"},
        "battery_power_w": {"column": "P", "unit": "kW"},
    }
    raw, cfg = recording([[0, 0, -60], [1, 1, -60]], columns)
    r = analyse(raw, cfg)
    assert r["summary"]["peak_signed_power_w"]["value"] == -60000
    assert any(e["type"] == "high_electrical_magnitude" for e in r["events"])
    assert not r["quality"]["energy_integration_available"]


def test_exports_are_deterministic_and_keep_original_bytes(tmp_path):
    raw, cfg = recording([[0, 0, 400, 1], [1, 2, 400, 1]])
    a, b = analyse(raw, cfg), analyse(raw, cfg)
    assert a == b
    assert (
        a["configuration_sha256"]
        == hashlib.sha256(canonical(a["configuration"])).hexdigest()
    )
    body = {k: v for k, v in a.items() if k != "analysis_sha256"}
    assert a["analysis_sha256"] == hashlib.sha256(canonical(body)).hexdigest()
    target = tmp_path / "report"
    save(target, a, raw)
    assert (target / "original.csv").read_bytes() == raw
    assert (target / "configuration.json").read_bytes() == canonical(a["configuration"])
    html = (target / "report.html").read_text()
    assert (
        "Synthetic software fixture" in html and "no physical validation claim" in html
    )
    assert (target / "events.csv").read_text() == event_csv(a)
    assert "source_time_s" in (target / "derived.csv").read_text()
    with pytest.raises(ValueError):
        save(target, b, raw)
    config = tmp_path / "input.json"
    config.write_text(cfg.model_dump_json())
    csvfile = tmp_path / "input.csv"
    csvfile.write_bytes(raw)
    assert main([str(config), str(csvfile), "--output", str(tmp_path / "cli")]) == 0
    assert main([str(config), str(csvfile), "--output", str(tmp_path / "cli")]) == 2


def test_api_provenance_hash_guard_and_session_separation():
    with TestClient(app) as client:
        assert len(client.get("/api/replay/datasets").json()) == 2
        assert client.get("/api/replay/datasets/other").status_code == 404
        example = client.get("/api/replay/datasets/ved-10-1561").json()
        payload = {k: example[k] for k in ["configuration", "csv_base64"]}
        response = client.post("/api/replay/analyse", json=payload)
        assert response.status_code == 200
        assert response.json() == example["analysis"]
        with client.websocket_connect("/ws/simulation") as ws:
            before = ws.receive_json()
            report = client.post("/api/replay/report", json=payload)
            assert report.status_code == 200
            assert (
                report.json()["analysis_sha256"]
                == example["analysis"]["analysis_sha256"]
            )
            ws.send_json({"action": "pause"})
            after = ws.receive_json()
            assert after["time_s"] == before["time_s"] == 0
            assert after["position_m"] == before["position_m"] == 0
            assert after["resolved_config"] == before["resolved_config"]
        payload["csv_base64"] = base64.b64encode(b"t,v\n0,0\n1,1\n").decode()
        assert client.post("/api/replay/analyse", json=payload).status_code == 422
        assert (
            client.post("/api/replay/analyse", content=b"x" * 3_000_001).status_code
            == 413
        )


def test_sign_claim_requires_evidence_and_import_limits():
    raw, cfg = recording([[0, 0, 400, 1], [1, 1, 400, 1]])
    with pytest.raises(ValueError):
        ReplayConfig.model_validate(
            cfg.model_dump() | {"current_sign": "discharge_positive"}
        )
    with pytest.raises(ValueError):
        analyse(b"x" * 2_000_001, cfg)
    rows = [[i, 0, 400, 1] for i in range(5001)]
    raw, cfg = recording(rows)
    with pytest.raises(ValueError, match="5000"):
        analyse(raw, cfg)


def test_hashes_survive_browser_integral_number_serialization():
    raw, cfg = recording(
        [[0, 0, 400, 1], [1, 2, 400, 1]], provenance={"start": 0.0, "end": 72100.0}
    )
    original = analyse(raw, cfg)
    browser_payload = cfg.model_dump(mode="json")
    browser_payload["provenance"] = {"start": 0, "end": 72100}
    browser = ReplayConfig.model_validate(browser_payload)
    roundtrip = analyse(raw, browser)
    assert roundtrip["analysis_sha256"] == original["analysis_sha256"]
    assert roundtrip["configuration_sha256"] == original["configuration_sha256"]
