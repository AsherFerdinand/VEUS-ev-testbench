"""Version 2 design snapshots: structural validation, not a compatibility verdict."""

from typing import Literal
from pydantic import Field
from veus.contracts import StrictModel

CATALOGUE_VERSION = "representative-v1"


class Battery(StrictModel):
    chemistry: Literal["unspecified", "LFP", "NMC"] = "unspecified"
    gross_capacity_kwh: float = Field(default=64, gt=0, le=300)
    usable_capacity_kwh: float = Field(default=60, gt=0, le=300)
    mass_kg: float = Field(default=420, gt=0, le=2000)
    minimum_voltage_v: float = Field(default=300, gt=0, le=1500)
    nominal_voltage_v: float = Field(default=400, gt=0, le=1500)
    maximum_voltage_v: float = Field(default=450, gt=0, le=1500)
    discharge_limit_a: float | None = Field(default=500, ge=0, le=3000)
    charge_limit_a: float | None = Field(default=200, ge=0, le=3000)
    resistance_ohm: float | None = Field(default=0.05, ge=0, le=5)


class Motor(StrictModel):
    topology: Literal["unspecified", "PMSM", "induction"] = "unspecified"
    rated_power_kw: float = Field(default=120, gt=0, le=1500)
    peak_power_kw: float | None = Field(default=150, gt=0, le=1500)
    rated_torque_nm: float = Field(default=200, gt=0, le=3000)
    peak_torque_nm: float | None = Field(default=300, gt=0, le=3000)
    maximum_speed_rpm: float | None = Field(default=12000, gt=0, le=40000)
    mass_kg: float | None = Field(default=70, gt=0, le=1000)
    drive_dc_minimum_v: float | None = Field(default=250, gt=0, le=1500)
    drive_dc_maximum_v: float | None = Field(default=500, gt=0, le=1500)
    efficiency_assumption: float | None = Field(default=0.94, gt=0, le=1)
    peak_duration_s: float | None = Field(default=None, gt=0, le=600)


class Inverter(StrictModel):
    technology: Literal["unspecified", "silicon", "SiC"] = "unspecified"
    minimum_dc_voltage_v: float | None = Field(default=250, gt=0, le=1500)
    maximum_dc_voltage_v: float = Field(default=500, gt=0, le=1500)
    continuous_power_kw: float = Field(default=150, gt=0, le=1500)
    peak_power_kw: float | None = Field(default=180, gt=0, le=1500)
    maximum_dc_current_a: float | None = Field(default=600, ge=0, le=3000)
    maximum_phase_current_a: float | None = Field(default=None, ge=0, le=3000)
    mass_kg: float | None = Field(default=25, gt=0, le=1000)
    efficiency_assumption: float | None = Field(default=0.97, gt=0, le=1)
    peak_duration_s: float | None = Field(default=None, gt=0, le=600)


class Body(StrictModel):
    mass_excluding_components_kg: float = Field(default=1200, gt=0, le=8000)
    drag_coefficient: float = Field(default=0.28, ge=0, le=1)
    frontal_area_m2: float = Field(default=2.2, gt=0, le=10)
    rolling_resistance_coefficient: float = Field(default=0.012, ge=0, le=0.1)
    wheel_radius_m: float = Field(default=0.32, gt=0, le=1.5)


class Charging(StrictModel):
    maximum_ac_kw: float = Field(default=11, gt=0, le=100)
    maximum_dc_kw: float = Field(default=100, gt=0, le=1000)
    minimum_dc_voltage_v: float | None = Field(default=250, gt=0, le=1500)
    maximum_dc_voltage_v: float = Field(default=500, gt=0, le=1500)
    maximum_dc_current_a: float | None = Field(default=300, ge=0, le=3000)
    mass_kg: float | None = Field(default=12, gt=0, le=500)
    efficiency_assumption: float | None = Field(default=0.93, gt=0, le=1)


class DCDC(StrictModel):
    input_minimum_v: float | None = Field(default=250, gt=0, le=1500)
    input_maximum_v: float | None = Field(default=500, gt=0, le=1500)
    output_voltage_v: float = Field(default=12, gt=0, le=60)
    rated_power_kw: float = Field(default=2, gt=0, le=30)
    mass_kg: float | None = Field(default=3, gt=0, le=100)


class Gearbox(StrictModel):
    reduction_ratio: float = Field(default=9, gt=0, le=30)
    mechanical_efficiency: float | None = Field(default=0.97, gt=0, le=1)
    maximum_input_torque_nm: float | None = Field(default=350, gt=0, le=4000)
    mass_kg: float | None = Field(default=18, gt=0, le=500)


class OperatingPoint(StrictModel):
    dc_voltage_v: float = Field(default=400, gt=0, le=1500)
    dc_power_kw: float = Field(default=80, ge=0, le=1500)
    motor_torque_nm: float = Field(default=100, ge=0, le=3000)


class Assumptions(StrictModel):
    drivetrain: Literal["single_equivalent_motor"] = "single_equivalent_motor"
    electrical_architecture: Literal["custom_dc_bus"] = "custom_dc_bus"
    thermal_model: Literal["not_modelled"] = "not_modelled"
    initial_soc: float = Field(default=0.8, ge=0, le=1)
    friction_coefficient: float = Field(default=0.9, ge=0, le=1.5)
    grade_percent: float = Field(default=0, ge=-30, le=30)
    air_density_kg_m3: float = Field(default=1.225, gt=0, le=2)
    regen_efficiency: float | None = Field(default=0.7, gt=0, le=1)


class VehicleDesignV2(StrictModel):
    schema_version: Literal[2] = 2
    name: str = Field(
        default="Study 01 · representative EV", min_length=1, max_length=100
    )
    classification: Literal["illustrative"] = "illustrative"
    catalogue_version: Literal["representative-v1"] = CATALOGUE_VERSION
    component_ids: dict[str, str] = Field(
        default_factory=lambda: {
            "battery": "battery-64",
            "motor": "motor-150",
            "inverter": "inverter-180",
            "body": "body-sedan",
            "charging": "charger-11",
            "dcdc": "dcdc-2",
            "gearbox": "gearbox-9",
        }
    )
    battery: Battery = Field(default_factory=Battery)
    motor: Motor = Field(default_factory=Motor)
    inverter: Inverter = Field(default_factory=Inverter)
    body: Body = Field(default_factory=Body)
    charging: Charging = Field(default_factory=Charging)
    dcdc: DCDC = Field(default_factory=DCDC)
    gearbox: Gearbox = Field(default_factory=Gearbox)
    operating_point: OperatingPoint = Field(default_factory=OperatingPoint)
    assumptions: Assumptions = Field(default_factory=Assumptions)
