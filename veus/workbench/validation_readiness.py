"""Evidence-specific validation/calibration assessment; no synthetic Leaf residuals."""

import hashlib
import math
from statistics import mean, median
from typing import Literal
from pydantic import Field, field_validator, model_validator
from fastapi import APIRouter, Request, HTTPException
from starlette.concurrency import run_in_threadpool
from veus.contracts import StrictModel
from veus.investigation.analysis import InvestigationInput, investigate
from veus.workbench.design import VehicleDesignV2
from veus.workbench.engineering import explicit_snapshot
from veus.workbench.insights import INSIGHT_SLOTS, bounded_body
from veus.replay.analysis import canonical

router = APIRouter(prefix="/api/workbench/v2/measurements")


def error_metrics(
    measured,
    simulated,
    *,
    unit,
    alignment_verified=False,
    mapping_verified=False,
    polarity_verified=False,
    uncertainty=None,
):
    """Numerical paired-series statistics, not evidence that mapping assertions are true."""
    if not alignment_verified or not mapping_verified:
        raise ValueError(
            "Verified units/mapping and explicit paired time alignment required"
        )
    if unit not in ["m/s", "V", "A", "W", "m", "Wh"]:
        raise ValueError("Unsupported compatible SI signal unit")
    if unit in ["A", "W", "Wh"] and not polarity_verified:
        raise ValueError("Electrical comparison requires established polarity")
    if len(measured) != len(simulated) or not measured:
        raise ValueError("Equal nonempty aligned series required")
    if uncertainty is not None and (not math.isfinite(uncertainty) or uncertainty < 0):
        raise ValueError(
            "Measurement uncertainty must be explicitly nonnegative in the signal unit"
        )
    residuals = [
        b - a
        if a is not None and b is not None and math.isfinite(a) and math.isfinite(b)
        else None
        for a, b in zip(measured, simulated)
    ]
    valid = [v for v in residuals if v is not None]
    n = len(valid)
    return dict(
        unit=unit,
        definition="simulated minus measured, at explicitly aligned original samples",
        valid_samples=n,
        total_samples=len(residuals),
        valid_sample_coverage=n / len(residuals),
        mae=mean(abs(v) for v in valid) if n else None,
        rmse=math.sqrt(mean(v * v for v in valid)) if n else None,
        bias=mean(valid) if n else None,
        residuals=residuals,
        error_distribution=dict(
            minimum=min(valid), median=median(valid), maximum=max(valid)
        )
        if n
        else None,
        supplied_measurement_uncertainty=uncertainty,
        uncertainty_note="User-supplied signal uncertainty, not estimated from residuals or independently authenticated",
        physical_validation="INCONCLUSIVE",
    )


def heldout(calibration, evaluation, duration):
    for values in [calibration, evaluation]:
        if (
            len(values) != 2
            or not all(math.isfinite(v) for v in values)
            or not 0 <= values[0] < values[1] <= duration
        ):
            raise ValueError(
                "Intervals must be ordered and within original recording duration"
            )
    if max(calibration[0], evaluation[0]) <= min(calibration[1], evaluation[1]):
        raise ValueError(
            "Calibration/evaluation intervals must be disjoint, including boundary samples"
        )
    return dict(
        calibration_interval_s=calibration,
        evaluation_interval_s=evaluation,
        no_sample_overlap=True,
    )


class Assessment(StrictModel):
    recording: InvestigationInput
    vehicle: VehicleDesignV2
    efficiency_model: Literal["illustrative_map"] | None = None
    calibration_interval_s: list[float] | None = Field(
        default=None, min_length=2, max_length=2
    )
    evaluation_interval_s: list[float] | None = Field(
        default=None, min_length=2, max_length=2
    )

    @field_validator("vehicle", mode="before")
    @classmethod
    def complete(cls, v):
        return v if isinstance(v, VehicleDesignV2) else explicit_snapshot(v)

    @model_validator(mode="after")
    def split_pair(self):
        if (self.calibration_interval_s is None) != (
            self.evaluation_interval_s is None
        ):
            raise ValueError(
                "Supply both calibration and held-out evaluation intervals"
            )
        return self


