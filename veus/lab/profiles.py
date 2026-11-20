"""Bounded profiles/routes, explicit units, gap policy and unchanged-source provenance."""

import base64
import bisect
import csv
import hashlib
import io
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from pydantic import Field, model_validator, ValidationError
from veus.contracts import StrictModel
from veus.replay.analysis import canonical

ROOT = Path(__file__).resolve().parents[2]
router = APIRouter(prefix="/api/lab")
MAX_ROWS = 5000


class Source(StrictModel):
    kind: Literal["illustrative", "sourced", "custom"]
    source_url: str = Field(max_length=1200)
    licence: str = Field(max_length=500)
    sha256: str = Field(pattern="^[0-9a-f]{64}$")
    units: dict[str, str]
    upstream_commit: str | None = None
    retrieved_on: str | None = None
    original_origin: float = 0
    notes: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def bounded_metadata(self):
        if not self.source_url.startswith(
            ("https://", "http://", "user://", "synthetic://")
        ):
            raise ValueError(
                "Source URL must be http(s), user:// or synthetic://; no URL is fetched at runtime"
            )
        if (
            len(self.units) > 12
            or any(len(k) > 60 or len(v) > 40 for k, v in self.units.items())
            or any(len(n) > 600 for n in self.notes)
        ):
            raise ValueError("Source metadata exceeds bounded size")
        return self


def _array(values, n, name):
    if values is not None and len(values) != n:
        raise ValueError(name + " length does not match index")


def _monotonic(values, name):
    if values[0] != 0 or any(b <= a for a, b in zip(values, values[1:])):
        raise ValueError(
            name + " must start at zero and be strictly increasing, with no duplicates"
        )


class ProfileData(StrictModel):
    schema_version: Literal[1] = 1
    id: str = Field(pattern="^[a-z0-9][a-z0-9_-]{0,63}$")
    name: str = Field(min_length=1, max_length=120)
    source: Source
    time_s: list[float] = Field(min_length=2, max_length=MAX_ROWS)
    speed_ms: list[float] = Field(min_length=2, max_length=MAX_ROWS)
    grade_percent: list[float | None] | None = None
    max_gap_s: float = Field(default=2, gt=0, le=60)

    @model_validator(mode="after")
    def consistency(self):
        _monotonic(self.time_s, "Time")
        _array(self.speed_ms, len(self.time_s), "Speed")
        _array(self.grade_percent, len(self.time_s), "Grade")
        if self.time_s[-1] > 1800 or any(not 0 <= v <= 100 for v in self.speed_ms):
            raise ValueError("Profile exceeds 1800 s or speed is outside 0..100 m/s")
        if self.grade_percent and any(
            g is not None and abs(g) > 30 for g in self.grade_percent
        ):
            raise ValueError("Profile grade must be within ±30 percent")
        return self


class RouteData(StrictModel):
    schema_version: Literal[1] = 1
    id: str = Field(pattern="^[a-z0-9][a-z0-9_-]{0,63}$")
    name: str = Field(min_length=1, max_length=120)
    source: Source
    s_m: list[float] = Field(min_length=2, max_length=MAX_ROWS)
    latitude: list[float | None] | None = None
    longitude: list[float | None] | None = None
    elevation_m: list[float | None] | None = None
    grade_percent: list[float | None] | None = None
    max_gap_m: float = Field(default=1500, gt=0, le=10000)
    time_s: list[float] | None = None
    speed_ms: list[float] | None = None
    max_gap_s: float = Field(default=2, gt=0, le=60)
    diagnostics: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def consistency(self):
        _monotonic(self.s_m, "Route distance")
        if self.s_m[-1] > 500000:
            raise ValueError("Route exceeds 500 km")
        n = len(self.s_m)
        for name in [
            "latitude",
            "longitude",
            "elevation_m",
            "grade_percent",
            "time_s",
            "speed_ms",
        ]:
            _array(getattr(self, name), n, name)
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Latitude and longitude must be provided together")
        if self.latitude:
            for lat, lon in zip(self.latitude, self.longitude):
                if (lat is None) != (lon is None):
                    raise ValueError(
                        "Coordinates must be complete pairs or both missing"
                    )
                if lat is not None and (not -90 <= lat <= 90 or not -180 <= lon <= 180):
                    raise ValueError("Coordinates outside degree ranges")
        if self.elevation_m and any(
            z is not None and not -500 <= z <= 10000 for z in self.elevation_m
        ):
            raise ValueError("Elevation outside -500..10000 m")
        if self.grade_percent and any(
            g is not None and abs(g) > 30 for g in self.grade_percent
        ):
            raise ValueError("Route grade outside ±30 percent")
        if self.elevation_m:
            for i, (a, b) in enumerate(zip(self.elevation_m, self.elevation_m[1:])):
                if (
                    a is not None
                    and b is not None
                    and abs(100 * (b - a) / (self.s_m[i + 1] - self.s_m[i])) > 30
                ):
                    raise ValueError(
                        "Elevation-implied route grade exceeds ±30 percent"
                    )
        if self.time_s is not None:
            _monotonic(self.time_s, "Route time")
            if self.time_s[-1] > 1800:
                raise ValueError("Timed route exceeds 1800 s")
        if self.speed_ms is not None and any(not 0 <= v <= 100 for v in self.speed_ms):
            raise ValueError("Route speeds outside 0..100 m/s")
        self.diagnostics = route_diagnostics(self)
        return self


