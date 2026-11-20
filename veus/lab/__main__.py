"""python -m veus.lab request.json --output NEW_DIR"""

import argparse
from pathlib import Path
from veus.replay.analysis import canonical
from .schema import LabRequest
from .runner import run
from .report import export


def main():
    p = argparse.ArgumentParser()
    p.add_argument("request", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    try:
        if a.output.exists():
            raise ValueError("Use a new output directory")
        if a.request.stat().st_size > 2_000_000:
            raise ValueError("Request exceeds 2 MB")
        result = run(LabRequest.model_validate_json(a.request.read_bytes()))
        a.output.mkdir(parents=True)
        (a.output / "request.json").write_bytes(canonical(result["request"]))
        for fmt in ["json", "csv", "html"]:
            artifact = export(result, fmt)
            (a.output / artifact["filename"]).write_text(
                artifact["content"], encoding="utf-8"
            )
        print(a.output / "veus-lab-report.html")
        return 0
    except (ValueError, OSError) as e:
        print(str(e))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
