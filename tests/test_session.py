import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from veus.sim.session import Controls, RunConfig, SimulationSession
from veus.studio.main import app


def run(config):
    session = SimulationSession(RunConfig(**config))
    session.status = 'running'
    frames = []
    while session.status == 'running':
        frames.append(session.advance())
    return frames


def test_deterministic_duration_and_configuration_effects():
    config = dict(mode='acceleration', duration_s=5)
    frames = run(config)
    assert frames == run(config)
    assert frames[-1]['time_s'] == 5
    assert frames[-1]['status'] == 'completed'
    assert frames[-1]['velocity_kmh'] > run(dict(config, mass_kg=3000))[-1]['velocity_kmh']
    assert frames[-1]['velocity_kmh'] > run(dict(config, friction=0.05))[-1]['velocity_kmh']
    assert len(frames) == 50


def test_braking_and_coasting():
    braking = run(dict(mode='braking', initial_speed_kmh=80, duration_s=5))
    coast = run(dict(mode='coast', initial_speed_kmh=80, duration_s=5))
    assert braking[-1]['velocity_kmh'] == 0
    assert coast[-1]['velocity_kmh'] > 0
    assert braking[-1]['position_m'] < coast[-1]['position_m']
    assert run(dict(mode='coast', initial_speed_kmh=80, duration_s=5, grade_percent=10))[-1]['velocity_kmh'] < coast[-1]['velocity_kmh']


def test_pause_manual_brake_priority_and_reset():
    session = SimulationSession()
    session.controls = Controls(throttle=1)
    session.status = 'running'
    assert session.advance()['velocity_kmh'] > 0
    session.status = 'paused'
    before = session.telemetry()
    assert session.advance() == before
    session.status = 'running'
    session.controls = Controls(throttle=1, brake=1)
    assert session.advance()['drive_force_n'] == 0
    session.reset(RunConfig())
    assert session.telemetry()['time_s'] == 0
    assert session.controls == Controls()


@pytest.mark.parametrize('config', [{'mass_kg':0}, {'friction':-1}, {'duration_s':999}, {'max_power_kw':float('nan')}, {'mode':'unknown'}])
def test_invalid_configuration(config):
    with pytest.raises(ValidationError):
        RunConfig(**config)


def test_websocket_commands_and_isolation():
    with TestClient(app) as client:
        with client.websocket_connect('/ws/simulation') as ws, client.websocket_connect('/ws/simulation') as other:
            assert ws.receive_json()['status'] == 'ready'
            assert other.receive_json()['time_s'] == 0
            ws.send_json({'action':'reset','config':{'mode':'acceleration','duration_s':1}})
            assert ws.receive_json()['status'] == 'ready'
            ws.send_json({'action':'start'})
            assert ws.receive_json()['status'] == 'running'
            frames = [ws.receive_json() for _ in range(10)]
            assert frames[-1]['time_s'] == 1
            assert frames[-1]['velocity_kmh'] > 0
            assert frames[-1]['status'] == 'completed'
            ws.send_json({'action':'reset', 'config':{'mass_kg':0}})
            assert ws.receive_json()['type'] == 'error'
            ws.send_json({'action':'pause'})
            assert ws.receive_json()['time_s'] == 1
            other.send_json({'action':'pause'})
            assert other.receive_json()['time_s'] == 0
