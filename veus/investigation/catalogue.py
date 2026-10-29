"""Small recording catalogue; measurements and metadata use the existing importer."""

import base64
from pathlib import Path
from veus.replay.analysis import ReplayConfig, validate_window
from veus.validation.measurements import load_csv

ROOT = Path(__file__).resolve().parents[2]
RECORDINGS = {
    "ved-10-1561": ("VED · Vehicle 10 · Trip 1561 (72 s window)", True),
    "ved-10-1558": ("VED · Vehicle 10 · Trip 1558 (50 s window)", True),
    "ved-10-1561-full": (
        "VED · Vehicle 10 · Trip 1561 (full group · 7 min 40 s)",
        False,
    ),
    "ved-10-1567-full": (
        "VED · Vehicle 10 · Trip 1567 (full group · 6 min 10 s)",
        False,
    ),
}


def load(name):
    if name not in RECORDINGS:
        raise ValueError("Unknown recording ID")
    config = ReplayConfig.model_validate_json(
        (ROOT / "examples/replay" / f"{name}.json").read_text()
    )
    raw = (ROOT / "datasets/ved" / f"{name}.csv").read_bytes()
    data = load_csv(raw, config.source, config.preprocessing)
    validate_window(data, config.sanity_limits)
    return config, raw, data


def entry(name):
    config, raw, data = load(name)
    return dict(
        id=name,
        label=RECORDINGS[name][0],
        source=config.source.model_dump(mode="json"),
        vehicle_id=config.source.vehicle_id,
        trip_id=config.source.run_id,
        duration_s=data.times[-1],
        sample_count=len(data.times),
        bytes=len(raw),
        signals={"time_s": "s", **data.metadata["canonical_units"]},
        kind=config.source.kind,
        licence=config.source.licence,
        limitations=config.limitations,
        missing_counts=data.metadata["missing_counts"],
        timestamp_gaps=data.metadata["gaps"],
        source_sha256=data.metadata["raw_sha256"],
        provenance=config.provenance,
        legacy=RECORDINGS[name][1],
    )


def catalogue():
    return [entry(name) for name in RECORDINGS]


def payload(name):
    config, raw, _ = load(name)
    return dict(
        configuration=config.model_dump(mode="json"),
        csv_base64=base64.b64encode(raw).decode(),
        catalogue=entry(name),
    )
