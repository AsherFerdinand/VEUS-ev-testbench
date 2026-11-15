"""python -m veus.testing run scenarios --output reports/run-001"""

import argparse
from pathlib import Path
import sys
from veus.testing.schema import Scenario
from veus.testing.runner import run_scenario
from veus.testing.report import physics_report, provenance, write_json, page, save_batch


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline analytical verification and scenario reporting"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("inputs", nargs="+", type=Path)
    run.add_argument("--output", type=Path, required=True)
    physics = sub.add_parser("physics")
    physics.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        root = Path(__file__).resolve().parents[2]
        scenarios = []
        originals = {}
        if args.command == "run":
            files = []
            for path in args.inputs:
                if path.is_dir():
                    matches = sorted(path.glob("*.json"))
                    if not matches:
                        raise ValueError(f"No scenario JSON files in {path}")
                    files.extend(matches)
                else:
                    files.append(path)
            for path in files:
                raw = path.read_text(encoding="utf-8-sig")
                scenario = Scenario.model_validate_json(raw)
                if scenario.id in originals:
                    raise ValueError(f"Duplicate scenario ID: {scenario.id}")
                originals[scenario.id] = raw
                scenarios.append(scenario)
        if args.output.exists() and (
            not args.output.is_dir() or any(args.output.iterdir())
        ):
            raise ValueError(
                "Output must be a new or empty directory; existing results are never overwritten"
            )
        args.output.mkdir(parents=True, exist_ok=True)
        if args.command == "run":
            results = [run_scenario(s) for s in scenarios]
            summary = save_batch(args.output, scenarios, results, root, originals)
            status = summary["status"]
            for result in results:
                print(f"{result.scenario_id}: {result.status} ({result.termination})")
        else:
            result = physics_report(args.output)
            meta = provenance(root)
            write_json(args.output / "provenance.json", meta)
            (args.output / "report.html").write_text(
                page("VEUS analytical physics verification", result["html"]),
                encoding="utf-8",
            )
            status = result["result"]["status"]
        print(f"{status}: {args.output / 'report.html'}")
        # 0 = every required check passed, 1 = FAIL or INCONCLUSIVE, 2 = setup/input error.
        return 0 if status == "PASS" else 1
    except (ValueError, OSError, ImportError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