class ImportConfig(StrictModel):
    name: str = Field(default="Custom engineering input", min_length=1, max_length=120)
    kind: Literal["custom"] = "custom"
    time_unit: Literal["s", "ms"] = "s"
    speed_unit: Literal["m/s", "km/h"] = "m/s"
    distance_unit: Literal["m", "km"] = "m"
    elevation_unit: Literal["m"] = "m"
    grade_unit: Literal["percent", "fraction"] = "percent"
    distance_policy: Literal["require", "haversine_chords"] = "require"
    columns: dict[str, str] = Field(default_factory=dict)
    max_gap_s: float = Field(default=2, gt=0, le=60)
    max_gap_m: float = Field(default=1500, gt=0, le=10000)
    source_url: str = Field(default="user://uploaded-csv", max_length=1200)
    licence: str = Field(
        default="User supplied; usage rights not independently verified", max_length=500
    )


class ImportRequest(StrictModel):
    csv_base64: str
    configuration: ImportConfig


def _rows(raw, config, required):
    if not raw or len(raw) > 2_000_000:
        raise ValueError("CSV must be nonempty and at most 2 MB")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise ValueError("CSV must be UTF-8") from e
    reader = csv.DictReader(io.StringIO(text, newline=""))
    fields = reader.fieldnames or []
    if not fields or len(fields) > 30 or len(set(fields)) != len(fields):
        raise ValueError("CSV needs a unique bounded header")
    allowed = {
        "time",
        "speed",
        "distance",
        "latitude",
        "longitude",
        "elevation",
        "grade",
    }
    if set(config.columns) - allowed or any(
        not v or v not in fields for v in config.columns.values()
    ):
        raise ValueError("Mapped column missing or mapping key unsupported")
    if any(k not in config.columns for k in required):
        raise ValueError("Explicit column mappings required: " + ", ".join(required))
    rows = []
    for row in reader:
        if len(rows) >= MAX_ROWS:
            raise ValueError("CSV exceeds 5000 rows; no truncation is applied")
        if None in row:
            raise ValueError("CSV row has more fields than its header")
        rows.append(row)
    if len(rows) < 2:
        raise ValueError("At least two samples required")

    def col(key, optional=False):
        if key not in config.columns:
            return None
        values = []
        for row in rows:
            text = row.get(config.columns[key])
            if text is None or not text.strip():
                if optional:
                    values.append(None)
                    continue
                raise ValueError(
                    "Missing required " + key + " sample; continuity is unknown"
                )
            try:
                v = float(text)
            except ValueError as e:
                raise ValueError("Nonnumeric " + key + " sample") from e
            if not math.isfinite(v):
                raise ValueError("Nonfinite " + key + " sample")
            values.append(v)
        return values

    return col


def _source(raw, cfg, origin, notes):
    return Source(
        kind="custom",
        source_url=cfg.source_url,
        licence=cfg.licence,
        sha256=hashlib.sha256(raw).hexdigest(),
        units={
            "time": cfg.time_unit,
            "speed": cfg.speed_unit,
            "distance": cfg.distance_unit,
            "elevation": cfg.elevation_unit,
            "grade": cfg.grade_unit,
            "coordinates": "degrees",
        },
        original_origin=origin,
        notes=notes,
    )


