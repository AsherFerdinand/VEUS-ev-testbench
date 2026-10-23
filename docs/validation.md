# Physics verification and engineering reporting

This work verifies equations and deterministic software scenarios. There is no
measured vehicle reference dataset, parameter identification, regulatory test
approval or production ADAS safety evidence. A passing report means only its
explicit criteria passed for its recorded configuration and finite horizon.

## Reproduce on Windows (Anaconda Prompt)

From the checkout containing README.md:

```bat
"%LOCALAPPDATA%\veus-venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
"%LOCALAPPDATA%\veus-venv\Scripts\python.exe" -m pytest -q
"%LOCALAPPDATA%\veus-venv\Scripts\python.exe" -m veus.testing physics --output reports\physics-001
"%LOCALAPPDATA%\veus-venv\Scripts\python.exe" -m veus.testing run scenarios --output reports\batch-001
start "" reports\batch-001\report.html
```

Use a new output directory each time. Existing results are never overwritten.
No dashboard server, GPU or network connection is required after installation.
The last command opens the static engineering report in your browser; it is not
another dashboard. Linux: use your environment's `python` for the same modules.
For reporting without development tools, install requirements-report.txt instead.
The lockfile records the tested Python 3.12 environment; on Python 3.11 use the
requirements files to resolve compatible dependency wheels rather than assuming
all lockfile pins support that interpreter/platform.

**Exit status:** 0 = all checks PASS; 1 = any FAIL or INCONCLUSIVE;
2 = invalid input, missing dependency or output/filesystem error. The supplied
8-scenario suite deliberately returns 1: low-grip and delayed AEB examples fail
collision avoidance. Reports still complete and preserve the failures. They are
not software crashes. Never discard this exit status in a CI pipeline.

A passing-only example:

```bat
"%LOCALAPPDATA%\veus-venv\Scripts\python.exe" -m veus.testing run scenarios\lead_braking_dry.json --output reports\dry-001
```

## Analytical references

All reference plots show analytical and numerical trajectories, not vehicle data.
The reference generator emits PNG, raw CSV and JSON summaries. Eleven traces cover:

| Case | Isolated model and independent reference | Numerical acceptance bound |
|---|---|---|
| Acceleration | m=1000 kg, r=0.5 m, T=500 Nm, ratio/efficiency=1, no resistance; a=1 m/s², v=at, x=at²/2; T_run=4 s | Speed 1e-9 m/s floating-point allowance; max position error <= abs(a)*T_run*dt/2 + 1e-9 m |
| Braking | m=1000 kg, v0=10 m/s, F_brake=2000 N, no resistance; a=-2 m/s², stop time 5 s, distance 25 m | Speed 1e-9 m/s; position <= v0*dt/2 + abs(a)*dt²/2 + 1e-9 m |
| Gradient | m=1000 kg, v0=20 m/s, grade=0.1 rad, no rolling/aero; a=-g sin(grade), T_run=4 s | Same constant-acceleration bounds |
| Coasting | m=1000 kg, v0=20 m/s, Cd=0.3, A=2 m², rho=1.225 kg/m³, no rolling/grade; k=rho Cd A/(2m), v=v0/(1+k v0 t), x=ln(1+k v0 t)/k; T_run=10 s | Speed <= T_run*k²*v0³*dt + 1e-9; position <= dt*(v0-v_end)+T_run*speed_bound + 1e-9 |
| Battery draw | Voc=400 V, R=0.05 ohm, P_terminal=20 kW, 10 s; I=(Voc-sqrt(Voc²-4RP))/(2R), E_chemical=Voc I t | 1e-4 J accumulated floating-point allowance, with inactive power/current/SOC limits |
| Coupled drive energy | m=1000 kg, r=0.5 m, torque=300 Nm, no road loads, ratio/transmission efficiency=1, motor/inverter eta=0.8, battery R=0; a=0.6 m/s², E_terminal=m(at)²/(2 eta), 4 s | 1e-4 J; verifies mechanics-to-battery coupling, not merely the pack identity |
| Regenerative energy | m=1000 kg, v0=10 m/s, brake=0.05 m g, no road loads, ratio/transmission efficiency=1, regen eta=0.7, R=0; E_recovered=eta*m*(v0²-(v0-0.05 g t)²)/2 over 2 s | 1e-4 J, with motor/charge acceptance limits inactive |

Mechanical speed/position create two traces per trajectory case. Battery, coupled drive energy and
regenerative energy create one each. Set dt=0.01 s and halve to 0.005 s to
measure convergence; do not adjust tolerances to force outputs to pass.

The constant-acceleration position bound follows the exact accumulated left-
rectangle (explicit Euler) error. In quadratic-drag coasting, the Euler update is
non-expansive for these parameter/timestep ranges and abs(v'') <= 2 k² v0³;
accumulating local truncation errors gives the stated speed bound. Integrating
that speed error and bounding the left-rectangle distance error gives the
position bound. Energy tests use constant or analytically known input power,
so only roundoff remains; tolerances are tiny relative to total run energy.
These bounds are for the listed isolated cases, not arbitrary scenarios.

## Scenario contract

