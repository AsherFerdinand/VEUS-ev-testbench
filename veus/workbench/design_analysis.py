"""Matched bounded studies, reusing the Insights service and coupled Lab unchanged."""

import copy
import csv
import hashlib
import io
from html import escape
from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from pydantic import Field, ValidationError, field_validator, model_validator
from starlette.concurrency import run_in_threadpool
from veus.contracts import StrictModel
from veus.replay.analysis import canonical
from veus.workbench.design import VehicleDesignV2
from veus.workbench.engineering import explicit_snapshot
from .insights import InsightsRequest, calculate, INSIGHT_SLOTS, bounded_body

router = APIRouter(prefix="/api/workbench/v2")
VERSION = "veus-controlled-analysis-v1"
PARAMETERS = {
    "body.mass_excluding_components_kg": (100, 8000),
    "body.drag_coefficient": (0, 1),
    "body.frontal_area_m2": (0.2, 10),
    "body.rolling_resistance_coefficient": (0, 0.1),
    "battery.usable_capacity_kwh": (1, 300),
    "motor.rated_power_kw": (1, 1500),
}


class StudyRequest(StrictModel):
    schema_version: Literal[1] = 1
    kind: Literal["compare", "sensitivity", "battery_size"] = "compare"
    baseline: VehicleDesignV2
    modified: VehicleDesignV2 | None = None
    conditions: dict
    parameter: str = "body.drag_coefficient"
    values: list[float] = Field(default_factory=list, max_length=5)
    battery_mass_kg_per_usable_kwh: float | None = Field(default=None, gt=0, le=40)

    @field_validator("baseline", "modified", mode="before")
    @classmethod
    def complete(cls, v):
        return (
            v if v is None or isinstance(v, VehicleDesignV2) else explicit_snapshot(v)
        )

    @model_validator(mode="after")
    def bounds(self):
        if self.kind == "compare" and self.modified is None:
            raise ValueError("Modified snapshot required")
        if self.kind != "compare" and not 2 <= len(self.values) <= 5:
            raise ValueError("Use two to five explicit sweep values")
        if self.kind == "sensitivity" and self.parameter not in PARAMETERS:
            raise ValueError("Unsupported single parameter")
        if self.kind == "battery_size" and self.battery_mass_kg_per_usable_kwh is None:
            raise ValueError("Battery sizing requires explicit kg per usable kWh")
        if len(set(self.values)) != len(self.values):
            raise ValueError("Sweep values must be distinct")
        if "vehicle" in self.conditions:
            raise ValueError("Conditions must not override vehicle snapshots")
        # Strict shared contract rejects unknown controls and validates step budgets before any work.
        InsightsRequest(vehicle=self.baseline, **self.conditions)
        return self


def delta(a, b):
    if type(a) not in (int, float) or type(b) not in (int, float):
        return dict(
            absolute=None, percent=None, reason="Unavailable or inconclusive input"
        )
    return dict(
        absolute=b - a,
        percent=(b - a) / abs(a) * 100 if a != 0 else None,
        reason=None if a != 0 else "Zero baseline: percentage undefined",
    )


def changes(a, b, prefix=""):
    out = []
    for key in sorted(set(a) | set(b)):
        aa, bb = a.get(key), b.get(key)
        path = prefix + key
        if isinstance(aa, dict) and isinstance(bb, dict):
            out += changes(aa, bb, path + ".")
        elif aa != bb:
            out.append(dict(parameter=path, baseline=aa, modified=bb))
    return out


def variants(request):
    original = request.baseline.model_dump(mode="json")
    out = [("baseline", None, original)]
    if request.kind == "compare":
        return out + [("modified", None, request.modified.model_dump(mode="json"))]
    for i, value in enumerate(request.values):
        d = copy.deepcopy(original)
        if request.kind == "battery_size":
            if not 1 <= value <= 300:
                raise ValueError("Battery sweep usable kWh outside 1..300")
            fraction = (
                original["battery"]["gross_capacity_kwh"]
                / original["battery"]["usable_capacity_kwh"]
            )
            d["battery"].update(
                usable_capacity_kwh=value,
                gross_capacity_kwh=value * fraction,
                mass_kg=value * request.battery_mass_kg_per_usable_kwh,
            )
            d["component_ids"]["battery"] = "custom"
        else:
            lo, hi = PARAMETERS[request.parameter]
            if not lo <= value <= hi:
                raise ValueError("Parameter outside bounded envelope")
            group, key = request.parameter.split(".")
            d[group][key] = value
            d["component_ids"][group] = "custom"
        out.append((f"point-{i + 1}", value, d))
    return out