def parse_profile(raw: bytes, cfg: ImportConfig):
    col = _rows(raw, cfg, ["time", "speed"])
    time = col("time")
    speed = col("speed")
    grade = col("grade", True)
    scale = 0.001 if cfg.time_unit == "ms" else 1
    origin = time[0] * scale
    t = [v * scale - origin for v in time]
    v = [x / 3.6 if cfg.speed_unit == "km/h" else x for x in speed]
    g = (
        [
            None if x is None else x * 100 if cfg.grade_unit == "fraction" else x
            for x in grade
        ]
        if grade
        else None
    )
    id = (
        "custom-"
        + hashlib.sha256(raw + canonical(cfg.model_dump(mode="json"))).hexdigest()[:16]
    )
    notes = [
        "Original bytes hashed; numeric values converted by explicit unit mapping. Time origin normalized; no resampling.",
        "Piecewise-linear speed; no interpolation across gaps over declared max_gap_s. Missing required time/speed is rejected.",
    ]
    return ProfileData(
        id=id,
        name=cfg.name,
        source=_source(raw, cfg, origin, notes),
        time_s=t,
        speed_ms=v,
        grade_percent=g,
        max_gap_s=cfg.max_gap_s,
    )


def chord_distance(lat1, lon1, lat2, lon2):
    p, q = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    dp = q - p
    return (
        2
        * 6371000
        * math.asin(
            min(
                1,
                math.sqrt(
                    math.sin(dp / 2) ** 2
                    + math.cos(p) * math.cos(q) * math.sin(dl / 2) ** 2
                ),
            )
        )
    )


def parse_route(raw: bytes, cfg: ImportConfig):
    required = (
        ["distance"] if cfg.distance_policy == "require" else ["latitude", "longitude"]
    )
    col = _rows(raw, cfg, required)
    latitude = col("latitude", True)
    longitude = col("longitude", True)
    distance = col("distance")
    if distance is None:
        if not latitude or not longitude or None in latitude or None in longitude:
            raise ValueError("Haversine distance needs complete coordinate pairs")
        if any(not -90 <= x <= 90 for x in latitude) or any(
            not -180 <= x <= 180 for x in longitude
        ):
            raise ValueError("Coordinate degrees outside bounds")
        distance = [0.0]
        for i in range(1, len(latitude)):
            distance.append(
                distance[-1]
                + chord_distance(
                    latitude[i - 1], longitude[i - 1], latitude[i], longitude[i]
                )
            )
        factor = 1
    else:
        factor = 1000 if cfg.distance_unit == "km" else 1
    origin = distance[0] * factor
    g = col("grade", True)
    t = col("time")
    v = col("speed")
    if g:
        g = [
            None if x is None else x * 100 if cfg.grade_unit == "fraction" else x
            for x in g
        ]
    if t:
        tf = 0.001 if cfg.time_unit == "ms" else 1
        t0 = t[0] * tf
        t = [x * tf - t0 for x in t]
    if v:
        v = [x / 3.6 if cfg.speed_unit == "km/h" else x for x in v]
    notes = [
        "Distance-indexed input, separate from a timed speed profile. No missing coordinates/elevation are fabricated.",
        "Linear interpolation only within valid adjacent source segments; gaps remain uncovered.",
    ]
    if cfg.distance_policy == "haversine_chords":
        notes.append(
            "Explicit geometry-chord distance policy selected; when no distance column is supplied, distance is derived from coordinate chords, not surveyed road length."
        )
    return RouteData(
        id="route-"
        + hashlib.sha256(raw + canonical(cfg.model_dump(mode="json"))).hexdigest()[:16],
        name=cfg.name,
        source=_source(raw, cfg, origin, notes),
        s_m=[x * factor - origin for x in distance],
        latitude=latitude,
        longitude=longitude,
        elevation_m=col("elevation", True),
        grade_percent=g,
        max_gap_m=cfg.max_gap_m,
        time_s=t,
        speed_ms=v,
        max_gap_s=cfg.max_gap_s,
    )


def route_profile(route: RouteData):
    if route.time_s is None or route.speed_ms is None:
        raise ValueError(
            "Route has no timed speed profile; provide a separate speed-time profile"
        )
    return ProfileData(
        id=route.id,
        name=route.name,
        source=route.source,
        time_s=route.time_s,
        speed_ms=route.speed_ms,
        grade_percent=route.grade_percent,
        max_gap_s=route.max_gap_s,
    )


def _segment(index, value):
    if value < index[0] - 1e-8 or value > index[-1] + 1e-8:
        return None
    i = max(0, min(len(index) - 2, bisect.bisect_right(index, value) - 1))
    width = index[i + 1] - index[i]
    return i, max(0, min(1, (value - index[i]) / width)), width


