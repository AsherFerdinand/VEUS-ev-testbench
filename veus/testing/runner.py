"""Deterministic batch execution on the same plant/controller used by the UI."""

import operator
from veus.sim.session import SimulationSession
from veus.testing.schema import (
    Metrics,
    RequirementResult,
    Scenario,
    ScenarioResult,
    UNITS,
)


def run_scenario(scenario: Scenario) -> ScenarioResult:
    session = SimulationSession(scenario.config)
    session.status = "running"
    frames = [session.telemetry()]
    events = {round(e.time_s / session.dt_s): e.controls for e in scenario.controls}
    # Manual schedule inputs belong to the following/recorded interval. Presets
    # and controller modes do not pretend to be measured pedal inputs.
    initial_manual = 0.0 if scenario.config.mode == "manual" else None
    frames[0].update(
        manual_throttle_command=initial_manual, manual_brake_command=initial_manual
    )
    while session.status == "running":
        if session.ticks in events:
            session.controls = events[session.ticks]
        frame = session.step()
        manual = scenario.config.mode == "manual"
        frame.update(
            manual_throttle_command=session.controls.throttle if manual else None,
            manual_brake_command=session.controls.brake if manual else None,
        )
        frames.append(frame)
    final = frames[-1]
    braking_index = next(
        (i for i, f in enumerate(frames) if i and f["brake_force_n"] > 1e-6), None
    )
    # Forces describe the preceding integration interval; onset uses its start.
    onset = frames[braking_index - 1] if braking_index is not None else None
    stop = (
        next(
            (
                f
                for f in frames[braking_index or len(frames) :]
                if f["velocity_kmh"] <= 1e-6
            ),
            None,
        )
        if onset
        else None
    )
    emergency_index = next(
        (
            i
            for i, f in enumerate(frames)
            if i and f["controller_state"] == "emergency_braking"
        ),
        None,
    )
    response = (
        frames[emergency_index - 1]["time_s"] - scenario.config.lead_brake_start_s
        if emergency_index is not None
        else None
    )
    # A trigger before the prescribed lead braking cannot measure its response.
    if response is not None and response < 0:
        response = None
    ttcs = [f["ttc_s"] for f in frames if f["ttc_s"] is not None]
    metrics = Metrics(
        collision_count=int(final["collision"]),
        minimum_separation_m=final["minimum_gap_m"],
        minimum_ttc_s=min(ttcs) if ttcs else None,
        impact_ego_speed_kmh=final["velocity_kmh"] if final["collision"] else None,
        impact_closing_speed_kmh=max(
            0.0, final["velocity_kmh"] - final["lead_speed_kmh"]
        )
        if final["collision"]
        else None,
        braking_distance_m=stop["position_m"] - onset["position_m"] if stop else None,
        brake_onset_time_s=onset["time_s"] if onset else None,
        stop_time_s=stop["time_s"] if stop else None,
        aeb_detection_time_s=final["aeb_trigger_time_s"],
        controller_response_s=response,
        final_speed_error_kmh=(
            abs(final["velocity_kmh"] - scenario.config.target_speed_kmh)
            if final["status"] == "completed" and scenario.config.mode == "cruise"
            else None
        ),
        final_gap_error_m=(
            abs(final["gap_m"] - final["desired_gap_m"])
            if final["status"] == "completed" and session.has_lead
            else None
        ),
        max_energy_balance_error_j=max(
            abs(f["energy_balance_error_j"]) for f in frames
        ),
    )
    requirements = []
    compare = {"<=": operator.le, ">=": operator.ge, "==": operator.eq}
    for criterion in scenario.criteria:
        measured = getattr(metrics, criterion.metric)
        status = (
            "INCONCLUSIVE"
            if measured is None
            else "PASS"
            if compare[criterion.operator](measured, criterion.threshold)
            else "FAIL"
        )
        evidence = (
            "Metric unavailable: event did not occur, horizon was interrupted, or not applicable."
            if measured is None
            else f"{criterion.metric} from 0.01 s telemetry; run ended at {final['time_s']:.2f} s ({final['status']})."
        )
        requirements.append(
            RequirementResult(
                **criterion.model_dump(),
                measured=measured,
                unit=UNITS[criterion.metric],
                status=status,
                evidence=evidence,
            )
        )
    statuses = [r.status for r in requirements]
    status = (
        "FAIL"
        if "FAIL" in statuses
        else "INCONCLUSIVE"
        if not statuses or "INCONCLUSIVE" in statuses
        else "PASS"
    )
    return ScenarioResult(
        scenario_id=scenario.id,
        status=status,
        termination=final["status"],
        duration_executed_s=final["time_s"],
        metrics=metrics,
        requirements=requirements,
        telemetry=frames,
    )
