"""Descriptive investigation tests; synthetic fixtures never prove physical validity."""

import base64, csv, hashlib, io, json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from veus.studio.main import app
from veus.investigation.catalogue import catalogue, payload, load
from veus.investigation.analysis import InvestigationInput, investigate, case_study
from veus.investigation.report import measurement_csv, save
from veus.replay.analysis import ReplayConfig, canonical, analyse
from veus.readiness.analysis import ReadinessConfig

ROOT = Path(__file__).resolve().parents[1]


def fixture(speed_only=False, known=False):
    raw = (
        b"t,v\n0,0\n1,2\n2,4\n3,2\n4,0\n5,0\n"
        if speed_only
        else b"t,v,V,I,S\n0,0,400,10,80\n1,2,400,20,79.9\n2,4,400,30,79.8\n3,2,400,-20,79.9\n4,0,400,-10,80\n5,0,400,0,80\n"
    )
    columns = {
        "time_s": {"column": "t", "unit": "s"},
        "vehicle_speed_ms": {"column": "v", "unit": "m/s"},
    }
    if not speed_only:
        columns |= {
            "battery_voltage_v": {"column": "V", "unit": "V"},
            "battery_current_a": {"column": "I", "unit": "A"},
            "battery_soc": {"column": "S", "unit": "%"},
        }
    cfg = ReplayConfig.model_validate(
        dict(
            source=dict(
                dataset="Synthetic arithmetic investigation fixture",
                source_url="synthetic://unit-test",
                licence="Test fixture",
                kind="synthetic",
                role="exploration",
                run_id="fixture",
                expected_sha256=hashlib.sha256(raw).hexdigest(),
                provenance_evidence="Explicit synthetic software fixture; not measurements.",
            ),
            preprocessing=dict(columns=columns),
            current_sign="discharge_positive" if known else "unknown",
            sign_evidence="Known synthetic sign convention for arithmetic test only"
            if known
            else None,
            thresholds={"minimum_duration_s": 0, "acceleration_ms2": 1},
            limitations=["Synthetic test, not physical validation."],
        )
    )
    return InvestigationInput(
        configuration=cfg,
        csv_base64=base64.b64encode(raw).decode(),
        mappings_confirmed=True,
    )


def test_catalogue_real_metadata_hashes_and_old_prefix_are_preserved():
    entries = catalogue()
    assert len(entries) == 4
    for entry in entries:
        cfg, raw, data = load(entry["id"])
        assert entry["kind"] == "measured" and "Apache" in entry["licence"]
        assert (
            entry["source_sha256"]
            == hashlib.sha256(raw).hexdigest()
            == cfg.source.expected_sha256
        )
        assert entry["sample_count"] == len(data.times)
        assert entry["duration_s"] == data.times[-1]
        assert {
            "time_s",
            "vehicle_speed_ms",
            "battery_voltage_v",
            "battery_current_a",
            "battery_soc",
        } <= entry["signals"].keys()
        assert len(raw) < 2_000_000 and len(data.times) < 5000
    manifest = json.loads(
        (ROOT / "datasets/ved/full-recordings-provenance.json").read_text()
    )
    for name in ["ved-10-1561-full", "ved-10-1567-full"]:
        entry = next(e for e in entries if e["id"] == name)
        info = manifest["recordings"][name]
        assert (
            entry["duration_s"] > 300
            and info["source_line_range"][1] - info["source_line_range"][0] + 1
            == info["rows"]
        )
        assert entry["source_sha256"] == info["subset_sha256"]
    short = list(
        csv.reader(io.StringIO((ROOT / "datasets/ved/ved-10-1561.csv").read_text()))
    )
    full = list(
        csv.reader(
            io.StringIO((ROOT / "datasets/ved/ved-10-1561-full.csv").read_text())
        )
    )
    assert short == full[: len(short)]


def test_full_trip_keeps_unknown_travel_and_sign_not_fabricated_totals():
    p = payload("ved-10-1561-full")
    r = investigate(
        InvestigationInput(
            **{k: p[k] for k in ["configuration", "csv_base64"]},
            mappings_confirmed=True,
        )
    )
    assert len(r["analysis"]["time_s"]) == 534
    assert r["metrics"]["recording_duration_s"]["value"] == pytest.approx(460.4)
    assert r["metrics"]["known_segment_distance_m"]["value"] == pytest.approx(
        2371.5910598238
    )
    assert r["metrics"]["speed_interval_coverage"]["value"] == pytest.approx(
        342.5 / 460.4
    )
    assert (
        r["metrics"]["distance_m"]["value"] is None
        and r["metrics"]["average_speed_ms"]["value"] is None
    )
    assert r["analysis"]["measured"]["battery_current_a"][0] == -22.5
    assert r["metrics"]["electrical_energy_used_wh"]["value"] is None
    assert len(r["analysis"]["metadata"]["gaps"]) == 23


