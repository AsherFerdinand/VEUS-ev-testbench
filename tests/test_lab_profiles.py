"""Independent input provenance, unit conversion and missing-coverage checks."""

import base64
import hashlib
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from veus.lab.profiles import (
    ImportConfig,
    builtin_profile,
    builtin_route,
    parse_profile,
    parse_route,
    profile_distance,
    route_profile,
    router,
    sample_profile,
    sample_route,
)


def test_pinned_cycles_preserve_source_samples_and_distances():
    for name, count, duration, distance in [
        ("udds", 1370, 1369, 11990.433188725),
        ("hwfet", 766, 765, 16506.817470511),
    ]:
        p = builtin_profile(name)
        assert len(p.time_s) == count and p.time_s[-1] == duration
        assert profile_distance(p) == pytest.approx(distance, abs=1e-6)
        assert p.source.kind == "sourced" and p.source.upstream_commit
        assert p.source.licence.startswith("Apache-2.0")
    assert builtin_profile("urban").source.kind == "illustrative"


def test_explicit_units_hash_origin_and_linear_interpolation():
    raw = b"t,v,g\n1000,0,0\n2000,36,0.02\n"
    p = parse_profile(
        raw,
        ImportConfig(
            columns={"time": "t", "speed": "v", "grade": "g"},
            time_unit="ms",
            speed_unit="km/h",
            grade_unit="fraction",
        ),
    )
    assert p.source.sha256 == hashlib.sha256(raw).hexdigest()
    assert p.source.original_origin == 1
    assert p.time_s == [0, 1] and p.speed_ms == [0, 10]
    assert sample_profile(p, 0.5) == {
        "target_speed_ms": 5,
        "target_acceleration_ms2": 10,
        "grade_percent": 1,
    }
    assert profile_distance(p) == 5


@pytest.mark.parametrize(
    "rows", ["0,0\n0,1", "0,0\n-1,1", "0,0\n1,", "0,0\n1,nan", "0,0\n1,101"]
)
def test_bad_speed_samples_rejected(rows):
    with pytest.raises(ValueError):
        parse_profile(
            ("t,v\n" + rows + "\n").encode(),
            ImportConfig(columns={"time": "t", "speed": "v"}),
        )


def test_time_gaps_not_bridged_and_missing_grade_stays_missing():
    p = parse_profile(
        b"t,v\n0,1\n10,2\n", ImportConfig(columns={"time": "t", "speed": "v"})
    )
    assert profile_distance(p) is None
    with pytest.raises(ValueError, match="gap"):
        sample_profile(p, 5)
    p = parse_profile(
        b"t,v\n0,1\n1,2\n", ImportConfig(columns={"time": "t", "speed": "v"})
    )
    assert sample_profile(p, 0.5)["grade_percent"] is None
    with pytest.raises(ValueError, match="coverage"):
        sample_profile(p, 2)


def test_route_missing_geography_coverage_and_grade_from_elevation():
    r = parse_route(
        b"d,z\n1,10\n1.1,12\n",
        ImportConfig(columns={"distance": "d", "elevation": "z"}, distance_unit="km"),
    )
    s = sample_route(r, 50)
    assert s["latitude"] is None and s["longitude"] is None
    assert s["grade_percent"] == pytest.approx(2) and s["elevation_m"] == 11
    assert not sample_route(r, 101)["covered"]
    assert builtin_route("synthetic-local-loop").source.kind == "illustrative"
    with pytest.raises(ValueError, match="timed"):
        route_profile(r)


def test_coordinate_distance_requires_explicit_derived_policy():
    raw = b"lat,lon,t,v\n0,0,0,10\n0,0.001,1,10\n"
    cfg = ImportConfig(
        columns={"latitude": "lat", "longitude": "lon", "time": "t", "speed": "v"}
    )
    with pytest.raises(ValueError, match="mapping"):
        parse_route(raw, cfg)
    r = parse_route(raw, cfg.model_copy(update={"distance_policy": "haversine_chords"}))
    assert r.s_m[-1] == pytest.approx(111.1949266, abs=1e-6)
    assert route_profile(r).speed_ms == [10, 10]
    assert any("chord" in n for n in r.source.notes)


def test_inconsistent_grade_is_diagnosed_and_not_silently_changed():
    r = parse_route(
        b"d,z,g\n0,0,9\n100,1,9\n",
        ImportConfig(columns={"distance": "d", "elevation": "z", "grade": "g"}),
    )
    assert r.diagnostics and sample_route(r, 50)["grade_percent"] == 9


def test_bounded_import_api_and_invalid_base64():
    app = FastAPI()
    app.include_router(router)
    c = TestClient(app)
    assert len(c.get("/api/lab/catalogue").json()["profiles"]) == 6
    assert c.get("/api/lab/profiles/unknown").status_code == 404
    assert (
        c.post(
            "/api/lab/import/profile", json={"csv_base64": "!!!", "configuration": {}}
        ).status_code
        == 422
    )
    body = {
        "csv_base64": base64.b64encode(b"t,v\n0,0\n1,1\n").decode(),
        "configuration": {"columns": {"time": "t", "speed": "v"}},
    }
    assert c.post("/api/lab/import/profile", json=body).status_code == 200
    assert (
        c.post("/api/lab/import/profile", content=b"x" * 3_000_001).status_code == 413
    )
