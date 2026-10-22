"""
VEUS - Module: veus.model.vehicle
Inverse road-load calculation for forward motion; SI units.
"""
from dataclasses import dataclass
import math


@dataclass
class HighPerformanceVehicle:
    mass_kg: float = 2395.0
    cd: float = 0.24
    frontal_area_m2: float = 2.35
    wheel_radius_m: float = 0.355
    rr_coeff: float = 0.015

    def calculate_road_loads(self, velocity_ms: float, acceleration_ms2: float = 0.0) -> dict:
        values = (velocity_ms, acceleration_ms2, self.mass_kg, self.cd,
                  self.frontal_area_m2, self.wheel_radius_m, self.rr_coeff)
        if (not all(math.isfinite(x) for x in values) or velocity_ms < 0
                or min(self.mass_kg, self.frontal_area_m2, self.wheel_radius_m) <= 0
                or min(self.cd, self.rr_coeff) < 0):
            raise ValueError("Finite forward velocity and valid vehicle parameters required")
        v_abs = velocity_ms
        f_aero = 0.5 * 1.225 * self.cd * self.frontal_area_m2 * (v_abs ** 2)
        f_roll = self.rr_coeff * self.mass_kg * 9.81
        f_inertial = self.mass_kg * acceleration_ms2
        
        f_tractive = f_aero + f_roll + f_inertial
        wheel_torque_nm = f_tractive * self.wheel_radius_m
        wheel_rpm = (v_abs / (2.0 * math.pi * self.wheel_radius_m)) * 60.0

        return {
            "f_tractive_n": f_tractive,
            "wheel_torque_nm": wheel_torque_nm,
            "wheel_rpm": wheel_rpm,
        }