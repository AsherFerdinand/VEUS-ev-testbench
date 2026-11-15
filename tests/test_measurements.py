import hashlib
import math
import pytest
from veus.validation.measurements import (
    DataSource,
    ImportConfig,
    load_csv,
    interpolate,
    derive_acceleration,
)


def load(text, columns=None, **kw):
    raw = text.encode()
    source = DataSource(
        dataset="Test synthetic",
        source_url="fixture",
        licence="test",
        kind="synthetic",
        run_id="test",
        role="exploration",
        expected_sha256=hashlib.sha256(raw).hexdigest(),
        provenance_evidence="test fixture",
    )
    config = ImportConfig(
        columns=columns
        or {
            "time_s": {"column": "t", "unit": "s"},
            "vehicle_speed_ms": {"column": "v", "unit": "m/s"},
        },
        **kw,
    )
    return load_csv(raw, source, config)


def test_si_conversion_sign_origin_and_provenance():
    text = "t,v,i,soc,grade,rpm\n1000,36,-10,80,10,60\n2000,72,-20,79,-10,120\n"
    columns = {
        k: dict(column=c, unit=u, sign=s)
        for k, c, u, s in [
            ("time_s", "t", "ms", 1),
            ("vehicle_speed_ms", "v", "km/h", 1),
            ("battery_current_a", "i", "A", -1),
            ("battery_soc", "soc", "%", 1),
            ("road_gradient_rad", "grade", "%", 1),
            ("motor_speed_rad_s", "rpm", "rpm", 1),
        ]
    }
    d = load(text, columns)
    assert d.times == [0, 1]
    assert d.signals["vehicle_speed_ms"] == [10, 20]
    assert d.signals["battery_current_a"] == [10, 20]
    assert d.signals["battery_soc"] == [0.8, 0.79]
    assert d.signals["road_gradient_rad"][0] == pytest.approx(math.atan(0.1))
    assert d.signals["motor_speed_rad_s"][0] == pytest.approx(2 * math.pi)
    assert d.metadata["time_origin_s"] == 1
    assert d.metadata["raw_sha256"] == hashlib.sha256(text.encode()).hexdigest()


@pytest.mark.parametrize(
    "text",
    [
        "t,v\n0,1\n0,2\n",
        "t,v\n1,1\n0,2\n",
        "t,v\nNaN,1\n1,2\n",
        "t,v\n0,inf\n1,2\n",
        "t,t\n0,1\n1,2\n",
        "t,v\n0,-1\n1,2\n",
        "t,v\n0,1,2\n1,2\n",
        "t,v\n0,1\n",
    ],
)
def test_invalid_data(text):
    with pytest.raises(ValueError):
        load(text)


def test_missing_gaps_and_alignment_never_invent_samples():
    d = load("t,v\n0,0\n1,\n2,4\n10,20\n", max_gap_s=2)
    assert d.metadata["missing_counts"]["vehicle_speed_ms"] == 1
    assert d.metadata["gaps"] == [{"start_s": 2.0, "end_s": 10.0}]
    assert d.at("vehicle_speed_ms", 1) is None
    assert d.at("vehicle_speed_ms", 1.5) is None
    assert d.at("vehicle_speed_ms", 5) is None
    assert d.at("vehicle_speed_ms", -1) is None
    assert d.at("vehicle_speed_ms", 11) is None
    assert all(x is None for x in derive_acceleration(d))
    assert interpolate([0, 1], [0, 2], 0.5, 2) == 1
    assert interpolate([0, 1], [0, 2], 0.5, 2, "previous") == 0
    assert interpolate([0, 1], [0, 2], 0.5, 2, "none") is None


def test_derivative_is_explicit_output_reference():
    d = load("t,v\n0,0\n1,2\n2,4\n")
    assert derive_acceleration(d) == [2, 2, 2]


def test_hash_and_units_are_mandatory():
    with pytest.raises(ValueError):
        load(
            "t,v\n0,1\n1,2\n",
            {
                "time_s": {"column": "t", "unit": "s"},
                "vehicle_speed_ms": {"column": "v", "unit": "unknown"},
            },
        )
    raw = b"t,v\n0,1\n1,2\n"
    source = DataSource(
        dataset="fixture",
        source_url="fixture",
        licence="fixture",
        kind="synthetic",
        run_id="a",
        role="calibration",
        expected_sha256="0" * 64,
        provenance_evidence="test",
    )
    with pytest.raises(ValueError, match="SHA-256"):
        load_csv(
            raw, source, ImportConfig(columns={"time_s": {"column": "t", "unit": "s"}})
        )
