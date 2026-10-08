"""
VEUS - Module: veus.model.cell
Single lithium-ion cell OCV, internal resistance sag, and SOC tracking.
"""
from dataclasses import dataclass, field
from typing import Tuple


@dataclass
class Cell:
    capacity_ah: float = 60.0
    v_nom: float = 3.7
    v_max: float = 4.2
    v_min: float = 2.8
    r_int_ohms: float = 0.0012
    mass_kg: float = 0.85

    ocv_table: Tuple[Tuple[float, float], ...] = (
        (0.00, 2.80),
        (0.10, 3.40),
        (0.20, 3.58),
        (0.40, 3.70),
        (0.60, 3.82),
        (0.80, 4.00),
        (1.00, 4.20),
    )

    def get_ocv(self, soc: float) -> float:
        soc_clamped = max(0.0, min(1.0, soc))
        for i in range(len(self.ocv_table) - 1):
            soc_lo, v_lo = self.ocv_table[i]
            soc_hi, v_hi = self.ocv_table[i + 1]
            if soc_lo <= soc_clamped <= soc_hi:
                frac = (soc_clamped - soc_lo) / (soc_hi - soc_lo)
                return v_lo + frac * (v_hi - v_lo)
        return self.ocv_table[-1][1]

    def terminal_voltage(self, soc: float, current_a: float) -> float:
        return self.get_ocv(soc) - (current_a * self.r_int_ohms)