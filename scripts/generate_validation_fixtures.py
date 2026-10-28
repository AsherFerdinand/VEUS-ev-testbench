"""Regenerate analytical SYNTHETIC CSV fixtures; never generates measured data."""

import csv, hashlib, io, json, math
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "examples/validation"
for name, v0 in [("synthetic-coast-train", 40), ("synthetic-coast-holdout", 20)]:
    stream = io.StringIO(newline="")
    w = csv.writer(stream)
    w.writerow(
        [
            "time_s",
            "vehicle_speed_ms",
            "motor_torque_nm",
            "brake_force_n",
            "road_gradient_rad",
        ]
    )
    a = 0.012 * 9.81
    b = 0.5 * 1.225 * 0.62 / 1800
    for t in range(31):
        speed = math.sqrt(a / b) * math.tan(
            math.atan(v0 * math.sqrt(b / a)) - math.sqrt(a * b) * t
        )
        w.writerow([t, speed, 0, 0, 0])
    (root / (name + ".csv")).write_bytes(stream.getvalue().encode())
for name, shift in [("synthetic-battery-train", 0), ("synthetic-battery-holdout", 3)]:
    stream = io.StringIO(newline="")
    w = csv.writer(stream)
    w.writerow(["time_s", "battery_current_a", "battery_voltage_v"])
    for t in range(11):
        current = 10 + ((t + shift) % 5) * 10
        w.writerow([t, current, 390 - 0.12 * current])
    (root / (name + ".csv")).write_bytes(stream.getvalue().encode())
for p in root.glob("synthetic-*.csv"):
    config = p.with_suffix(".json")
    value = json.loads(config.read_text())
    value["source"]["expected_sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    config.write_text(json.dumps(value, indent=2) + "\n")
print("Synthetic fixtures regenerated; no measured-data files touched")
