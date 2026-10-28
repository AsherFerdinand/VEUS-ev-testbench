"""Portable, measured/derived-labelled analysis artifacts."""

import base64
import csv
from html import escape
import io
import json
from pathlib import Path
from veus.testing.report import page, table, pyplot, write_csv
from veus.replay.analysis import canonical


def event_csv(result):
    stream = io.StringIO(newline="")
    keys = [
        "type",
        "start_s",
        "end_s",
        "source_start_s",
        "source_end_s",
        "classification",
        "signals",
        "rule",
        "qualification",
    ]
    writer = csv.DictWriter(stream, fieldnames=keys, lineterminator="\n")
    writer.writeheader()
    for event in result["events"]:
        writer.writerow(event | {"signals": ";".join(event["signals"])})
    return stream.getvalue()


def html_report(result):
    source = result["configuration"]["source"]
    label = (
        "Genuine measured recording"
        if source["kind"] == "measured"
        else "Synthetic software fixture"
    )
    body = (
        "<h2>"
        + escape(source["dataset"] + " / " + source["run_id"])
        + "</h2><p>"
        + label
        + ". No simulation prediction or model fitting was performed.</p>"
    )
    body += "<h2>Trip summary</h2>" + table(
        ["Metric", "Value", "Unit", "Class", "Definition / unavailable reason"],
        [
            [
                k,
                v["value"],
                v["unit"],
                v["classification"],
                v["definition"]
                + (" " + v["unavailable_reason"] if v["value"] is None else ""),
            ]
            for k, v in result["summary"].items()
        ],
    )
    for signal, values in [
        ("vehicle_speed_ms", result["measured"]["vehicle_speed_ms"]),
        ("electrical_power_w", result["derived"].get("electrical_power_w")),
    ]:
        if values is None:
            continue
        fig, ax = pyplot().subplots(figsize=(10, 3))
        # Insert NaN in timestamp gaps instead of drawing a misleading connecting line.
        xs, ys = [], []
        for i, (time, value) in enumerate(zip(result["time_s"], values)):
            if (
                i
                and time - result["time_s"][i - 1]
                > result["configuration"]["preprocessing"]["max_gap_s"]
            ):
                xs.append(float("nan"))
                ys.append(float("nan"))
            xs.append(time)
            ys.append(float("nan") if value is None else value)
        ax.plot(xs, ys, marker=".", markersize=3)
        ax.set(
            xlabel="Elapsed recorded time (s)",
            ylabel=signal + " / " + result["units"][signal],
            title=result["classifications"][signal],
        )
        ax.grid(alpha=0.2)
        fig.tight_layout()
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=110)
        pyplot().close(fig)
        body += (
            '<img alt="'
            + escape(signal)
            + ' full-resolution recorded series" src="data:image/png;base64,'
            + base64.b64encode(buffer.getvalue()).decode()
            + '">'
        )
    body += "<h2>Threshold events</h2><p>Sample-based rules, not machine learning or diagnosed causes. Timing depends on measurement cadence and noise.</p>"
    body += table(
        [
            "Type",
            "Elapsed start/end (s)",
            "Source start/end (s)",
            "Class",
            "Signals",
            "Rule",
            "Qualification",
        ],
        [
            [
                e["type"],
                f"{e['start_s']} / {e['end_s']}",
                f"{e['source_start_s']} / {e['source_end_s']}",
                e["classification"],
                ", ".join(e["signals"]),
                e["rule"],
                e["qualification"],
            ]
            for e in result["events"]
        ],
    )
    body += (
        "<h2>Comparison availability</h2><p>"
        + escape(result["comparison"]["reason"])
        + "</p><p>"
        + escape(result["quality"]["physical_validation"])
        + "</p>"
    )
    for title, key in [
        ("Dataset / provenance / units", "metadata"),
        ("Settings and thresholds", "configuration"),
        ("Derivation and interpolation rules", "methods"),
        ("Data quality", "quality"),
    ]:
        body += (
            "<h2>"
            + title
            + "</h2><pre>"
            + escape(json.dumps(result[key], indent=2))
            + "</pre>"
        )
    body += (
        "<h2>Reproduction hashes</h2><pre>"
        + escape(
            json.dumps(
                {
                    k: result[k]
                    for k in [
                        "algorithm_version",
                        "software",
                        "configuration_sha256",
                        "analysis_sha256",
                    ]
                },
                indent=2,
            )
        )
        + "</pre><p>The analysis hash covers canonical JSON before its own hash is inserted. Elapsed timestamps are relative to metadata.time_origin_s; original CSV bytes are unchanged. This report is descriptive measurement analysis, not model validation. Full resolution is used; plot lines are a visual connection, not added measurements.</p>"
    )
    return page(
        "VEUS recorded EV analysis",
        body,
        scope=label
        + " — recorded-data replay and descriptive engineering analysis; no physical validation claim.",
    )


def summary_export(result):
    return {
        k: v
        for k, v in result.items()
        if k not in ["time_s", "measured", "derived", "valid_speed_intervals"]
    }


def save(directory: Path, result, raw):
    if directory.exists() and (not directory.is_dir() or any(directory.iterdir())):
        raise ValueError("Use a new/empty analysis directory")
    # Render first so missing optional dependencies cannot leave incomplete output.
    html = html_report(result)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "original.csv").write_bytes(raw)
    (directory / "configuration.json").write_bytes(canonical(result["configuration"]))
    (directory / "analysis.json").write_bytes(canonical(result))
    (directory / "summary.json").write_bytes(canonical(summary_export(result)))
    (directory / "events.json").write_bytes(canonical(result["events"]))
    (directory / "events.csv").write_text(event_csv(result), encoding="utf-8")
    (directory / "report.html").write_text(html, encoding="utf-8")
    for name, signals in [
        ("standardised-measured", result["measured"]),
        ("derived", result["derived"]),
    ]:
        write_csv(
            directory / (name + ".csv"),
            [
                {
                    "elapsed_time_s": t,
                    "source_time_s": t + result["metadata"]["time_origin_s"],
                    **{k: v[i] for k, v in signals.items()},
                }
                for i, t in enumerate(result["time_s"])
            ],
        )
