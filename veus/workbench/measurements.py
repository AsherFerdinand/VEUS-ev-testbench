"""Modern bindings delegate to the legacy investigation service without new data processing."""

import hashlib
from fastapi import APIRouter, Request, HTTPException
from pydantic import Field, field_validator
from starlette.concurrency import run_in_threadpool
from veus.contracts import StrictModel
from veus.investigation.api import perform
from veus.investigation.analysis import InvestigationInput, investigate
from veus.replay.analysis import canonical
from veus.workbench.design import VehicleDesignV2
from veus.workbench.engineering import explicit_snapshot
from .insights import INSIGHT_SLOTS, bounded_body

router = APIRouter(prefix="/api/workbench/v2/measurements")


@router.post("/case-study")
async def case(request: Request):
    raw = await bounded_body(request, 6_000_000)
    try:
        if INSIGHT_SLOTS.locked():
            raise HTTPException(429, "Two engineering analyses already active")
        await INSIGHT_SLOTS.acquire()
        try:
            return await run_in_threadpool(perform, raw)
        finally:
            INSIGHT_SLOTS.release()
    except ImportError as e:
        raise HTTPException(
            503, "HTML reports require the existing requirements-report.txt environment"
        ) from e
    except (ValueError, TypeError, KeyError, OverflowError) as e:
        raise HTTPException(422, str(e)) from e


class ComparisonGate(StrictModel):
    recording: InvestigationInput
    vehicle: VehicleDesignV2
    interval_start_s: float = Field(default=0, ge=0)
    interval_end_s: float | None = Field(default=None, gt=0)

    @field_validator("vehicle", mode="before")
    @classmethod
    def complete(cls, v):
        return v if isinstance(v, VehicleDesignV2) else explicit_snapshot(v)


def comparison_gate(request):
    recording = investigate(request.recording)
    a = recording["analysis"]
    end = (
        request.interval_end_s
        if request.interval_end_s is not None
        else a["time_s"][-1]
    )
    if (
        end <= request.interval_start_s
        or request.interval_start_s < a["time_s"][0]
        or end > a["time_s"][-1]
    ):
        raise ValueError("Interval must be within original recording coverage")
    missing = [
        "No independently verified vehicle/parameter/measurement-boundary mapping exists for this illustrative design and recording.",
        "Measured propulsion torque, brake demand and road gradient are required for an independent forward-speed comparison.",
    ]
    if a["configuration"]["current_sign"] == "unknown":
        missing.append(
            "Recorded current polarity is unknown; discharge/regeneration/energy residuals are unavailable."
        )
    if not a["configuration"]["source"]["inputs_verified"]:
        missing.append(
            "Source operating inputs, channel synchronization and calibration are not independently verified."
        )
    return dict(
        status="INCONCLUSIVE",
        physical_validation="INCONCLUSIVE",
        residuals=None,
        measurement_source_sha256=recording["source_sha256"],
        model_configuration_sha256=hashlib.sha256(
            canonical(request.vehicle.model_dump(mode="json"))
        ).hexdigest(),
        vehicle_snapshot=request.vehicle.model_dump(mode="json"),
        interval_s=[request.interval_start_s, end],
        time_alignment="Elapsed SI seconds, original time origin retained; no calibration or forced alignment performed",
        speed_interval_coverage=a["quality"]["speed_interval_coverage"],
        capabilities=recording["readiness"]["capabilities"],
        missing_inputs=missing,
        explanation="Inspect supported recorded signals or compare recordings descriptively. S1/R1/X1 are not the measured Nissan Leaf. No quantitative model residual is fabricated.",
    )


@router.post("/comparison-readiness")
async def gate(request: Request):
    raw = await bounded_body(request, 3_000_000)
    try:
        parsed = ComparisonGate.model_validate_json(raw)
        if INSIGHT_SLOTS.locked():
            raise HTTPException(429, "Two engineering analyses already active")
        await INSIGHT_SLOTS.acquire()
        try:
            return await run_in_threadpool(comparison_gate, parsed)
        finally:
            INSIGHT_SLOTS.release()
    except (ValueError, TypeError) as e:
        raise HTTPException(422, str(e)) from e
