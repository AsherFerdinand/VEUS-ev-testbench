"""Transparent specification calculations and bounded design API, no fake outcomes."""

import hashlib
import json
from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from pydantic import Field, ValidationError
from veus.contracts import StrictModel
from veus.replay.analysis import canonical
from .design import VehicleDesignV2
from .catalogue import catalogue, check_references, unit
from .adapter import readiness, build_models, mapped_parameters, ACKNOWLEDGEMENTS

router = APIRouter(prefix="/api/workbench/v2")


class AdapterRequest(StrictModel):
    design: VehicleDesignV2
    acknowledgements: list[
        Literal[
            "illustrative_parameters",
            "constant_efficiency",
            "constant_ocv",
            "longitudinal_only",
            "unmodelled_thermal_charging",
        ]
    ] = Field(default_factory=list, max_length=5)


class CompareRequest(StrictModel):
    baseline: VehicleDesignV2
    modified: VehicleDesignV2


def specification(value, unit, equation, inputs, assumptions, reason=None):
    return dict(
        value=value,
        unit=unit,
        equation=equation,
        inputs=inputs,
        assumptions=assumptions,
        classification="derived from illustrative parameters",
        unavailable_reason=reason if value is None else None,
    )


def evaluate(d):
    references = check_references(d)
    checks = []

    def add(id, status, explanation):
        checks.append(dict(id=id, status=status, explanation=explanation))

    def bound(id, available, condition, explanation):
        add(
            id,
            "insufficient_data"
            if not available
            else ("compatible_within_checked_limits" if condition else "incompatible"),
            explanation,
        )

    add(
        "catalogue_references",
        "incompatible" if references["errors"] else "compatible_within_checked_limits",
        "; ".join(references["errors"])
        or "Component IDs match their declared kinds and catalogue version; custom snapshots retain explicit resolved values.",
    )
    b, m, i, g, c, o = (
        d.battery,
        d.motor,
        d.inverter,
        d.gearbox,
        d.charging,
        d.operating_point,
    )
    bound(
        "battery_energy",
        True,
        b.usable_capacity_kwh <= b.gross_capacity_kwh,
        "Usable energy must not exceed gross energy.",
    )
    bound(
        "battery_voltage_order",
        True,
        b.minimum_voltage_v <= b.nominal_voltage_v <= b.maximum_voltage_v,
        "Battery minimum <= nominal <= maximum voltage is required.",
    )
    bound(
        "battery_inverter_voltage",
        i.minimum_dc_voltage_v is not None,
        i.minimum_dc_voltage_v is not None
        and i.minimum_dc_voltage_v <= b.minimum_voltage_v
        and b.maximum_voltage_v <= i.maximum_dc_voltage_v,
        "Inverter DC input envelope must contain the complete declared battery range.",
    )
    bound(
        "motor_drive_voltage",
        m.drive_dc_minimum_v is not None and m.drive_dc_maximum_v is not None,
        m.drive_dc_minimum_v is not None
        and m.drive_dc_maximum_v is not None
        and m.drive_dc_minimum_v <= b.minimum_voltage_v
        and b.maximum_voltage_v <= m.drive_dc_maximum_v,
        "Motor drive DC envelope is a declared drive input range, not motor phase voltage.",
    )
    bound(
        "motor_peak_order",
        m.peak_power_kw is not None and m.peak_torque_nm is not None,
        m.peak_power_kw is not None
        and m.peak_torque_nm is not None
        and m.rated_power_kw <= m.peak_power_kw
        and m.rated_torque_nm <= m.peak_torque_nm,
        "Motor peak power/torque must be at least their rated values; these maxima need not coincide.",
    )
    bound(
        "inverter_peak_order",
        i.peak_power_kw is not None,
        i.peak_power_kw is not None and i.continuous_power_kw <= i.peak_power_kw,
        "Inverter peak AC output rating must be at least its continuous AC output rating.",
    )
    eta = m.efficiency_assumption
    bound(
        "rated_motor_inverter_power",
        eta is not None,
        eta is not None and m.rated_power_kw / eta <= i.continuous_power_kw,
        "Motor mechanical rated power / assumed motor efficiency must fit inverter continuous AC output power.",
    )
    bound(
        "peak_motor_inverter_power",
        eta is not None and m.peak_power_kw is not None and i.peak_power_kw is not None,
        eta is not None
        and m.peak_power_kw is not None
        and i.peak_power_kw is not None
        and m.peak_power_kw / eta <= i.peak_power_kw,
        "Assumed motor electrical peak demand must fit inverter peak AC output rating; duty duration is assessed separately.",
    )
    bound(
        "gearbox_torque",
        m.peak_torque_nm is not None and g.maximum_input_torque_nm is not None,
        m.peak_torque_nm is not None
        and g.maximum_input_torque_nm is not None
        and m.peak_torque_nm <= g.maximum_input_torque_nm,
        "Gearbox input rating is compared with motor peak input torque, not multiplied wheel torque.",
    )
    bound(
        "charging_voltage",
        c.minimum_dc_voltage_v is not None,
        c.minimum_dc_voltage_v is not None
        and c.minimum_dc_voltage_v <= b.minimum_voltage_v
        and b.maximum_voltage_v <= c.maximum_dc_voltage_v,
        "Declared charging DC envelope must contain battery range; connector/protocol/insulation compatibility is not established.",
    )
    bound(
        "dcdc_voltage",
        d.dcdc.input_minimum_v is not None and d.dcdc.input_maximum_v is not None,
        d.dcdc.input_minimum_v is not None
        and d.dcdc.input_maximum_v is not None
        and d.dcdc.input_minimum_v <= b.minimum_voltage_v
        and b.maximum_voltage_v <= d.dcdc.input_maximum_v,
        "DC/DC input range must contain the battery DC range.",
    )
    bound(
        "operating_voltage",
        True,
        b.minimum_voltage_v <= o.dc_voltage_v <= b.maximum_voltage_v
        and (i.minimum_dc_voltage_v is None or i.minimum_dc_voltage_v <= o.dc_voltage_v)
        and o.dc_voltage_v <= i.maximum_dc_voltage_v,
        "The defined DC operating-point voltage must lie within battery and inverter limits.",
    )
    current = o.dc_power_kw * 1000 / o.dc_voltage_v
    bound(
        "operating_discharge_current",
        b.discharge_limit_a is not None,
        b.discharge_limit_a is not None and current <= b.discharge_limit_a,
        "Required current at the explicitly defined positive-discharge DC operating point must fit the battery discharge limit.",
    )
    bound(
        "inverter_dc_current",
        i.maximum_dc_current_a is not None,
        i.maximum_dc_current_a is not None and current <= i.maximum_dc_current_a,
        "DC operating current is compared with inverter DC current rating; DC and phase current must not be equated.",
    )
    bound(
        "operating_inverter_power",
        i.efficiency_assumption is not None and i.peak_power_kw is not None,
        i.efficiency_assumption is not None
        and i.peak_power_kw is not None
        and o.dc_power_kw * i.efficiency_assumption <= i.peak_power_kw,
        "At the defined inverter DC input point, assumed AC output power must not exceed its peak AC output rating; this does not establish continuous duty.",
    )
    bound(
        "operating_motor_torque",
        m.peak_torque_nm is not None,
        m.peak_torque_nm is not None and o.motor_torque_nm <= m.peak_torque_nm,
        "Illustrative torque for the wheel-torque calculation must fit the motor torque envelope; no speed point is implied.",
    )
    if b.charge_limit_a is None or c.maximum_dc_current_a is None:
        add(
            "charging_acceptance",
            "insufficient_data",
            "Battery and charger charge-current limits are required; a nameplate power is not a charging curve.",
        )
    else:
        charging_current = c.maximum_dc_kw * 1000 / b.nominal_voltage_v
        add(
            "charging_acceptance",
            "warning"
            if charging_current > min(b.charge_limit_a, c.maximum_dc_current_a)
            else "compatible_within_checked_limits",
            "At nominal voltage, declared DC peak charging power requires %.3f A; acceptance is limited to min(battery, charger current), not evidence of attainable sustained charge power."
            % charging_current,
        )
    if m.peak_duration_s is None or i.peak_duration_s is None:
        add(
            "peak_duration",
            "insufficient_data",
            "Motor and inverter peak-rating durations are unknown. Continuous thermal/duty compatibility cannot be claimed.",
        )
    else:
        bound(
            "peak_duration",
            True,
            i.peak_duration_s >= m.peak_duration_s,
            "Inverter declared peak duration must cover motor peak duration; equal durations do not establish matched thermal conditions.",
        )
    add(
        "phase_current",
        "insufficient_data",
        "Motor torque-current/back-EMF/control maps are unavailable; inverter phase current alone cannot establish motor phase compatibility.",
    )
    add(
        "physical_conditions",
        "warning",
        "Illustrative nameplate checks do not establish thermal, mechanical packaging, cell safety or production compatibility.",
    )
    masses = {
        "body_and_unlisted_systems_kg": d.body.mass_excluding_components_kg,
        **{
            kind + "_kg": getattr(d, kind).mass_kg
            for kind in ["battery", "motor", "inverter", "charging", "dcdc", "gearbox"]
        },
    }
    mass = sum(masses.values()) if all(v is not None for v in masses.values()) else None
    bound(
        "mass_accounting",
        mass is not None,
        True,
        "Body mass explicitly excludes the six listed component masses, which are each added exactly once. Unlisted systems are included in body/residual mass.",
    )
    specs = {
        "total_mass_kg": specification(
            mass,
            "kg",
            "m_total = m_body_residual + Σ m_listed_components",
            masses,
            [
                "Residual body includes wheels, thermal plumbing, wiring, BMS and other unlisted systems; excludes each of the six explicit masses."
            ],
            "At least one component mass is unknown.",
        ),
        "gross_energy_kwh": specification(
            b.gross_capacity_kwh,
            "kWh",
            "E_gross = declared gross energy",
            {"gross_capacity_kwh": b.gross_capacity_kwh},
            ["Declared illustrative input, not a capacity test."],
        ),
        "usable_energy_kwh": specification(
            b.usable_capacity_kwh,
            "kWh",
            "E_usable = declared usable energy",
            {"usable_capacity_kwh": b.usable_capacity_kwh},
            ["No cycle/range or temperature adjustment."],
        ),
        "gross_nominal_capacity_ah": specification(
            b.gross_capacity_kwh * 1000 / b.nominal_voltage_v,
            "Ah",
            "Q_approx = E_gross[kWh] × 1000 / V_nominal[V]",
            {
                "gross_capacity_kwh": b.gross_capacity_kwh,
                "nominal_voltage_v": b.nominal_voltage_v,
            },
            [
                "Approximation at nominal voltage, not coulomb-counted measured capacity."
            ],
        ),
        "usable_nominal_capacity_ah": specification(
            b.usable_capacity_kwh * 1000 / b.nominal_voltage_v,
            "Ah",
            "Q_approx = E_usable[kWh] × 1000 / V_nominal[V]",
            {
                "usable_capacity_kwh": b.usable_capacity_kwh,
                "nominal_voltage_v": b.nominal_voltage_v,
            },
            ["Approximation at nominal voltage."],
        ),
        "peak_power_to_weight_kw_per_tonne": specification(
            m.peak_power_kw * 1000 / mass
            if m.peak_power_kw is not None and mass is not None
            else None,
            "kW/t",
            "P_specific = P_motor_peak[kW] / (m_total[kg]/1000)",
            {"peak_power_kw": m.peak_power_kw, "mass_kg": mass},
            [
                "Motor nameplate ratio; not achieved acceleration or feasible continuous power."
            ],
            "Peak motor power or total mass unavailable.",
        ),
        "required_dc_current_a": specification(
            current,
            "A",
            "I_DC = P_DC[kW] × 1000 / V_DC[V]",
            o.model_dump(),
            [
                "Positive DC input power at this defined operating point; no battery sag or auxiliary-load estimate."
            ],
        ),
        "wheel_torque_nm": specification(
            o.motor_torque_nm * g.reduction_ratio * g.mechanical_efficiency
            if g.mechanical_efficiency is not None
            else None,
            "N·m",
            "T_wheel = T_motor × reduction_ratio × η_gear",
            {
                "motor_torque_nm": o.motor_torque_nm,
                "reduction_ratio": g.reduction_ratio,
                "mechanical_efficiency": g.mechanical_efficiency,
            },
            [
                "Idealized combined driven-wheel torque before tyre traction limits; constant explicit mechanical efficiency."
            ],
            "Gearbox efficiency assumption unavailable.",
        ),
        "drag_area_m2": specification(
            d.body.drag_coefficient * d.body.frontal_area_m2,
            "m²",
            "CdA = Cd × A",
            {
                "drag_coefficient": d.body.drag_coefficient,
                "frontal_area_m2": d.body.frontal_area_m2,
            },
            [
                "Declared drag coefficient and frontal area; no coast-down/wind-tunnel validation."
            ],
        ),
    }
    statuses = {c["status"] for c in checks}
    status = next(
        (s for s in ["incompatible", "insufficient_data", "warning"] if s in statuses),
        "compatible_within_checked_limits",
    )
    normalized = d.model_dump(mode="json")
    return dict(
        design=normalized,
        configuration_sha256=hashlib.sha256(canonical(normalized)).hexdigest(),
        checks=checks,
        compatibility_status=status,
        specifications=specs,
        catalogue_overrides=references["overrides"],
        simulation_readiness=readiness(d, checks, mass),
        unavailable=[
            "range",
            "acceleration_prediction",
            "energy_consumption",
            "charging_time",
            "cost",
            "physical_validation",
        ],
    )


