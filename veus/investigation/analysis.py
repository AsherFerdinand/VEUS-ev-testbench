"""Traceable recorded-event evidence and descriptive comparisons, no causal model."""

import copy
import hashlib
from pydantic import Field
from veus.replay.api import ReplayRequest, decode
from veus.readiness.analysis import ReadinessConfig, assess
from veus.replay.analysis import analyse, canonical

VERSION = "veus-investigation-v1"
ENERGY_REASON = "Energy calculation unavailable: current polarity or measurement-quality requirements are unresolved."
COMMON_LIMITATIONS = [
    "Recorded rows and derived calculations do not establish road gradient, auxiliary load, motor efficiency or a causal explanation.",
    "Channel synchronization, instrument accuracy and calibration are not independently authenticated by this software.",
    "A generic replay illustration is not a GPS trajectory or a validated model prediction. Phase 8 physical validation remains INCONCLUSIVE.",
    "SOC changes are endpoint observations, not battery health, degradation or efficiency estimates.",
]


class InvestigationInput(ReplayRequest):
    mappings_confirmed: bool
    readiness_configuration: ReadinessConfig | None = None
    selected_events: list[int] | None = Field(default=None, max_length=20)


def stats(values, times, indices):
    available = [i for i in indices if values[i] is not None]
    return dict(
        valid_samples=len(available),
        missing_samples=len(indices) - len(available),
        minimum=min(values[i] for i in available) if available else None,
        maximum=max(values[i] for i in available) if available else None,
        first=dict(
            index=available[0], time_s=times[available[0]], value=values[available[0]]
        )
        if available
        else None,
        last=dict(
            index=available[-1],
            time_s=times[available[-1]],
            value=values[available[-1]],
        )
        if available
        else None,
        sample_indices=available,
    )