def sample_profile(profile: ProfileData, t: float):
    part = _segment(profile.time_s, t)
    if part is None:
        raise ValueError("Profile time coverage exhausted")
    i, a, width = part
    if width > profile.max_gap_s:
        raise ValueError(
            "Profile contains an unsupported time gap; select a covered window explicitly"
        )
    v0, v1 = profile.speed_ms[i : i + 2]
    g = None
    if profile.grade_percent:
        g0, g1 = profile.grade_percent[i : i + 2]
        if g0 is not None and g1 is not None:
            g = g0 + (g1 - g0) * a
    return {
        "target_speed_ms": v0 + (v1 - v0) * a,
        "target_acceleration_ms2": (v1 - v0) / width,
        "grade_percent": g,
    }


def sample_route(route: RouteData, s: float):
    part = _segment(route.s_m, s)
    out = {
        "covered": False,
        "grade_percent": None,
        "elevation_m": None,
        "latitude": None,
        "longitude": None,
    }
    if part is None:
        return out
    i, a, width = part
    if width > route.max_gap_m:
        return out
    out["covered"] = True
    for name in ["latitude", "longitude", "elevation_m", "grade_percent"]:
        values = getattr(route, name)
        if values is not None:
            lo, hi = values[i : i + 2]
            if lo is not None and hi is not None:
                out[name] = lo + (hi - lo) * a
    if out["grade_percent"] is None and route.elevation_m:
        lo, hi = route.elevation_m[i : i + 2]
        if lo is not None and hi is not None:
            out["grade_percent"] = 100 * (hi - lo) / width
    return out


def profile_distance(profile: ProfileData):
    if any(
        b - a > profile.max_gap_s for a, b in zip(profile.time_s, profile.time_s[1:])
    ):
        return None
    return sum(
        (b - a) * (u + v) / 2
        for a, b, u, v in zip(
            profile.time_s, profile.time_s[1:], profile.speed_ms, profile.speed_ms[1:]
        )
    )


def route_diagnostics(route: RouteData):
    warnings = []
    if route.latitude:
        for i in range(len(route.s_m) - 1):
            lat1, lat2 = route.latitude[i : i + 2]
            lon1, lon2 = route.longitude[i : i + 2]
            if None in [lat1, lat2, lon1, lon2]:
                continue
            chord = chord_distance(lat1, lon1, lat2, lon2)
            ds = route.s_m[i + 1] - route.s_m[i]
            if chord > ds * 1.05 + 2 or (chord > 1 and ds > chord * 1.5 + 10):
                warnings.append(
                    "Coordinate chord / supplied distance inconsistency at segment "
                    + str(i)
                )
    if route.grade_percent and route.elevation_m:
        for i in range(len(route.s_m) - 1):
            a, b = route.elevation_m[i : i + 2]
            g = route.grade_percent[i]
            if (
                a is not None
                and b is not None
                and g is not None
                and abs(g - 100 * (b - a) / (route.s_m[i + 1] - route.s_m[i])) > 2
            ):
                warnings.append(
                    "Provided grade differs from elevation difference at segment "
                    + str(i)
                    + "; provided grade takes precedence"
                )
    return warnings[:20]


ILLUSTRATIVE = {
    "urban": (
        "Illustrative urban",
        [
            (0, 0),
            (8, 13.9),
            (30, 13.9),
            (38, 0),
            (50, 0),
            (60, 11.1),
            (90, 11.1),
            (100, 0),
            (120, 0),
        ],
    ),
    "motorway": (
        "Illustrative motorway",
        [(0, 0), (30, 27.7777777778), (150, 27.7777777778), (180, 0)],
    ),
    "stop-go": (
        "Illustrative stop and go",
        [
            (0, 0),
            (10, 10),
            (20, 10),
            (30, 0),
            (40, 0),
            (50, 10),
            (60, 10),
            (70, 0),
            (90, 0),
        ],
    ),
    "constant-reference": (
        "Constant-speed reference",
        [(0, 27.7777777778), (120, 27.7777777778)],
    ),
}