def test_event_detector_is_reused_and_insights_trace_exact_samples():
    item = fixture()
    r = investigate(item)
    original = analyse(base64.b64decode(item.csv_base64), item.configuration)
    assert [
        {k: v for k, v in e.items() if k != "event_index"} for e in r["events"]
    ] == original["events"]
    for insight in r["insights"]:
        assert insight["rule"] == original["events"][insight["event_index"]]["rule"]
        for evidence in insight["evidence"]:
            values = original["measured"].get(
                evidence["signal"],
                original["derived"].get(evidence["signal"], original["time_s"]),
            )
            for i in evidence["sample_indices"]:
                assert (
                    insight["start_s"] - 1e-8
                    <= original["time_s"][i]
                    <= insight["end_s"] + 1e-8
                )
            if evidence["first"]:
                assert evidence["first"]["value"] == values[evidence["first"]["index"]]
        assert "not a statistical confidence" in insight["confidence"]
        assert any("polarity" in text for text in insight["limitations"])
    assert "accompanied by" not in json.dumps(r)  # no unconditional association claim


def test_selected_events_validate_and_missing_signals_do_not_make_zero_metrics():
    item = fixture(speed_only=True)
    r = investigate(item)
    assert r["metrics"]["high_power_event_count"]["value"] is None
    assert r["metrics"]["voltage_minimum"]["value"] is None
    assert r["metrics"]["soc_change_pp"]["value"] is None
    assert "electrical_power_w" not in r["analysis"]["derived"]
    selected = r["events"][0]["event_index"]
    one = investigate(item.model_copy(update={"selected_events": [selected]}))
    assert len(one["insights"]) == 1 and one["insights"][0]["event_index"] == selected
    with pytest.raises(ValueError):
        investigate(item.model_copy(update={"selected_events": [99999]}))
    with pytest.raises(ValueError):
        investigate(item.model_copy(update={"selected_events": [selected, selected]}))


def test_energy_is_gated_by_readiness_not_only_the_legacy_known_sign_flag():
    item = fixture(known=True)
    raw = base64.b64decode(item.csv_base64)
    assert analyse(raw, item.configuration)["quality"]["energy_integration_available"]
    r = investigate(item)
    assert not r["analysis"]["quality"]["energy_integration_available"]
    assert r["metrics"]["electrical_energy_used_wh"]["value"] is None
    assert "electrical_energy_used_wh" not in r["analysis"]["derived"]
    assert not any(e["type"] == "possible_regenerative_braking" for e in r["events"])
    cfg = item.configuration.model_dump(mode="json")
    cfg.pop("schema_version")
    cfg.pop("thresholds")
    cfg["assertions"] = {
        "synchronization_confirmed": True,
        "measurement_quality_documented": True,
        "evidence_notes": "Known synthetic fixture; emulated policy assertions, not instrument evidence.",
    }
    ready = ReadinessConfig.model_validate(cfg)
    r = investigate(item.model_copy(update={"readiness_configuration": ready}))
    assert r["analysis"]["investigation_energy_gate"]["available"]
    assert r["metrics"]["electrical_energy_used_wh"]["value"] > 0
    assert r["analysis"]["summary"]["regenerative_energy_wh"]["value"] is None
    assert "derived__electrical_energy_used_wh" not in measurement_csv(
        case_study(investigate(item))
    )


def test_readiness_must_describe_the_same_input_and_be_confirmed():
    item = fixture()
    with pytest.raises(ValueError, match="Confirm"):
        investigate(item.model_copy(update={"mappings_confirmed": False}))
    cfg = item.configuration.model_dump(mode="json")
    cfg.pop("schema_version")
    cfg.pop("thresholds")
    cfg["source"]["run_id"] = "other"
    with pytest.raises(ValueError, match="identical"):
        investigate(
            item.model_copy(
                update={"readiness_configuration": ReadinessConfig.model_validate(cfg)}
            )
        )