def insight(replay, event, index):
    times = replay["time_s"]
    indices = [
        i
        for i, t in enumerate(times)
        if event["start_s"] - 1e-8 <= t <= event["end_s"] + 1e-8
    ]
    channels = {"time_s": times, **replay["measured"], **replay["derived"]}
    evidence = []
    keys = list(
        dict.fromkeys(
            [
                *event["signals"],
                "vehicle_speed_ms",
                "acceleration_ms2",
                "battery_voltage_v",
                "battery_current_a",
                "electrical_power_w",
                "battery_soc",
            ]
        )
    )
    for key in keys:
        if key not in channels:
            continue
        s = stats(channels[key], times, indices)
        evidence.append(
            dict(
                signal=key,
                unit=replay["units"].get(key, "s"),
                classification=replay["classifications"].get(
                    key, replay["quality"]["data_origin"] + " timestamp"
                ),
                **s,
            )
        )
    speed = next((e for e in evidence if e["signal"] == "vehicle_speed_ms"), None)
    power = next((e for e in evidence if e["signal"] == "electrical_power_w"), None)
    delta_speed = (
        speed["last"]["value"] - speed["first"]["value"]
        if speed and speed["first"]
        else None
    )
    delta_magnitude = (
        abs(power["last"]["value"]) - abs(power["first"]["value"])
        if power and power["first"]
        else None
    )
    kind = event["type"]
    interpretation = {
        "strong_acceleration": "A speed-derived acceleration episode meets the stated threshold; this is not an accelerometer measurement.",
        "strong_deceleration": "A speed-derived deceleration episode meets the stated threshold; brake demand or its cause is not independently observed.",
        "standstill": "Recorded speed samples meet the configured standstill threshold for this qualifying episode.",
        "high_electrical_magnitude": "Available signed electrical power samples meet the magnitude threshold; this does not establish discharge or propulsion demand.",
        "timestamp_gap": "The recording has a timestamp gap. Travel and measurement evolution inside it are unknown; endpoint differences do not reconstruct it.",
        "missing_measurements": "Mapped measurement fields are missing. This is an availability issue, not a diagnosed sensor failure.",
        "possible_regenerative_braking": "Under the asserted sign convention, received electrical power coincides with speed-derived deceleration. The charging source is not independently established.",
    }.get(
        kind,
        "The recorded samples satisfy the stated detector rule; no causal mechanism is established.",
    )
    observations = []
    if (
        kind not in ["timestamp_gap", "missing_measurements"]
        and delta_speed is not None
    ):
        observations.append(
            dict(
                classification="derived difference of recorded samples",
                statement=f"Last minus first available speed is {delta_speed:.6g} m/s.",
                signals=["vehicle_speed_ms"],
                calculation="last available event sample minus first available event sample",
                value=delta_speed,
                unit="m/s",
            )
        )
    if (
        kind not in ["timestamp_gap", "missing_measurements"]
        and delta_magnitude is not None
    ):
        observations.append(
            dict(
                classification="derived",
                statement=f"Last minus first available |V×I| is {delta_magnitude:.6g} W.",
                signals=["battery_voltage_v", "battery_current_a"],
                calculation="abs(last sampled V×I) - abs(first sampled V×I)",
                value=delta_magnitude,
                unit="W",
            )
        )
        if delta_speed is not None and delta_speed > 0 and delta_magnitude > 0:
            interpretation += " Speed and sampled electrical-power magnitude both increase between the available interval endpoints. This is an association, not a causal finding."
    limits = COMMON_LIMITATIONS + [event["qualification"]]
    if replay["quality"]["current_sign"] == "unknown":
        limits.append(
            "Source current polarity remains unverified. Signed current/power is not labelled charging, discharge or regeneration."
        )
    if any(
        g["start_s"] < event["end_s"] and g["end_s"] > event["start_s"]
        for g in replay["metadata"]["gaps"]
    ):
        limits.append(
            "This interval overlaps unknown timestamp coverage; no interpolation across the gap is evidence."
        )
    return dict(
        event_index=index,
        event_type=kind,
        start_s=event["start_s"],
        end_s=event["end_s"],
        source_start_s=event["source_start_s"],
        source_end_s=event["source_end_s"],
        event_classification=event["classification"],
        rule=event["rule"],
        evidence=evidence,
        observations=observations,
        interpretation=interpretation,
        interpretation_classification="inferred association only"
        if delta_speed is not None
        and delta_magnitude is not None
        and delta_speed > 0
        and delta_magnitude > 0
        and kind not in ["timestamp_gap", "missing_measurements"]
        else "descriptive interpretation of the stated rule",
        limitations=list(dict.fromkeys(limits)),
        confidence="Rule-based evidence qualification, not a statistical confidence score or causal identification.",
    )