async def body_json(request, limit=64_000):
    body = bytearray()
    async for part in request.stream():
        body.extend(part)
        if len(body) > limit:
            raise HTTPException(413, "Design request exceeds 64 KB")
    return body


@router.get("/catalogue")
def get_catalogue():
    return catalogue()


@router.get("/design")
def get_design():
    return VehicleDesignV2().model_dump(mode="json")


@router.get("/schema")
def get_schema():
    schema = VehicleDesignV2.model_json_schema()
    schema["required"] = list(schema["properties"])
    for definition in schema.get("$defs", {}).values():
        if "properties" in definition:
            definition["required"] = list(definition["properties"])
    return schema


def explicit_snapshot(value):
    """Imports are complete resolved snapshots; missing is never a default vehicle."""
    if not isinstance(value, dict):
        raise ValueError("Design must be a complete versioned object")
    template = VehicleDesignV2().model_dump(mode="json")
    missing = []
    for key, expected in template.items():
        if key not in value:
            missing.append(key)
        elif isinstance(expected, dict):
            if not isinstance(value[key], dict):
                raise ValueError(f"{key} must be an object")
            missing.extend(
                key + "." + field for field in expected if field not in value[key]
            )
    if missing:
        raise ValueError(
            "Incomplete resolved design snapshot: "
            + ", ".join(missing)
            + ". Use explicit null for supported unknown values, not omitted fields."
        )
    return value


