"""Portable case studies use existing report primitives; source samples stay intact."""

import base64
import csv
from html import escape
import io
from pathlib import Path
from veus.testing.report import page, table, pyplot
from veus.replay.analysis import canonical


def measurement_csv(case):
    rows = []
    fields = [
        "recording",
        "source_run",
        "source_sha256",
        "sample_index",
        "elapsed_time_s",
        "source_time_s",
    ]
    for number, recording in enumerate(case["recordings"], 1):
        a = recording["analysis"]
        channels = {
            **{"measured__" + k: (v, a["units"][k]) for k, v in a["measured"].items()},
            **{"derived__" + k: (v, a["units"][k]) for k, v in a["derived"].items()},
        }
        for key, (_, unit) in channels.items():
            header = key + " [" + unit + "]"
            if header not in fields:
                fields.append(header)
        for i, time in enumerate(a["time_s"]):
            rows.append(
                dict(
                    recording=number,
                    source_run=a["configuration"]["source"]["run_id"],
                    source_sha256=recording["source_sha256"],
                    sample_index=i,
                    elapsed_time_s=time,
                    source_time_s=time + a["metadata"]["time_origin_s"],
                    **{
                        key + " [" + unit + "]": values[i]
                        for key, (values, unit) in channels.items()
                    },
                )
            )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def plot(recording, keys, title, interval=None):
    a = recording["analysis"]
    plt = pyplot()
    fig, axes = plt.subplots(
        len(keys), 1, figsize=(10, 2.3 * len(keys)), squeeze=False, sharex=True
    )
    channels = a["measured"] | a["derived"]
    for ax, key in zip(axes[:, 0], keys):
        xs = []
        ys = []
        for i, (time, value) in enumerate(zip(a["time_s"], channels[key])):
            if (
                i
                and time - a["time_s"][i - 1]
                > a["configuration"]["preprocessing"]["max_gap_s"]
            ):
                xs.append(float("nan"))
                ys.append(float("nan"))
            xs.append(time)
            ys.append(float("nan") if value is None else value)
        ax.plot(xs, ys, linewidth=1.3)
        ax.set_ylabel(key + "\n" + a["units"][key], fontsize=8)
        ax.grid(alpha=0.2)
        for gap in a["metadata"]["gaps"]:
            ax.axvspan(gap["start_s"], gap["end_s"], color="#e8c9a6", alpha=0.5)
        if interval:
            ax.axvspan(interval[0], interval[1], color="#a5d5b0", alpha=0.6)
            pad = max(2, (interval[1] - interval[0]) * 0.3)
            ax.set_xlim(
                max(0, interval[0] - pad), min(a["time_s"][-1], interval[1] + pad)
            )
    axes[-1, 0].set_xlabel("Elapsed recorded time (s)")
    fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=105)
    plt.close(fig)
    return (
        '<img alt="'
        + escape(title, quote=True)
        + '" src="data:image/png;base64,'
        + base64.b64encode(buf.getvalue()).decode()
        + '">'
    )


