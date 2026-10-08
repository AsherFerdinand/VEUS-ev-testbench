"""
VEUS - Module: veus.model.pack
High-voltage battery pack with series/parallel scaling and busbar loss.
"""
from dataclasses import dataclass, field
from veus.model.cell import Cell


@dataclass
class BatteryPack:
    cell: Cell = field(default_factory=Cell)
    series_cells: int = 198
    parallel_cells: int = 2
    bus_resistance_ohms: float = 0.015

    @property
    def total_internal_resistance(self) -> float:
        return ((self.cell.r_int_ohms * self.series_cells) / self.parallel_cells) + self.bus_resistance_ohms

    def solve_pack_state(self, soc: float, pack_current_a: float) -> dict:
        cell_current = pack_current_a / self.parallel_cells
        cell_v = self.cell.terminal_voltage(soc, cell_current)
        v_pack = (cell_v * self.series_cells) - (pack_current_a * self.bus_resistance_ohms)
        p_dc_watts = v_pack * pack_current_a
        i2r_loss_watts = (pack_current_a ** 2) * self.total_internal_resistance

        return {
            "v_pack": v_pack,
            "p_dc_watts": p_dc_watts,
            "i2r_loss_watts": i2r_loss_watts,
        }