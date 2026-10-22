import pytest
from veus.control.longitudinal import LongitudinalController, Observation
from veus.sim.session import RunConfig, SimulationSession


def execute(mode, **kwargs):
    session = SimulationSession(RunConfig(mode=mode, duration_s=30, **kwargs))
    session.status = 'running'
    frames=[]
    while session.status == 'running':
        frames.append(session.advance())
    return session, frames


def test_cruise_limits_and_tracking():
    controller = LongitudinalController('cruise', 20)
    assert controller.update(Observation(0)).acceleration_ms2 == 2
    assert controller.update(Observation(40)).acceleration_ms2 == -3
    assert controller.update(Observation(20)).acceleration_ms2 == 0
    _, frames = execute('cruise')
    assert frames[-1]['velocity_kmh'] == pytest.approx(80, abs=.05)
    assert max(f['requested_acceleration_ms2'] for f in frames) <= 2
    assert max(abs(f['energy_balance_error_j']) for f in frames) < 1e-4


def test_acc_headway_and_relative_speed():
    controller = LongitudinalController('acc', 30)
    assert controller.update(Observation(20,10,10)).acceleration_ms2 < 0
    assert controller.update(Observation(20,200,30)).acceleration_ms2 > 0
    _, frames = execute('acc', initial_speed_kmh=80)
    result=frames[-1]
    assert not result['collision']
    assert result['velocity_kmh'] == pytest.approx(60,abs=.1)
    assert result['gap_m'] == pytest.approx(result['desired_gap_m'],abs=.2)
    assert result['minimum_gap_m'] > 0


def test_ttc_mathematical_domain():
    assert Observation(20,40,10).ttc_s == 4
    assert Observation(20,40,20).ttc_s is None
    assert Observation(10,40,20).ttc_s is None
    assert Observation(20).ttc_s is None
    assert Observation(20,-1,10).ttc_s == 0


def test_aeb_trigger_latch_and_bounds():
    controller=LongitudinalController('aeb',30)
    assert controller.update(Observation(20,60,10)).state == 'cruise'
    assert controller.update(Observation(20,15,10)).state == 'emergency_braking'
    assert controller.update(Observation(0,100,0)).state == 'emergency_braking'
    assert not LongitudinalController('aeb',30).update(Observation(10,50,20)).state == 'emergency_braking'


def test_default_aeb_stop_and_low_friction_collision():
    kwargs=dict(initial_speed_kmh=80,lead_speed_kmh=80,initial_gap_m=35)
    _, dry=execute('aeb',**kwargs)
    _, ice=execute('aeb',friction=.1,**kwargs)
    assert dry[-1]['velocity_kmh'] == 0
    assert dry[-1]['minimum_gap_m'] > 0
    assert not dry[-1]['collision']
    assert dry[-1]['aeb_trigger_time_s'] > 3
    assert ice[-1]['collision'] and ice[-1]['status']=='collision'
    assert ice[-1]['velocity_kmh'] > 0
    assert ice[-1]['time_s'] < 30


def test_delays_reduce_gap_and_pause_reset_clear_controller():
    kwargs=dict(initial_speed_kmh=80,lead_speed_kmh=80,initial_gap_m=35)
    _, base=execute('aeb',**kwargs)
    session, delayed=execute('aeb',detection_delay_s=.3,actuation_delay_s=.2,**kwargs)
    assert delayed[-1]['aeb_trigger_time_s'] >= base[-1]['aeb_trigger_time_s']+.29
    assert delayed[-1]['minimum_gap_m'] < base[-1]['minimum_gap_m']
    session.status='paused'
    before=session.telemetry()
    assert session.advance()==before
    session.reset(RunConfig(mode='aeb'))
    assert session.telemetry()['aeb_trigger_time_s'] is None
    assert not session.controller.emergency_latched
    assert not session.commands


def test_lead_analytic_motion_and_standstill():
    session=SimulationSession(RunConfig(mode='aeb',lead_speed_kmh=36,initial_gap_m=50,
                                       lead_brake_start_s=2,lead_deceleration_ms2=5))
    assert session._lead_state(1)==(60,10)
    assert session._lead_state(3)==(77.5,5)
    assert session._lead_state(10)==(80,0)


def test_invalid_controller_observations():
    with pytest.raises(ValueError):
        Observation(float('nan'))
    with pytest.raises(ValueError):
        LongitudinalController('unknown',20)


def test_collision_websocket_requires_reset():
    from fastapi.testclient import TestClient
    from veus.studio.main import app
    with TestClient(app) as client:
        with client.websocket_connect('/ws/simulation') as ws:
            ws.receive_json()
            ws.send_json({'action':'reset','config':{'mode':'acc','initial_speed_kmh':80,
                          'lead_speed_kmh':0,'initial_gap_m':1,'duration_s':1}})
            assert ws.receive_json()['gap_m'] == 1
            ws.send_json({'action':'start'})
            ws.receive_json()
            frame=ws.receive_json()
            assert frame['status']=='collision' and frame['collision']
            ws.send_json({'action':'start'})
            assert ws.receive_json()['type']=='error'
            ws.send_json({'action':'reset','config':{'mode':'cruise'}})
            frame=ws.receive_json()
            assert frame['status']=='ready' and frame['gap_m'] is None
