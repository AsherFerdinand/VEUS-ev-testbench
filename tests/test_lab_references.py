"""Closed-form force-balance references, independent of simulator functions."""

import math
import pytest
from veus.lab.runner import run
from veus.lab.schema import LabRequest
from veus.workbench.adapter import ACKNOWLEDGEMENTS
from veus.workbench.design import VehicleDesignV2


def reference_run(kind, dt=0.05, **experiment):
    d = VehicleDesignV2().model_dump(mode="json")
    d["body"].update(drag_coefficient=0, rolling_resistance_coefficient=0)
    d["battery"]["resistance_ohm"] = 0
    d["motor"]["efficiency_assumption"] = 1
    d["inverter"]["efficiency_assumption"] = 1
    d["gearbox"]["mechanical_efficiency"] = 1
    e = dict(kind=kind, dt_s=dt, duration_s=2, initial_speed_ms=20, target_speed_ms=20)
    e.update(experiment)
    return run(LabRequest(vehicle=d, experiment=e, acknowledgements=ACKNOWLEDGEMENTS))


def test_coast_gradient_and_braking_closed_form_energy():
    theta = math.atan(0.05)
    mass = 1748
    v0 = 20
    duration = 2
    coast = reference_run("coast", grade_percent=5)
    a = -9.81 * math.sin(theta)
    assert coast["summary"]["final_speed_ms"] == pytest.approx(
        v0 + a * duration, abs=1e-11
    )
    assert coast["summary"]["gradient_work_kwh"] == pytest.approx(
        mass * 9.81 * math.sin(theta) * (v0 * duration + 0.5 * a * duration**2) / 3.6e6,
        abs=1e-11,
    )
    brake = reference_run("braking", brake_deceleration_ms2=3, regen_enabled=False)
    assert brake["summary"]["final_speed_ms"] == pytest.approx(14, abs=1e-11)
    assert brake["summary"]["friction_energy_kwh"] == pytest.approx(
        0.5 * mass * (20**2 - 14**2) / 3.6e6, abs=1e-11
    )
    flat = reference_run("coast")
    assert (
        flat["summary"]["final_speed_ms"] == 20
        and flat["summary"]["net_battery_energy_kwh"] == 0
    )


def test_euler_distance_error_converges_with_timestep():
    # Left-endpoint position gives error -a*T*dt/2 under constant acceleration.
    a = -3
    exact = 20 * 2 + 0.5 * a * 2**2
    errors = []
    for dt in [0.1, 0.05, 0.025]:
        r = reference_run(
            "braking", dt=dt, brake_deceleration_ms2=3, regen_enabled=False
        )
        error = r["summary"]["distance_m"] - exact
        assert error == pytest.approx(-a * 2 * dt / 2, abs=1e-10)
        errors.append(abs(error))
    assert errors[0] / errors[1] == pytest.approx(2)
    assert errors[1] / errors[2] == pytest.approx(2)


def test_gradient_steady_demand_matches_independent_force_balance():
    theta = math.atan(0.05)
    expected = 1748 * 9.81 * math.sin(theta) * 20
    r = reference_run("gradient", grade_percent=5)
    assert r["trace"][1]["battery_power_w"] == pytest.approx(expected, abs=1e-7)
    assert r["summary"]["energy_consumed_kwh"] == pytest.approx(
        expected * 2 / 3.6e6, abs=1e-10
    )
