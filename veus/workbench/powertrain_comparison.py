"""Same-design, same-cycle optional-model comparison; not hardware improvement."""

import hashlib
from fastapi import APIRouter, HTTPException, Request
from pydantic import Field, field_validator
from starlette.concurrency import run_in_threadpool
from veus.contracts import StrictModel
from veus.workbench.design import VehicleDesignV2
from veus.workbench.engineering import explicit_snapshot
from veus.workbench.insights import (
    InsightsRequest,
    calculate,
    INSIGHT_SLOTS,
    bounded_body,
)
from veus.replay.analysis import canonical

router = APIRouter(prefix="/api/workbench/v2")


class ModelComparison(StrictModel):
    vehicle: VehicleDesignV2
    acknowledgements: list[str] = Field(max_length=5)
    profile_id: str = "urban"

    @field_validator("vehicle", mode="before")
    @classmethod
    def complete(cls, v):
        return v if isinstance(v, VehicleDesignV2) else explicit_snapshot(v)


def compare_models(request):
    shared = dict(
        vehicle=request.vehicle,
        acknowledgements=request.acknowledgements,
        profile_id=request.profile_id,
        dt_s=0.2,
    )
    legacy = calculate(InsightsRequest(**shared))
    mapped = calculate(InsightsRequest(**shared, efficiency_model="illustrative_map"))
    result = dict(
        schema_version=1,
        request=request.model_dump(mode="json"),
        legacy=legacy,
        mapped=mapped,
        interpretation="Different illustrative loss assumptions, not an improvement to the physical vehicle. Both use identical designs, full cycle and continuous ratings.",
        physical_validation="INCONCLUSIVE",
    )
    result["comparison_sha256"] = hashlib.sha256(canonical(result)).hexdigest()
    return result


@router.post("/powertrain-comparison")
async def execute(request: Request):
    raw = await bounded_body(request, 2_000_000)
    try:
        parsed = ModelComparison.model_validate_json(raw)
        if INSIGHT_SLOTS.locked():
            raise HTTPException(429, "Two engineering analyses already active")
        await INSIGHT_SLOTS.acquire()
        try:
            return await run_in_threadpool(compare_models, parsed)
        finally:
            INSIGHT_SLOTS.release()
    except (ValueError, TypeError) as e:
        raise HTTPException(422, str(e)) from e
