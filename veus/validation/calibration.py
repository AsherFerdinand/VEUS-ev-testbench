"""Bounded, deterministic parameter studies with explicit held-out-data guards."""

import math
from pydantic import Field, model_validator
from veus.contracts import StrictModel
from veus.validation.experiments import ModelParameters, evaluate, predict, prepare

BOUNDS = {
    "mass_kg": (500.0, 5000.0),
    "road_gradient_offset_rad": (-0.2, 0.2),
    "rolling_resistance": (0.001, 0.04),
    "drag_area_m2": (0.2, 1.5),
    "drive_efficiency": (0.5, 1.0),
    "battery_voltage_v": (100.0, 1000.0),
    "battery_resistance_ohm": (0.0, 1.0),
}
SUPPORTED = {
    "dynamics": {"rolling_resistance", "drag_area_m2"},
    "battery_current": {"battery_voltage_v", "battery_resistance_ohm"},
    "energy_replay": {"drive_efficiency"},
}
SENSITIVITY_SUPPORTED = {
    **SUPPORTED,
    "dynamics": SUPPORTED["dynamics"]
    | {"mass_kg", "drive_efficiency", "road_gradient_offset_rad"},
}


class ParameterRange(StrictModel):
    name: str
    low: float
    high: float

    @model_validator(mode="after")
    def bounds(self):
        if self.name not in BOUNDS:
            raise ValueError("Unsupported calibration/sensitivity parameter")
        lo, hi = BOUNDS[self.name]
        if not lo <= self.low < self.high <= hi:
            raise ValueError("Parameter range outside physical study bounds")
        return self


class CalibrationConfig(StrictModel):
    parameters: list[ParameterRange] = Field(min_length=1, max_length=2)
    objective_signal: str
    grid_points: int = Field(default=5, ge=3, le=9)
    refinements: int = Field(default=2, ge=1, le=4)

    @model_validator(mode="after")
    def unique(self):
        if len({p.name for p in self.parameters}) != len(self.parameters):
            raise ValueError("Duplicate parameter")
        return self


def modified(original, updates):
    return ModelParameters.model_validate(original.model_dump() | updates)


def guard_holdout(artifact, experiment):
    if artifact.get("status") != "CALIBRATED":
        raise ValueError("Calibration artifact has no accepted fitted parameters")
    source = experiment.source
    if source.role != "validation":
        raise ValueError("Independent evaluation requires validation-role data")
    training = artifact["training_source"]
    if (training.get("vehicle_id") or source.vehicle_id) and training.get(
        "vehicle_id"
    ) != source.vehicle_id:
        raise ValueError(
            "Calibration transfer to another/unknown vehicle is unsupported"
        )
    if source.expected_sha256 == training["expected_sha256"] or (
        source.dataset == training["dataset"] and source.run_id == training["run_id"]
    ):
        raise ValueError(
            "Calibration/validation leakage: duplicate data hash or same driving-run identity"
        )
    if artifact["experiment_kind"] != experiment.kind:
        raise ValueError("Calibration model kind differs")