@lru_cache(maxsize=8)
def builtin_profile(id):
    if id in ILLUSTRATIVE:
        name, points = ILLUSTRATIVE[id]
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(["time_s", "speed_ms", "grade_percent"])
        for t in range(int(points[-1][0]) + 1):
            i = min(
                len(points) - 2,
                max(0, bisect.bisect_right([x[0] for x in points], t) - 1),
            )
            t0, v0 = points[i]
            t1, v1 = points[i + 1]
            writer.writerow([t, v0 + (v1 - v0) * (t - t0) / (t1 - t0), 0])
        raw = buf.getvalue().encode()
        p = parse_profile(
            raw,
            ImportConfig(
                name=name,
                columns={
                    "time": "time_s",
                    "speed": "speed_ms",
                    "grade": "grade_percent",
                },
            ),
        )
        return p.model_copy(
            update={
                "id": id,
                "source": p.source.model_copy(
                    update={
                        "kind": "illustrative",
                        "source_url": "synthetic://veus/" + id,
                        "licence": "Original VEUS illustrative fixture; no external vehicle measurements",
                        "notes": [
                            "Explicit synthetic piecewise-linear speed example, sampled at 1 s. Not a standardized or measured journey.",
                            "A flat grade=0 assumption is explicit for this synthetic profile; no geographic geometry or surveyed elevation is implied.",
                        ],
                    }
                ),
            }
        )
    if id in ["udds", "hwfet"]:
        meta = json.loads((ROOT / "datasets/cycles/provenance.json").read_text())[id]
        raw = (ROOT / "datasets/cycles" / f"{id}-fastsim.csv").read_bytes()
        if hashlib.sha256(raw).hexdigest() != meta["sha256"]:
            raise ValueError("Pinned cycle source hash mismatch")
        p = parse_profile(
            raw,
            ImportConfig(
                name=meta["name"],
                columns={
                    "time": "time_seconds",
                    "speed": "speed_meters_per_second",
                    "grade": "grade",
                },
                grade_unit="fraction",
            ),
        )
        return p.model_copy(
            update={
                "id": id,
                "source": p.source.model_copy(
                    update={
                        "kind": "sourced",
                        "source_url": meta["source_url"],
                        "licence": meta["licence"],
                        "upstream_commit": meta["upstream_commit"],
                        "retrieved_on": meta["retrieved_on"],
                        "notes": meta["notes"],
                    }
                ),
            }
        )
    raise ValueError("Unknown profile ID")


@lru_cache(maxsize=1)
def builtin_route(id):
    if id != "synthetic-local-loop":
        raise ValueError("Unknown route ID")
    raw = (ROOT / "examples/lab/synthetic-route.csv").read_bytes()
    p = parse_route(
        raw,
        ImportConfig(
            name="Synthetic local loop · not a real road",
            columns={
                "distance": "distance_m",
                "latitude": "latitude",
                "longitude": "longitude",
                "elevation": "elevation_m",
            },
        ),
    )
    return p.model_copy(
        update={
            "id": id,
            "source": p.source.model_copy(
                update={
                    "kind": "illustrative",
                    "source_url": "synthetic://veus/local-loop",
                    "licence": "Original VEUS illustrative fixture; no external geometry",
                    "notes": [
                        "Synthetic coordinate/elevation example near 0° latitude/longitude, not a surveyed location or any real circuit."
                    ],
                }
            ),
        }
    )


@router.get("/catalogue")
def catalogue():
    profiles = [
        dict(
            id=id,
            name=v[0],
            source={"kind": "illustrative"},
            duration_s=v[1][-1][0],
            sample_count=int(v[1][-1][0]) + 1,
        )
        for id, v in ILLUSTRATIVE.items()
    ]
    meta = json.loads((ROOT / "datasets/cycles/provenance.json").read_text())
    profiles.extend(
        dict(
            id=id,
            name=m["name"],
            source={
                "kind": "sourced",
                "licence": m["licence"],
                "source_url": m["source_url"],
            },
            duration_s=m["duration_s"],
            sample_count=m["sample_count"],
        )
        for id, m in meta.items()
    )
    return dict(
        experiments=[
            dict(id=id, name=name)
            for id, name in [
                ("constant_speed", "Constant speed"),
                ("acceleration", "Acceleration"),
                ("braking", "Braking & regeneration"),
                ("gradient", "Road gradient"),
                ("coast", "Coast-down"),
            ]
        ],
        profiles=profiles,
        routes=[
            dict(
                id="synthetic-local-loop",
                name="Synthetic local loop · not a real road",
                source={"kind": "illustrative"},
            )
        ],
    )


@router.get("/profiles/{id}")
def get_profile(id: str):
    try:
        return builtin_profile(id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/routes/{id}")
def get_route(id: str):
    try:
        return builtin_route(id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


async def _import(request, parser):
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > 3_000_000:
            raise HTTPException(413, "Import JSON exceeds 3 MB")
    try:
        req = ImportRequest.model_validate_json(data)
        raw = base64.b64decode(req.csv_base64, validate=True)
        return parser(raw, req.configuration)
    except (ValueError, ValidationError) as e:
        raise HTTPException(422, str(e)) from e


@router.post("/import/profile")
async def import_profile(request: Request):
    return await _import(request, parse_profile)


@router.post("/import/route")
async def import_route(request: Request):
    return await _import(request, parse_route)
