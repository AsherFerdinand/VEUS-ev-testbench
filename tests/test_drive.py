"""Preset API/config mapping and compatibility checks; UI exercised in browser."""

import pytest
from fastapi.testclient import TestClient
from veus.sim.session import RunConfig, SimulationSession, Controls
from veus.studio.main import app
from veus.studio.presets import vehicle_presets


@pytest.mark.parametrize("preset", vehicle_presets(), ids=lambda p: p["id"])
def test_preset_maps_to_resolved_physics(preset):
    config = RunConfig.model_validate(preset["config"])
    with TestClient(app).websocket_connect("/ws/simulation") as ws:
        ws.receive_json()
        ws.send_json({"action": "reset", "config": preset["config"]})
        frame = ws.receive_json()
        assert frame["resolved_config"] == config.model_dump(mode="json")
        assert frame["position_m"] == 0
        assert frame["status"] == "ready"
    assert "Illustrative" in preset["classification"]
    assert preset["maximum_speed_kmh"] is None


def test_vehicle_api_and_existing_routes_remain_available():
    with TestClient(app) as client:
        presets = client.get("/api/vehicles").json()
        assert {p["id"] for p in presets} == {"hatch", "sedan", "coupe", "suv"}
        assert len({p["config"]["mass_kg"] for p in presets}) == 4
        assert len({p["config"]["battery_capacity_kwh"] for p in presets}) == 4
        assert client.get("/api/validation/examples").status_code == 200
        for p in presets:
            svg = client.get("/static/vehicles/" + p["id"] + ".svg")
            assert svg.status_code == 200
            assert "<svg" in svg.text
        index = client.get("/").text
        for name in ("workspaces.js", "dashboard.js", "validation.js", "drive.js"):
            assert name in index


def test_preset_selection_has_a_physical_effect():
    speeds = []
    for preset in vehicle_presets():
        session = SimulationSession(RunConfig.model_validate(preset["config"]))
        session.status = "running"
        session.controls = Controls(throttle=1)
        for _ in range(100):
            session.step()
        speeds.append(session.telemetry()["velocity_kmh"])
    assert len(set(speeds)) == 4
