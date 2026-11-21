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
    # Additive fictional VEUS class records: original IDs/values remain immutable.
    class_definitions = [
        (
            "battery-s1",
            "battery",
            "S1 representative 60 kWh usable pack",
            "NMC label only",
            dict(chemistry="NMC", charge_limit_a=250, discharge_limit_a=700),
        ),
        (
            "motor-s1",
            "motor",
            "S1 representative 180 kW peak motor",
            "PMSM label only",
            dict(
                topology="PMSM",
                rated_power_kw=145,
                peak_power_kw=180,
                rated_torque_nm=220,
                peak_torque_nm=350,
                maximum_speed_rpm=14000,
                mass_kg=75,
            ),
        ),
        (
            "body-s1",
            "body",
            "S1 sedan body and residual systems",
            "Illustrative sedan",
            dict(
                mass_excluding_components_kg=1191,
                drag_coefficient=0.25,
                rolling_resistance_coefficient=0.011,
            ),
        ),
        (
            "battery-r1",
            "battery",
            "R1 representative 90 kWh usable pack",
            "NMC label only",
            dict(
                chemistry="NMC",
                gross_capacity_kwh=96,
                usable_capacity_kwh=90,
                mass_kg=560,
                minimum_voltage_v=600,
                nominal_voltage_v=800,
                maximum_voltage_v=900,
                discharge_limit_a=900,
                charge_limit_a=400,
                resistance_ohm=0.045,
            ),
        ),
        (
            "motor-r1",
            "motor",
            "R1 representative 450 kW peak motor",
            "PMSM label only",
            dict(
                topology="PMSM",
                rated_power_kw=300,
                peak_power_kw=450,
                rated_torque_nm=500,
                peak_torque_nm=800,
                maximum_speed_rpm=18000,
                mass_kg=100,
                drive_dc_minimum_v=500,
                drive_dc_maximum_v=950,
            ),
        ),
        (
            "inverter-r1",
            "inverter",
            "R1 representative 520 kW peak inverter",
            "SiC label only",
            dict(
                technology="SiC",
                minimum_dc_voltage_v=500,
                maximum_dc_voltage_v=950,
                continuous_power_kw=350,
                peak_power_kw=520,
                maximum_dc_current_a=1100,
                mass_kg=40,
            ),
        ),
        (
            "body-r1",
            "body",
            "R1 performance body and residual systems",
            "Illustrative performance body; no downforce model",
            dict(
                mass_excluding_components_kg=1201,
                drag_coefficient=0.30,
                frontal_area_m2=2.1,
                wheel_radius_m=0.335,
            ),
        ),
        (
            "battery-x1",
            "battery",
            "X1 representative 100 kWh usable pack",
            "LFP label only",
            dict(
                chemistry="LFP",
                gross_capacity_kwh=108,
                usable_capacity_kwh=100,
                mass_kg=650,
                minimum_voltage_v=350,
                nominal_voltage_v=450,
                maximum_voltage_v=510,
                discharge_limit_a=900,
                charge_limit_a=350,
            ),
        ),
        (
            "motor-x1",
            "motor",
            "X1 representative 250 kW peak motor",
            "Induction label only",
            dict(
                topology="induction",
                rated_power_kw=180,
                peak_power_kw=250,
                rated_torque_nm=350,
                peak_torque_nm=500,
                maximum_speed_rpm=14000,
                mass_kg=95,
                drive_dc_minimum_v=300,
                drive_dc_maximum_v=650,
            ),
        ),
        (
            "inverter-x1",
            "inverter",
            "X1 representative 300 kW peak inverter",
            "Silicon label only",
            dict(
                technology="silicon",
                minimum_dc_voltage_v=300,
                maximum_dc_voltage_v=650,
                continuous_power_kw=230,
                peak_power_kw=300,
                maximum_dc_current_a=1000,
                mass_kg=35,
            ),
        ),
        (
            "body-x1",
            "body",
            "X1 SUV body and residual systems",
            "Illustrative SUV",
            dict(
                mass_excluding_components_kg=1621,
                drag_coefficient=0.32,
                frontal_area_m2=2.75,
                wheel_radius_m=0.37,
                rolling_resistance_coefficient=0.013,
            ),
        ),
        (
            "charger-wide-22",
            "charging",
            "22 kW AC / 150 kW DC representative envelope",
            "Wide DC voltage; AC onboard and DC offboard",
            dict(
                maximum_ac_kw=22,
                maximum_dc_kw=150,
                minimum_dc_voltage_v=250,
                maximum_dc_voltage_v=950,
                maximum_dc_current_a=450,
                mass_kg=20,
            ),
        ),
        (
            "dcdc-wide-2",
            "dcdc",
            "Wide-voltage 2 kW representative DC/DC",
            "HV to 12 V",
            dict(input_maximum_v=950, mass_kg=4),
        ),
        (
            "gearbox-heavy-9",
            "gearbox",
            "9:1 representative high-torque reduction",
            "Single equivalent drive unit",
            dict(reduction_ratio=9, maximum_input_torque_nm=900, mass_kg=25),
        ),
    ]
    new_ids = {record[0] for record in class_definitions}
    records = []
    for id, kind, label, tech, changes in definitions + class_definitions:
        values = d[kind] | changes
        records.append(
            Component(
                id=id,
                kind=kind,
                label=label,
                technology=tech,
                parameters=values,
                parameter_metadata={
                    k: ParameterEvidence(
                        unit=unit(k),
                        source_id="veus-classes-2.3.2"
                        if id in new_ids
                        else "veus-representative",
                    )
                    for k in values
                },
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
            ),
            dict(
                id="veus-classes-2.3.2",
                title="VEUS S1/R1/X1 fictional representative class assumptions",
                url="/engineering-docs/veus2/design-engineering.md",
                publication_date="2026-11-21",
                retrieved_on=None,
                authority="Original VEUS illustrative design study, not a manufacturer",
                classification="illustrative",
                limitations="Fictional class envelopes. No commercial specifications, CAD dimensions, energy-density inference, downforce or performance validation. Original catalogue record values are unchanged.",
            ),
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