JSON files use schema version 1. Run `python -m veus.testing run <file-or-directory>
--output <new-directory>`. Multiple files/directories are accepted; duplicate IDs,
unknown fields, NaN/infinity, invalid configurations, unsorted/duplicate event
times and out-of-horizon events are rejected before output generation. Scenario
IDs are safe filename components. Times/delays must align to the 0.01 s grid.
RunConfig defaults are resolved and saved: changing software defaults must not
silently alter the archived input. No random process is used in these scenarios.

Each file includes id, description, config, optional timed manual controls and
criteria. Manual command events take effect at interval start; their time and
pedal values are recorded in both the resolved scenario and telemetry. Nonmanual
presets/controllers ignore manual input; their recorded manual-command columns
are null rather than misleading pedal measurements. The dashboard and batch
runner share SimulationSession.step(); advance() still emits ten ticks per frame.

Examples include a stationary target, lead braking at 60/80 km/h, constant-speed
ACC following, observation/actuation delays, low friction, cruise tracking and a
manual pedal schedule. AEB and ACC algorithms themselves are unchanged.

## Metrics and event definitions

Raw telemetry includes every 0.01 s tick plus the initial sample. State quantities
are interval-end values; forces/power/controller commands describe the preceding
interval. Initial force/power placeholders are zero. telemetry-schema.json lists
units. TTC/gap and battery/power signals retain the existing dashboard names.
Null in JSON and empty CSV fields mean unavailable, never a fabricated zero.

- **Minimum separation:** minimum bumper gap at all ticks, including first overlap.
  Negative final gap records discretized penetration, not a crash deformation.
- **Minimum TTC:** minimum defined true-state TTC across ticks; no closing yields
  null. At overlap while closing it is zero. This is not the delayed observation.
- **Collision:** first tick with gap <= 0 ends the run. Impact ego speed and
  nonnegative closing speed are sampled at that tick, not interpolated impact or
  crash severity. Without a collision both impact speeds are null.
- **Brake onset:** start of the first interval with nonzero delivered brake force.
- **Braking distance:** position at first stop after onset minus onset position.
  It excludes reaction/coasting distance. Collision or no stop within the horizon
  makes this metric null, not the distance to collision. Ego position uses Euler.
- **Stop time:** absolute time of that first stopped sample, quantized to a tick.
- **AEB detection time:** first controller latch, before actuator delay.
- **Controller response:** start time of first applied emergency-brake interval
  minus the prescribed lead-braking event time. Null if no response or it precedes
  the event. It includes detection/threshold evolution plus actuator delay; it is
  not pure ECU computational latency.
- **Final speed error:** absolute target-speed error for completed cruise runs.
  **Final gap error:** absolute desired-headway error for completed lead runs.
  Interrupted horizons return null. AEB standstill-gap error is not ACC tracking.
- **Max energy residual:** max absolute battery + kinetic energy accounting
  residual across every tick. Consistency of accounting is not physical fidelity.

## Requirements, outcomes and report artifacts

Each criterion has a unique ID, description, supported metric, comparison
(<=, >=, ==), finite numeric threshold and written rationale. Units derive from
the metric, never the author guessing. Tests include illustrative development
objectives (no overlap, >=2 m clearance, settled ACC gap error <=0.25 m) and an
explicit 1 mJ energy roundoff check. These are not statutory/regulatory limits.
Exact equality should be used only for discrete counts, not noisy real signals.

A measured criterion is PASS or FAIL; unavailable metrics are INCONCLUSIVE.
Any FAIL makes the scenario FAIL; otherwise any INCONCLUSIVE, or no criteria,
makes it INCONCLUSIVE. Every required check must pass for a batch PASS, including
analytical physics references. A regression expectation of a collision can PASS
while collision avoidance FAILS; the scenario and batch still show FAIL.

The TTC report axis is explicitly zoomed to 0–10 s to show collision-risk evolution;
values above 10 s are clipped in that view and preserved in the raw CSV.

The static report embeds its PNG plots (no CDN, server or JavaScript needed) and
contains all numerical metrics, criteria, rationales, outcomes and resolved
scenario settings. Alongside it are:

- summary.csv/json, provenance.json, physics.json and physics-reference.csv/png;
- per-scenario input.json (original), scenario.json (resolved), config.json,
  result.json, telemetry.csv, telemetry-schema.json, requirements.csv and signals.png.

Provenance records Python/platform/dependency versions, model version, Git commit
when available, working-tree dirty state, file hashes and a combined source hash.
In a ZIP without .git, commit/dirty status are null rather than fabricated. A dirty
commit ID alone cannot reproduce source; preserve the recorded source snapshot or
check hashes. UTC generation time describes the report, not simulation time.
Version/hashes identify inputs; deterministic equality applies to simulation data,
not timestamps or plot renderer metadata. Reports are generated afresh and an
existing nonempty output directory is rejected to protect old evidence.

## Coverage and limitations

Use `python -m pytest --cov=veus --cov-branch --cov-report=term-missing` for measured
Python statement/branch coverage. This does not cover JavaScript or establish
physics validity. Missing lines/branches are reported rather than hidden behind
an arbitrary coverage target. See development-audit.md and engineering.md for
remaining model limits, and soh-integration.md for the future external interface.

A checked-in [execution snapshot](verification/README.md) preserves the source
commit, numerical results and example HTML report. Error ratios for roundoff-
dominated energy traces are not convergence rates; first-order convergence
assertions apply to the documented mechanical position/coasting cases.