def run_study(request: StudyRequest):
    rows = []
    # Prevalidate all structural snapshots before launching a sweep. Incompatibilities are retained per point.
    raw = variants(request)
    for name, value, d in raw:
        try:
            analysis = calculate(InsightsRequest(vehicle=d, **request.conditions))
            rows.append(
                dict(
                    name=name,
                    parameter_value=value,
                    status=analysis["cycle"]["eligibility"]["status"],
                    error=None,
                    design=d,
                    analysis=analysis,
                )
            )
        except (ValueError, TypeError) as e:
            rows.append(
                dict(
                    name=name,
                    parameter_value=value,
                    status="inconclusive",
                    error=str(e),
                    design=d,
                    analysis=None,
                )
            )
    baseline = rows[0]["analysis"]
    keys = list(baseline["metrics"]) if baseline else []
    for row in rows:
        r = row["analysis"]
        row["configuration_sha256"] = hashlib.sha256(
            canonical(row["design"])
        ).hexdigest()
        row["changed_parameters"] = changes(
            request.baseline.model_dump(mode="json"), row["design"]
        )
        row["differences"] = (
            {
                k: delta(
                    baseline["metrics"][k]["value"]
                    if baseline["metrics"][k]["status"] == "available"
                    else None,
                    r["metrics"][k]["value"]
                    if r["metrics"][k]["status"] == "available"
                    else None,
                )
                for k in keys
            }
            if baseline and r
            else {}
        )
    matched = True
    warnings = []
    identities = {
        (
            r["analysis"]["cycle"]["scenario_sha256"],
            r["analysis"]["acceleration"]["scenario_sha256"],
        )
        for r in rows
        if r["analysis"]
    }
    if len(identities) > 1:
        matched = False
        warnings.append(
            "Scenarios differ in driving conditions; do not interpret differences as controlled design effects"
        )
    if not matched:
        for row in rows:
            row["differences"] = {}
    result = dict(
        schema_version=1,
        model_version=VERSION,
        request=request.model_dump(mode="json"),
        rows=rows,
        matched_conditions=matched,
        warnings=warnings,
        limitations=[
            "Illustrative controlled model study, not an optimizer or measured vehicle ranking.",
            "Battery-size studies scale pack mass with explicitly supplied kg per usable kWh and retain the original gross/usable ratio, voltage, resistance and current limits; these are assumptions, not pack engineering.",
            "Usable-capacity-only sensitivity holds other fields fixed by design; it is not a realistic battery-sizing study.",
            "Incompatible points and infeasible cycles remain inconclusive; no failed result is dropped.",
            "No automatic optimum or parameter calibration. Physical validation INCONCLUSIVE.",
        ],
    )
    result["study_sha256"] = hashlib.sha256(canonical(result)).hexdigest()
    return result


@router.post("/design-analysis")
async def execute(request: Request):
    raw = await bounded_body(request, 2_000_000)
    try:
        parsed = StudyRequest.model_validate_json(raw)
        if INSIGHT_SLOTS.locked():
            raise HTTPException(429, "Two engineering analyses already active")
        await INSIGHT_SLOTS.acquire()
        try:
            return await run_in_threadpool(run_study, parsed)
        finally:
            INSIGHT_SLOTS.release()
    except (ValueError, ValidationError, TypeError) as e:
        raise HTTPException(422, str(e)) from e


def study_export(result, format):
    payload = {k: v for k, v in result.items() if k != "study_sha256"}
    if (
        result.get("model_version") != VERSION
        or result.get("study_sha256") != hashlib.sha256(canonical(payload)).hexdigest()
    ):
        raise ValueError("Frozen study hash mismatch")
    if format == "json":
        return dict(
            content=canonical(result).decode(),
            media_type="application/json",
            filename="veus-design-analysis.json",
        )
    rows = []
    for row in result["rows"]:
        r = row["analysis"]
        metrics = r["metrics"] if r else {}
        rows.append(
            dict(
                point=row["name"],
                parameter_value=row["parameter_value"],
                status=row["status"],
                configuration_sha256=row["configuration_sha256"],
                error=row["error"],
                **{k: v["value"] for k, v in metrics.items()},
            )
        )
    if format == "csv":
        stream = io.StringIO()
        fields = list(dict.fromkeys(k for row in rows for k in row))
        w = csv.DictWriter(stream, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
        return dict(
            content=stream.getvalue(),
            media_type="text/csv",
            filename="veus-design-analysis.csv",
        )
    if format != "html":
        raise ValueError("Unknown report format")
    # Snapshot-bearing portable report, no external assets or recomputation.
    from veus.testing.report import page, table

    fields = [
        "point",
        "parameter_value",
        "status",
        "modelled_consumption_kwh_100km",
        "cycle_equivalent_range_km",
        "modelled_acceleration_time_s",
    ]
    body = (
        "<p>Frozen study "
        + escape(result["study_sha256"])
        + "</p>"
        + table(fields, [[r.get(k) for k in fields] for r in rows])
    )
    values = [r.get("modelled_consumption_kwh_100km") for r in rows]
    maxv = max([v for v in values if isinstance(v, (int, float))] + [1])
    body += (
        '<svg viewBox="0 0 600 220" role="img" aria-label="Modelled consumption, kWh/100km">'
        + "".join(
            f'<rect x="{30 + i * 90}" y="{180 - (v / maxv * 140):.3f}" width="45" height="{v / maxv * 140:.3f}" fill="#39878e"/><text x="{30 + i * 90}" y="205">{escape(rows[i]["point"])}</text>'
            for i, v in enumerate(values)
            if isinstance(v, (int, float))
        )
        + "</svg>"
    )
    body += "<pre>" + escape(canonical(result).decode()) + "</pre>"
    return dict(
        content=page("Controlled Design Analysis", body),
        media_type="text/html",
        filename="veus-design-analysis.html",
    )


class ExportRequest(StrictModel):
    result: dict
    format: Literal["json", "csv", "html"] = "json"


@router.post("/design-analysis/export")
async def export_endpoint(request: Request):
    raw = await bounded_body(request, 12_000_000)
    try:
        parsed = ExportRequest.model_validate_json(raw)
        return await run_in_threadpool(study_export, parsed.result, parsed.format)
    except (ValueError, TypeError) as e:
        raise HTTPException(422, str(e)) from e
