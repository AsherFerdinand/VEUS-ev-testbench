"""Bounded foundation API; no new simulation or optimization results."""

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError
from veus.replay.analysis import canonical
from .schema import VehicleDesign

router = APIRouter(prefix="/api/workbench")


@lru_cache
def content_data():
    return json.loads(
        Path(__file__).with_name("content.json").read_text(encoding="utf-8")
    )


@router.get("/content")
def content():
    return content_data()


@router.get("/design")
def default_design():
    return VehicleDesign().model_dump(mode="json")


@router.get("/design/schema")
def design_schema():
    return VehicleDesign.model_json_schema()


@router.post("/design/validate")
async def validate_design(request: Request):
    body = bytearray()
    async for part in request.stream():
        body.extend(part)
        if len(body) > 64_000:
            raise HTTPException(413, "Design JSON exceeds 64 KB")
    try:
        design = VehicleDesign.model_validate_json(body).model_dump(mode="json")
    except ValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    return dict(
        design=design,
        configuration_sha256=hashlib.sha256(canonical(design)).hexdigest(),
        status="Configuration envelope checked; no simulation executed",
        limitations=[
            "Illustrative user inputs, not sourced component specifications.",
            "Voltage and nameplate power checks are necessary, not sufficient for compatibility.",
            "Current limits, transient operation, cooling, insulation, charging curves and efficiency maps still need models and evidence.",
            "No range, charging time, price, efficiency improvement or physical-validation result is calculated.",
        ],
    )
