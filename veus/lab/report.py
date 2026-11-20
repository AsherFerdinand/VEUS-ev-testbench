"""Exports of a frozen, hash-checked run; no recomputation or external assets."""

import csv
import hashlib
from html import escape
import io
import math
from .schema import LabRequest
from veus.replay.analysis import canonical
from veus.testing.report import page, table


def validate_result(result):
    if not isinstance(result, dict) or len(result.get("trace", [])) > 12001:
        raise ValueError("Invalid bounded run result")
    payload = {k: v for k, v in result.items() if k != "run_sha256"}
    if result.get("run_sha256") != hashlib.sha256(canonical(payload)).hexdigest():
        raise ValueError("Run hash mismatch; export only a frozen unchanged result")
    if (
        result.get("schema_version") != 1
        or result.get("model_version") != "veus-lab-coupled-v1"
    ):
        raise ValueError("Unsupported result version")
    request = LabRequest.model_validate(result.get("request"))
    if result.get("vehicle") != request.vehicle.model_dump(mode="json") or result.get(
        "experiment"
    ) != request.experiment.model_dump(mode="json"):
        raise ValueError("Frozen result/request snapshots differ")
    rows = result["trace"]
    if len(rows) != round(request.experiment.duration_s / request.experiment.dt_s) + 1:
        raise ValueError("Run trace does not contain every bounded simulation tick")
    required = [
        "time_s",
        "position_m",
        "speed_ms",
        "soc",
        "battery_power_w",
        "motor_power_w",
        "motor_torque_nm",
        "acceleration_ms2",
        "battery_current_a",
        "battery_voltage_v",
        "regen_power_w",
        "friction_power_w",
        "grade_percent",
        "energy_balance_error_j",
    ]
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or any(
            type(row.get(k)) not in (int, float) or not math.isfinite(row[k])
            for k in required
        ):
            raise ValueError("Invalid or nonfinite required trace fields")
        if abs(row["time_s"] - index * request.experiment.dt_s) > 1e-7:
            raise ValueError("Trace time grid differs from the frozen experiment")
    return result


def export(result, format):
    validate_result(result)
    if format == "json":
        return dict(
            content=canonical(result).decode(),
            media_type="application/json",
            filename="veus-lab-run.json",
        )
    if format == "csv":
        s = io.StringIO(newline="")
        rows = result["trace"]
        w = csv.DictWriter(s, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(
                {k: ";".join(v) if isinstance(v, list) else v for k, v in r.items()}
            )
        return dict(
            content=s.getvalue(), media_type="text/csv", filename="veus-lab-trace.csv"
        )
    if format != "html":
        raise ValueError("Unsupported export format")
    body = "<p>Run SHA256: " + escape(result["run_sha256"]) + "</p>"
    body += table(
        ["Metric", "Value", "Unit"],
        [[k, v, result["summary_units"][k]] for k, v in result["summary"].items()],
    )
    # Lightweight SVG curves preserve every original sample; no plotting dependency.
    points = result["trace"]
    duration = result["summary"]["duration_s"]
    maximum = max(
        1, max(max(r["speed_ms"], r.get("target_speed_ms") or 0) for r in points)
    )
    poly = " ".join(
        f"{40 + 820 * r['time_s'] / duration:.5f},{230 - 200 * r['speed_ms'] / maximum:.5f}"
        for r in points
    )
    target_points = [r for r in points if r.get("target_speed_ms") is not None]
    target_poly = " ".join(
        f"{40 + 820 * r['time_s'] / duration:.5f},{230 - 200 * r['target_speed_ms'] / maximum:.5f}"
        for r in target_points
    )
    target_line = (
        f'<polyline points="{target_poly}" fill="none" stroke="#b17a32" stroke-width="1.5" stroke-dasharray="4 3"/>'
        if target_points
        else ""
    )
    body += f'<h2>Achieved and requested speed · m/s</h2><p>Green: achieved. Dashed orange: requested, where defined. Scale maximum {maximum:.4g} m/s.</p><svg viewBox="0 0 900 270" role="img" aria-label="Achieved and requested simulated speed versus elapsed time"><path d="M40 20V230H860" fill="none" stroke="#777"/>{target_line}<polyline points="{poly}" fill="none" stroke="#476e5e" stroke-width="2"/><text x="40" y="260">0 s</text><text x="800" y="260">{duration} s</text></svg>'
    body += (
        "<h2>Deterministic findings</h2><ul>"
        + "".join(
            "<li>" + escape(f["message"]) + "</li>" for f in result.get("findings", [])
        )
        + "</ul>"
    )

    body += (
        "<h2>Limitations</h2><ul>"
        + "".join("<li>" + escape(x) + "</li>" for x in result["limitations"])
        + "</ul>"
    )
    body += (
        "<h2>Frozen request and provenance</h2><pre>"
        + escape(
            canonical(
                dict(request=result["request"], provenance=result["provenance"])
            ).decode()
        )
        + "</pre>"
    )
    return dict(
        content=page(
            "VEUS Simulation Lab engineering report",
            body,
            scope="Illustrative numerical experiment. Physical validation remains INCONCLUSIVE.",
        ),
        media_type="text/html",
        filename="veus-lab-report.html",
    )
