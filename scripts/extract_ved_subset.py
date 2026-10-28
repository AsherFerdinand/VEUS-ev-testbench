"""Optional reproducibility helper. Uses libarchive-c + native libarchive locally.

The application itself needs neither package. Supply the downloaded upstream
Part1 archive; it is never modified. Exact selected lines/hashes are pinned.
"""

import argparse, csv, hashlib, io, json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("archive", type=Path)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "datasets/ved/provenance.json").read_text())
digest = hashlib.sha256()
with args.archive.open("rb") as stream:
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
if digest.hexdigest() != manifest["archive_sha256"]:
    raise ValueError("Upstream archive hash mismatch")
if args.output.exists() and any(args.output.iterdir()):
    raise ValueError("Use a new/empty output directory")
try:
    import libarchive
except ImportError:
    raise SystemExit(
        "Optional extraction requires libarchive-c and a native libarchive installation; checked-in subsets need neither"
    )
args.output.mkdir(parents=True, exist_ok=True)
columns = [
    "Timestamp(ms)",
    "Vehicle Speed[km/h]",
    "HV Battery Current[A]",
    "HV Battery Voltage[V]",
    "HV Battery SOC[%]",
    "OAT[DegC]",
]
with libarchive.file_reader(str(args.archive)) as archive:
    for entry in archive:
        if entry.pathname != "VED_171101_week.csv":
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

        targets = {
            key: value
            for key, value in manifest.items()
            if isinstance(value, dict) and "selected_source_line_numbers" in value
        }
        selected = {key: [] for key in targets}
        maximum = max(max(v["selected_source_line_numbers"]) for v in targets.values())
        for line, row in enumerate(csv.DictReader(lines()), 2):
            for key, info in targets.items():
                if line in info["selected_source_line_numbers"]:
                    selected[key].append({k: row[k] for k in columns})
            if line >= maximum:
                break
        for key, rows in selected.items():
            buffer = io.StringIO(newline="")
            w = csv.DictWriter(buffer, fieldnames=columns)
            w.writeheader()
            w.writerows(rows)
            raw = buffer.getvalue().encode()
            if hashlib.sha256(raw).hexdigest() != targets[key]["subset_sha256"]:
                raise ValueError("Subset hash mismatch")
            (args.output / (key + ".csv")).write_bytes(raw)
        break
print("Recreated exact measured subsets; original archive unchanged")
