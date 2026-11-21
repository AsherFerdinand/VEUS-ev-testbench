"""Click-triggered, bounded cycle/performance insights from the retained Lab runner."""

import asyncio
import csv
import hashlib
import io
import math
from html import escape
from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from pydantic import (
    Field,
    field_validator,
    model_validator,
    model_serializer,
    ValidationError,
)
from starlette.concurrency import run_in_threadpool
from veus.contracts import StrictModel
from veus.replay.analysis import canonical
from veus.lab.schema import LabRequest, ExperimentConfig
from veus.lab.runner import run
from veus.lab.profiles import builtin_profile, profile_distance
from .adapter import ACKNOWLEDGEMENTS
from .design import VehicleDesignV2
from .engineering import explicit_snapshot, evaluate

MODEL_VERSION = "veus-insights-v1"
router = APIRouter(prefix="/api/workbench/v2")
INSIGHT_SLOTS = asyncio.Semaphore(2)
PREVIEW_LIMIT = 400
MIN_CYCLE_DISTANCE_M = 100.0
MAX_CYCLE_TRACKING_ERROR_MS = 0.05


class InsightsRequest(StrictModel):
    vehicle: VehicleDesignV2
    acknowledgements: list[
        Literal[
            "illustrative_parameters",
            "constant_efficiency",
            "constant_ocv",
            "longitudinal_only",
            "unmodelled_thermal_charging",
        ]
    ] = Field(default_factory=list, max_length=5)
    profile_id: Literal["udds", "hwfet", "urban", "motorway"] = "urban"
    daily_distance_km: float = Field(default=40, ge=0, le=1000)
    tariff_eur_kwh: float = Field(default=0.3, ge=0, le=10)
    charging_efficiency: float | None = Field(default=None, gt=0, le=1)
    driving_days: int | None = Field(default=20, ge=0, le=31)
    acceleration_target_ms: float = Field(default=27.7777777778, gt=0, le=60)
    acceleration_duration_s: float = Field(default=30, ge=1, le=120)
    dt_s: float = Field(default=0.2, ge=0.05, le=0.25)
    efficiency_model: Literal["illustrative_map"] | None = None

    @model_serializer(mode="wrap")
    def omit_legacy_efficiency_option(self, handler):
        values = handler(self)
        if values.get("efficiency_model") is None:
            values.pop("efficiency_model", None)
        return values

    @field_validator("vehicle", mode="before")
    @classmethod
    def complete_vehicle(cls, value):
        return value if isinstance(value, VehicleDesignV2) else explicit_snapshot(value)

    @model_validator(mode="after")
    def explicit_assumptions(self):
        if set(self.acknowledgements) != set(ACKNOWLEDGEMENTS):
            raise ValueError(
                "All model assumptions must be explicitly acknowledged before calculating insights"
            )
        ExperimentConfig(
            kind="acceleration", duration_s=self.acceleration_duration_s, dt_s=self.dt_s
        )
        return self


def _finite_positive(value, name, allow_zero=False):
    if (
        not isinstance(value, (int, float))
        or not math.isfinite(value)
        or (value < 0 if allow_zero else value <= 0)
    ):
        raise ValueError(
            name
            + " must be finite and "
            + ("nonnegative" if allow_zero else "positive")
        )


def cycle_range_km(usable_energy_kwh, stored_consumption_kwh_100km):
    """Cycle-equivalent model reservoir range, never a certified/remaining-range value."""
    _finite_positive(usable_energy_kwh, "Usable energy")
    _finite_positive(stored_consumption_kwh_100km, "Stored-energy consumption")
    return 100 * usable_energy_kwh / stored_consumption_kwh_100km


