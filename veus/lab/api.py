"""Bounded CPU work off the event loop, no retained run cache."""

from typing import Literal
import asyncio
from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from veus.contracts import StrictModel
from .schema import LabRequest
from .runner import run
from .report import export

router = APIRouter(prefix="/api/lab")
RUN_SLOTS = asyncio.Semaphore(2)


async def read_body(request, limit):
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > limit:
            raise HTTPException(413, "Lab request exceeds bounded body size")
    return data


@router.post("/run")
async def execute(request: Request):
    raw = await read_body(request, 2_000_000)
    try:
        parsed = LabRequest.model_validate_json(raw)
        if RUN_SLOTS.locked():
            raise HTTPException(
                429, "Two Lab runs already active; retry after they finish"
            )
        await RUN_SLOTS.acquire()
        try:
            return await run_in_threadpool(run, parsed)
        finally:
            RUN_SLOTS.release()
    except (ValueError, ValidationError, TypeError) as e:
        raise HTTPException(422, str(e)) from e


class ExportRequest(StrictModel):
    result: dict
    format: Literal["json", "csv", "html"] = "json"


@router.post("/export")
async def export_result(request: Request):
    raw = await read_body(request, 24_000_000)
    try:
        parsed = ExportRequest.model_validate_json(raw)
        return await run_in_threadpool(export, parsed.result, parsed.format)
    except (ValueError, ValidationError, TypeError) as e:
        raise HTTPException(422, str(e)) from e
