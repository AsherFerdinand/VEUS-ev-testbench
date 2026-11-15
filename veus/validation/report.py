"""Portable experiment reports, separate from scenario safety verdicts."""

import base64
import hashlib
from html import escape
import io
import json
from pathlib import Path
from veus.testing.report import pyplot, page, table, write_json, write_csv, provenance
from veus.validation.experiments import evaluate, ModelParameters
from veus.validation.measurements import load_csv, CANONICAL
from veus.validation.calibration import guard_holdout, sensitivity


def image(fig):
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=110)
    pyplot().close(fig)
    return (
        '<img alt="Measured versus predicted signals and residuals" src="data:image/png;base64,'
        + base64.b64encode(buffer.getvalue()).decode()
        + '">'
    )


def analyse(
    experiment,
    raw,
    artifact=None,
    ranges=None,
    sensitivity_signal=None,
    training_study=False,
    config_file_bytes=None,
):
    data = load_csv(raw, experiment.source, experiment.preprocessing)
    original = evaluate(experiment, data)
    calibrated = None
    if artifact and artifact.get("status") == "CALIBRATED":
        if training_study:
            if (
                experiment.source.role != "calibration"
                or artifact["training_source"]["expected_sha256"]
                != experiment.source.expected_sha256
            ):
                raise ValueError("Training report source mismatch")
        else:
            guard_holdout(artifact, experiment)
        learned = ModelParameters.model_validate(artifact["calibrated_parameters"])
        names = [r["name"] for r in artifact["settings"]["parameters"]]
        applied = ModelParameters.model_validate(
            experiment.parameters.model_dump()
            | {name: getattr(learned, name) for name in names}
        )
        calibrated = evaluate(experiment, data, applied)
    elif artifact and not training_study:
        raise ValueError("Calibration did not yield identifiable bounded parameters")
    numeric = (calibrated or original)["status"]
    label = (
        "Synthetic pipeline demonstration"
        if experiment.source.kind == "synthetic"
        else "Calibration study"
        if training_study
        else "Experimental validation"
        if experiment.source.role == "validation" and experiment.source.inputs_verified
        else "Measured-data exploratory comparison — validation pending"
    )
    if experiment.source.kind == "synthetic" and training_study:
        label += " — calibration study"
    evidence = (
        "SYNTHETIC_ONLY"
        if experiment.source.kind == "synthetic"
        else "CONDITIONS_ASSERTED_BY_DATA_PROVIDER"
        if experiment.source.inputs_verified
        else "CONDITIONS_UNVERIFIED"
    )
    outcome = (
        "INCONCLUSIVE"
        if evidence == "CONDITIONS_UNVERIFIED"
        or (artifact and artifact["status"] != "CALIBRATED")
        else numeric
    )
    study = (
        sensitivity(experiment, data, ranges, sensitivity_signal) if ranges else None
    )
    summary = dict(
        schema_version=1,
        framework_version="veus-measurements-v1",
        label=label,
        status=outcome,
        numerical_status=numeric,
        evidence_status=evidence,
        experimental_scope="No broad vehicle or safety validation is implied. Inputs/provenance verification is a source assertion, not authenticated by this software.",
        source=data.metadata,
        experiment=experiment.model_dump(mode="json"),
        configuration_sha256=hashlib.sha256(
            (json.dumps(experiment.model_dump(mode="json"), indent=2) + "\n").encode()
        ).hexdigest(),
        configuration_hash_basis="experiment.json emitted by this report, UTF-8 with indent=2 and final newline",
        original_configuration_sha256=hashlib.sha256(config_file_bytes).hexdigest()
        if config_file_bytes
        else None,
        calibration_artifact_sha256=hashlib.sha256(
            json.dumps(artifact, sort_keys=True).encode()
        ).hexdigest()
        if artifact
        else None,
        calibration=artifact,
        original={
            k: v for k, v in original.items() if k not in ["predictions", "residuals"]
        },
        calibrated={
            k: v for k, v in calibrated.items() if k not in ["predictions", "residuals"]
        }
        if calibrated
        else None,
        sensitivity=study,
        provenance=provenance(Path(__file__).resolve().parents[2])
        | {"validation_scope": label + "; no broad vehicle or safety validation"},
    )
    body = (
        "<h2>"
        + escape(label)
        + "</h2><p>Outcome: <strong>"
        + outcome
        + "</strong>; numerical criteria: "
        + numeric
        + "; evidence: "
        + evidence
        + ".</p>"
    )
    body += (
        "<p>"
        + escape(experiment.objective)
        + "</p><h2>Dataset, units and preprocessing</h2><pre>"
        + escape(json.dumps(data.metadata, indent=2))
        + "</pre>"
    )
    body += (
        "<h2>Model and initial conditions</h2><pre>"
        + escape(
            json.dumps(
                dict(
                    parameters=original["parameters"],
                    initial_conditions=original["initial_conditions"],
                    assumptions=experiment.assumptions,
                ),
                indent=2,
            )
        )
        + "</pre>"
    )
    body += "<h2>Errors and acceptance criteria</h2>"
    rows = []
    for variant, result in [("Original", original), ("Calibrated", calibrated)]:
        if result is None:
            continue
        for key, m in result["metrics"].items():
            c = m["criterion"]
            rows.append(
                [
                    variant,
                    key,
                    CANONICAL[key],
                    m["mae"],
                    m["rmse"],
                    m["max_abs_error"],
                    m["bias"],
                    m["coverage"],
                    f"{c['metric']} <= {c['threshold']}",
                    str(m["uncertainty_interval"]),
                    m["status"],
                    c["rationale"],
                ]
            )
    body += table(
        [
            "Model",
            "Signal",
            "Unit",
            "MAE",
            "RMSE",
            "Maximum absolute error",
            "Bias",
            "Coverage",
            "Criterion",
            "Criterion uncertainty interval",
            "Status",
            "Rationale",
        ],
        rows,
    )
    body += "<p>Residual = prediction minus measurement. Initial-condition sample is excluded. Missing values are not zero. Uncertainty intervals use bounded output allowances; input uncertainty is not propagated. No percentage error or correlation-only accuracy claim.</p>"
    plt = pyplot()
    for comparison in experiment.comparisons:
        key = comparison.signal
        points = [r for r in original["residuals"] if r["signal"] == key]
        fig, axes = plt.subplots(
            2, 1, figsize=(11, 6), layout="constrained", sharex=True
        )
        times = [r["time_s"] for r in points]
        clean = lambda k: [r[k] if r[k] is not None else float("nan") for r in points]
        axes[0].plot(
            times,
            clean("measured"),
            label="Reference (" + experiment.source.kind + ")",
            color="#172b3f",
        )
        axes[0].plot(times, clean("predicted"), label="Original model", linestyle="--")
        axes[1].plot(times, clean("residual"), label="Original residual")
        if calibrated:
            after = [r for r in calibrated["residuals"] if r["signal"] == key]
            axes[0].plot(
                times,
                [r["predicted"] for r in after],
                label="Calibrated model",
                linestyle=":",
            )
            axes[1].plot(
                times,
                [
                    r["residual"] if r["residual"] is not None else float("nan")
                    for r in after
                ],
                label="Calibrated residual",
            )
        for ax in axes:
            ax.grid(alpha=0.25)
            ax.legend()
        axes[0].set(ylabel=key + " (" + CANONICAL[key] + ")")
        axes[1].set(xlabel="Time (s)", ylabel="Residual (" + CANONICAL[key] + ")")
        if comparison.uncertainty:
            axes[1].axhspan(
                -comparison.uncertainty,
                comparison.uncertainty,
                alpha=0.15,
                color="grey",
            )
        body += image(fig)
    body += (
        "<h2>Stopping event comparison</h2><pre>"
        + escape(json.dumps(original.get("events", {}), indent=2))
        + "</pre>"
    )
    if artifact:
        body += (
            "<h2>Calibration and identifiability</h2><pre>"
            + escape(json.dumps(artifact, indent=2))
            + "</pre>"
        )
    if study:
        body += "<h2>One-at-a-time sensitivity (not calibration)</h2>" + table(
            ["Parameter", "Low", "High", "Output", "RMS prediction span"],
            [
                [
                    r["parameter"],
                    r["low"],
                    r["high"],
                    r["signal"],
                    r["rms_prediction_span"],
                ]
                for r in study["rows"]
            ],
        )
        for name, curve in study["curves"].items():
            fig, ax = plt.subplots(figsize=(10, 4), layout="constrained")
            for key in ("baseline", "low", "high"):
                ax.plot(curve["time_s"], curve[key], label=key)
            ax.set(
                title=name,
                xlabel="Time (s)",
                ylabel=sensitivity_signal + " (" + CANONICAL[sensitivity_signal] + ")",
            )
            ax.grid(alpha=0.25)
            ax.legend()
            body += image(fig)
    body += (
        "<h2>Limitations and reproducibility</h2><p>Fixed OCV/resistance and efficiencies; no thermal dynamics, parameter calibration against vehicle measurements unless explicitly identified above, or production safety evidence. Unverified inputs/conditions leave physical validation pending. Source hashes cannot authenticate provenance claims.</p><pre>"
        + escape(json.dumps(summary["provenance"], indent=2))
        + "</pre>"
    )
    html = page(
        "VEUS measurement experiment report",
        body,
        scope="Evidence class: "
        + label
        + ". No broad vehicle accuracy or automotive safety certification is established.",
    )
    # Limit browser preview, not the full stored offline residuals.
    residuals = (calibrated or original)["residuals"]
    preview = residuals[:: max(1, len(residuals) // 2000)]
    return dict(
        summary=summary,
        html=html,
        preview=preview,
        original=original,
        calibrated=calibrated,
        data=data,
    )


def save(output: Path, result, raw: bytes):
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError(
            "Output must be empty/new; previous evidence is never overwritten"
        )
    (output / "original.csv").write_bytes(raw)
    write_json(output / "experiment.json", result["summary"]["experiment"])
    data = result["data"]
    rows = [
        dict(time_s=t, **{k: v[i] for k, v in data.signals.items()})
        for i, t in enumerate(data.times)
    ]
    write_csv(output / "standardised.csv", rows)
    write_json(output / "report.json", result["summary"])
    write_csv(output / "original-residuals.csv", result["original"]["residuals"])
    if result["calibrated"]:
        write_csv(
            output / "calibrated-residuals.csv", result["calibrated"]["residuals"]
        )
    (output / "report.html").write_text(result["html"], encoding="utf-8")
