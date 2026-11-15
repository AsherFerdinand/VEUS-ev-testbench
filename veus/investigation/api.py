"""Two bounded recordings per case; shared readiness and existing event detector."""

from typing import Literal
from pydantic import Field
from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from veus.contracts import StrictModel
from veus.investigation.catalogue import catalogue, payload
from veus.investigation.analysis import InvestigationInput, investigate, case_study
from veus.investigation.report import html_report, measurement_csv

router = APIRouter(prefix="/api/investigation")


class CaseRequest(StrictModel):
    first: InvestigationInput
    second: InvestigationInput | None = None
    title: str = Field(
        default="Recorded EV engineering investigation", min_length=1, max_length=160
    )
    axis: Literal["elapsed", "normalized"] = "elapsed"
    format: Literal["json", "html", "csv"] = "json"


@router.get("/catalogue")
def recordings():
    return catalogue()


@router.get("/recordings/{name}")
def recording(name: str):
    try:
        return payload(name)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


def perform(body):
    request = CaseRequest.model_validate_json(body)
    result = case_study(
        investigate(request.first),
        investigate(request.second) if request.second else None,
        request.title,
        request.axis,
    )
    if request.format == "html":
        from veus.validation.api import PLOT_LOCK

        with PLOT_LOCK:
            content = html_report(result)
        return dict(case_sha256=result["case_sha256"], content=content)
    if request.format == "csv":
        return dict(case_sha256=result["case_sha256"], content=measurement_csv(result))
    return result


@router.post("/case-study")
async def case(request: Request):
    body = bytearray()
    async for part in request.stream():
        body.extend(part)
        if len(body) > 6_000_000:
            raise HTTPException(
                413,
                "Two-recording request exceeds 6 MB; each CSV still has a 2 MB / 5000-row limit.",
            )
    try:
        return await run_in_threadpool(perform, bytes(body))
    except ImportError as exc:
        raise HTTPException(
            503, "HTML plots require -r requirements-report.txt"
        ) from exc
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise HTTPException(422, str(exc)) from exc