def assess_validation(request):
    recording = investigate(request.recording)
    a = recording["analysis"]
    cfg = recording["configuration"]
    source = cfg["source"]
    signals = a["measured"]
    duration = a["time_s"][-1]
    split = (
        heldout(request.calibration_interval_s, request.evaluation_interval_s, duration)
        if request.calibration_interval_s is not None
        else None
    )
    checks = []

    def add(item, status, observed, blocker):
        checks.append(
            dict(item=item, status=status, observed=observed, missing_evidence=blocker)
        )

    add(
        "vehicle_identity",
        "CONDITIONAL",
        source.get("vehicle_id"),
        "Published source identity does not establish an independent mapping to this illustrative design",
    )
    add(
        "speed_and_timestamps",
        "AVAILABLE_FOR_INVESTIGATION",
        dict(
            samples=len(a["time_s"]),
            units=a["units"].get("vehicle_speed_ms"),
            source_time_origin_s=a["metadata"]["time_origin_s"],
        ),
        "Independent clock accuracy and synchronization uncertainty remain unknown",
    )
    for name in ["battery_voltage_v", "battery_current_a"]:
        add(
            name,
            "AVAILABLE_FOR_INVESTIGATION" if name in signals else "UNAVAILABLE",
            dict(
                valid_samples=sum(v is not None for v in signals.get(name, [])),
                unit=a["units"].get(name),
            ),
            "Presence of a channel does not verify sensor calibration or measurement boundary",
        )
    add(
        "current_polarity",
        "UNAVAILABLE"
        if cfg["current_sign"] == "unknown"
        else "ASSERTED_NOT_AUTHENTICATED",
        cfg["current_sign"],
        "Independent sign and discharge/charge boundary evidence required",
    )
    add(
        "battery_power",
        "UNAVAILABLE" if cfg["current_sign"] == "unknown" else "CONDITIONAL",
        None,
        "Verified polarity, synchronized V/I and electrical boundary needed; raw |V×I| is not validated discharge power",
    )
    specs = source.get("vehicle_specifications", {})
    add(
        "vehicle_mass",
        "UNAVAILABLE",
        specs.get("weight_note", specs.get("generalized_weight_lb")),
        "Fleet/binned weight is not measured loaded vehicle mass",
    )
    add(
        "tyres_and_aerodynamics",
        "UNAVAILABLE",
        None,
        "Verified wheel radius, rolling model, drag area, air density and wind/grade conditions required",
    )
    add(
        "drivetrain_and_forward_inputs",
        "UNAVAILABLE",
        source.get("vehicle_specifications", {}).get("model"),
        "Verified drivetrain mapping plus measured propulsion/braking input and road gradient required",
    )
    add(
        "signal_synchronization",
        "UNAVAILABLE",
        None,
        "Independent channel delay/calibration/uncertainty evidence missing",
    )
    add(
        "coverage",
        "AVAILABLE_FOR_INVESTIGATION",
        dict(
            speed_interval_coverage=a["quality"]["speed_interval_coverage"],
            gaps=a["metadata"]["gaps"],
        ),
        "Gaps are retained, not extrapolated or filled",
    )
    initial = dict(
        rolling_resistance=request.vehicle.body.rolling_resistance_coefficient,
        drag_area_m2=request.vehicle.body.drag_coefficient
        * request.vehicle.body.frontal_area_m2,
        drive_efficiency=request.vehicle.motor.efficiency_assumption,
        battery_resistance_ohm=request.vehicle.battery.resistance_ohm,
    )
    requirements = {
        "rolling_resistance": [
            "Verified loaded mass and grade",
            "Zero or independently measured propulsion/braking force",
            "Coast-down coverage across appropriate speeds",
        ],
        "drag_area_m2": [
            "Verified density/wind and grade",
            "Independent wheel-force/torque boundary",
            "Sufficient speed excitation separate from rolling resistance",
        ],
        "drive_efficiency": [
            "Verified signed DC power and auxiliaries boundary",
            "Independent shaft/wheel power",
            "Synchronized current/voltage/mechanical samples",
        ],
        "battery_resistance_ohm": [
            "Verified current sign, OCV/SOC/temperature boundary",
            "Synchronized load transients and voltage/current uncertainty",
            "Identifiable electrical-model structure",
        ],
    }
    candidates = {
        key: dict(
            status="BLOCKED",
            initial_value=value,
            calibrated_value=None,
            bounds=None,
            objective=None,
            calibration_error=None,
            heldout_error=None,
            remaining_residuals=None,
            missing_evidence=requirements[key]
            + (
                []
                if split
                else ["Explicit separate calibration and held-out evaluation intervals"]
            ),
            identifiability="Not established; correlated/missing inputs cannot identify this parameter",
            uncertainty="Unavailable; not inferred from residuals",
        )
        for key, value in initial.items()
    }
    result = dict(
        schema_version=1,
        model_version="veus-evidence-readiness-v1",
        status="INCONCLUSIVE",
        physical_validation="INCONCLUSIVE",
        request=request.model_dump(mode="json"),
        dataset_provenance=source,
        source_sha256=recording["source_sha256"],
        model_configuration_sha256=hashlib.sha256(
            canonical(
                dict(
                    vehicle=request.vehicle.model_dump(mode="json"),
                    efficiency_model=request.efficiency_model,
                )
            )
        ).hexdigest(),
        powertrain_model_version="veus-illustrative-motor-map-v1"
        if request.efficiency_model
        else "legacy-constant-efficiency / veus-lab-coupled-v1",
        signal_definitions=cfg["preprocessing"],
        checks=checks,
        split=split,
        metrics=None,
        aligned_traces=None,
        residuals=None,
        measurement_uncertainty=None,
        calibration=candidates,
        conclusion="Supported recorded-signal investigation is available. VED does not independently establish the inputs/measurement boundary needed for residuals or calibration against these illustrative vehicles. No parameters were fitted; no same-data evaluation leakage.",
        limitations=recording["limitations"]
        + [
            "A user assertion or a synthetic recovery test is not real-world validation. Existing legacy calibration tools remain available for appropriately documented separate data."
        ],
    )
    result["assessment_sha256"] = hashlib.sha256(canonical(result)).hexdigest()
    return result


