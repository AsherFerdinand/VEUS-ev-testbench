"""Recognition is a proposal. Readiness follows confirmed mappings and validation."""

import hashlib
from typing import Literal
from pydantic import Field, model_validator
from veus.contracts import StrictModel
from veus.validation.measurements import (
    DataSource,
    ImportConfig,
    UNITS,
    csv_structure,
    load_csv,
    derive_acceleration,
)
from veus.validation.experiments import Experiment, prepare
from veus.replay.analysis import SanityLimits, ReplayConfig, canonical, validate_window
from veus.readiness.registry import CAPABILITIES, registry, SIGNAL_NAMES

# Suggestions never select units, polarity, calibration or synchronization.
ALIASES = {
    "time_s": ("timestamp", "time", "time_s", "Timestamp(ms)"),
    "vehicle_speed_ms": (
        "speed",
        "vehicle_speed",
        "speed_kmh",
        "vehicle_speed_ms",
        "Vehicle Speed[km/h]",
    ),
    "battery_voltage_v": (
        "voltage",
        "battery_voltage",
        "pack_voltage",
        "battery_voltage_v",
        "HV Battery Voltage[V]",
    ),
    "battery_current_a": (
        "current",
        "battery_current",
        "pack_current",
        "battery_current_a",
        "HV Battery Current[A]",
    ),
    "battery_soc": (
        "soc",
        "battery_soc",
        "state_of_charge",
        "soc_pct",
        "HV Battery SOC[%]",
    ),
    "motor_torque_nm": ("motor_torque", "torque_nm", "motor_torque_nm"),
    "motor_speed_rad_s": ("motor_speed", "motor_rpm", "motor_speed_rad_s"),
    "brake_force_n": ("brake_force_n", "brake_force"),
    "road_gradient_rad": ("grade", "road_slope", "road_gradient_rad", "grade_percent"),
    "ambient_temperature_c": (
        "ambient_temp",
        "outside_temperature",
        "ambient_temperature_c",
        "OAT[DegC]",
    ),
    "longitudinal_acceleration_ms2": (
        "acceleration",
        "acceleration_ms2",
        "longitudinal_acceleration_ms2",
    ),
    "battery_power_w": ("battery_power_w", "battery_power", "power_kw"),
    "position_m": ("position_m", "distance_m"),
    "energy_wh": ("energy_wh", "energy_kwh"),
}
UNSUPPORTED_ALIASES = {
    "throttle": "Accelerator pedal position is not a supported measured replay input. Do not map it to motor torque.",
    "accelerator_pedal": "Accelerator position is not motor torque; no conversion model is supplied.",
    "brake": "Pedal demand is not a brake force in N; no conversion model is supplied.",
    "brake_pedal": "Brake pedal position is not brake force; do not assume units or a conversion.",
}


def inspect(raw):
    if len(raw) > 2_000_000:
        raise ValueError("Select a CSV window no larger than 2 MB.")
    header, rows = csv_structure(raw)
    count = 0
    preview = []
    for row in rows:
        count += 1
        if count > 5000:
            raise ValueError("Select at most 5000 rows for interactive readiness.")
        if len(preview) < 3:
            preview.append(row)
    return dict(
        columns=header,
        record_count=count,
        preview=preview,
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        suggestions=[
            dict(
                signal=signal,
                label=SIGNAL_NAMES[signal],
                candidates=[
                    h
                    for h in header
                    if h.strip().casefold() in {alias.casefold() for alias in names}
                ],
                units=list(UNITS[signal]),
            )
            for signal, names in ALIASES.items()
        ],
        unsupported=[
            dict(column=h, explanation=UNSUPPORTED_ALIASES[h.strip().casefold()])
            for h in header
            if h.strip().casefold() in UNSUPPORTED_ALIASES
        ],
        warning="Suggestions only. Confirm columns, units and source origin; no current/torque polarity or measurement quality is inferred.",
    )


class Assertions(StrictModel):
    synchronization_confirmed: bool = False
    measurement_quality_documented: bool = False
    operating_conditions_documented: bool = False
    torque_sign_confirmed: bool = False
    evidence_notes: str = ""

    @model_validator(mode="after")
    def evidence(self):
        if (
            any(
                [
                    self.synchronization_confirmed,
                    self.measurement_quality_documented,
                    self.operating_conditions_documented,
                    self.torque_sign_confirmed,
                ]
            )
            and len(self.evidence_notes.strip()) < 10
        ):
            raise ValueError(
                "Add evidence notes for checked engineering assertions; presence of columns is not evidence."
            )
        return self


