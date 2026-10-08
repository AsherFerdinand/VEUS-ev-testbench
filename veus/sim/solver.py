"""
VEUS - Module: veus.sim.solver
Integrated solver resolving circular powertrain dependencies.
"""
from dataclasses import dataclass
from veus.model.cell import Cell
from veus.model.pack import BatteryPack
from veus.model.motor import ElectricMotor
from veus.model.inverter import Inverter
from veus.model.transmission import Transmission
from veus.model.vehicle import HighPerformanceVehicle


@dataclass
class VehiclePowertrain:
    pack: BatteryPack = None
    motor: ElectricMotor = None
    inverter: Inverter = None
    transmission: Transmission = None
    vehicle: HighPerformanceVehicle = None

    def __post_init__(self):
        if self.pack is None:
            self.pack = BatteryPack()
        if self.motor is None:
            self.motor = ElectricMotor()
        if self.inverter is None:
            self.inverter = Inverter()
        if self.transmission is None:
            self.transmission = Transmission()
        if self.vehicle is None:
            self.vehicle = HighPerformanceVehicle()

    def solve_point(self, velocity_ms: float, acceleration_ms2: float, soc: float) -> dict:
        road = self.vehicle.calculate_road_loads(velocity_ms, acceleration_ms2)
        
        # 2-speed shift logic
        self.transmission.current_gear = 1 if velocity_ms > 27.7 else 0

        req_motor_torque, motor_rpm = self.transmission.wheel_to_motor(road["wheel_torque_nm"], road["wheel_rpm"])
        motor_state = self.motor.solve_mechanical_output(req_motor_torque, motor_rpm)

        v_bus_guess = self.pack.cell.get_ocv(soc) * self.pack.series_cells
        for _ in range(4):
            inv_state = self.inverter.solve_dc_power(motor_state["p_elec_w"], motor_state["i_phase_rms"], v_bus_guess)
            pack_state = self.pack.solve_pack_state(soc, inv_state["i_dc_a"])
            v_bus_guess = max(100.0, pack_state["v_pack"])

        return {
            "velocity_kmh": velocity_ms * 3.6,
            "soc": soc,
            "v_pack_v": pack_state["v_pack"],
            "i_pack_a": inv_state["i_dc_a"],
            "p_battery_kw": pack_state["p_dc_watts"] / 1000.0,
            "motor_rpm": motor_rpm,
            "current_gear": self.transmission.current_gear + 1,
            "losses": {
                "pack_i2r_w": pack_state["i2r_loss_watts"],
                "inverter_w": inv_state["inverter_loss_w"],
                "motor_w": motor_state["motor_loss_w"],
                "total_loss_kw": (pack_state["i2r_loss_watts"] + inv_state["inverter_loss_w"] + motor_state["motor_loss_w"]) / 1000.0,
            },
        }