def investigate(request: InvestigationInput):
    if not request.mappings_confirmed:
        raise ValueError(
            "Confirm current recording column/unit mappings before investigation."
        )
    raw = decode(request)
    cfg = request.configuration
    rc = request.readiness_configuration or ReadinessConfig.model_validate(
        {
            k: v
            for k, v in cfg.model_dump(mode="json").items()
            if k not in ["schema_version", "thresholds"]
        }
    )
    if (
        rc.source.model_dump() != cfg.source.model_dump()
        or rc.preprocessing.model_dump() != cfg.preprocessing.model_dump()
        or rc.current_sign != cfg.current_sign
        or rc.sign_evidence != cfg.sign_evidence
        or rc.sanity_limits.model_dump() != cfg.sanity_limits.model_dump()
    ):
        raise ValueError(
            "Readiness evidence must describe the identical source, mapping, polarity and sanity limits as the investigated recording."
        )
    readiness = assess(raw, rc)
    caps = {c["id"]: c for c in readiness["capabilities"]}
    if caps["recorded_replay"]["status"] == "UNAVAILABLE":
        raise ValueError(caps["recorded_replay"]["explanation"])
    original = analyse(raw, cfg)
    r = copy.deepcopy(original)
    energy_available = caps["energy_consumption"]["status"] == "AVAILABLE"
    r["original_replay_analysis_sha256"] = r.pop("analysis_sha256")
    if not energy_available:
        for key in ["electrical_energy_used_wh", "electrical_energy_received_wh"]:
            r["derived"].pop(key, None)
            r["classifications"].pop(key, None)
            r["units"].pop(key, None)
            r["summary"][key]["value"] = None
            r["summary"][key]["unavailable_reason"] = ENERGY_REASON
        r["quality"]["energy_integration_available"] = False
    events = [
        dict(event_index=i, **event)
        for i, event in enumerate(original["events"])
        if energy_available or event["type"] != "possible_regenerative_braking"
    ]
    r["events"] = [{k: v for k, v in e.items() if k != "event_index"} for e in events]
    r["investigation_energy_gate"] = dict(
        status=caps["energy_consumption"]["status"],
        explanation=caps["energy_consumption"]["explanation"],
        available=energy_available,
    )
    r["analysis_sha256"] = hashlib.sha256(canonical(r)).hexdigest()
    allowed = {e["event_index"]: e for e in events}
    selected = request.selected_events
    if selected is None:
        selected = []
        for kind in [
            "strong_acceleration",
            "strong_deceleration",
            "high_electrical_magnitude",
            "standstill",
        ]:
            match = next((e["event_index"] for e in events if e["type"] == kind), None)
            if match is not None:
                selected.append(match)
            if len(selected) == 3:
                break
        if not selected:
            selected = list(allowed)[:3]
    if len(selected) != len(set(selected)) or any(i not in allowed for i in selected):
        raise ValueError(
            "Selected events must be unique valid detector event indices under the current readiness gate."
        )
    findings = [insight(r, allowed[i], i) for i in selected]
    metrics = {}

    def metric(key, value, unit, origin, definition, conditional=False, reason=None):
        metrics[key] = dict(
            value=value,
            unit=unit,
            classification="unavailable"
            if value is None
            else "conditional"
            if conditional
            else origin,
            status="UNAVAILABLE"
            if value is None
            else "CONDITIONAL"
            if conditional
            else "AVAILABLE",
            definition=definition,
            unavailable_reason=reason if value is None else None,
        )

    measured = "measured" if cfg.source.kind == "measured" else "synthetic"
    metric(
        "sample_count",
        len(r["time_s"]),
        "samples",
        measured,
        "Number of retained original rows, not a resampled count.",
    )
    for key in [
        "recording_duration_s",
        "known_segment_distance_m",
        "distance_m",
        "average_speed_ms",
        "maximum_speed_ms",
        "peak_acceleration_ms2",
        "peak_deceleration_ms2",
        "peak_power_magnitude_w",
        "electrical_energy_used_wh",
        "electrical_energy_received_wh",
    ]:
        m = r["summary"][key]
        metric(
            key,
            m["value"],
            m["unit"],
            measured
            if key in ["recording_duration_s", "maximum_speed_ms"]
            else "derived",
            m["definition"],
            reason=m["unavailable_reason"],
        )
    coverage = r["quality"]["speed_interval_coverage"]
    metric(
        "speed_interval_coverage",
        coverage,
        "fraction",
        "derived",
        "Valid adjacent speed interval duration / recording duration; excludes unknown travel.",
    )
    metric(
        "standstill_duration_s",
        sum(e["end_s"] - e["start_s"] for e in events if e["type"] == "standstill"),
        "s",
        "derived",
        "Sum of qualifying sampled standstill episode spans from the existing event detector; short/isolated samples are excluded.",
        conditional=coverage < 1,
    )
    pvalues = r["derived"].get(
        "electrical_power_w", r["measured"].get("battery_power_w", [])
    )
    has_power = any(v is not None for v in pvalues)
    metric(
        "high_power_event_count",
        sum(e["type"] == "high_electrical_magnitude" for e in events)
        if has_power
        else None,
        "events",
        "derived",
        "Existing detector high-electrical-magnitude episode count; not discharge/efficiency ranking.",
        conditional=has_power
        and (any(v is None for v in pvalues) or bool(r["metadata"]["gaps"])),
        reason="Electrical power samples are unavailable; an event count cannot be inferred.",
    )
    for channel, label in [
        ("battery_voltage_v", "voltage"),
        ("battery_current_a", "current"),
    ]:
        values = r["measured"].get(channel)
        finite = [v for v in (values or []) if v is not None]
        for bound, fn in [("minimum", min), ("maximum", max)]:
            metric(
                label + "_" + bound,
                fn(finite) if finite else None,
                r["units"].get(channel, "V" if label == "voltage" else "A"),
                measured,
                "Available recorded sample "
                + bound
                + "; not an estimate of unsampled extrema.",
                conditional=bool(values) and len(finite) < len(values),
                reason="No valid " + label + " samples.",
            )
    soc = r["measured"].get("battery_soc")
    valid_soc = soc is not None and soc[0] is not None and soc[-1] is not None
    metric(
        "soc_change_pp",
        (soc[-1] - soc[0]) * 100 if valid_soc else None,
        "percentage points",
        "derived",
        "Last recorded SOC minus first, multiplied by 100; no battery-health or degradation inference.",
        reason="SOC endpoint samples are unavailable.",
    )
    warnings = list(cfg.limitations) + COMMON_LIMITATIONS
    if r["metadata"]["gaps"]:
        warnings.append(
            f"{len(r['metadata']['gaps'])} timestamp gaps exceed {cfg.preprocessing.max_gap_s} s. Total distance and whole-window average are unknown where speed coverage is incomplete."
        )
    if not energy_available:
        warnings.append(ENERGY_REASON + " " + caps["energy_consumption"]["explanation"])
    return dict(
        configuration=cfg.model_dump(mode="json"),
        readiness=readiness,
        analysis=r,
        events=events,
        selected_event_indices=selected,
        insights=findings,
        metrics=metrics,
        limitations=list(dict.fromkeys(warnings)),
        source_sha256=cfg.source.expected_sha256,
    )


