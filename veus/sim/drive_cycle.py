"""
VEUS - Module: veus.sim.drive_cycle
Time-series simulator for launch runs and drive profiles.
"""
from dataclasses import dataclass
from typing import List, Dict
from veus.sim.solver import VehiclePowertrain


@dataclass
class DriveCycleSimulator:
    powertrain: VehiclePowertrain = None

    def __post_init__(self):
        if self.powertrain is None:
            self.powertrain = VehiclePowertrain()

    def run_launch_simulation(self) -> List[Dict]:
        results = []
        v_ms = 0.0
        t = 0.0
        dt = 0.1

        while v_ms <= 33.33 and t <= 10.0:  # 0 to 120 km/h
            state = self.powertrain.solve_point(velocity_ms=v_ms, acceleration_ms2=3.5, soc=0.90)
            state["time_s"] = round(t, 2)
            results.append(state)
            v_ms += 3.5 * dt
            t += dt

        return results