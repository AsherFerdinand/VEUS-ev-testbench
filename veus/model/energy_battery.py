"""Constant-OCV energy reservoir with resistive sag and analytic power solving.

Positive terminal power/current discharges. Capacity is chemical energy, not
terminal-deliverable energy. No temperature, SOC-dependent OCV or aging model.
"""
from dataclasses import dataclass
import math


@dataclass
class EnergyBattery:
    capacity_kwh: float = 60.0
    soc: float = 0.8
    voltage_v: float = 400.0
    resistance_ohm: float = 0.05
    discharge_limit_a: float = 500.0
    charge_limit_a: float = 200.0

    def __post_init__(self):
        values = vars(self).values()
        if (not all(math.isfinite(v) for v in values) or self.capacity_kwh <= 0
                or not 0 <= self.soc <= 1 or self.voltage_v <= 0
                or min(self.resistance_ohm, self.discharge_limit_a, self.charge_limit_a) < 0):
            raise ValueError('Invalid battery parameters')
        self.energy_j = self.capacity_kwh*3_600_000*self.soc

    def power_limits(self, dt_s: float, *, terminal_minimum_v: float | None = None,
                     terminal_maximum_v: float | None = None,
                     terminal_current_limit_a: float | None = None,
                     discharge_power_limit_w: float | None = None,
                     charge_power_limit_w: float | None = None) -> tuple[float, float]:
        if not math.isfinite(dt_s) or dt_s <= 0:
            raise ValueError('Positive finite timestep required')
        # Restrict to the stable high-voltage branch; Vterminal >= 0.5 Voc.
        max_i = min(self.discharge_limit_a, self.energy_j/(self.voltage_v*dt_s))
        if self.resistance_ohm:
            max_i = min(max_i, self.voltage_v/(2*self.resistance_ohm))
        charge_i = min(self.charge_limit_a,
                       max(0, self.capacity_kwh*3_600_000-self.energy_j)/(self.voltage_v*dt_s))
        # Fixed voltage window: 0.5 Voc <= terminal voltage <= 1.1 Voc.
        if self.resistance_ohm:
            charge_i = min(charge_i, 0.1*self.voltage_v/self.resistance_ohm)
        optional = (terminal_minimum_v, terminal_maximum_v, terminal_current_limit_a,
                    discharge_power_limit_w, charge_power_limit_w)
        if any(v is not None and (not math.isfinite(v) or v < 0) for v in optional):
            raise ValueError('Electrical envelope limits must be finite and nonnegative')
        if terminal_minimum_v is not None and terminal_maximum_v is not None and terminal_minimum_v > terminal_maximum_v:
            raise ValueError('Terminal voltage limits are reversed')
        if terminal_current_limit_a is not None:
            max_i = min(max_i, terminal_current_limit_a)
            charge_i = min(charge_i, terminal_current_limit_a)
        if self.resistance_ohm:
            if terminal_minimum_v is not None:
                max_i = min(max_i, max(0, (self.voltage_v-terminal_minimum_v)/self.resistance_ohm))
            if terminal_maximum_v is not None:
                charge_i = min(charge_i, max(0, (terminal_maximum_v-self.voltage_v)/self.resistance_ohm))
        else:
            if terminal_minimum_v is not None and self.voltage_v < terminal_minimum_v:
                max_i = 0
            if terminal_maximum_v is not None and self.voltage_v > terminal_maximum_v:
                charge_i = 0
        discharge = (self.voltage_v-max_i*self.resistance_ohm)*max_i
        charge = (self.voltage_v+charge_i*self.resistance_ohm)*charge_i
        if discharge_power_limit_w is not None:
            discharge = min(discharge, discharge_power_limit_w)
        if charge_power_limit_w is not None:
            charge = min(charge, charge_power_limit_w)
        return discharge, charge

    def exchange(self, terminal_power_w: float, dt_s: float) -> dict:
        discharge, charge = self.power_limits(dt_s)
        if not math.isfinite(terminal_power_w):
            raise ValueError('Finite terminal power required')
        power = max(-charge, min(discharge, terminal_power_w))
        # Rationalized quadratic root avoids cancellation for small power.
        discriminant = max(0, self.voltage_v**2-4*self.resistance_ohm*power)
        current = 2*power/(self.voltage_v+math.sqrt(discriminant))
        terminal_v = self.voltage_v-current*self.resistance_ohm
        chemical_w = self.voltage_v*current
        heat_w = current**2*self.resistance_ohm
        self.energy_j = max(0, min(self.capacity_kwh*3_600_000,
                                   self.energy_j-chemical_w*dt_s))
        self.soc = self.energy_j/(self.capacity_kwh*3_600_000)
        return dict(terminal_power_w=power, current_a=current, voltage_v=terminal_v,
                    chemical_power_w=chemical_w, heat_w=heat_w,
                    limited=abs(power-terminal_power_w) > 1e-6)