@router.post("/evaluate")
async def evaluate_request(request: Request):
    body = await body_json(request)
    try:
        return evaluate(
            VehicleDesignV2.model_validate(explicit_snapshot(json.loads(body)))
        )
    except (ValidationError, ValueError) as e:
        raise HTTPException(422, str(e)) from e


@router.post("/adapter")
async def adapter_request(request: Request):
    body = await body_json(request)
    try:
        raw = json.loads(body)
        if not isinstance(raw, dict):
            raise ValueError("Request must be an object")
        explicit_snapshot(raw.get("design"))
        req = AdapterRequest.model_validate(raw)
        d = req.design
        result = evaluate(d)
        mass = result["specifications"]["total_mass_kg"]["value"]
        build_models(d, result["checks"], mass, req.acknowledgements)
        return dict(
            configuration_sha256=result["configuration_sha256"],
            status="prepared_for_model_inspection",
            ready=True,
            scope="Existing model objects constructed; no experiment executed and no coupled runner supplied.",
            mappings=mapped_parameters(d, mass),
            acknowledgements=ACKNOWLEDGEMENTS,
            limitations=result["simulation_readiness"]["limitations"],
        )
    except (ValidationError, ValueError, TypeError) as e:
        raise HTTPException(422, str(e)) from e


@router.post("/compare")
async def compare_request(request: Request):
    body = await body_json(request, 128_000)
    try:
        raw = json.loads(body)
        if not isinstance(raw, dict):
            raise ValueError("Request must be an object")
        explicit_snapshot(raw.get("baseline"))
        explicit_snapshot(raw.get("modified"))
        req = CompareRequest.model_validate(raw)
        first = evaluate(req.baseline)
        second = evaluate(req.modified)
        differences = []
        for key, a in first["specifications"].items():
            b = second["specifications"][key]
            av, bv = a["value"], b["value"]
            differences.append(
                dict(
                    key=key,
                    unit=a["unit"],
                    baseline=av,
                    modified=bv,
                    delta=bv - av if av is not None and bv is not None else None,
                )
            )
        changed = []
        for group, av in first["design"].items():
            if not isinstance(av, dict) or group == "component_ids":
                continue
            for field, a in av.items():
                b = second["design"][group][field]
                if a != b:
                    changed.append(
                        dict(
                            key=group + "." + field,
                            unit=unit(field),
                            baseline=a,
                            modified=b,
                            delta=b - a
                            if type(a) in [int, float] and type(b) in [int, float]
                            else None,
                        )
                    )
        return dict(
            baseline=first,
            modified=second,
            differences=differences,
            changed_parameters=changed,
            scope="Specification comparison only; no simulated outcomes or efficiency ranking.",
        )
    except (ValidationError, ValueError, TypeError) as e:
        raise HTTPException(422, str(e)) from e


@router.post("/migrate")
async def reject_ambiguous_legacy_design(request: Request):
    await body_json(request)
    raise HTTPException(
        422,
        "Version 1 uses body mass excluding battery only and lacks the component masses, torque, speed and electrical assumptions required by version 2. Automatic migration would invent values or double-count mass. Create a version 2 design, explicitly enter the body/residual mass excluding all six listed components, copy verified values, and review the unknown fields before saving. The original version 1 file remains usable through the retained foundation API.",
    )
