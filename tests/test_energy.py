import math
import pytest
from veus.model.energy_battery import EnergyBattery
from veus.sim.session import RunConfig, SimulationSession


def execute(**kwargs):
    session = SimulationSession(RunConfig(duration_s=5, **kwargs))
    session.status = 'running'
    while session.status == 'running':
        frame = session.advance()
        assert abs(frame['energy_balance_error_j']) < 1e-5
        assert 0 <= frame['soc'] <= 1
    return frame


@pytest.mark.parametrize('power', [-10000, 0, 10000])
@pytest.mark.parametrize('resistance', [0, .05])
def test_analytic_power_energy_identity(power, resistance):
    battery = EnergyBattery(resistance_ohm=resistance)
    initial = battery.energy_j
    result = battery.exchange(power, .1)
    assert result['current_a']*result['voltage_v'] == pytest.approx(power)
    assert result['chemical_power_w'] == pytest.approx(power+result['heat_w'])
    assert initial-battery.energy_j == pytest.approx(result['chemical_power_w']*.1)


def test_bounds_and_current_voltage_limits():
    for soc in (0, .000001, .999999, 1):
        battery = EnergyBattery(soc=soc)
        for power in (1e10, -1e10):
            result = battery.exchange(power, 1)
            assert -battery.charge_limit_a-1e-8 <= result['current_a'] <= battery.discharge_limit_a+1e-8
            assert 0 <= battery.soc <= 1
            assert .5*battery.voltage_v-1e-6 <= result['voltage_v'] <= 1.1*battery.voltage_v+1e-6
    assert EnergyBattery(soc=0).power_limits(1)[0] == 0
    assert EnergyBattery(soc=1).power_limits(1)[1] == 0


def test_driving_consumes_energy_and_reduces_soc():
    result = execute(mode='acceleration')
    assert result['soc'] < .8
    assert result['energy_consumed_kwh'] > 0
    assert result['energy_recovered_kwh'] == 0
    assert result['battery_heat_kwh'] > 0
    assert result['conversion_loss_kwh'] > 0


def test_empty_and_current_limited_battery_reduce_drive():
    normal = execute(mode='acceleration')
    empty = execute(mode='acceleration', initial_soc=0)
    limited = execute(mode='acceleration', discharge_limit_a=10)
    assert empty['velocity_kmh'] == 0
    assert empty['soc'] == 0
    assert limited['velocity_kmh'] < normal['velocity_kmh']
    assert limited['battery_limited']


def test_brake_blending_and_full_pack():
    regen = execute(mode='braking', initial_speed_kmh=80)
    friction = execute(mode='braking', initial_speed_kmh=80, regen_enabled=False)
    full = execute(mode='braking', initial_speed_kmh=80, initial_soc=1)
    assert regen['soc'] > .8
    assert regen['energy_recovered_kwh'] > 0
    assert regen['energy_recovered_kwh']*3_600_000 < .5*1800*(80/3.6)**2
    assert friction['energy_recovered_kwh'] == full['energy_recovered_kwh'] == 0
    assert regen['position_m'] == pytest.approx(friction['position_m'])
    assert full['position_m'] == pytest.approx(friction['position_m'])
    assert friction['friction_heat_kwh'] > regen['friction_heat_kwh']


def test_low_friction_and_downhill_energy_balance():
    for mode in ('braking', 'acceleration', 'coast'):
        execute(mode=mode, initial_speed_kmh=80, grade_percent=-10, friction=.1)


def test_zero_charge_acceptance_and_coasting():
    result = execute(mode='braking', initial_speed_kmh=80, charge_limit_a=0)
    assert result['energy_recovered_kwh'] == 0
    result = execute(mode='coast', initial_speed_kmh=80)
    assert result['soc'] == .8
    assert result['energy_consumed_kwh'] == 0


@pytest.mark.parametrize('kwargs', [{'soc':-1}, {'capacity_kwh':0}, {'voltage_v':float('nan')}, {'resistance_ohm':-1}])
def test_invalid_battery(kwargs):
    with pytest.raises(ValueError):
        EnergyBattery(**kwargs)
