"""Readiness policy tests use labelled numerical fixtures, not validation evidence."""

import base64
import hashlib
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from veus.readiness.analysis import ReadinessConfig, inspect, assess
from veus.readiness.registry import registry, CAPABILITIES
from veus.replay.analysis import canonical
from veus.studio.main import app

ROOT = Path(__file__).resolve().parents[1]


def fixture(text="time_s,speed_kmh\n0,0\n1,3.6\n2,7.2\n", columns=None, **updates):
    raw = text.encode()
    cfg = dict(
        source=dict(
            dataset="Explicit synthetic readiness fixture",
            source_url="synthetic://unit-test",
            licence="Test fixture",
            kind="synthetic",
            role="exploration",
            run_id="test-only",
            expected_sha256=hashlib.sha256(raw).hexdigest(),
            provenance_evidence="Synthetic numbers for software readiness tests, not measured data.",
        ),
        preprocessing=dict(
            columns=columns
            or {
                "time_s": {"column": "time_s", "unit": "s"},
                "vehicle_speed_ms": {"column": "speed_kmh", "unit": "km/h"},
            },
            max_gap_s=2,
        ),
        **updates,
    )
    return raw, ReadinessConfig.model_validate(cfg)


def statuses(result):
    return {c["id"]: c["status"] for c in result["capabilities"]}


def test_registry_is_the_api_and_evaluation_contract():
    ids = [c.id for c in CAPABILITIES]
    assert len(ids) == len(set(ids)) == 9
    with TestClient(app) as client:
        assert client.get("/api/readiness/capabilities").json() == json.loads(
            json.dumps(registry())
        )
    for cap in registry():
        assert (
            cap["required_signals"]
            and cap["quality_conditions"]
            and cap["availability_explanation"]
        )
    raw, cfg = fixture()
    r = assess(raw, cfg)
    for cap in r["capabilities"]:
        assert cap["requirements"] == next(
            c for c in registry() if c["id"] == cap["id"]
        )
        assert cap["explanation"]


def test_aliases_are_proposals_without_inferred_units_or_polarity():
    raw = b"timestamp,speed,pack_voltage,pack_current,soc,motor_rpm,throttle,brake,grade\n0,0,400,1,80,100,20,0,0\n1,1,400,1,80,100,20,0,0\n"
    r = inspect(raw)
    by = {s["signal"]: s for s in r["suggestions"]}
    assert by["time_s"]["candidates"] == ["timestamp"]
    assert by["vehicle_speed_ms"]["candidates"] == ["speed"]
    assert by["motor_speed_rad_s"]["candidates"] == ["motor_rpm"]
    assert "unit" not in by["vehicle_speed_ms"]
    assert {u["column"] for u in r["unsupported"]} == {"throttle", "brake"}
    assert r["record_count"] == 2 and len(r["preview"]) == 2
    assert r["raw_sha256"] == hashlib.sha256(raw).hexdigest()


def test_minimum_replay_is_available_with_explicit_units():
    raw, cfg = fixture()
    r = assess(raw, cfg)
    s = statuses(r)
    assert s["recorded_replay"] == s["speed_acceleration"] == "AVAILABLE"
    assert s["signed_power"] == s["energy_consumption"] == "UNAVAILABLE"
    assert r["recording_duration_s"] == 2 and r["duplicate_timestamps"] == 0
    assert r["signal_quality"]["vehicle_speed_ms"]["unit"] == "m/s"
    assert r["replay_configuration"]["source"]["kind"] == "synthetic"
    assert (
        r["replay_configuration"]["preprocessing"]["columns"]["vehicle_speed_ms"][
            "unit"
        ]
        == "km/h"
    )


