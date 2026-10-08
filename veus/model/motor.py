"""
VEUS - Module: veus.model.motor
Electric motor torque-speed curve, copper loss, and back-EMF limits.
"""
from dataclasses import dataclass
import math


@dataclass
class ElectricMotor:
    max_torque_nm: float = 830.0
    max_power_kw: float = 475.0
    max_rpm: float = 16000.0
    r_phase_ohms: float = 0.008
    k_t_nm_a: float = 0.55
    friction_coeff: float = 0.05

    def max_available_torque(self, rpm: float) -> float:
        rad_s = max(0.1, (rpm * math.pi) / 30.0)
        power_limited_torque = (self.max_power_kw * 1000.0) / rad_s
        return min(self.max_torque_nm, power_limited_torque)

    def solve_mechanical_output(self, requested_torque_nm: float, rpm: float) -> dict:
        rad_s = (rpm * math.pi) / 30.0
        avail = self.max_available_torque(rpm)
        actual_torque = max(-avail, min(avail, requested_torque_nm))
        i_phase_rms = abs(actual_torque) / self.k_t_nm_a if self.k_t_nm_a > 0 else 0.0
        
        copper_loss_w = 3.0 * (i_phase_rms ** 2) * self.r_phase_ohms
        friction_loss_w = self.friction_coeff * (rad_s ** 2)
        total_loss_w = copper_loss_w + friction_loss_w

        p_mech_w = actual_torque * rad_s
        p_elec_w = p_mech_w + total_loss_w if p_mech_w >= 0 else p_mech_w + total_loss_w

        return {
            "actual_torque_nm": actual_torque,
            "p_mech_w": p_mech_w,
            "p_elec_w": p_elec_w,
            "i_phase_rms": i_phase_rms,
            "motor_loss_w": total_loss_w,
        }