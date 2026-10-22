import math

import pytest
from fastapi.testclient import TestClient
from veus.model.cell import Cell
from veus.model.pack import BatteryPack
from veus.model.motor import ElectricMotor
from veus.model.transmission import Transmission
from veus.model.vehicle import HighPerformanceVehicle
from veus.sim.dynamics import LongitudinalSimulator, VehicleState
from veus.sim.drive_cycle import DriveCycleSimulator
from veus.sim.solver import VehiclePowertrain
from veus.studio.main import app


def ideal(**kwargs):
    return LongitudinalSimulator(
        vehicle=HighPerformanceVehicle(mass_kg=1000, cd=0, rr_coeff=0, wheel_radius_m=0.5),
        transmission=Transmission(gear_ratios=[1], mechanical_efficiency=1), **kwargs)


def test_road_load_analytical():
    v = HighPerformanceVehicle()
    for speed in (0, 10, 20):
        road = v.calculate_road_loads(speed, 2)
        expected = 0.5 * 1.225 * v.cd * v.frontal_area_m2 * speed**2 + v.rr_coeff*v.mass_kg*9.81 + v.mass_kg*2
        assert road['f_tractive_n'] == pytest.approx(expected)
        assert road['wheel_torque_nm'] == pytest.approx(expected*v.wheel_radius_m)


def test_cell_and_pack_energy_identity():
    cell = Cell()
    assert cell.get_ocv(0.7) == pytest.approx(3.91)
    pack = BatteryPack()
    for current in (-100, 0, 100):
        state = pack.solve_pack_state(0.8, current)
        ocv = 4*198
        assert state['v_pack'] == pytest.approx(ocv-current*pack.total_internal_resistance)
        assert state['p_dc_watts']+state['i2r_loss_watts'] == pytest.approx(ocv*current)


@pytest.mark.parametrize('torque', [100, -100])
def test_transmission_power(torque):
    tr = Transmission()
    motor_torque, rpm = tr.wheel_to_motor(torque, 100)
    wheel_power = torque*100*math.pi/30
    motor_power = motor_torque*rpm*math.pi/30
    assert motor_power == pytest.approx(wheel_power / tr.mechanical_efficiency if torque > 0 else wheel_power*tr.mechanical_efficiency)


def test_motor_limits():
    motor = ElectricMotor()
    assert motor.solve_mechanical_output(10000, 0)['actual_torque_nm'] == 830
    result = motor.solve_mechanical_output(10000, 10000)
    assert result['p_mech_w'] == pytest.approx(475000)
    assert motor.solve_mechanical_output(100, 20000)['actual_torque_nm'] == 0


def test_force_acceleration_and_position_convergence():
    def run(dt):
        sim, state = ideal(), VehicleState()
        for _ in range(round(2/dt)):
            state = sim.step(state, 500, 0, dt).state
        return state
    coarse, fine = run(0.1), run(0.05)
    assert coarse.velocity_ms == pytest.approx(2)
    assert fine.velocity_ms == pytest.approx(2)
    # a=1; x(2)=2. Explicit Euler has first-order position error.
    assert abs(fine.position_m-2) == pytest.approx(abs(coarse.position_m-2)/2)


def test_braking_distance_and_no_reverse():
    sim, state = ideal(), VehicleState(velocity_ms=10)
    for _ in range(51):
        state = sim.step(state, 0, 2000, 0.1).state
    assert state.velocity_ms == 0
    assert state.position_m == pytest.approx(25, abs=0.51)
    held = sim.step(state, 0, 2000, 1).state
    assert held.position_m == state.position_m


def test_stopping_event_inside_step():
    result = ideal().step(VehicleState(velocity_ms=1), 0, 2000, 1)
    assert result.state.velocity_ms == 0
    assert result.state.position_m == pytest.approx(0.25)


def test_grade_and_traction():
    sim = ideal(gradient_rad=0.1)
    result = sim.step(VehicleState(velocity_ms=10), 0, 0, 0.1)
    assert result.acceleration_ms2 == pytest.approx(-9.81*math.sin(0.1))
    sim = ideal(friction_coefficient=0.01)
    result = sim.step(VehicleState(), 500, 0, 0.1)
    assert result.acceleration_ms2 == pytest.approx(0.01*9.81)
    assert result.traction_limited


def test_saturation_changes_acceleration_and_overspeed():
    sim = ideal()
    high = sim.step(VehicleState(), 1000, 0, 0.1)
    assert high.torque_limited
    sim.motor.max_torque_nm = 100
    low = sim.step(VehicleState(), 1000, 0, 0.1)
    assert low.acceleration_ms2 < high.acceleration_ms2
    result = sim.step(VehicleState(velocity_ms=1000), 100, 0, 0.1)
    assert result.drive_force_n == 0


@pytest.mark.parametrize('dt,torque,brake', [(0, 0, 0), (-1, 0, 0), (0.1, -1, 0), (0.1, 0, -1), (float('nan'), 0, 0)])
def test_invalid_commands(dt, torque, brake):
    with pytest.raises(ValueError):
        ideal().step(VehicleState(), torque, brake, dt)


@pytest.mark.parametrize('field,value', [('mass_kg',0), ('wheel_radius_m',0), ('cd',-1)])
def test_invalid_vehicle(field, value):
    sim = ideal()
    setattr(sim.vehicle, field, value)
    with pytest.raises(ValueError):
        sim.step(VehicleState(), 0, 0, 0.1)


def test_reverse_rejected():
    with pytest.raises(ValueError):
        VehicleState(velocity_ms=-1)


def test_operating_point_and_legacy_launch():
    state = VehiclePowertrain().solve_point(33.33, 0, 0.8)
    assert state['p_battery_kw'] == pytest.approx(59.56814668, rel=1e-6)
    assert state['current_gear'] == 2
    first = DriveCycleSimulator().run_launch_simulation()
    assert first == DriveCycleSimulator().run_launch_simulation()
    assert len(first) == 96
    assert first[-1]['velocity_kmh'] == pytest.approx(119.7)


def test_dashboard_and_telemetry():
    with TestClient(app) as client:
        for path in ('/', '/static/index.html'):
            response = client.get(path)
            assert response.status_code == 200
            assert 'VEUS Studio Telemetry' in response.text
        with client.websocket_connect('/ws/telemetry') as ws:
            expected = DriveCycleSimulator().run_launch_simulation()
            for step in expected:
                assert ws.receive_json() == step
            assert ws.receive_json() == expected[0]