def energy_economics(
    consumption_kwh_100km,
    daily_distance_km,
    tariff_eur_kwh,
    charging_efficiency=None,
    driving_days=20,
):
    """Independent user-assumption arithmetic; no live tariff or implicit charger loss."""
    _finite_positive(consumption_kwh_100km, "Consumption")
    _finite_positive(daily_distance_km, "Daily distance", True)
    _finite_positive(tariff_eur_kwh, "Tariff", True)
    if charging_efficiency is not None:
        _finite_positive(charging_efficiency, "Charging efficiency")
        if charging_efficiency > 1:
            raise ValueError("Charging efficiency must not exceed one")
    if driving_days is not None and (
        type(driving_days) is not int or not 0 <= driving_days <= 31
    ):
        raise ValueError("Driving days must be an integer in 0..31 or null")
    battery = daily_distance_km * consumption_kwh_100km / 100
    grid = battery / charging_efficiency if charging_efficiency is not None else None
    result = dict(
        daily_battery_energy_kwh=battery,
        daily_grid_energy_kwh=grid,
        daily_battery_energy_cost_eur=battery * tariff_eur_kwh,
        daily_electricity_cost_eur=grid * tariff_eur_kwh if grid is not None else None,
    )
    for key, value in list(result.items()):
        result[key.replace("daily_", "monthly_")] = (
            value * driving_days
            if value is not None and driving_days is not None
            else None
        )
    return result


def cycle_eligibility(result, profile, usable_energy_kwh):
    """Gate extrapolation from a complete meaningful cycle, not its requested trace."""
    summary = result["summary"]
    trace = result["trace"]
    terminal = summary["net_battery_energy_kwh"]
    depletion = terminal + summary["battery_heat_kwh"]
    distance = summary["distance_m"]
    reasons = []
    if profile_distance(profile) is None:
        reasons.append("Profile contains an unresolved time gap")
    if (
        abs(summary["duration_s"] - profile.time_s[-1]) > 1e-7
        or not trace
        or abs(trace[-1]["time_s"] - profile.time_s[-1]) > 1e-7
    ):
        reasons.append("The complete source cycle was not executed")
    if summary["requested_motion_infeasible_duration_s"] > 1e-8:
        reasons.append(
            "The cycle contains physically infeasible target-motion intervals"
        )
    if (
        summary.get("maximum_tracking_error_ms") is None
        or summary["maximum_tracking_error_ms"] > MAX_CYCLE_TRACKING_ERROR_MS
    ):
        reasons.append(
            "Achieved speed does not follow the requested cycle within the 0.05 m/s extrapolation tolerance"
        )
    if any(row["soc"] <= 1e-8 or row["soc"] >= 1 - 1e-8 for row in trace):
        reasons.append("A battery SOC boundary was encountered")
    if distance < MIN_CYCLE_DISTANCE_M:
        reasons.append(
            "Achieved cycle distance is below the 100 m minimum for extrapolation"
        )
    if not math.isfinite(depletion) or depletion <= 1e-6:
        reasons.append("Stored-energy depletion is not meaningfully positive")
    soc_depletion = usable_energy_kwh * (summary["initial_soc"] - summary["final_soc"])
    if abs(soc_depletion - depletion) > 1e-7 * max(1.0, abs(depletion)):
        reasons.append(
            "Stored-energy and SOC accounting do not agree within floating-point tolerance"
        )
    consumption = depletion * 100000 / distance if distance > 0 else None
    return dict(
        status="available" if not reasons else "inconclusive",
        reasons=reasons,
        stored_depletion_kwh=depletion,
        terminal_net_energy_kwh=terminal,
        battery_heat_kwh=summary["battery_heat_kwh"],
        stored_consumption_kwh_100km=consumption,
        range_basis="Usable model chemical-energy reservoir divided by achieved stored-energy depletion per distance; includes battery heat",
        maximum_tracking_error_tolerance_ms=MAX_CYCLE_TRACKING_ERROR_MS,
    )


def metric(value, unit, basis, status="available", reason=None):
    return dict(value=value, unit=unit, status=status, basis=basis, reason=reason)


