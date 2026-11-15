"""Inspect/confirm/assess with the same bounded CSV contracts used by replay."""

import base64
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import Field
from starlette.concurrency import run_in_threadpool
from veus.contracts import StrictModel
from veus.readiness.analysis import ReadinessConfig, inspect, assess
from veus.readiness.registry import registry

router = APIRouter(prefix="/api/readiness")
ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = {
    "basic-replay": {
        "csv": "examples/onboarding/basic-replay.csv",
        "config": "examples/onboarding/basic-replay.json",
    },
    "electrical-analysis": {
        "csv": "examples/onboarding/electrical-analysis.csv",
        "config": "examples/onboarding/electrical-analysis.json",
    },
    "engineering-example": {
        "csv": "examples/validation/synthetic-battery-train.csv",
        "config": "examples/validation/synthetic-battery-train.json",
        "settings": "examples/validation/battery-calibration.json",
        "holdout-csv": "examples/validation/synthetic-battery-holdout.csv",
        "holdout-config": "examples/validation/synthetic-battery-holdout.json",
    },
}


class InspectionRequest(StrictModel):
    csv_base64: str = Field(max_length=2_670_000)


class AssessmentRequest(InspectionRequest):
    configuration: ReadinessConfig
    mappings_confirmed: Literal[True]


@router.get("/capabilities")
def capabilities():
    return registry()


@router.get("/templates/{name}/{artifact}")
def template(name: str, artifact: str):
    if name not in TEMPLATES or artifact not in TEMPLATES[name]:
        raise HTTPException(404, "Unknown input template")
    path = ROOT / TEMPLATES[name][artifact]
    return FileResponse(path, filename=path.name)


async def handle(request, assessment=False):
    body = bytearray()
    async for part in request.stream():
        body.extend(part)
        if len(body) > 3_000_000:
            raise HTTPException(
                413,
                "Request exceeds 3 MB. Choose a CSV no larger than 2 MB / 5000 rows.",
            )
    try:
        parsed = (
            AssessmentRequest if assessment else InspectionRequest
        ).model_validate_json(bytes(body))
        raw = base64.b64decode(parsed.csv_base64, validate=True)
        return (
            await run_in_threadpool(assess, raw, parsed.configuration)
            if assessment
            else await run_in_threadpool(inspect, raw)
        )
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/inspect")
async def inspect_recording(request: Request):
    return await handle(request)


@router.post("/assess")
async def assess_recording(request: Request):
    return await handle(request, True)
