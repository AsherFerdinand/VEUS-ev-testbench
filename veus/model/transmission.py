"""
VEUS - Module: veus.model.transmission
Automated 2-speed transmission reduction and gear efficiency.
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class Transmission:
    gear_ratios: List[float] = field(default_factory=lambda: [15.0, 8.05])
    mechanical_efficiency: float = 0.97
    current_gear: int = 0

    @property
    def active_ratio(self) -> float:
        return self.gear_ratios[self.current_gear]

    def wheel_to_motor(self, wheel_torque_nm: float, wheel_rpm: float) -> tuple[float, float]:
        ratio = self.active_ratio
        motor_rpm = wheel_rpm * ratio
        motor_torque_nm = wheel_torque_nm / (ratio * self.mechanical_efficiency) if wheel_torque_nm >= 0 else (wheel_torque_nm * self.mechanical_efficiency) / ratio
        return motor_torque_nm, motor_rpm