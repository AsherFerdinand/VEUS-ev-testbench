"""
VEUS - Module: veus.studio.main
FastAPI application serving web UI and streaming WebSocket telemetry.
"""

import asyncio
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from veus.sim.drive_cycle import DriveCycleSimulator

app = FastAPI(title="VEUS Studio")

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/")
async def read_index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await websocket.accept()
    sim = DriveCycleSimulator()
    telemetry_data = sim.run_launch_simulation()

    try:
        while True:
            for step in telemetry_data:
                await websocket.send_json(step)
                await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/simulation")
async def interactive_simulation(websocket: WebSocket):
    """Each connection owns a run. Fixed 0.01 s steps, nominal 1x playback."""
    import time
    from pydantic import ValidationError
    from veus.sim.session import Controls, RunConfig, SimulationSession

    await websocket.accept()
    session = SimulationSession()
    last_sensor_events = None

    async def send_state(frame):
        nonlocal last_sensor_events
        events = session.sensor_suite.events if session.sensor_suite else []
        if frame.get("status") == "ready" or events != last_sensor_events:
            frame["sensor_fault_events"] = list(events)
            last_sensor_events = list(events)
        if frame.get("status") == "ready":
            frame["resolved_config"] = session.config.model_dump(mode="json")
        await websocket.send_json(frame)

    await send_state(session.telemetry())
    next_tick = time.monotonic() + 0.1
    try:
        while True:
            if session.status == "running" and time.monotonic() >= next_tick:
                await send_state(session.advance())
                # No unbounded catch-up if a client/network is slow.
                next_tick = time.monotonic() + 0.1
            timeout = (
                max(0.001, next_tick - time.monotonic())
                if session.status == "running"
                else None
            )
            try:
                command = await asyncio.wait_for(websocket.receive_json(), timeout)
            except asyncio.TimeoutError:
                continue
            try:
                if not isinstance(command, dict):
                    raise ValueError("Command must be an object")
                action = command.get("action")
                if action == "reset":
                    config = RunConfig.model_validate(command.get("config", {}))
                    session.reset(config)
                elif action == "controls":
                    session.controls = Controls.model_validate(
                        command.get("controls", {})
                    )
                elif action == "start":
                    if session.status in {"completed", "collision"}:
                        raise ValueError("Reset before starting a finished run")
                    session.status = "running"
                    next_tick = time.monotonic() + 0.1
                elif action == "pause":
                    if session.status == "running":
                        session.status = "paused"
                else:
                    raise ValueError("Unknown action")
                await send_state(session.telemetry())
            except (ValueError, ValidationError) as exc:
                await websocket.send_json({"type": "error", "message": str(exc)})
    except WebSocketDisconnect:
        pass
