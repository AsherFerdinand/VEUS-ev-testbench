"""python -m veus.investigation --first ID [--second ID] --output NEW_DIR"""

import argparse
from pathlib import Path
from veus.investigation.catalogue import payload, RECORDINGS
from veus.investigation.analysis import InvestigationInput, investigate, case_study
from veus.investigation.report import save


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Reproducible descriptive recorded-EV case study; not physical validation"
    )
    parser.add_argument("--first", choices=RECORDINGS, default="ved-10-1561-full")
    parser.add_argument("--second", choices=RECORDINGS)
    parser.add_argument("--title", default="VED recorded EV engineering investigation")
    parser.add_argument("--axis", choices=["elapsed", "normalized"], default="elapsed")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    inputs = []
    try:
        for name in [args.first] + ([args.second] if args.second else []):
            p = payload(name)
            inputs.append(
                InvestigationInput(
                    configuration=p["configuration"],
                    csv_base64=p["csv_base64"],
                    mappings_confirmed=True,
                )
            )
        result = case_study(
            investigate(inputs[0]),
            investigate(inputs[1]) if len(inputs) > 1 else None,
            args.title,
            args.axis,
        )
        save(args.output, result, inputs)
        print(
            "Recorded-data case study saved; physical validation remains INCONCLUSIVE."
        )
        print(args.output / "report.html")
        return 0
    except (ValueError, OSError, ImportError) as exc:
        print("ERROR: " + str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
