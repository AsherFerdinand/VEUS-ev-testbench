"""Bounded JSON/CSV validation requests; does not alter live driving sessions."""

import base64
import json
from pathlib import Path
import threading
from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from pydantic import Field
from veus.contracts import StrictModel
from veus.validation.experiments import Experiment
from veus.validation.calibration import CalibrationConfig, ParameterRange, calibrate
from veus.validation.measurements import load_csv
from veus.validation.report import analyse

router = APIRouter(prefix="/api/validation")
ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = {
    name: (
        ROOT / "examples/validation" / f"{name}.json",
        (
            ROOT / "datasets/ved"
            if name.startswith("ved-")
            else ROOT / "examples/validation"
        )
        / f"{name}.csv",
    )
    for name in [
        "synthetic-coast-train",
        "synthetic-coast-holdout",
        "synthetic-battery-train",
        "synthetic-battery-holdout",
        "ved-10-1558",
        "ved-10-1561",
    ]
}
PLOT_LOCK = threading.Lock()


class AnalysisRequest(StrictModel):
    experiment: Experiment
    csv_base64: str = Field(max_length=13_400_000)
    action: Literal["evaluate", "calibrate"] = "evaluate"
    calibration: dict | None = None
    calibration_settings: CalibrationConfig | None = None
    sensitivity_parameters: list[ParameterRange] = Field(
        default_factory=list, max_length=5
    )
    sensitivity_signal: str | None = None


def perform(request: AnalysisRequest):
    raw = base64.b64decode(request.csv_base64, validate=True)
    data = load_csv(raw, request.experiment.source, request.experiment.preprocessing)
    artifact = request.calibration
    if request.action == "calibrate":
        if not request.calibration_settings:
            raise ValueError("Calibration settings required")
        artifact = calibrate(request.experiment, data, request.calibration_settings)
    with PLOT_LOCK:
        result = analyse(
            request.experiment,
            raw,
            artifact,
            request.sensitivity_parameters,
            request.sensitivity_signal,
            training_study=request.action == "calibrate",
        )
    return dict(
        summary=result["summary"],
        report_html=result["html"],
        preview=result["preview"],
        calibration=artifact,
    )


@router.get("/examples")
def examples():
    return [
        {
            "id": name,
            "kind": "measured (exploratory, validation pending)"
            if name.startswith("ved-")
            else "synthetic software fixture",
        }
        for name in EXAMPLES
    ]


@router.get("/examples/{name}")
def example(name: str):
    if name not in EXAMPLES:
        raise HTTPException(404, "Unknown example")
    config, path = EXAMPLES[name]
    settings = (
        ROOT
        / "examples/validation"
        / ("coast-calibration.json" if "coast" in name else "battery-calibration.json")
    )
    return dict(
        experiment=json.loads(config.read_text()),
        csv_base64=base64.b64encode(path.read_bytes()).decode(),
        calibration_settings=json.loads(settings.read_text()),
    )


@router.post("/analyse")
async def analyse_request(request: Request):
    body = await request.body()
    if len(body) > 14_000_000:
        raise HTTPException(
            413, "Request exceeds 14 MB; select a small measurement window"
        )
    try:
        parsed = AnalysisRequest.model_validate_json(body)
        return await run_in_threadpool(perform, parsed)
    except ImportError as exc:
        raise HTTPException(
            503,
            "Model validation needs optional reporting dependencies: install -r requirements-report.txt",
        ) from exc
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        raise HTTPException(422, str(exc)) from exc
