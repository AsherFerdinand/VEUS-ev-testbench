"""Reproduce two illustrative engineering studies with the production Lab kernel.

Run from repository root: python scripts/lab_studies.py --output PATH
No measured-vehicle or regulatory validation is implied.
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from veus.lab.profiles import builtin_profile
from veus.lab.report import export
from veus.lab.runner import run
from veus.lab.schema import LabRequest
from veus.workbench.adapter import ACKNOWLEDGEMENTS
from veus.workbench.design import VehicleDesignV2


def execute(name, design, experiment, profile=None):
    return run(
        LabRequest(
            vehicle=design,
            experiment=experiment,
            acknowledgements=ACKNOWLEDGEMENTS,
            profile=profile,
        )
    )


def studies(output):
    output.mkdir(parents=True, exist_ok=True)
    design = VehicleDesignV2().model_dump(mode="json")
    design["name"] = "Illustrative study reference EV"
    rows = {}
    for cd in [0.28, 0.22]:
        d = json.loads(json.dumps(design))
        d["body"]["drag_coefficient"] = cd
        name = f"drag-{cd:.2f}"
        rows[name] = execute(
            name,
            d,
            dict(
                kind="constant_speed",
                mode="predictive",
                duration_s=30,
                dt_s=0.05,
                initial_speed_ms=100 / 3.6,
                target_speed_ms=100 / 3.6,
            ),
        )
    for id in ["urban", "motorway", "hwfet"]:
        p = builtin_profile(id)
        rows[id] = execute(
            id,
            design,
            dict(kind="profile", mode="predictive", duration_s=p.time_s[-1], dt_s=0.1),
            p,
        )
    ideal = json.loads(json.dumps(design))
    ideal["body"].update(drag_coefficient=0, rolling_resistance_coefficient=0)
    ideal["battery"]["resistance_ohm"] = 0
    ideal["motor"]["efficiency_assumption"] = 1
    ideal["inverter"]["efficiency_assumption"] = 1
    ideal["gearbox"]["mechanical_efficiency"] = 1
    braking = execute(
        "reference-braking",
        ideal,
        dict(
            kind="braking",
            duration_s=5,
            dt_s=0.05,
            initial_speed_ms=20,
            brake_deceleration_ms2=3,
            regen_enabled=False,
        ),
    )

    def points(values):
        return " ".join(f"{50 + 100 * t:.3f},{260 - 10 * v:.3f}" for t, v in values)

    actual = points((r["time_s"], r["speed_ms"]) for r in braking["trace"])
    reference = points((r["time_s"], 20 - 3 * r["time_s"]) for r in braking["trace"])
    (output / "analytical-reference.svg").write_text(
        f'''<svg xmlns="http://www.w3.org/2000/svg" width="640" height="330" viewBox="0 0 640 330"><rect width="640" height="330" fill="white"/><g font-family="sans-serif" fill="#172a35"><text x="30" y="25">Ideal braking: v = 20 − 3t (m/s); dt = .05 s</text><path d="M50 45V260H570" fill="none" stroke="#999"/><polyline points="{reference}" fill="none" stroke="#bd6824" stroke-width="4"/><polyline points="{actual}" fill="none" stroke="#137e74" stroke-width="2" stroke-dasharray="5 4"/><text x="50" y="285">0 s</text><text x="520" y="285">5 s</text><text x="30" y="310">Orange: analytical; dashed teal: simulated. Speed error &lt; 1e−11 m/s.</text></g></svg>'''
    )
    summaries = {
        name: dict(
            run_sha256=r["run_sha256"],
            summary=r["summary"],
            summary_units=r["summary_units"],
            request=r["request"],
            limitations=r["limitations"],
        )
        for name, r in rows.items()
    }
    # Independent steady-speed force balance, not the Lab road-load function.
    mass = sum([1200, 420, 70, 25, 12, 3, 18])
    v = 100 / 3.6
    references = {}
    for cd in [0.28, 0.22]:
        aero = 0.5 * 1.225 * cd * 2.2 * v * v
        rolling = 0.012 * mass * 9.81
        dc = (aero + rolling) * v / (0.94 * 0.97 * 0.97)
        references[f"drag-{cd:.2f}"] = dict(
            mass_kg=mass,
            aerodynamic_force_n=aero,
            rolling_force_n=rolling,
            dc_power_w=dc,
            terminal_consumption_kwh_100km=dc / 1000,
            explanation="At 100 km/h, terminal DC kW numerically equals kWh/100km. SOC additionally includes internal resistance heating.",
        )
    evidence = dict(
        classification="Illustrative model verification and comparison; physical validation INCONCLUSIVE",
        reference_equations="Fa=.5 rho Cd A v^2; Fr=Crr m g; Pdc=(Fa+Fr)v/(eta_motor eta_inverter eta_gearbox)",
        studies=summaries,
        steady_speed_references=references,
    )
    (output / "studies.json").write_text(json.dumps(evidence, indent=2) + "\n")
    # Compact actual trace exports and standalone HTML; exact input snapshots in studies.json.
    for name, r in rows.items():
        for fmt in ["csv", "html"]:
            exported = export(r, fmt)
            (output / f"{name}.{fmt}").write_text(exported["content"])
    print(
        json.dumps(
            {
                k: {
                    m: v
                    for m, v in r["summary"].items()
                    if m
                    in [
                        "consumption_kwh_100km",
                        "maximum_tracking_error_ms",
                        "requested_infeasible_duration_s",
                    ]
                }
                for k, r in rows.items()
            },
            indent=2,
        )
    )
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("/tmp/veus-lab-studies"))
    studies(parser.parse_args().output)
