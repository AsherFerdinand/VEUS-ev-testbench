"""Versioned design intent. No technology-to-efficiency or RunConfig conversion."""

from typing import Literal
from pydantic import Field, model_validator
from veus.contracts import StrictModel


class Battery(StrictModel):
    chemistry: Literal["unspecified", "LFP", "NMC"] = "unspecified"
    gross_capacity_kwh: float = Field(default=64, gt=0, le=300)
    usable_capacity_kwh: float = Field(default=60, gt=0, le=300)
    mass_kg: float = Field(default=420, gt=0, le=2000)
    minimum_voltage_v: float = Field(default=300, gt=0, le=1500)
    nominal_voltage_v: float = Field(default=400, gt=0, le=1500)
    maximum_voltage_v: float = Field(default=450, gt=0, le=1500)

    @model_validator(mode="after")
    def compatibility(self):
        if self.usable_capacity_kwh > self.gross_capacity_kwh:
            raise ValueError("Usable capacity must not exceed gross capacity")
        if (
            not self.minimum_voltage_v
            <= self.nominal_voltage_v
            <= self.maximum_voltage_v
        ):
            raise ValueError(
                "Battery voltages must satisfy minimum <= nominal <= maximum"
            )
        return self


class Motor(StrictModel):
    topology: Literal["unspecified", "PMSM", "induction"] = "unspecified"
    rated_power_kw: float = Field(default=120, gt=0, le=1000)
    rated_dc_minimum_v: float = Field(default=250, gt=0, le=1500)
    rated_dc_maximum_v: float = Field(default=500, gt=0, le=1500)


class Inverter(StrictModel):
    technology: Literal["unspecified", "silicon", "SiC"] = "unspecified"
    maximum_dc_voltage_v: float = Field(default=500, gt=0, le=1500)
    continuous_power_kw: float = Field(default=150, gt=0, le=1000)


class Body(StrictModel):
    mass_excluding_battery_kg: float = Field(default=1380, gt=0, le=8000)
    drag_coefficient: float = Field(default=0.28, gt=0, le=1)
    frontal_area_m2: float = Field(default=2.2, gt=0, le=10)
    rolling_resistance_coefficient: float = Field(default=0.012, ge=0, le=0.1)


class Charging(StrictModel):
    maximum_ac_kw: float = Field(default=11, gt=0, le=100)
    maximum_dc_kw: float = Field(default=100, gt=0, le=1000)
    charger_dc_maximum_v: float = Field(default=500, gt=0, le=1500)


class Tariffs(StrictModel):
    home_eur_kwh: float = Field(default=0.30, ge=0, le=10)
    public_ac_eur_kwh: float = Field(default=0.45, ge=0, le=10)
    public_dc_eur_kwh: float = Field(default=0.60, ge=0, le=10)
    charging_efficiency: float = Field(default=0.9, gt=0, le=1)


class VehicleDesign(StrictModel):
    schema_version: Literal[1] = 1
    name: str = Field(
        default="Study 01 · illustrative EV", min_length=1, max_length=100
    )
    classification: Literal["illustrative"] = "illustrative"
    battery: Battery = Field(default_factory=Battery)
    motor: Motor = Field(default_factory=Motor)
    inverter: Inverter = Field(default_factory=Inverter)
    body: Body = Field(default_factory=Body)
    charging: Charging = Field(default_factory=Charging)
    tariffs: Tariffs = Field(default_factory=Tariffs)
    drivetrain: Literal["single_equivalent_motor"] = "single_equivalent_motor"
    reduction_ratio: float = Field(default=9, gt=0, le=30)
    electrical_architecture: Literal["custom_dc_bus"] = "custom_dc_bus"
    thermal_assumption: Literal["not_modelled"] = "not_modelled"

    @model_validator(mode="after")
    def compatibility(self):
        if self.battery.maximum_voltage_v > self.inverter.maximum_dc_voltage_v:
            raise ValueError("Battery maximum voltage exceeds inverter DC rating")
        if not (
            self.motor.rated_dc_minimum_v
            <= self.battery.minimum_voltage_v
            <= self.battery.maximum_voltage_v
            <= self.motor.rated_dc_maximum_v
        ):
            raise ValueError(
                "Motor drive DC envelope must contain the battery voltage range"
            )
        if self.motor.rated_power_kw > self.inverter.continuous_power_kw:
            raise ValueError(
                "Motor rated power exceeds inverter continuous power rating"
            )
        if self.charging.charger_dc_maximum_v < self.battery.maximum_voltage_v:
            raise ValueError("Charger DC voltage capability is insufficient")
        return self
