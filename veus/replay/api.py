"""Bounded recording imports, no access to the live simulation session."""

import base64
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from pydantic import Field
from veus.contracts import StrictModel
from veus.replay.analysis import ReplayConfig, analyse
from veus.replay.report import html_report

router = APIRouter(prefix="/api/replay")
ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ("ved-10-1561", "ved-10-1558")


class ReplayRequest(StrictModel):
    configuration: ReplayConfig
    csv_base64: str = Field(max_length=2_670_000)


def decode(request):
    return base64.b64decode(request.csv_base64, validate=True)


@router.get("/datasets")
def datasets():
    return [
        dict(
            id=name,
            label="VED · Vehicle 10 · Trip "
            + name.rsplit("-", 1)[1]
            + " (measured window)",
        )
        for name in EXAMPLES
    ]


@router.get("/datasets/{name}")
def dataset(name: str):
    if name not in EXAMPLES:
        raise HTTPException(404, "Unknown recording")
    config = json.loads((ROOT / "examples/replay" / f"{name}.json").read_text())
    raw = (ROOT / "datasets/ved" / f"{name}.csv").read_bytes()
    return dict(
        configuration=config,
        csv_base64=base64.b64encode(raw).decode(),
        analysis=analyse(raw, ReplayConfig.model_validate(config)),
    )


def perform(body, report=False):
    request = ReplayRequest.model_validate_json(body)
    result = analyse(decode(request), request.configuration)
    if report:
        # Shared matplotlib lock also serializes Phase 8 plots.
        from veus.validation.api import PLOT_LOCK as shared_lock

        with shared_lock:
            return dict(
                report_html=html_report(result),
                analysis_sha256=result["analysis_sha256"],
            )
    return result


async def handle(request, report=False):
    body = bytearray()
    async for part in request.stream():
        body.extend(part)
        if len(body) > 3_000_000:
            raise HTTPException(
                413, "Replay request exceeds 3 MB; select a small recording window"
            )
    try:
        return await run_in_threadpool(perform, bytes(body), report)
    except ImportError as exc:
        raise HTTPException(
            503,
            "HTML plots require optional dependencies: install -r requirements-report.txt",
        ) from exc
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/analyse")
async def analyse_recording(request: Request):
    return await handle(request)


@router.post("/report")
async def report_recording(request: Request):
    return await handle(request, True)
