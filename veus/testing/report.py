"""Portable reports: no external JavaScript/CDN, complete machine-readable evidence."""

import base64
import csv
from datetime import datetime, timezone
import hashlib
from html import escape
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import platform
import os
import tempfile
import subprocess
from veus.validation.physics import physics_references


MODEL_VERSION = "veus-verification-v4"


def write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError("Refusing empty telemetry output")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def provenance(root: Path) -> dict:
    files = []
    for directory in ("veus", "tests", "scenarios", "docs"):
        if (root / directory).exists():
            files.extend(
                p
                for p in (root / directory).rglob("*")
                if p.is_file()
                and p.suffix in {".py", ".json", ".md", ".js", ".html", ".toml", ".txt"}
            )
    files.extend(
        p
        for p in root.iterdir()
        if p.is_file()
        and (
            p.name == "README.md"
            or p.name == "pyproject.toml"
            or p.name.startswith("requirements")
        )
    )
    manifest = {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(set(files))
    }
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"],
                cwd=root,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        )
    except (OSError, subprocess.CalledProcessError):
        commit = None
        dirty = None
    packages = {}
    for name in ("fastapi", "pydantic", "matplotlib", "numpy", "pytest"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    return dict(
        model_version=MODEL_VERSION,
        git_commit=commit,
        working_tree_dirty=dirty,
        source_sha256=hashlib.sha256(
            json.dumps(manifest, sort_keys=True).encode()
        ).hexdigest(),
        source_manifest=manifest,
        python=platform.python_version(),
        platform=platform.system(),
        dependencies=packages,
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
        dt_s=0.01,
        validation_scope="Analytical software verification only; no measured vehicle validation.",
    )


def pyplot():
    # Respect a caller's cache settings; default to a writable per-user temp cache
    # on managed cloud machines where the home directory may be read-only.
    cache = Path(tempfile.gettempdir()) / "veus-matplotlib"
    cache.mkdir(exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def inline_image(path: Path, alt: str) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f'<img alt="{escape(alt, quote=True)}" src="data:image/png;base64,{data}">'


def page(title: str, body: str) -> str:
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>body{{font:16px system-ui;max-width:1200px;margin:32px auto;padding:0 20px;color:#172b3f}}table{{border-collapse:collapse;width:100%;margin:20px 0;display:block;overflow:auto}}td,th{{text-align:left;border:1px solid #ccd7df;padding:9px}}img{{width:100%;height:auto}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f5f8;padding:16px}}.PASS{{color:#126a41}}.FAIL{{color:#b42318}}.INCONCLUSIVE{{color:#875400}}section{{border-top:2px solid #ccd7df;margin-top:32px}}small{{color:#40556b}}</style>
<h1>{escape(title)}</h1><p><strong>Analytical verification and defined model scenarios. No real-world vehicle or production ADAS safety validation.</strong></p>{body}</html>"""


def table(headers: list[str], rows: list[list]) -> str:
    return (
        "<table><thead><tr>"
        + "".join(f"<th>{escape(h)}</th>" for h in headers)
        + "</tr></thead><tbody>"
        + "".join(
            "<tr>"
            + "".join(f"<td>{escape('N/A' if v is None else str(v))}</td>" for v in row)
            + "</tr>"
            for row in rows
        )
        + "</tbody></table>"
    )


def physics_report(output: Path) -> dict:
    traces = physics_references()
    plt = pyplot()
    fig, axes = plt.subplots(4, 3, figsize=(15, 15), layout="constrained")
    rows = []
    for axis, trace in zip(axes.flat, traces):
        axis.plot(
            trace.times_s,
            trace.reference,
            label="Analytical",
            color="#172b3f",
            linewidth=2,
        )
        axis.plot(
            trace.times_s,
            trace.simulated,
            label="Numerical dt=0.01 s",
            linestyle="--",
            color="#c45c00",
        )
        axis.set(
            title=trace.name.replace("_", " "), xlabel="Time (s)", ylabel=trace.unit
        )
        axis.grid(alpha=0.25)
        axis.legend(fontsize=8)
        rows.extend(
            dict(
                case=trace.name,
                time_s=t,
                unit=trace.unit,
                reference=a,
                simulated=b,
                error=b - a,
                tolerance=trace.tolerance,
            )
            for t, a, b in zip(trace.times_s, trace.reference, trace.simulated)
        )
    for axis in list(axes.flat)[len(traces) :]:
        axis.set_visible(False)
    fig.savefig(output / "physics-reference.png", dpi=130)
    plt.close(fig)
    # Include timestep-halving evidence, rather than only a single chosen step.
    half = {t.name: t for t in physics_references(0.005)}
    summaries = [
        dict(
            t.summary(),
            half_dt_error=half[t.name].max_error,
            error_ratio=t.max_error / half[t.name].max_error
            if half[t.name].max_error
            else None,
        )
        for t in traces
    ]
    result = dict(
        status="PASS" if all(t["status"] == "PASS" for t in summaries) else "FAIL",
        dt_s=0.01,
        assumptions="Isolated constant-force, quadratic-drag and constant-OCV reference cases; see docs/validation.md.",
        cases=summaries,
    )
    write_csv(output / "physics-reference.csv", rows)
    write_json(output / "physics.json", result)
    body = table(
        ["Reference", "Unit", "Max error", "Bound", "dt/2 error", "Status"],
        [
            [
                s["name"],
                s["unit"],
                f"{s['max_absolute_error']:.8g}",
                f"{s['tolerance']:.8g}",
                f"{s['half_dt_error']:.8g}",
                s["status"],
            ]
            for s in summaries
        ],
    )
    body += inline_image(
        output / "physics-reference.png",
        "Analytical reference versus numerical trajectories",
    )
    return dict(result=result, html=body)


def scenario_plot(output: Path, result) -> None:
    plt = pyplot()
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout="constrained")
    time = [f["time_s"] for f in result.telemetry]
    specs = [
        ("Speed (km/h)", ("velocity_kmh", "lead_speed_kmh", "target_speed_kmh")),
        ("Separation (m)", ("gap_m", "desired_gap_m")),
        ("TTC (s)", ("ttc_s",)),
        ("Acceleration (m/s²)", ("acceleration_ms2", "requested_acceleration_ms2")),
    ]
    for axis, (label, keys) in zip(axes.flat, specs):
        for key in keys:
            values = [
                float("nan") if f[key] is None else f[key] for f in result.telemetry
            ]
            if any(f[key] is not None for f in result.telemetry):
                axis.plot(time, values, label=key, linewidth=1.5)
        axis.set(xlabel="Simulation time (s)", ylabel=label)
        if label == "TTC (s)":
            axis.set_ylim(0, 10)
            axis.set_ylabel("TTC (s; view limited to 0–10 s)")
        if result.metrics.aeb_detection_time_s is not None:
            axis.axvline(
                result.metrics.aeb_detection_time_s,
                color="#bb3355",
                linestyle=":",
                label="AEB detected",
            )
        axis.grid(alpha=0.25)
        if axis.lines:
            axis.legend(fontsize=8)
        else:
            axis.text(
                0.5,
                0.5,
                "Not applicable / undefined",
                ha="center",
                transform=axis.transAxes,
            )
    fig.suptitle(result.scenario_id + " — " + result.status)
    fig.savefig(output / "signals.png", dpi=120)
    plt.close(fig)


def save_batch(
    output: Path, scenarios: list, results: list, root: Path, originals: dict
) -> dict:
    meta = provenance(root)
    write_json(output / "provenance.json", meta)
    body = (
        "<h2>Run provenance</h2><pre>" + escape(json.dumps(meta, indent=2)) + "</pre>"
    )
    summary_rows = []
    for scenario, result in zip(scenarios, results):
        directory = output / scenario.id
        directory.mkdir()
        resolved = scenario.model_dump(mode="json")
        write_json(directory / "scenario.json", resolved)
        write_json(directory / "config.json", resolved["config"])
        if scenario.id in originals:
            (directory / "input.json").write_text(
                originals[scenario.id], encoding="utf-8"
            )
        write_json(
            directory / "result.json",
            result.model_dump(mode="json", exclude={"telemetry"}),
        )
        write_csv(directory / "telemetry.csv", result.telemetry)
        suffix_units = [
            ("_ms2", "m/s²"),
            ("_kmh", "km/h"),
            ("_kwh", "kWh"),
            ("_rpm", "rpm"),
            ("_kw", "kW"),
            ("_nm", "Nm"),
            ("_m", "m"),
            ("_s", "s"),
            ("_n", "N"),
            ("_v", "V"),
            ("_a", "A"),
            ("_j", "J"),
        ]
        signals = {}
        for key, value in result.telemetry[0].items():
            unit = next((u for suffix, u in suffix_units if key.endswith(suffix)), None)
            if key == "soc" or key.startswith("manual_"):
                unit = "fraction"
            if key == "current_gear":
                unit = "one-based index"
            if unit is None:
                unit = "boolean" if isinstance(value, bool) else "enum/text"
            signals[key] = dict(
                unit=unit, nullable=any(f[key] is None for f in result.telemetry)
            )
        write_json(
            directory / "telemetry-schema.json",
            dict(
                schema_version=1,
                signals=signals,
                timing="State at interval end; force/power/commands over preceding 0.01 s interval. Null means unavailable, never zero.",
            ),
        )
        if result.requirements:
            write_csv(
                directory / "requirements.csv",
                [r.model_dump() for r in result.requirements],
            )
        scenario_plot(directory, result)
        config_hash = hashlib.sha256(
            json.dumps(resolved, sort_keys=True).encode()
        ).hexdigest()
        row = dict(
            scenario_id=scenario.id,
            status=result.status,
            termination=result.termination,
            duration_executed_s=result.duration_executed_s,
            config_sha256=config_hash,
            **result.metrics.model_dump(),
        )
        summary_rows.append(row)
        body += f'<section><h2>{escape(scenario.id)} — <span class="{result.status}">{result.status}</span></h2><p>{escape(scenario.description)}</p>'
        body += table(
            [
                "Requirement",
                "Metric",
                "Measured",
                "Unit",
                "Criterion",
                "Status",
                "Rationale",
                "Evidence",
            ],
            [
                [
                    r.id,
                    r.metric,
                    r.measured,
                    r.unit,
                    f"{r.operator} {r.threshold}",
                    r.status,
                    r.rationale,
                    r.evidence,
                ]
                for r in result.requirements
            ],
        )
        body += table(["Metric", "Value"], list(result.metrics.model_dump().items()))
        body += inline_image(directory / "signals.png", scenario.id + " time histories")
        body += (
            "<details><summary>Resolved scenario / configuration</summary><pre>"
            + escape(json.dumps(resolved, indent=2))
            + "</pre></details></section>"
        )
    physics = physics_report(output)
    status = (
        "FAIL"
        if physics["result"]["status"] == "FAIL"
        or any(r.status == "FAIL" for r in results)
        else "INCONCLUSIVE"
        if any(r.status == "INCONCLUSIVE" for r in results)
        else "PASS"
    )
    summary = dict(
        schema_version=1,
        status=status,
        scenarios=summary_rows,
        physics_status=physics["result"]["status"],
        provenance=meta,
    )
    write_csv(output / "summary.csv", summary_rows)
    write_json(output / "summary.json", summary)
    (output / "report.html").write_text(
        page(
            "VEUS engineering verification report",
            "<h2>Batch outcome: "
            + status
            + "</h2>"
            + table(
                ["Scenario", "Status", "Termination"],
                [[r.scenario_id, r.status, r.termination] for r in results],
            )
            + physics["html"]
            + body,
        ),
        encoding="utf-8",
    )
    return summary