class ReadinessConfig(StrictModel):
    source: DataSource
    preprocessing: ImportConfig
    current_sign: Literal["unknown", "discharge_positive", "charge_positive"] = (
        "unknown"
    )
    sign_evidence: str | None = None
    assertions: Assertions = Field(default_factory=Assertions)
    sanity_limits: SanityLimits = Field(default_factory=SanityLimits)
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Uploader-supplied metadata and evidence are not independently authenticated."
        ]
    )
    experiment: Experiment | None = None
    provenance: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def sign(self):
        if self.current_sign != "unknown" and (
            not self.sign_evidence or len(self.sign_evidence.strip()) < 10
        ):
            raise ValueError(
                "A known current polarity requires explicit sign evidence."
            )
        mappings = [m.column for m in self.preprocessing.columns.values()]
        if len(mappings) != len(set(mappings)):
            raise ValueError(
                "Map each source column to at most one signal; do not use an output as a missing independent input."
            )
        return self


ASSUMPTION_TEXT = {
    "current_polarity": "Verify current polarity and document its source; no discharge or charging direction is inferred.",
    "synchronization_confirmed": "Document channel synchronization and time alignment.",
    "measurement_quality_documented": "Document measurement accuracy, calibration and signal-quality evidence.",
    "operating_conditions_documented": "Document vehicle configuration, road loads, payload and relevant operating conditions.",
    "torque_sign_confirmed": "Establish propulsion torque sign/convention; pedal position is not motor torque.",
    "measured_origin": "Physical validation requires independently measured references, not synthetic fixtures.",
    "phase8_experiment": "Supply a matching explicit Phase 8 dynamics Experiment JSON with defined parameters, initial conditions, measured grade, validation-role references and verified input-condition metadata.",
    "charging_origin_established": "Establish the charging source; negative pack power alone does not prove regeneration.",
    "motor_boundary_power": "Motor-boundary electrical power and loss-boundary evidence are needed; pack power is insufficient.",
}