def test_genuine_ved_has_conditional_energy_and_no_physical_validation_claim():
    replay = json.loads((ROOT / "examples/replay/ved-10-1561.json").read_text())
    cfg = ReadinessConfig.model_validate(
        {k: v for k, v in replay.items() if k != "schema_version"}
    )
    raw = (ROOT / "datasets/ved/ved-10-1561.csv").read_bytes()
    r = assess(raw, cfg)
    s = statuses(r)
    assert s["recorded_replay"] == s["signed_power"] == "AVAILABLE"
    assert s["energy_consumption"] == "CONDITIONAL"
    assert (
        s["regenerative_energy"]
        == s["motor_efficiency"]
        == s["longitudinal_validation"]
        == "UNAVAILABLE"
    )
    assert r["metadata"]["source"]["kind"] == "measured"
    assert r["metadata"]["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert "INCONCLUSIVE" in r["physical_validation"]
    assert r["replay_configuration"]["provenance"] == cfg.provenance


def electrical(**updates):
    return fixture(
        "t,V,I\n0,400,1\n1,400,2\n2,400,3\n",
        {
            "time_s": {"column": "t", "unit": "s"},
            "battery_voltage_v": {"column": "V", "unit": "V"},
            "battery_current_a": {"column": "I", "unit": "A"},
        },
        **updates,
    )


def test_electrical_inspection_does_not_require_speed():
    raw, cfg = electrical()
    r = assess(raw, cfg)
    s = statuses(r)
    assert s["recorded_replay"] == "UNAVAILABLE" and r["replay_configuration"] is None
    assert (
        s["voltage_inspection"]
        == s["current_inspection"]
        == s["signed_power"]
        == "AVAILABLE"
    )
    assert s["energy_consumption"] == "CONDITIONAL"


def test_energy_needs_evidence_not_column_presence():
    raw, cfg = electrical(
        current_sign="discharge_positive",
        sign_evidence="Synthetic fixture convention explicitly defined",
    )
    assert statuses(assess(raw, cfg))["energy_consumption"] == "CONDITIONAL"
    cfg = ReadinessConfig.model_validate(
        cfg.model_dump()
        | {
            "assertions": {
                "synchronization_confirmed": True,
                "measurement_quality_documented": True,
                "evidence_notes": "Known independent test fixture; not actual instrument evidence.",
            }
        }
    )
    r = assess(raw, cfg)
    assert statuses(r)["energy_consumption"] == "AVAILABLE"
    assert statuses(r)["regenerative_energy"] == "UNAVAILABLE"
    with pytest.raises(ValueError, match="evidence"):
        ReadinessConfig.model_validate(cfg.model_dump() | {"sign_evidence": None})
    with pytest.raises(ValueError, match="evidence"):
        ReadinessConfig.model_validate(
            cfg.model_dump() | {"assertions": {"synchronization_confirmed": True}}
        )


@pytest.mark.parametrize(
    "text",
    [
        "time_s,speed_kmh\n0,0\n0,1\n",
        "time_s,speed_kmh\n1,0\n0,1\n",
        "time_s,speed_kmh\nNaN,0\n1,1\n",
        "time_s,speed_kmh\n0,0\n1,inf\n",
    ],
)
def test_invalid_timestamps_or_values_rejected_not_repaired(text):
    raw, cfg = fixture(text)
    with pytest.raises(ValueError):
        assess(raw, cfg)


def test_invalid_units_missing_headers_and_hashes_remain_errors():
    raw, cfg = fixture()
    bad = cfg.model_dump()
    bad["preprocessing"]["columns"]["vehicle_speed_ms"]["unit"] = "knots"
    with pytest.raises(ValueError, match="unit"):
        assess(raw, ReadinessConfig.model_validate(bad))
    bad = cfg.model_dump()
    bad["preprocessing"]["columns"]["vehicle_speed_ms"]["column"] = "absent"
    with pytest.raises(ValueError, match="column"):
        assess(raw, ReadinessConfig.model_validate(bad))
    with pytest.raises(ValueError, match="SHA"):
        assess(raw + b"\n", cfg)


def test_partial_missing_and_gap_quality_affect_the_actual_capabilities():
    raw, cfg = fixture("time_s,speed_kmh\n0,0\n1,3.6\n9,7.2\n10,\n")
    r = assess(raw, cfg)
    s = statuses(r)
    assert s["recorded_replay"] == "CONDITIONAL"
    assert r["signal_quality"]["vehicle_speed_ms"]["missing_samples"] == 1
    assert len(r["metadata"]["gaps"]) == 1
    raw, cfg = fixture("time_s,speed_kmh\n0,\n1,\n")
    assert statuses(assess(raw, cfg))["recorded_replay"] == "UNAVAILABLE"
    raw, cfg = electrical()
    raw = raw.replace(b"1,400,2", b"1,,2")
    cfg = ReadinessConfig.model_validate(
        cfg.model_dump()
        | {
            "source": cfg.source.model_dump()
            | {"expected_sha256": hashlib.sha256(raw).hexdigest()}
        }
    )
    s = statuses(assess(raw, cfg))
    assert (
        s["signed_power"] == "CONDITIONAL" and s["energy_consumption"] == "UNAVAILABLE"
    )


def test_manual_mapping_is_validated_and_a_column_cannot_stand_for_two_signals():
    raw, cfg = fixture(
        "clock,velocity\n1000,0\n2000,10\n",
        {
            "time_s": {"column": "clock", "unit": "ms"},
            "vehicle_speed_ms": {"column": "velocity", "unit": "mph"},
        },
    )
    r = assess(raw, cfg)
    assert r["recording_duration_s"] == 1
    assert statuses(r)["recorded_replay"] == "AVAILABLE"
    bad = cfg.model_dump()
    bad["preprocessing"]["columns"]["motor_torque_nm"] = {
        "column": "velocity",
        "unit": "Nm",
    }
    with pytest.raises(ValueError, match="one signal"):
        ReadinessConfig.model_validate(bad)


def test_validation_needs_a_matching_explicit_experiment_and_asserted_evidence():
    raw, cfg = fixture(
        "t,v,T,B,G\n0,0,0,0,0\n1,1,0,0,0\n2,2,0,0,0\n",
        {
            "time_s": {"column": "t", "unit": "s"},
            "vehicle_speed_ms": {"column": "v", "unit": "m/s"},
            "motor_torque_nm": {"column": "T", "unit": "Nm"},
            "brake_force_n": {"column": "B", "unit": "N"},
            "road_gradient_rad": {"column": "G", "unit": "rad"},
        },
    )
    assert statuses(assess(raw, cfg))["longitudinal_validation"] == "UNAVAILABLE"
    # Emulate a provider's assertions only. These synthetic numbers are not evidence.
    body = cfg.model_dump()
    body["source"] |= {
        "kind": "measured",
        "vehicle_id": "TEST-ASSERTION",
        "vehicle_specifications": {
            "note": "Synthetic policy-test fixture; not a measured vehicle"
        },
        "inputs_verified": True,
    }
    body["assertions"] = {
        "synchronization_confirmed": True,
        "measurement_quality_documented": True,
        "operating_conditions_documented": True,
        "torque_sign_confirmed": True,
        "evidence_notes": "Emulated evidence assertion for unit testing only.",
    }
    assert (
        statuses(assess(raw, ReadinessConfig.model_validate(body)))[
            "longitudinal_validation"
        ]
        == "CONDITIONAL"
    )
    body["experiment"] = {
        "id": "test-policy",
        "objective": "Synthetic policy guard test, not an executed physical comparison",
        "source": body["source"] | {"role": "validation"},
        "preprocessing": body["preprocessing"],
        "kind": "dynamics",
        "assumptions": ["Synthetic unit test of readiness policy, not real evidence."],
        "comparisons": [
            {
                "signal": "vehicle_speed_ms",
                "threshold": 1,
                "rationale": "Unit test only",
            }
        ],
    }
    r = assess(raw, ReadinessConfig.model_validate(body))
    assert statuses(r)["longitudinal_validation"] == "AVAILABLE"
    assert "not a validation PASS" in r["physical_validation"]
    body["experiment"]["comparisons"] = [
        {
            "signal": "position_m",
            "threshold": 1,
            "rationale": "Missing reference must not unlock readiness",
        }
    ]
    assert (
        statuses(assess(raw, ReadinessConfig.model_validate(body)))[
            "longitudinal_validation"
        ]
        == "UNAVAILABLE"
    )
    body["experiment"]["comparisons"] = [
        {"signal": "vehicle_speed_ms", "threshold": 1, "rationale": "Unit test only"}
    ]
    body["experiment"]["source"]["expected_sha256"] = "0" * 64
    assert (
        statuses(assess(raw, ReadinessConfig.model_validate(body)))[
            "longitudinal_validation"
        ]
        == "CONDITIONAL"
    )


def test_unsupported_efficiency_is_not_unlocked_by_related_columns():
    raw, cfg = fixture(
        "t,v,T,w,V,I\n0,0,10,100,400,1\n1,1,10,100,400,1\n",
        {
            "time_s": {"column": "t", "unit": "s"},
            "vehicle_speed_ms": {"column": "v", "unit": "m/s"},
            "motor_torque_nm": {"column": "T", "unit": "Nm"},
            "motor_speed_rad_s": {"column": "w", "unit": "rad/s"},
            "battery_voltage_v": {"column": "V", "unit": "V"},
            "battery_current_a": {"column": "I", "unit": "A"},
        },
    )
    r = assess(raw, cfg)
    motor = next(c for c in r["capabilities"] if c["id"] == "motor_efficiency")
    assert not motor["missing_signals"] and motor["status"] == "UNAVAILABLE"
    assert "Not implemented" in motor["explanation"]


def test_api_explicit_confirmation_downloads_and_reproducible_assessment():
    raw, cfg = fixture()
    payload = {
        "configuration": cfg.model_dump(mode="json"),
        "csv_base64": base64.b64encode(raw).decode(),
    }
    with TestClient(app) as client:
        assert client.post("/api/readiness/assess", json=payload).status_code == 422
        payload["mappings_confirmed"] = True
        a = client.post("/api/readiness/assess", json=payload).json()
        b = client.post("/api/readiness/assess", json=payload).json()
        assert a == b
        assert (
            a["assessment_sha256"]
            == hashlib.sha256(
                canonical({k: v for k, v in a.items() if k != "assessment_sha256"})
            ).hexdigest()
        )
        assert (
            client.post(
                "/api/readiness/inspect", json={"csv_base64": payload["csv_base64"]}
            ).status_code
            == 200
        )
        assert (
            client.post("/api/readiness/inspect", content=b"x" * 3_000_001).status_code
            == 413
        )
        for name in ["basic-replay", "electrical-analysis", "engineering-example"]:
            assert (
                client.get("/api/readiness/templates/" + name + "/csv").status_code
                == 200
            )
            assert (
                client.get("/api/readiness/templates/" + name + "/config").status_code
                == 200
            )
        assert client.get("/api/readiness/templates/nope/csv").status_code == 404
