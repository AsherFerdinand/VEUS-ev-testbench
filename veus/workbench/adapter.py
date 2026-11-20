"""Explicit adapter into retained models. This is not a new simulation engine."""

from dataclasses import dataclass
import math
from veus.model.vehicle import HighPerformanceVehicle
from veus.model.motor import ElectricMotor
from veus.model.transmission import Transmission
from veus.model.energy_battery import EnergyBattery
from veus.sim.dynamics import LongitudinalSimulator

ACKNOWLEDGEMENTS = [
    "illustrative_parameters",
    "constant_efficiency",
    "constant_ocv",
    "longitudinal_only",
    "unmodelled_thermal_charging",
]


@dataclass
class AdaptedModels:
    dynamics: LongitudinalSimulator
    battery: EnergyBattery
    drive_efficiency: float
    regen_efficiency: float


def readiness(design, checks, mass):
    required = {
        "total_mass": mass,
        "motor_peak_power": design.motor.peak_power_kw,
        "motor_peak_torque": design.motor.peak_torque_nm,
        "motor_speed_limit": design.motor.maximum_speed_rpm,
        "battery_resistance": design.battery.resistance_ohm,
        "battery_discharge_limit": design.battery.discharge_limit_a,
        "battery_charge_limit": design.battery.charge_limit_a,
        "motor_efficiency": design.motor.efficiency_assumption,
        "inverter_efficiency": design.inverter.efficiency_assumption,
        "gear_efficiency": design.gearbox.mechanical_efficiency,
        "regeneration_efficiency": design.assumptions.regen_efficiency,
    }
    missing = [k for k, v in required.items() if v is None]
    # A positive motor/drive request must have some discharge capability.
    if design.battery.discharge_limit_a == 0:
        missing.append("nonzero_discharge_capability")
    incompatible = [c["id"] for c in checks if c["status"] == "incompatible"]
    status = (
        "incompatible"
        if incompatible
        else ("insufficient_data" if missing else "requires_acknowledgement")
    )
    return dict(
        status=status,
        ready=False,
        missing_inputs=missing,
        blocking_checks=incompatible,
        required_acknowledgements=ACKNOWLEDGEMENTS,
        scope="Preparation for illustrative longitudinal mechanical dynamics plus a separate retained energy battery; no experiment is executed.",
        limitations=[
            "No phase-current motor/inverter map, continuous/peak duty or thermal prediction.",
            "A single fixed reduction is supplied explicitly; no default gear or vehicle substitution.",
            "Battery maximum/minimum voltage labels do not replace EnergyBattery's fixed OCV and internal voltage-window assumptions.",
            "The adapter does not couple battery/inverter power limits back into a mechanical experiment; a verified runner integration is still required.",
            "Chemistry, technology, charging specifications, tariffs and safety assertions are not simulated.",
        ],
    )


def mapped_parameters(d, mass):
    return dict(
        vehicle=dict(
            mass_kg=mass,
            cd=d.body.drag_coefficient,
            frontal_area_m2=d.body.frontal_area_m2,
            wheel_radius_m=d.body.wheel_radius_m,
            rr_coeff=d.body.rolling_resistance_coefficient,
        ),
        motor=dict(
            max_torque_nm=d.motor.peak_torque_nm,
            max_power_kw=d.motor.peak_power_kw,
            max_rpm=d.motor.maximum_speed_rpm,
        ),
        transmission=dict(
            gear_ratios=[d.gearbox.reduction_ratio],
            mechanical_efficiency=d.gearbox.mechanical_efficiency,
            current_gear=0,
        ),
        road=dict(
            friction_coefficient=d.assumptions.friction_coefficient,
            gradient_rad=math.atan(d.assumptions.grade_percent / 100),
            air_density_kg_m3=d.assumptions.air_density_kg_m3,
        ),
        battery=dict(
            capacity_kwh=d.battery.usable_capacity_kwh,
            soc=d.assumptions.initial_soc,
            voltage_v=d.battery.nominal_voltage_v,
            resistance_ohm=d.battery.resistance_ohm,
            discharge_limit_a=d.battery.discharge_limit_a,
            charge_limit_a=d.battery.charge_limit_a,
        ),
        conversion=dict(
            drive_efficiency=d.motor.efficiency_assumption
            * d.inverter.efficiency_assumption,
            regen_efficiency=d.assumptions.regen_efficiency,
        ),
    )


def build_models(design, checks, mass, acknowledgements):
    state = readiness(design, checks, mass)
    if state["status"] != "requires_acknowledgement":
        raise ValueError("Adapter cannot prepare this design: " + state["status"])
    if set(acknowledgements) != set(ACKNOWLEDGEMENTS):
        raise ValueError("All stated model assumptions must be explicitly acknowledged")
    p = mapped_parameters(design, mass)
    return AdaptedModels(
        LongitudinalSimulator(
            vehicle=HighPerformanceVehicle(**p["vehicle"]),
            motor=ElectricMotor(**p["motor"]),
            transmission=Transmission(**p["transmission"]),
            **p["road"],
        ),
        EnergyBattery(**p["battery"]),
        **p["conversion"],
    )