def assess(raw, config: ReadinessConfig):
    if len(raw) > 2_000_000:
        raise ValueError("Select a CSV window no larger than 2 MB.")
    data = load_csv(raw, config.source, config.preprocessing)
    validate_window(data, config.sanity_limits)
    signals = {"time_s": data.times, **data.signals}
    n = len(data.times)
    valid = {key: sum(v is not None for v in values) for key, values in signals.items()}
    speed = data.signals.get("vehicle_speed_ms")
    speed_intervals = [
        i
        for i in range(n - 1)
        if speed
        and speed[i] is not None
        and speed[i + 1] is not None
        and data.times[i + 1] - data.times[i] <= data.max_gap_s
    ]
    accel = derive_acceleration(data) if speed is not None else []
    joint = sum(
        v is not None and i is not None
        for v, i in zip(
            signals.get("battery_voltage_v", [None] * n),
            signals.get("battery_current_a", [None] * n),
        )
    )
    exp = config.experiment
    reference_error = None
    try:
        references = prepare(data, exp).signals if exp else {}
    except ValueError as exc:
        references = {}
        reference_error = str(exc)
    explicit = bool(
        exp
        and exp.kind == "dynamics"
        and exp.source.kind == "measured"
        and exp.source.role == "validation"
        and exp.source.inputs_verified
        and exp.source.expected_sha256 == config.source.expected_sha256
        and exp.source.vehicle_id == config.source.vehicle_id
        and exp.source.dataset == config.source.dataset
        and exp.source.run_id == config.source.run_id
        and exp.preprocessing.model_dump() == config.preprocessing.model_dump()
        and exp.road_grade_policy == "measured"
        and exp.comparisons
        and any(
            c.signal
            in {"vehicle_speed_ms", "longitudinal_acceleration_ms2", "position_m"}
            for c in exp.comparisons
        )
        and all(
            c.signal in references and all(v is not None for v in references[c.signal])
            for c in exp.comparisons
        )
        and (
            exp.initial_speed_ms is not None
            or (speed is not None and speed[0] is not None)
        )
    )
    assertions = config.assertions.model_dump()
    established = assertions | {
        "current_polarity": config.current_sign != "unknown",
        "measured_origin": config.source.kind == "measured",
        "phase8_experiment": explicit,
        "charging_origin_established": False,
        "motor_boundary_power": False,
    }
    capabilities = []
    for cap in CAPABILITIES:
        missing = [key for key in cap.required_signals if key not in signals]
        invalid = [
            key for key in cap.required_signals if key in signals and valid[key] == 0
        ]
        partial = [
            key for key in cap.required_signals if key in signals and 0 < valid[key] < n
        ]
        blockers = [] if cap.implemented else [cap.availability_explanation]
        conditions = []
        if missing:
            blockers.append(
                "Missing mapped signals: "
                + ", ".join(SIGNAL_NAMES[key] for key in missing)
                + "."
            )
        if invalid:
            blockers.append(
                "No valid samples in: "
                + ", ".join(SIGNAL_NAMES[key] for key in invalid)
                + "."
            )
        if cap.id == "longitudinal_validation" and config.source.kind != "measured":
            blockers.append(
                "Synthetic references support verification, not physical validation. Obtain independent measured reference data."
            )
        if cap.id == "longitudinal_validation" and reference_error:
            blockers.append(
                "The explicit experiment cannot use this recording: "
                + reference_error
                + ". Supply the independent reference or correct the configuration."
            )
        if not missing and not invalid:
            for quality in cap.quality_conditions:
                if quality == "valid_speed_intervals" and not speed_intervals:
                    blockers.append(
                        "No adjacent valid speed/time interval within the gap limit; motion cannot be replayed reliably."
                    )
                if quality == "acceleration_stencil" and not any(
                    v is not None for v in accel
                ):
                    blockers.append(
                        "No complete speed stencil for local acceleration; missing values or timestamp gaps prevent differentiation."
                    )
                if quality == "joint_electrical_samples" and joint == 0:
                    blockers.append(
                        "Voltage/current have no jointly valid samples; signed power cannot be calculated."
                    )
                if quality == "complete_electrical_window" and (
                    joint != n or data.metadata["gaps"]
                ):
                    blockers.append(
                        "Full-window energy needs complete joint voltage/current samples and no excessive timestamp gaps. Select a complete window or obtain the missing measurements."
                    )
                if quality == "complete_required_window" and (
                    partial or data.metadata["gaps"]
                ):
                    blockers.append(
                        "A complete independent model-input/reference window is required; gaps/missing required samples prevent physical-comparison readiness."
                    )
                if quality == "nonnegative_drive_torque" and any(
                    v is not None and v < 0 for v in signals.get("motor_torque_nm", [])
                ):
                    blockers.append(
                        "The existing predictive plant requires nonnegative drive torque with separate brake force; this mapping contains negative drive torque."
                    )
        unmet = [key for key in cap.assumptions if not established.get(key, False)]
        conditions.extend(ASSUMPTION_TEXT[key] for key in unmet)
        # Inspection is gap-aware; partial coverage is usable but explicitly conditional.
        if cap.implemented and partial:
            conditions.append(
                "Some required samples are missing: "
                + ", ".join(partial)
                + ". Results cover available samples only."
            )
        if (
            cap.implemented
            and data.metadata["gaps"]
            and cap.id not in ["energy_consumption", "longitudinal_validation"]
        ):
            conditions.append(
                "Timestamp gaps remain unknown; no interpolation or integration is performed across them."
            )
        status = (
            "UNAVAILABLE" if blockers else "CONDITIONAL" if conditions else "AVAILABLE"
        )
        capabilities.append(
            dict(
                id=cap.id,
                name=cap.name,
                description=cap.description,
                status=status,
                workspace=cap.workspace,
                explanation=" ".join(blockers + conditions)
                if blockers or conditions
                else cap.availability_explanation,
                missing_signals=missing,
                invalid_signals=invalid,
                partial_signals=partial,
                unresolved_assumptions=unmet,
                additional_data=list(
                    dict.fromkeys(
                        [
                            "Provide " + key + " with explicit units and timestamps."
                            for key in missing
                        ]
                        + conditions
                    )
                ),
                requirements=next(item for item in registry() if item["id"] == cap.id),
            )
        )
    replayable = (
        next(c for c in capabilities if c["id"] == "recorded_replay")["status"]
        != "UNAVAILABLE"
    )
    replay = None
    if replayable:
        replay = ReplayConfig(
            source=config.source,
            preprocessing=config.preprocessing,
            current_sign=config.current_sign,
            sign_evidence=config.sign_evidence,
            sanity_limits=config.sanity_limits,
            limitations=config.limitations
            + [
                c["name"] + ": " + c["explanation"]
                for c in capabilities
                if c["status"] == "CONDITIONAL"
            ],
            provenance=config.provenance,
        ).model_dump(mode="json")
    result = dict(
        schema_version=1,
        scope="Software/data readiness under stated assumptions; not physical model validation or authenticated measurement quality.",
        metadata=data.metadata,
        recording_duration_s=data.times[-1],
        duplicate_timestamps=0,
        timestamp_status="Strictly increasing; duplicates are rejected, not repaired.",
        signal_quality={
            key: dict(
                valid_samples=valid[key],
                missing_samples=n - valid[key],
                unit="s" if key == "time_s" else data.metadata["canonical_units"][key],
            )
            for key in signals
        },
        assumptions=config.assertions.model_dump(),
        current_sign=config.current_sign,
        capabilities=capabilities,
        configuration=config.model_dump(mode="json"),
        replay_configuration=replay,
        physical_validation="Phase 8 INCONCLUSIVE findings remain unchanged. AVAILABLE is not a validation PASS.",
    )
    result["assessment_sha256"] = hashlib.sha256(canonical(result)).hexdigest()
    return result
