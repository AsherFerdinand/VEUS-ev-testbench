"""Deterministic bounded runs, requested demand and achieved movement kept separate."""

import hashlib
import math
from veus.replay.analysis import canonical
from veus.sim.dynamics import road_loads
from .schema import LabRequest
from .kernel import CoupledKernel
from .profiles import sample_profile, sample_route, route_profile

MODEL_VERSION = "veus-lab-coupled-v1"
LIMITATIONS = [
    "Illustrative forward-only longitudinal model; fixed OCV/resistance and constant conversion efficiencies, no thermal/ageing or vehicle validation.",
    "Continuous ratings are used unless peak envelope is explicitly acknowledged. Unknown peak duration is not a continuous capability claim.",
    "Regeneration efficiency is the explicit total reverse motor/inverter assumption, excluding gearbox; forward efficiencies are not applied again.",
    "No auxiliary loads are included. Distance uses retained Euler position; energy work uses held-acceleration mean displacement, an O(dt) distinction.",
    "Prescribed target demand and achieved constraint-aware motion have separate power/energy fields. A target is never substituted for achieved speed.",
    "Motor/inverter phase-current maps, transient duty and thermal protection remain unavailable; simulated limits do not establish hardware safety.",
    "Physical model validation remains INCONCLUSIVE.",
]


def control(kernel, target, desired_accel):
    sim = kernel.sim
    v = kernel.state.velocity_ms
    road = road_loads(sim.vehicle, v, sim.gradient_rad, sim.air_density_kg_m3)
    force = kernel.mass * desired_accel + sum(road.values())
    if force >= 0:
        return force * sim.vehicle.wheel_radius_m / (
            sim.transmission.active_ratio * sim.transmission.mechanical_efficiency
        ), 0.0
    return 0.0, -force


def resolved_grade(request, distance, profile_grade=None):
    e = request.experiment
    route = request.route
    if route is not None:
        sampled = sample_route(route, distance)
        if sampled["covered"] and sampled["grade_percent"] is not None:
            return sampled["grade_percent"], "route", sampled
        if e.route_grade_policy == "require":
            raise ValueError(
                "Route grade/coverage unavailable at distance %.6f m; choose a covered scenario or explicitly acknowledge constant-grade assumption"
                % distance
            )
        return e.grade_percent, "experiment_constant_assumption", sampled
    if request.profile is not None:
        if profile_grade is not None:
            return profile_grade, "timed_profile", None
        if e.route_grade_policy == "require":
            raise ValueError(
                "Profile grade is unavailable; explicitly select experiment_constant_assumption"
            )
        return e.grade_percent, "experiment_constant_assumption", None
    return e.grade_percent, "experiment_constant", None