@router.post("/validation-readiness")
async def execute(request: Request):
    raw = await bounded_body(request, 3_000_000)
    try:
        parsed = Assessment.model_validate_json(raw)
        if INSIGHT_SLOTS.locked():
            raise HTTPException(429, "Two engineering analyses already active")
        await INSIGHT_SLOTS.acquire()
        try:
            return await run_in_threadpool(assess_validation, parsed)
        finally:
            INSIGHT_SLOTS.release()
    except (ValueError, TypeError) as e:
        raise HTTPException(422, str(e)) from e


class ReportRequest(StrictModel):
    result: dict
    format: Literal["html", "json"] = "html"


def readiness_report(result, format):
    from html import escape
    from veus.testing.report import page, table

    raw = {k: v for k, v in result.items() if k != "assessment_sha256"}
    if result.get("assessment_sha256") != hashlib.sha256(canonical(raw)).hexdigest():
        raise ValueError("Assessment fingerprint mismatch")
    if format == "json":
        return dict(
            content=canonical(result).decode(),
            filename="veus-validation-readiness.json",
            media_type="application/json",
        )
    body = (
        "<h2>INCONCLUSIVE · no calibration performed</h2><p>"
        + escape(result["conclusion"])
        + "</p>"
    )
    body += (
        "<p>Assessment "
        + escape(result["assessment_sha256"])
        + "; model "
        + escape(result["model_configuration_sha256"])
        + "</p>"
    )
    body += table(
        ["Signal / boundary", "Status", "Missing evidence"],
        [[v["item"], v["status"], v["missing_evidence"]] for v in result["checks"]],
    )
    body += (
        "<h2>Provenance, model version, split, candidate parameters and uncertainty</h2><pre>"
        + escape(canonical(result).decode())
        + "</pre>"
    )
    return dict(
        content=page("Engineering validation and calibration readiness", body),
        filename="veus-validation-readiness.html",
        media_type="text/html",
    )


@router.post("/validation-readiness/export")
async def report(request: Request):
    raw = await bounded_body(request, 3_000_000)
    try:
        parsed = ReportRequest.model_validate_json(raw)
        return await run_in_threadpool(readiness_report, parsed.result, parsed.format)
    except (ValueError, TypeError) as e:
        raise HTTPException(422, str(e)) from e