def calibrate(experiment, data, config: CalibrationConfig):
    import numpy as np

    if experiment.source.role != "calibration":
        raise ValueError("Never fit final validation/exploration data")
    if not {p.name for p in config.parameters} <= SUPPORTED[experiment.kind]:
        raise ValueError(
            "Selected parameters are not identifiable from this experiment type"
        )
    if config.objective_signal not in {c.signal for c in experiment.comparisons}:
        raise ValueError("Objective must be an explicitly compared output")
    original = experiment.parameters
    for r in config.parameters:
        if not r.low <= getattr(original, r.name) <= r.high:
            raise ValueError("Initial parameters must lie within search bounds")
    data = prepare(data, experiment)
    evaluations = 0
    history = []

    def objective(parameters):
        nonlocal evaluations
        evaluations += 1
        value = evaluate(experiment, data, parameters)["metrics"][
            config.objective_signal
        ]
        if value["coverage"] < experiment.minimum_coverage or value["rmse"] is None:
            raise ValueError("Insufficient training-reference coverage")
        return value["rmse"]

    def rejected(status, reason, condition=None):
        return dict(
            schema_version=1,
            status=status,
            reason=reason,
            condition_number=condition
            if condition is not None and math.isfinite(condition)
            else None,
            experiment_kind=experiment.kind,
            training_source=experiment.source.model_dump(mode="json"),
            training_experiment=experiment.model_dump(mode="json"),
            initial_parameters=original.model_dump(),
            settings=config.model_dump(mode="json"),
            calibrated_parameters=None,
            objective="RMSE of " + config.objective_signal,
            initial_rmse=initial_error,
        )

    initial_error = objective(original)
    if (
        experiment.kind == "battery_current"
        and config.objective_signal == "battery_voltage_v"
    ):
        current = np.array(data.signals["battery_current_a"][1:], dtype=float)
        voltage = np.array(data.signals["battery_voltage_v"][1:], dtype=float)
        mask = np.isfinite(current) & np.isfinite(voltage)
        current = current[mask]
        voltage = voltage[mask]
        columns = []
        target = voltage.copy()
        names = [r.name for r in config.parameters]
        if "battery_voltage_v" in names:
            columns.append(np.ones_like(current))
        else:
            target -= original.battery_voltage_v
        if "battery_resistance_ohm" in names:
            columns.append(-current)
        else:
            target += original.battery_resistance_ohm * current
        design = np.column_stack(columns)
        norms = np.linalg.norm(design, axis=0)
        normalized = design / np.where(norms > 0, norms, 1)
        singular = np.linalg.svd(normalized, compute_uv=False)
        condition = (
            float(singular[0] / singular[-1]) if singular[-1] > 1e-12 else float("inf")
        )
        rank = int(np.linalg.matrix_rank(normalized, tol=1e-6))
        if rank < len(names) or condition > 100:
            return rejected(
                "NOT_IDENTIFIABLE",
                "Insufficient independent current excitation for local Voc/R regression",
                condition,
            )
        solution = np.linalg.lstsq(design, target, rcond=None)[0]
        ordered = [
            n for n in ("battery_voltage_v", "battery_resistance_ohm") if n in names
        ]
        updates = dict(zip(ordered, map(float, solution)))
        if any(not r.low <= updates[r.name] <= r.high for r in config.parameters):
            return rejected(
                "OUT_OF_BOUNDS",
                "Unconstrained local least-squares solution exceeds declared physical bounds; no clipped estimate is presented",
                condition,
            )
        best = modified(original, updates)
        best_error = objective(best)
        method = "bounded-acceptance linear least squares (Voc - R*I)"
    else:
        # Finite-difference observability at the original model, before fitting.
        signal = config.objective_signal
        columns = []
        for r in config.parameters:
            delta = (r.high - r.low) * 0.001
            at = getattr(original, r.name)
            lo = max(r.low, at - delta)
            hi = min(r.high, at + delta)
            a = predict(experiment, data, modified(original, {r.name: lo}))
            b = predict(experiment, data, modified(original, {r.name: hi}))
            columns.append(
                np.array([bb[signal] - aa[signal] for aa, bb in zip(a, b)])
                / (hi - lo)
                * (r.high - r.low)
            )
        design = np.column_stack(columns)
        norms = np.linalg.norm(design, axis=0)
        normalized = design / np.where(norms > 1e-12, norms, 1)
        singular = np.linalg.svd(normalized, compute_uv=False)
        rank = int(np.linalg.matrix_rank(normalized, tol=1e-6))
        condition = (
            float(singular[0] / singular[-1]) if singular[-1] > 1e-12 else float("inf")
        )
        if rank < len(config.parameters) or min(norms) < 1e-8 or condition > 100:
            return rejected(
                "NOT_IDENTIFIABLE",
                "Prediction sensitivities are zero or too dependent for selected parameters",
                condition,
            )
        import itertools

        ranges = [(r.low, r.high) for r in config.parameters]
        best = original
        best_error = initial_error
        for refinement in range(config.refinements):
            axes = [np.linspace(lo, hi, config.grid_points) for lo, hi in ranges]
            for combination in itertools.product(*axes):
                candidate = modified(
                    original,
                    {
                        r.name: float(value)
                        for r, value in zip(config.parameters, combination)
                    },
                )
                score = objective(candidate)
                if score < best_error:
                    best = candidate
                    best_error = score
            history.append(
                dict(
                    refinement=refinement, rmse=best_error, parameters=best.model_dump()
                )
            )
            ranges = [
                (
                    max(
                        r.low,
                        getattr(best, r.name) - (hi - lo) / (config.grid_points - 1),
                    ),
                    min(
                        r.high,
                        getattr(best, r.name) + (hi - lo) / (config.grid_points - 1),
                    ),
                )
                for r, (lo, hi) in zip(config.parameters, ranges)
            ]
        method = "deterministic bounded grid refinement"
    return dict(
        schema_version=1,
        status="CALIBRATED",
        experiment_kind=experiment.kind,
        evidence_kind=experiment.source.kind,
        training_source=experiment.source.model_dump(mode="json"),
        training_experiment=experiment.model_dump(mode="json"),
        initial_parameters=original.model_dump(),
        calibrated_parameters=best.model_dump(),
        settings=config.model_dump(mode="json"),
        objective="RMSE of " + config.objective_signal,
        initial_rmse=initial_error,
        training_rmse=best_error,
        condition_number=condition,
        identifiability="Local to chosen inputs, fixed other parameters and model assumptions; not global physical uniqueness",
        method=method,
        evaluations=evaluations,
        history=history,
    )


def sensitivity(experiment, data, ranges: list[ParameterRange], signal: str):
    if signal not in {c.signal for c in experiment.comparisons}:
        raise ValueError("Sensitivity signal must be a supported compared output")
    data = prepare(data, experiment)
    base = predict(experiment, data)
    rows = []
    curves = {}
    for r in ranges:
        if r.name not in SENSITIVITY_SUPPORTED[experiment.kind]:
            raise ValueError("Parameter unsupported by experiment")
        if not r.low <= getattr(experiment.parameters, r.name) <= r.high:
            raise ValueError("Sensitivity baseline must be inside the requested range")
        low = predict(
            experiment, data, modified(experiment.parameters, {r.name: r.low})
        )
        high = predict(
            experiment, data, modified(experiment.parameters, {r.name: r.high})
        )
        delta = [b[signal] - a[signal] for a, b in zip(low, high)]
        rows.append(
            dict(
                parameter=r.name,
                low=r.low,
                high=r.high,
                signal=signal,
                rms_prediction_span=math.sqrt(sum(v * v for v in delta) / len(delta)),
                final_prediction_span=delta[-1],
                interpretation="One-at-a-time range effect; ranking depends on specified ranges, not parameter identification",
            )
        )
        curves[r.name] = dict(
            time_s=[f["time_s"] for f in base],
            baseline=[f[signal] for f in base],
            low=[f[signal] for f in low],
            high=[f[signal] for f in high],
        )
    return dict(
        rows=sorted(rows, key=lambda r: r["rms_prediction_span"], reverse=True),
        curves=curves,
    )