def test_missing_measurements_and_gaps_produce_availability_insights():
    item = fixture()
    raw = (
        base64.b64decode(item.csv_base64)
        .replace(b"2,4,400,30,79.8", b"9,4,400,30,79.8")
        .replace(b"3,2,400,-20,79.9", b"10,2,,20,79.9")
        .replace(b"4,0,400,-10,80", b"11,0,400,-10,80")
        .replace(b"5,0,400,0,80", b"12,0,400,0,80")
    )
    cfg = item.configuration.model_dump(mode="json")
    cfg["source"]["expected_sha256"] = hashlib.sha256(raw).hexdigest()
    item = InvestigationInput(
        configuration=cfg,
        csv_base64=base64.b64encode(raw).decode(),
        mappings_confirmed=True,
    )
    r = investigate(item)
    gap = next(e["event_index"] for e in r["events"] if e["type"] == "timestamp_gap")
    r = investigate(item.model_copy(update={"selected_events": [gap]}))
    assert (
        "unknown" in r["insights"][0]["interpretation"]
        and not r["insights"][0]["observations"]
    )
    assert r["metrics"]["distance_m"]["value"] is None
    assert r["analysis"]["measured"]["battery_voltage_v"][3] is None


def test_comparison_handles_duration_missing_metrics_and_overlap_without_rankings():
    a = investigate(fixture())
    b = investigate(fixture(speed_only=True))
    case = case_study(a, b, axis="normalized")
    power = next(
        r
        for r in case["comparison"]["metrics"]
        if r["metric"] == "peak_power_magnitude_w"
    )
    assert power["difference_second_minus_first"] is None
    assert "display transformation only" in case["comparison"]["axis_definition"]
    same = case_study(a, a)["comparison"]
    assert same["same_source_run"] and any("overlap" in s for s in same["limitations"])
    first = payload("ved-10-1561-full")
    second = payload("ved-10-1567-full")
    x = investigate(
        InvestigationInput(
            **{k: first[k] for k in ["configuration", "csv_base64"]},
            mappings_confirmed=True,
        )
    )
    y = investigate(
        InvestigationInput(
            **{k: second[k] for k in ["configuration", "csv_base64"]},
            mappings_confirmed=True,
        )
    )
    c = case_study(x, y)["comparison"]
    assert not c["same_source_run"]
    duration = next(r for r in c["metrics"] if r["metric"] == "recording_duration_s")
    assert duration["difference_second_minus_first"] == pytest.approx(-90.1)


def test_case_exports_are_deterministic_original_rows_and_scope_consistent(tmp_path):
    item = fixture()
    a = case_study(investigate(item))
    b = case_study(investigate(item))
    assert a == b
    assert (
        a["case_sha256"]
        == hashlib.sha256(
            canonical({k: v for k, v in a.items() if k != "case_sha256"})
        ).hexdigest()
    )
    rows = list(csv.DictReader(io.StringIO(measurement_csv(a))))
    assert len(rows) == 6 and [float(r["elapsed_time_s"]) for r in rows] == [
        0,
        1,
        2,
        3,
        4,
        5,
    ]
    assert float(rows[2]["measured__vehicle_speed_ms [m/s]"]) == 4
    assert not any("energy_used" in key for key in rows[0])
    save(tmp_path / "case", a, [item])
    assert (tmp_path / "case/original-1.csv").read_bytes() == base64.b64decode(
        item.csv_base64
    )
    assert (
        "No physical vehicle validation" in (tmp_path / "case/report.html").read_text()
    )
    with pytest.raises(ValueError):
        save(tmp_path / "case", a, [item])


def test_api_catalogue_legacy_compatibility_and_report_matching_hash():
    with TestClient(app) as client:
        assert len(client.get("/api/replay/datasets").json()) == 2
        assert len(client.get("/api/investigation/catalogue").json()) == 4
        assert client.get("/api/investigation/recordings/invalid").status_code == 404
        item = fixture(speed_only=True)
        body = {
            "first": item.model_dump(mode="json"),
            "title": "<script>safe title</script>",
        }
        response = client.post("/api/investigation/case-study", json=body)
        assert response.status_code == 200
        r = response.json()
        h = client.post(
            "/api/investigation/case-study", json=body | {"format": "html"}
        ).json()
        assert (
            h["case_sha256"] == r["case_sha256"]
            and "<script>safe title</script>" not in h["content"]
        )
        assert (
            client.post(
                "/api/investigation/case-study", content=b"x" * 6_000_001
            ).status_code
            == 413
        )
