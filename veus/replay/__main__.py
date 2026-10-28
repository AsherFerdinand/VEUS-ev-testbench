"""python -m veus.replay CONFIG CSV --output NEW_DIRECTORY"""

import argparse
from pathlib import Path
import sys
from veus.replay.analysis import ReplayConfig, analyse
from veus.replay.report import save


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Reproducible recorded EV descriptive analysis, not physical validation"
    )
    parser.add_argument("configuration", type=Path)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        config = ReplayConfig.model_validate_json(
            args.configuration.read_text(encoding="utf-8-sig")
        )
        raw = args.csv.read_bytes()
        result = analyse(raw, config)
        save(args.output, result, raw)
        (args.output / "configuration-input.json").write_bytes(
            args.configuration.read_bytes()
        )
        print("Recorded-data analysis complete; physical validation remains pending.")
        print(args.output / "report.html")
        return 0
    except (ValueError, OSError, ImportError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
