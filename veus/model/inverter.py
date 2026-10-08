"""
VEUS - Module: veus.model.inverter
Inverter PWM switching and conduction loss model.
"""
from dataclasses import dataclass


@dataclass
class Inverter:
    r_ds_on_ohms: float = 0.002
    switching_loss_j: float = 0.008
    f_pwm_hz: float = 10000.0
    quiescent_power_w: float = 80.0

    def solve_dc_power(self, p_ac_w: float, i_phase_rms: float, v_bus_v: float) -> dict:
        conduction_loss_w = 3.0 * (i_phase_rms ** 2) * self.r_ds_on_ohms
        switching_loss_w = self.switching_loss_j * self.f_pwm_hz * (abs(p_ac_w) / max(1.0, v_bus_v))
        total_loss_w = conduction_loss_w + switching_loss_w + self.quiescent_power_w

        p_dc_w = p_ac_w + total_loss_w
        i_dc_a = p_dc_w / max(1.0, v_bus_v)

        return {
            "p_dc_w": p_dc_w,
            "i_dc_a": i_dc_a,
            "inverter_loss_w": total_loss_w,
        }