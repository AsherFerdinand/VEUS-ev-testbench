"""Reproduce complete VED trip projections; optional libarchive-c + native library."""

import argparse, csv, hashlib, io, json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("archive", type=Path)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
manifest = json.loads(
    (root / "datasets/ved/full-recordings-provenance.json").read_text()
)
digest = hashlib.sha256()
with args.archive.open("rb") as stream:
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
if digest.hexdigest() != manifest["archive_sha256"]:
    raise ValueError("Pinned VED archive hash mismatch")
if args.output.exists() and any(args.output.iterdir()):
    raise ValueError("Use a new/empty output directory")
import libarchive

columns = [
    "Timestamp(ms)",
    "Vehicle Speed[km/h]",
    "HV Battery Current[A]",
    "HV Battery Voltage[V]",
    "HV Battery SOC[%]",
    "OAT[DegC]",
]
selected = {key: [] for key in manifest["recordings"]}
maximum = max(v["source_line_range"][1] for v in manifest["recordings"].values())
with libarchive.file_reader(str(args.archive)) as archive:
    for entry in archive:
        if entry.pathname != manifest["member"]:
            continue

        def lines():
            buffer = b""
            for block in entry.get_blocks():
                buffer += block
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    yield line.decode("utf-8-sig")
            if buffer:
                yield buffer.decode("utf-8-sig")

        for number, row in enumerate(csv.DictReader(lines()), 2):
            for key, info in manifest["recordings"].items():
                lo, hi = info["source_line_range"]
                if lo <= number <= hi:
                    if (
                        row["VehId"] != str(info["vehicle_id"])
                        or row["Trip"] != info["trip"]
                    ):
                        raise ValueError("Source identity mismatch")
                    selected[key].append({c: row[c] for c in columns})
            if number >= maximum:
                break
        break
outputs = {}
for key, rows in selected.items():
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    raw = output.getvalue().encode()
    if (
        len(rows) != manifest["recordings"][key]["rows"]
        or hashlib.sha256(raw).hexdigest()
        != manifest["recordings"][key]["subset_sha256"]
    ):
        raise ValueError("Projection row count/hash mismatch")
    outputs[key] = raw
args.output.mkdir(parents=True, exist_ok=True)
for key, raw in outputs.items():
    (args.output / (key + ".csv")).write_bytes(raw)
print("Reproduced full-trip projections byte for byte; original archive unchanged.")