def compact_run(result):
    trace = result["trace"]
    n = min(len(trace), PREVIEW_LIMIT)
    indices = (
        [round(i * (len(trace) - 1) / (n - 1)) for i in range(n)] if n > 1 else [0]
    )
    fields = [
        "time_s",
        "speed_ms",
        "target_speed_ms",
        "soc",
        "battery_power_w",
        "limits",
        "energy_balance_error_j",
    ]
    mapped = result["provenance"].get("powertrain_map")
    if mapped:
        fields += [
            "motor_rpm",
            "motor_torque_nm",
            "motor_efficiency",
            "motor_ac_power_w",
            "motor_loss_w",
            "inverter_loss_w",
            "gearbox_loss_w",
        ]
    compact = dict(
        run_sha256=result["run_sha256"],
        model_version=result["model_version"],
        scenario_sha256=hashlib.sha256(
            canonical(
                dict(
                    experiment=result["experiment"],
                    profile=result["request"]["profile"],
                    route=result["request"]["route"],
                    conditions={
                        key: result["vehicle"]["assumptions"][key]
                        for key in [
                            "initial_soc",
                            "friction_coefficient",
                            "air_density_kg_m3",
                        ]
                    },
                )
            )
        ).hexdigest(),
        summary=result["summary"],
        summary_units=result["summary_units"],
        limit_duration_s=result["limit_duration_s"],
        findings=result["findings"],
        preview_trace=[{k: trace[index][k] for k in fields} for index in indices],
        samples_simulated=len(trace),
        samples_returned=n,
        trace_scope="preview_only; selected original simulation rows, not the full trace",
        preview_method="Uniform index selection including first/last; no interpolated or fabricated samples",
        preview_fields=fields,
    )

    if mapped:
        compact["powertrain_map"] = mapped
    return compact


