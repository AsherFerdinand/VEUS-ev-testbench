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