def compare(first, second, axis="elapsed"):
    rows = []
    for key in first["metrics"]:
        a, b = first["metrics"][key], second["metrics"][key]
        rows.append(
            dict(
                metric=key,
                unit=a["unit"],
                first=a,
                second=b,
                difference_second_minus_first=b["value"] - a["value"]
                if a["value"] is not None and b["value"] is not None
                else None,
            )
        )
    a, b = first["configuration"]["source"], second["configuration"]["source"]
    same = a["expected_sha256"] == b["expected_sha256"] or (
        a["dataset"],
        a["vehicle_id"],
        a["run_id"],
    ) == (b["dataset"], b["vehicle_id"], b["run_id"])
    return dict(
        metrics=rows,
        axis=axis,
        axis_definition="Elapsed recorded seconds from each independent origin; not simultaneous real-world moments."
        if axis == "elapsed"
        else "Each elapsed time divided by its own duration; display transformation only, not resampling or simultaneous real-world moments.",
        same_source_run=same,
        limitations=[
            "Descriptive comparison, not a controlled experiment or driving-style efficiency ranking. Distances, vehicles, traffic, grade, temperature and measurement quality may differ.",
            "Threshold-dependent event counts and derivative extrema depend on sampling, noise, settings and recording duration.",
        ]
        + (
            [
                "These entries describe the same source run or file and may overlap; this is not independent validation."
            ]
            if same
            else []
        ),
    )


def case_study(
    first, second=None, title="Recorded EV engineering investigation", axis="elapsed"
):
    if axis not in ["elapsed", "normalized"]:
        raise ValueError("Unknown display time axis")
    result = dict(
        schema_version=1,
        software_version=VERSION,
        title=title,
        scope="Descriptive measured/derived/inferred evidence, not causal identification, physical model validation or safety certification.",
        recordings=[first] + ([second] if second else []),
        comparison=compare(first, second, axis) if second else None,
    )
    result["case_sha256"] = hashlib.sha256(canonical(result)).hexdigest()
    return result