def calculate(request: InsightsRequest):
    profile = builtin_profile(request.profile_id)
    # No profile is trimmed, repeated or resampled to fit the integration budget.
    cycle_request = LabRequest(
        vehicle=request.vehicle,
        acknowledgements=request.acknowledgements,
        efficiency_model=request.efficiency_model,
        experiment=ExperimentConfig(
            kind="profile",
            mode="prescribed",
            duration_s=profile.time_s[-1],
            dt_s=request.dt_s,
            initial_speed_ms=profile.speed_ms[0],
            power_policy="continuous",
            route_grade_policy="require",
        ),
        profile=profile,
    )
    acceleration_request = LabRequest(
        vehicle=request.vehicle,
        acknowledgements=request.acknowledgements,
        efficiency_model=request.efficiency_model,
        experiment=ExperimentConfig(
            kind="acceleration",
            mode="predictive",
            duration_s=request.acceleration_duration_s,
            dt_s=request.dt_s,
            initial_speed_ms=0,
            target_speed_ms=request.acceleration_target_ms,
            power_policy="continuous",
        ),
    )
    cycle = run(cycle_request)
    acceleration = run(acceleration_request)
    usable = request.vehicle.battery.usable_capacity_kwh
    eligibility = cycle_eligibility(cycle, profile, usable)
    valid = eligibility["status"] == "available"
    reason = "; ".join(eligibility["reasons"]) or None
    stored_consumption = eligibility["stored_consumption_kwh_100km"]
    spec = evaluate(request.vehicle)["specifications"]
    metrics = dict(
        usable_battery_capacity_kwh=metric(
            usable,
            "kWh",
            "Explicit usable chemical-energy capacity in the selected model snapshot",
        ),
        total_vehicle_mass_kg=metric(
            spec["total_mass_kg"]["value"],
            "kg",
            "Existing explicit component/residual mass accounting",
        ),
        continuous_motor_power_kw=metric(
            request.vehicle.motor.rated_power_kw,
            "kW",
            "Declared continuous mechanical shaft rating; used by these experiments",
        ),
        peak_motor_power_kw=metric(
            request.vehicle.motor.peak_power_kw,
            "kW",
            "Declared peak shaft rating; not the operation policy for these runs",
            status="available"
            if request.vehicle.motor.peak_power_kw is not None
            else "unavailable",
            reason=None
            if request.vehicle.motor.peak_power_kw is not None
            else "Peak rating is unknown",
        ),
        achieved_cycle_distance_km=metric(
            cycle["summary"]["distance_m"] / 1000,
            "km",
            "Achieved constrained movement, not prescribed distance",
        ),
        terminal_consumption_kwh_100km=metric(
            cycle["summary"]["consumption_kwh_100km"],
            "kWh/100 km",
            "Descriptive achieved net terminal energy; excludes battery heat",
            status="available"
            if cycle["summary"]["consumption_kwh_100km"] is not None
            else "unavailable",
            reason=None
            if cycle["summary"]["consumption_kwh_100km"] is not None
            else "No achieved distance",
        ),
        modelled_consumption_kwh_100km=metric(
            stored_consumption if valid else None,
            "kWh/100 km",
            "Achieved stored-energy depletion = net terminal energy + battery heat; extrapolation gate applies",
            status=eligibility["status"],
            reason=reason,
        ),
        cycle_equivalent_range_km=metric(
            cycle_range_km(usable, stored_consumption) if valid else None,
            "km",
            "100 × usable model reservoir kWh / stored-depletion kWh per 100 km; not current-SOC remaining range or certified range",
            status=eligibility["status"],
            reason=reason,
        ),
        modelled_acceleration_time_s=metric(
            acceleration["summary"]["time_to_target_s"],
            "s",
            "Observed tick time from zero to the user-selected target under continuous-rating policy",
            status="available"
            if acceleration["summary"]["time_to_target_s"] is not None
            else "unavailable",
            reason=None
            if acceleration["summary"]["time_to_target_s"] is not None
            else "Target speed was not reached within the bounded experiment",
        ),
        acceleration_final_speed_ms=metric(
            acceleration["summary"]["final_speed_ms"],
            "m/s",
            "Achieved final speed in the bounded acceleration run; not maximum sustainable speed",
        ),
    )
    economics = (
        energy_economics(
            stored_consumption,
            request.daily_distance_km,
            request.tariff_eur_kwh,
            request.charging_efficiency,
            request.driving_days,
        )
        if valid
        else {
            key: None
            for key in [
                "daily_battery_energy_kwh",
                "daily_grid_energy_kwh",
                "daily_battery_energy_cost_eur",
                "daily_electricity_cost_eur",
                "monthly_battery_energy_kwh",
                "monthly_grid_energy_kwh",
                "monthly_battery_energy_cost_eur",
                "monthly_electricity_cost_eur",
            ]
        }
    )
    for key, value in economics.items():
        grid = "grid" in key or "electricity_cost" in key
        basis = (
            "User daily distance × eligible stored-depletion consumption /100"
            if not grid
            else "Battery depletion energy / explicitly supplied charging efficiency"
        )
        if "cost" in key:
            basis += (
                " × user tariff; battery-energy equivalent only, excludes charging losses"
                if "battery_energy_cost" in key
                else " × user electricity tariff"
            )
        if key.startswith("monthly"):
            basis += " × user selected driving days"
        unavailable_reason = reason
        status = eligibility["status"]
        if valid:
            status = "available" if value is not None else "unavailable"
            if grid and request.charging_efficiency is None:
                unavailable_reason = "No charging-efficiency assumption supplied; grid energy/cost cannot be inferred"
            elif key.startswith("monthly") and request.driving_days is None:
                unavailable_reason = "No monthly driving-day count supplied"
        metrics[key] = metric(
            value,
            "EUR" if key.endswith("eur") else "kWh",
            basis,
            status,
            unavailable_reason,
        )
    cycle_compact = compact_run(cycle)
    cycle_compact.update(
        profile_id=request.profile_id,
        source=profile.source.model_dump(mode="json"),
        eligibility=eligibility,
    )
    result = dict(
        schema_version=1,
        model_version=MODEL_VERSION,
        request=request.model_dump(mode="json"),
        configuration_sha256=hashlib.sha256(
            canonical(request.vehicle.model_dump(mode="json"))
        ).hexdigest(),
        cycle=cycle_compact,
        acceleration=compact_run(acceleration),
        metrics=metrics,
        assumptions=dict(
            power_policy="continuous",
            initial_soc=request.vehicle.assumptions.initial_soc,
            daily_distance_km=request.daily_distance_km,
            tariff_eur_kwh=request.tariff_eur_kwh,
            charging_efficiency=request.charging_efficiency,
            driving_days=request.driving_days,
            minimum_cycle_distance_m=MIN_CYCLE_DISTANCE_M,
        ),
        limitations=[
            "Modelled cycle-equivalent range, not certified EPA/WLTP or real-world range and not remaining range at current SOC.",
            "No top-speed/thermal-endurance solver is implemented; only bounded acceleration and achieved speeds are shown.",
            "Range assumes the same cycle consumption over the full usable model chemical-energy reservoir, with no temperature/ageing/auxiliary model.",
            "Charging efficiency and tariffs are user assumptions. Battery-energy cost is not grid electricity cost when charging efficiency is unknown.",
            "Compact traces are preview-only; full Lab requests and full-result hashes are retained for reproduction, not silently truncated evidence.",
            "Physical model validation remains INCONCLUSIVE.",
        ],
        provenance=dict(
            cycle_request=cycle_request.model_dump(mode="json"),
            acceleration_request=acceleration_request.model_dump(mode="json"),
        ),
    )
    result["insights_sha256"] = hashlib.sha256(canonical(result)).hexdigest()
    return result