def html_report(case):
    body = (
        "<p>"
        + escape(case["scope"])
        + "</p><p>Observed/source values, derived calculations and inferred interpretations are explicitly qualified. No driving-style efficiency or causal ranking is made.</p>"
    )
    for i, recording in enumerate(case["recordings"], 1):
        a = recording["analysis"]
        src = a["configuration"]["source"]
        body += (
            "<section><h2>Recording "
            + str(i)
            + " · "
            + escape(src["dataset"] + " / " + src["run_id"])
            + "</h2><p>Origin: "
            + escape(src["kind"])
            + " · licence: "
            + escape(src["licence"])
            + "</p>"
        )
        body += table(
            [
                "Metric",
                "Value",
                "Unit",
                "Classification",
                "Status",
                "Definition / unavailable reason",
            ],
            [
                [
                    k,
                    v["value"],
                    v["unit"],
                    v["classification"],
                    v["status"],
                    v["definition"]
                    + (" " + v["unavailable_reason"] if v["value"] is None else ""),
                ]
                for k, v in recording["metrics"].items()
            ],
        )
        keys = [
            k
            for k in [
                "vehicle_speed_ms",
                "electrical_power_w",
                "battery_voltage_v",
                "battery_current_a",
                "battery_soc",
            ]
            if k in a["measured"] or k in a["derived"]
        ]
        body += plot(recording, keys[:2], "Recorded overview; shaded gaps are unknown")
        body += "<h3>Selected engineering events</h3>"
        if not recording["insights"]:
            body += (
                "<p>No events selected; no unsupported event insight is generated.</p>"
            )
        for insight in recording["insights"]:
            body += (
                "<h4>"
                + escape(insight["event_type"])
                + f" · {insight['start_s']:.3f}–{insight['end_s']:.3f} s</h4><p>Rule: "
                + escape(insight["rule"])
                + "</p>"
            )
            body += table(
                [
                    "Signal",
                    "Class",
                    "Valid / missing samples",
                    "Minimum",
                    "Maximum",
                    "Unit",
                    "First/last supporting sample",
                ],
                [
                    [
                        e["signal"],
                        e["classification"],
                        str(e["valid_samples"]) + " / " + str(e["missing_samples"]),
                        e["minimum"],
                        e["maximum"],
                        e["unit"],
                        str(e["first"]) + " / " + str(e["last"]),
                    ]
                    for e in insight["evidence"]
                ],
            )
            body += (
                "<p>Interpretation ("
                + escape(insight["interpretation_classification"])
                + "): "
                + escape(insight["interpretation"])
                + "</p><ul>"
                + "".join("<li>" + escape(v) + "</li>" for v in insight["limitations"])
                + "</ul>"
            )
            keys = [
                e["signal"]
                for e in insight["evidence"]
                if e["signal"]
                in ["vehicle_speed_ms", "electrical_power_w", "acceleration_ms2"]
            ]
            if keys:
                body += plot(
                    recording,
                    keys[:3],
                    "Selected interval and actual supporting samples",
                    (insight["start_s"], insight["end_s"]),
                )
        body += "<h3>Readiness and quality</h3>" + table(
            ["Capability", "Status", "Explanation"],
            [
                [c["name"], c["status"], c["explanation"]]
                for c in recording["readiness"]["capabilities"]
            ],
        )
        for label, value in [
            ("Source and timestamp quality", a["metadata"]),
            ("Configuration / event thresholds", recording["configuration"]),
            ("Provenance", recording["configuration"]["provenance"]),
            ("Limitations", recording["limitations"]),
            ("Readiness evidence", recording["readiness"]["configuration"]),
        ]:
            body += (
                "<details><summary>"
                + label
                + "</summary><pre>"
                + escape(canonical(value).decode())
                + "</pre></details>"
            )
        body += "</section>"
    if case["comparison"]:
        c = case["comparison"]
        body += (
            "<h2>Descriptive trip comparison</h2><p>"
            + escape(c["axis_definition"])
            + "</p>"
        )
        body += table(
            [
                "Metric",
                "First",
                "First class/status",
                "Second",
                "Second class/status",
                "Unit",
                "Second − first",
            ],
            [
                [
                    r["metric"],
                    r["first"]["value"],
                    r["first"]["classification"] + "/" + r["first"]["status"],
                    r["second"]["value"],
                    r["second"]["classification"] + "/" + r["second"]["status"],
                    r["unit"],
                    r["difference_second_minus_first"],
                ]
                for r in c["metrics"]
            ],
        )
        body += (
            "<ul>"
            + "".join("<li>" + escape(v) + "</li>" for v in c["limitations"])
            + "</ul>"
        )
    body += (
        "<h2>Reproducibility</h2><pre>"
        + escape(
            canonical(
                dict(
                    software_version=case["software_version"],
                    case_sha256=case["case_sha256"],
                    recordings=[
                        dict(
                            source_sha256=r["source_sha256"],
                            configuration=r["configuration"],
                            selected_event_indices=r["selected_event_indices"],
                            readiness_sha256=r["readiness"]["assessment_sha256"],
                            scoped_analysis_sha256=r["analysis"]["analysis_sha256"],
                            original_replay_sha256=r["analysis"][
                                "original_replay_analysis_sha256"
                            ],
                            software=r["analysis"]["software"],
                        )
                        for r in case["recordings"]
                    ],
                )
            ).decode()
        )
        + "</pre><p>Source CSV bytes are not modified. CSV export contains actual original rows converted to SI and separate derived columns, never synthetic interpolated samples. Plot lines are visual connections only. Case hash covers canonical JSON before inserting the hash itself; raw source/configuration and event settings allow reproduction.</p>"
    )
    return page(
        case["title"],
        body,
        scope="Engineering case study of recorded data. No physical vehicle validation, causal identification or safety certification.",
    )


def save(path: Path, case, inputs):
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise ValueError("Use a new/empty case-study directory")
    html = html_report(case)
    path.mkdir(parents=True, exist_ok=True)
    (path / "case-study.json").write_bytes(canonical(case))
    (path / "report.html").write_text(html, encoding="utf-8")
    (path / "measurements-derived.csv").write_text(
        measurement_csv(case), encoding="utf-8"
    )
    from veus.replay.api import decode

    for i, item in enumerate(inputs, 1):
        (path / f"original-{i}.csv").write_bytes(decode(item))
        (path / f"configuration-{i}.json").write_bytes(
            canonical(item.model_dump(mode="json", exclude={"csv_base64"}))
        )