def run(request: LabRequest):
    e = request.experiment
    if e.kind == "profile" and request.profile is None:
        if request.route is None:
            raise ValueError(
                "A timed profile is required; geometry alone is not a speed trace"
            )
        request = request.model_copy(update={"profile": route_profile(request.route)})
    if (
        request.route is not None
        and request.profile is None
        and e.kind not in ["constant_speed", "gradient"]
    ):
        raise ValueError(
            "Route execution requires a timed profile or an explicit constant-speed experiment"
        )
    if request.profile is not None and e.kind != "profile":
        raise ValueError("Select profile experiment when supplying a timed profile")
    if request.profile is not None and e.duration_s > request.profile.time_s[-1] + 1e-8:
        raise ValueError(
            "Experiment duration exceeds profile time coverage; no repeated or clamped samples"
        )
    kernel = CoupledKernel(request.vehicle, e, request.acknowledgements)
    dt = e.dt_s
    n = round(e.duration_s / dt)
    trace = []
    requested_discharge = 0.0
    requested_received = 0.0
    requested_distance = 0.0
    first_profile = (
        sample_profile(request.profile, 0) if request.profile is not None else None
    )
    first_target = (
        first_profile["target_speed_ms"]
        if first_profile
        else (e.target_speed_ms if e.kind in ["constant_speed", "gradient"] else None)
    )
    initial_grade, initial_grade_source, initial_route = resolved_grade(
        request, 0, first_profile["grade_percent"] if first_profile else None
    )
    initial = dict(
        time_s=0.0,
        position_m=0.0,
        speed_ms=e.initial_speed_ms,
        target_speed_ms=first_target,
        soc=kernel.battery.soc,
        battery_power_w=0.0,
        motor_power_w=0.0,
        motor_torque_nm=0.0,
        acceleration_ms2=0.0,
        battery_current_a=0.0,
        battery_voltage_v=kernel.battery.voltage_v,
        regen_power_w=0.0,
        regen_wheel_power_w=0.0,
        friction_power_w=0.0,
        grade_percent=initial_grade,
        limits=[],
        energy_balance_error_j=0.0,
        requested_dc_power_w=None,
        requested_position_m=0.0 if first_target is not None else None,
        tracking_error_ms=e.initial_speed_ms - first_target
        if first_target is not None
        else None,
        requested_demand_feasible=None,
        requested_motion_feasible=None,
        requested_regen_recovery_limited=None,
        unmet_dc_power_w=None,
        battery_discharge_energy_j=0.0,
        battery_received_energy_j=0.0,
        battery_heat_j=0.0,
        conversion_loss_j=0.0,
        friction_energy_j=0.0,
        aerodynamic_j=0.0,
        rolling_j=0.0,
        gradient_j=0.0,
        road_force_n=0.0,
        aerodynamic_n=0.0,
        rolling_n=0.0,
        gradient_n=0.0,
        requested_grade_percent=initial_grade,
        grade_source=initial_grade_source,
        route_position_m=0.0 if request.route else None,
        route_basis="requested_distance"
        if e.mode == "prescribed"
        else "achieved_distance",
        route_covered=initial_route["covered"] if initial_route else None,
        **{
            k: initial_route[k] if initial_route else None
            for k in ["elevation_m", "latitude", "longitude"]
        },
    )
    trace.append(initial)
    for tick in range(n):
        target = None
        required_dc = None
        demand_feasible = None
        motion_feasible = None
        recovery_limited = None
        unmet_dc = None
        p0 = sample_profile(request.profile, tick * dt) if request.profile else None
        p1 = (
            sample_profile(request.profile, (tick + 1) * dt)
            if request.profile
            else None
        )
        route_distance = (
            requested_distance
            if e.mode == "prescribed" and first_target is not None
            else kernel.state.position_m
        )
        grade, grade_source, _ = resolved_grade(
            request, route_distance, p0["grade_percent"] if p0 else None
        )
        kernel.sim.gradient_rad = math.atan(grade / 100)
        if e.kind == "acceleration":
            torque, brake = kernel.sim.motor.max_torque_nm, 0.0
        elif e.kind == "braking":
            torque, brake = 0.0, kernel.mass * e.brake_deceleration_ms2
        elif e.kind == "coast":
            torque, brake = 0.0, 0.0
        else:
            target0 = p0["target_speed_ms"] if p0 else e.target_speed_ms
            target = p1["target_speed_ms"] if p1 else e.target_speed_ms
            target_accel = (target - target0) / dt
            if e.mode == "prescribed":
                accel = (target - kernel.state.velocity_ms) / dt
            else:
                accel = (
                    target_accel
                    + (target0 - kernel.state.velocity_ms) / e.tracking_time_constant_s
                )
            torque, brake = control(kernel, target, accel)
            demand_grade, _, _ = resolved_grade(
                request, requested_distance, p0["grade_percent"] if p0 else None
            )
            road = road_loads(
                kernel.sim.vehicle,
                target0,
                math.atan(demand_grade / 100),
                kernel.sim.air_density_kg_m3,
            )
            required_force = kernel.mass * target_accel + sum(road.values())
            mean_target_speed = (target0 + target) / 2
            wheel_power = required_force * mean_target_speed
            efficiency = (
                kernel.config.drive_efficiency
                * kernel.sim.transmission.mechanical_efficiency
            )
            reverse = (
                kernel.config.regen_efficiency
                * kernel.sim.transmission.mechanical_efficiency
            )
            required_dc = (
                wheel_power / efficiency
                if wheel_power >= 0
                else (wheel_power * reverse if e.regen_enabled else 0.0)
            )
            dis, charge = kernel.battery.power_limits(dt)
            rpm = (
                target0
                / kernel.sim.vehicle.wheel_radius_m
                * kernel.sim.transmission.active_ratio
                * 30
                / math.pi
            )
            available = (
                kernel.sim.motor.max_available_torque(rpm)
                * kernel.sim.transmission.active_ratio
                * kernel.sim.transmission.mechanical_efficiency
                / kernel.sim.vehicle.wheel_radius_m
            )
            traction = (
                kernel.sim.friction_coefficient
                * kernel.mass
                * 9.81
                * math.cos(math.atan(demand_grade / 100))
            )
            motion_feasible = abs(required_force) <= traction + 1e-7 and (
                required_force <= 0
                or (
                    rpm < kernel.sim.motor.max_rpm
                    and required_force <= available + 1e-7
                )
            )
            if required_force > 0:
                motion_feasible = motion_feasible and required_dc <= dis + 1e-7
            recovery_limited = False
            if wheel_power < 0 and e.regen_enabled:
                reverse_torque_force = (
                    kernel.sim.motor.max_available_torque(rpm)
                    * kernel.sim.transmission.active_ratio
                    / (
                        kernel.sim.transmission.mechanical_efficiency
                        * kernel.sim.vehicle.wheel_radius_m
                    )
                )
                recovery_limited = (
                    rpm >= kernel.sim.motor.max_rpm
                    or -required_force > reverse_torque_force + 1e-7
                    or -wheel_power * kernel.sim.transmission.mechanical_efficiency
                    > kernel.sim.motor.max_power_kw * 1000 + 1e-7
                    or -required_dc > charge + 1e-7
                )
            demand_feasible = motion_feasible and not recovery_limited
            unmet_dc = (
                max(0.0, required_dc - dis)
                if required_dc >= 0
                else max(0.0, -required_dc - charge)
            )
            requested_discharge += max(0, required_dc) * dt
            requested_received += max(0, -required_dc) * dt
            requested_distance += mean_target_speed * dt
        row = kernel.step_lab(torque, brake, grade)
        row["time_s"] = (tick + 1) * dt
        row.update(
            target_speed_ms=target,
            requested_dc_power_w=required_dc,
            requested_position_m=requested_distance if target is not None else None,
            tracking_error_ms=row["speed_ms"] - target if target is not None else None,
            requested_demand_feasible=demand_feasible,
            requested_motion_feasible=motion_feasible,
            requested_regen_recovery_limited=recovery_limited,
            unmet_dc_power_w=unmet_dc,
            requested_grade_percent=demand_grade if target is not None else grade,
            grade_source=grade_source,
        )
        end_route_distance = (
            requested_distance
            if e.mode == "prescribed" and target is not None
            else row["position_m"]
        )
        route_sample = (
            sample_route(request.route, end_route_distance) if request.route else None
        )
        if (
            route_sample
            and not route_sample["covered"]
            and e.route_grade_policy == "require"
        ):
            raise ValueError(
                "Route distance coverage exhausted; no geometry or grade is clamped beyond its source"
            )
        row.update(
            route_position_m=end_route_distance if request.route else None,
            route_basis="requested_distance"
            if e.mode == "prescribed"
            else "achieved_distance",
            route_covered=route_sample["covered"] if route_sample else None,
            **{
                k: route_sample[k] if route_sample else None
                for k in ["elevation_m", "latitude", "longitude"]
            },
        )
        if grade_source == "experiment_constant_assumption":
            row["limits"].append("explicit_constant_grade_assumption")
        if route_sample and not route_sample["covered"]:
            row["limits"].append("route_coverage_unavailable")
        if demand_feasible is False:
            row["limits"].append("requested_demand_infeasible")
        if motion_feasible is False:
            row["limits"].append("requested_motion_infeasible")
        if recovery_limited:
            row["limits"].append("requested_regen_recovery_limited")
        trace.append(row)
    final = trace[-1]
    distance = final["position_m"]
    energy = kernel.energy
    target_time = (
        next(
            (r["time_s"] for r in trace if r["speed_ms"] >= e.target_speed_ms - 1e-9),
            None,
        )
        if e.kind == "acceleration"
        else None
    )
    stop = (
        next((r for r in trace if r["speed_ms"] <= 1e-9), None)
        if e.kind == "braking" and e.initial_speed_ms > 0
        else None
    )
    summary = dict(
        duration_s=e.duration_s,
        distance_m=distance,
        final_speed_ms=final["speed_ms"],
        maximum_speed_ms=max(r["speed_ms"] for r in trace),
        initial_soc=request.vehicle.assumptions.initial_soc,
        final_soc=final["soc"],
        energy_consumed_kwh=energy["consumed_j"] / 3_600_000,
        energy_recovered_kwh=energy["recovered_j"] / 3_600_000,
        net_battery_energy_kwh=(energy["consumed_j"] - energy["recovered_j"])
        / 3_600_000,
        consumption_kwh_100km=(energy["consumed_j"] - energy["recovered_j"])
        / 36
        / distance
        if distance > 1e-9
        else None,
        battery_heat_kwh=energy["battery_heat_j"] / 3_600_000,
        conversion_loss_kwh=energy["conversion_loss_j"] / 3_600_000,
        friction_energy_kwh=energy["friction_heat_j"] / 3_600_000,
        aerodynamic_work_kwh=kernel.road_energy["aerodynamic_j"] / 3_600_000,
        rolling_work_kwh=kernel.road_energy["rolling_j"] / 3_600_000,
        gradient_work_kwh=kernel.road_energy["gradient_j"] / 3_600_000,
        time_to_target_s=target_time,
        stopping_time_s=stop["time_s"] if stop else None,
        stopping_distance_m=stop["position_m"] if stop else None,
        maximum_energy_balance_error_j=max(
            abs(r["energy_balance_error_j"]) for r in trace
        ),
        requested_discharge_energy_kwh=requested_discharge / 3_600_000
        if first_target is not None
        else None,
        requested_received_energy_kwh=requested_received / 3_600_000
        if first_target is not None
        else None,
        requested_distance_m=requested_distance if first_target is not None else None,
        requested_consumption_kwh_100km=(requested_discharge - requested_received)
        / 36
        / requested_distance
        if requested_distance > 0
        else None,
        requested_infeasible_duration_s=sum(
            dt for r in trace[1:] if r["requested_demand_feasible"] is False
        ),
        maximum_tracking_error_ms=max(
            (
                abs(r["tracking_error_ms"])
                for r in trace
                if r["tracking_error_ms"] is not None
            ),
            default=None,
        ),
    )
    summary.update(
        rms_tracking_error_ms=math.sqrt(
            sum(
                r["tracking_error_ms"] ** 2
                for r in trace[1:]
                if r["tracking_error_ms"] is not None
            )
            / n
        )
        if first_target is not None
        else None,
        requested_motion_infeasible_duration_s=sum(
            dt for r in trace[1:] if r["requested_motion_feasible"] is False
        ),
    )
    units = {
        k: (
            "kWh/100 km"
            if "consumption_" in k
            else "kWh"
            if k.endswith("_kwh")
            else "m/s"
            if k.endswith("_ms")
            else "m"
            if k.endswith("_m")
            else "s"
            if k.endswith("_s")
            else "J"
            if k.endswith("_j")
            else "1"
        )
        for k in summary
    }
    active = sorted({x for r in trace for x in r["limits"]})
    limit_duration = {
        key: sum(dt for r in trace[1:] if key in r["limits"]) for key in active
    }
    limit_intervals = []
    for key in active:
        start = None
        for row in trace[1:]:
            if key in row["limits"] and start is None:
                start = row["time_s"] - dt
            if key not in row["limits"] and start is not None:
                end = row["time_s"] - dt
                limit_intervals.append(
                    dict(limit=key, start_s=start, end_s=end, duration_s=end - start)
                )
                start = None
        if start is not None:
            limit_intervals.append(
                dict(
                    limit=key,
                    start_s=start,
                    end_s=e.duration_s,
                    duration_s=e.duration_s - start,
                )
            )
    findings = [
        dict(
            type="constraint_duration",
            id=key,
            value=seconds,
            unit="s",
            message=key
            + ": "
            + format(seconds, ".6g")
            + " s of the simulated time grid",
        )
        for key, seconds in limit_duration.items()
    ]
    if summary.get("maximum_tracking_error_ms") is not None:
        findings.append(
            dict(
                type="tracking",
                id="maximum_tracking_error",
                value=summary["maximum_tracking_error_ms"],
                unit="m/s",
                message="Maximum achieved-minus-target speed error magnitude; not a physical validation metric.",
            )
        )
    for key, title in [
        ("net_battery_energy_kwh", "Net terminal battery energy for achieved movement"),
        ("energy_recovered_kwh", "Recovered DC electrical energy"),
        ("aerodynamic_work_kwh", "Aerodynamic road work"),
        ("rolling_work_kwh", "Rolling-resistance road work"),
        ("gradient_work_kwh", "Signed gradient road work"),
        (
            "maximum_energy_balance_error_j",
            "Maximum numerical energy-accounting residual",
        ),
    ]:
        value = summary[key]
        unit = units[key]
        findings.append(
            dict(
                type="engineering_quantity",
                id=key,
                value=value,
                unit=unit,
                message=title
                + ": "
                + format(value, ".6g")
                + " "
                + unit
                + ". Model-derived quantity, not measured physical validation.",
            )
        )
    if summary["rms_tracking_error_ms"] is not None:
        value = summary["rms_tracking_error_ms"]
        findings.append(
            dict(
                type="tracking",
                id="rms_tracking_error",
                value=value,
                unit="m/s",
                message="RMS achieved-minus-target speed error: "
                + format(value, ".6g")
                + " m/s across completed time steps.",
            )
        )
    result = dict(
        schema_version=1,
        model_version=MODEL_VERSION,
        vehicle=request.vehicle.model_dump(mode="json"),
        experiment=e.model_dump(mode="json"),
        request=request.model_dump(mode="json"),
        summary=summary,
        summary_units=units,
        trace=trace,
        limit_duration_s=limit_duration,
        limit_intervals=limit_intervals,
        findings=findings,
        provenance=dict(
            classification="simulated illustrative experiment, not measured vehicle data",
            energy_basis="achieved movement for consumption/SOC; requested_* fields are separate target-trace demand",
            rating_policy=e.power_policy,
            profile=request.profile.model_dump(mode="json")
            if request.profile
            else None,
            route=request.route.model_dump(mode="json") if request.route else None,
            route_grade_policy=e.route_grade_policy,
            route_basis="requested_distance"
            if e.mode == "prescribed"
            else "achieved_distance",
        ),
        limitations=LIMITATIONS,
    )
    result["run_sha256"] = hashlib.sha256(canonical(result)).hexdigest()
    return result