async def bounded_body(request, limit):
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > limit:
            raise HTTPException(413, "Insights request exceeds bounded body size")
    return raw


@router.post("/insights")
async def insight_request(request: Request):
    raw = await bounded_body(request, 2_000_000)
    try:
        parsed = InsightsRequest.model_validate_json(raw)
        if INSIGHT_SLOTS.locked():
            raise HTTPException(
                429, "Two insight calculations are already active; retry when complete"
            )
        await INSIGHT_SLOTS.acquire()
        try:
            return await run_in_threadpool(calculate, parsed)
        finally:
            INSIGHT_SLOTS.release()
    except (ValidationError, ValueError, TypeError) as error:
        raise HTTPException(422, str(error)) from error


def insights_export(result, format):
    if (
        not isinstance(result, dict)
        or result.get("model_version") != MODEL_VERSION
        or result.get("schema_version") != 1
    ):
        raise ValueError("Unsupported insight result")
    value = {k: v for k, v in result.items() if k != "insights_sha256"}
    if result.get("insights_sha256") != hashlib.sha256(canonical(value)).hexdigest():
        raise ValueError("Insight result hash mismatch")
    InsightsRequest.model_validate(result["request"])
    if format == "json":
        return dict(
            content=canonical(result).decode(),
            media_type="application/json",
            filename="veus-engineering-insights.json",
        )
    if format == "csv":
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["metric", "value", "unit", "status", "basis", "reason"])
        for key, value in result["metrics"].items():
            writer.writerow(
                [
                    key,
                    *[
                        value.get(k)
                        for k in ["value", "unit", "status", "basis", "reason"]
                    ],
                ]
            )
        return dict(
            content=stream.getvalue(),
            media_type="text/csv",
            filename="veus-engineering-insights.csv",
        )
    if format != "html":
        raise ValueError("Unsupported insights export format")
    from veus.testing.report import page, table

    body = "<p>Insights SHA256: " + escape(result["insights_sha256"]) + "</p>"
    body += table(
        ["Quantity", "Value", "Unit", "Status", "Basis / reason"],
        [
            [
                k,
                m["value"],
                m["unit"],
                m["status"],
                m["basis"] + (" · " + m["reason"] if m["reason"] else ""),
            ]
            for k, m in result["metrics"].items()
        ],
    )
    body += (
        "<h2>Limitations</h2><ul>"
        + "".join("<li>" + escape(x) + "</li>" for x in result["limitations"])
        + "</ul>"
    )
    body += (
        "<h2>Frozen request, original-run hashes and reproduction requests</h2><pre>"
        + escape(
            canonical(
                dict(
                    request=result["request"],
                    cycle_run_sha256=result["cycle"]["run_sha256"],
                    acceleration_run_sha256=result["acceleration"]["run_sha256"],
                    provenance=result["provenance"],
                )
            ).decode()
        )
        + "</pre>"
    )
    return dict(
        content=page(
            "VEUS engineering insights",
            body,
            scope="Illustrative model-derived quantities. Not certified range or real-world validation.",
        ),
        media_type="text/html",
        filename="veus-engineering-insights.html",
    )


class InsightsExportRequest(StrictModel):
    result: dict
    format: Literal["json", "csv", "html"] = "json"


@router.post("/insights/export")
async def export_insights_request(request: Request):
    raw = await bounded_body(request, 2_000_000)
    try:
        parsed = InsightsExportRequest.model_validate_json(raw)
        return await run_in_threadpool(insights_export, parsed.result, parsed.format)
    except (ValidationError, ValueError, TypeError, KeyError) as error:
        raise HTTPException(422, str(error)) from error
