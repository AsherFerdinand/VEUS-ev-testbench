"""CSV experiment CLI; data file paths are explicit and never executed as code."""

import argparse, json
from pathlib import Path
import sys
from veus.validation.experiments import Experiment
from veus.validation.measurements import load_csv
from veus.validation.calibration import CalibrationConfig, ParameterRange, calibrate
from veus.validation.report import analyse, save
from veus.testing.report import write_json


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Measurement comparisons, bounded calibration and independent evaluation"
    )
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("evaluate", "calibrate"):
        cmd = sub.add_parser(action)
        cmd.add_argument("experiment", type=Path)
        cmd.add_argument("data", type=Path)
        cmd.add_argument("--output", type=Path, required=True)
        if action == "calibrate":
            cmd.add_argument("--settings", type=Path, required=True)
        else:
            cmd.add_argument("--calibration", type=Path)
            cmd.add_argument("--sensitivity", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output.exists() and (
            not args.output.is_dir() or any(args.output.iterdir())
        ):
            raise ValueError("Use a new/empty report directory")
        experiment = Experiment.model_validate_json(
            args.experiment.read_text(encoding="utf-8-sig")
        )
        raw = args.data.read_bytes()
        data = load_csv(raw, experiment.source, experiment.preprocessing)
        artifact = None
        spec = None
        if args.action == "calibrate":
            spec = CalibrationConfig.model_validate_json(args.settings.read_text())
            artifact = calibrate(experiment, data, spec)
        elif args.calibration:
            artifact = json.loads(args.calibration.read_text())
        ranges = None
        signal = None
        if args.action == "evaluate" and args.sensitivity:
            sensitivity = json.loads(args.sensitivity.read_text())
            ranges = [
                ParameterRange.model_validate(r) for r in sensitivity["parameters"]
            ]
            signal = sensitivity["signal"]
        result = analyse(
            experiment,
            raw,
            artifact,
            ranges,
            signal,
            training_study=args.action == "calibrate",
            config_file_bytes=args.experiment.read_bytes(),
        )
        save(args.output, result, raw)
        (args.output / "experiment-input.json").write_bytes(
            args.experiment.read_bytes()
        )
        if artifact:
            write_json(args.output / "calibration.json", artifact)
        print(result["summary"]["label"] + ": " + result["summary"]["status"])
        print(args.output / "report.html")
        return 0 if result["summary"]["status"] == "PASS" else 1
    except (ValueError, OSError, ImportError, KeyError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
