"""Small typed representative catalogue. No commercial specifications are invented."""

from functools import lru_cache
from typing import Literal
from veus.contracts import StrictModel
from .design import VehicleDesignV2, CATALOGUE_VERSION


class ParameterEvidence(StrictModel):
    unit: str
    source_id: str = "veus-representative"
    classification: Literal["illustrative"] = "illustrative"
    operating_conditions: str = (
        "Conceptual nameplate study; no hardware test or temperature/duty calibration"
    )
    uncertainty: str = (
        "Not quantified; illustrative assumptions, not measured uncertainty"
    )


class Component(StrictModel):
    id: str
    kind: Literal["battery", "motor", "inverter", "charging", "dcdc", "gearbox", "body"]
    label: str
    manufacturer: str | None = None
    model: str | None = None
    technology: str
    parameters: dict[str, float | str | None]
    parameter_metadata: dict[str, ParameterEvidence]


def unit(field):
    for suffix, u in [
        ("_kwh", "kWh"),
        ("_kg", "kg"),
        ("_kw", "kW"),
        ("_nm", "N·m"),
        ("_rpm", "rpm"),
        ("_ohm", "Ω"),
        ("_m2", "m²"),
        ("_m", "m"),
        ("_a", "A"),
        ("_v", "V"),
        ("_s", "s"),
    ]:
        if field.endswith(suffix):
            return u
    return (
        "1"
        if field.endswith(("efficiency", "assumption", "ratio", "coefficient"))
        else "category"
    )


@lru_cache(maxsize=1)
def catalogue():
    d = VehicleDesignV2().model_dump(mode="json")
    definitions = [
        ("battery-64", "battery", "64 kWh representative pack", "unspecified", {}),
        (
            "battery-80",
            "battery",
            "80 kWh representative pack",
            "LFP label; same explicit loss assumption",
            dict(
                chemistry="LFP",
                gross_capacity_kwh=80,
                usable_capacity_kwh=75,
                mass_kg=520,
            ),
        ),
        ("motor-150", "motor", "150 kW peak representative motor", "unspecified", {}),
        (
            "motor-220",
            "motor",
            "220 kW peak representative motor",
            "PMSM label; efficiency explicitly assumed",
            dict(
                topology="PMSM",
                rated_power_kw=160,
                peak_power_kw=220,
                rated_torque_nm=250,
                peak_torque_nm=400,
                mass_kg=90,
            ),
        ),
        (
            "inverter-180",
            "inverter",
            "180 kW peak representative inverter",
            "unspecified",
            {},
        ),
        (
            "inverter-260",
            "inverter",
            "260 kW peak representative inverter",
            "SiC label; unchanged efficiency assumption",
            dict(
                technology="SiC",
                continuous_power_kw=200,
                peak_power_kw=260,
                maximum_dc_current_a=800,
                mass_kg=30,
            ),
        ),
        (
            "charger-11",
            "charging",
            "11 kW AC representative onboard charger",
            "AC onboard / DC offboard",
            {},
        ),
        (
            "charger-22",
            "charging",
            "22 kW AC representative onboard charger",
            "AC onboard / DC offboard",
            dict(
                maximum_ac_kw=22,
                maximum_dc_kw=150,
                maximum_dc_current_a=400,
                mass_kg=20,
            ),
        ),
        ("dcdc-2", "dcdc", "2 kW representative DC/DC", "HV to 12 V", {}),
        (
            "gearbox-9",
            "gearbox",
            "9:1 representative reduction",
            "Single reduction",
            {},
        ),
        (
            "gearbox-11",
            "gearbox",
            "11:1 representative reduction",
            "Single reduction",
            dict(reduction_ratio=11, maximum_input_torque_nm=450, mass_kg=22),
        ),
        (
            "body-sedan",
            "body",
            "Representative sedan body + residual systems",
            "Mass excludes listed subsystem masses",
            {},
        ),
        (
            "body-compact",
            "body",
            "Representative compact body + residual systems",
            "Mass excludes listed subsystem masses",
            dict(
                mass_excluding_components_kg=1050,
                frontal_area_m2=2.05,
                drag_coefficient=0.30,
            ),
        ),
    ]
    records = []
    for id, kind, label, tech, changes in definitions:
        values = d[kind] | changes
        records.append(
            Component(
                id=id,
                kind=kind,
                label=label,
                technology=tech,
                parameters=values,
                parameter_metadata={k: ParameterEvidence(unit=unit(k)) for k in values},
            ).model_dump(mode="json")
        )
    return dict(
        schema_version=1,
        version=CATALOGUE_VERSION,
        sources=[
            dict(
                id="veus-representative",
                title="VEUS representative analytical design assumptions",
                url="/engineering-docs/veus2/design-engineering.md",
                publication_date="2026-11-20",
                retrieved_on=None,
                authority="VEUS illustrative design study, not a manufacturer",
                classification="illustrative",
                limitations="No commercial datasheet retrieval or manufacturer values. Missing peak durations, phase current data and calibrated efficiency maps remain missing.",
            )
        ],
        components=records,
    )


def check_references(design):
    records = {c["id"]: c for c in catalogue()["components"]}
    overrides = {}
    errors = []
    kinds = {"battery", "motor", "inverter", "charging", "dcdc", "gearbox", "body"}
    for kind, id in design.component_ids.items():
        if kind not in kinds:
            errors.append(f"Unknown component kind: {kind}")
            continue
        if id == "custom":
            continue
        if id not in records or records[id]["kind"] != kind:
            errors.append(
                f"Unknown or mismatched catalogue component reference: {kind}"
            )
            continue
        current = getattr(design, kind).model_dump(mode="json")
        changed = [
            key
            for key, value in records[id]["parameters"].items()
            if current[key] != value
        ]
        if changed:
            overrides[kind] = changed
    return dict(overrides=overrides, errors=errors)
