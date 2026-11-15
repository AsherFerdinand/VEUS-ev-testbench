# Choose your VEUS workflow

VEUS has three purposes: drive a simulated EV, inspect recorded measurements,
and test models/software. These are different activities. Replaying measured
speed does not show that a model predicts it, and a data-readiness badge is not a
physical-validation result. Phase 8's INCONCLUSIVE physical-validation findings
remain unchanged.

## Welcome and navigation

New browser visitors see **VEUS — Explore. Analyse. Validate.** with three cards.
There is no blocking onboarding dialog, account or required form. The main
Drive / Analyse / Validate / Settings navigation remains available. Welcome/Home
in that navigation always returns to the cards. The Drive garage does not open
on top of Welcome; it appears when choosing a vehicle in Drive.

The default checked **Remember that I have seen Welcome on this browser** stores
only `veus.welcome.seen.v1=yes` in localStorage after choosing/leaving Welcome.
Future visits start in Drive. Uncheck it before leaving to keep Welcome on the
next visit. Settings → **Show Welcome on next startup** clears this flag; choosing
a workflow with Remember checked sets it again. No account/cloud storage or
analytics is involved. If storage is blocked, navigation still works for the
current visit; the nonmodal Welcome panel may return after reload.

Explicit direct links override the startup preference:

- `http://localhost:8770/?workspace=drive`
- `http://localhost:8770/?workspace=analyse`
- `http://localhost:8770/?workspace=validate`
- `http://localhost:8770/?workspace=settings`

Only these known workspace names are accepted. Navigation does not reload the
app or delete run/analysis state. Existing input release/pause policies still
apply when leaving Drive; replay pauses when leaving its workspace/tab.

## Drive a Virtual EV

**Required inputs: none.** Choose an illustrative vehicle, press Run and hold W
or Arrow Up to accelerate; S/Arrow Down brakes, Space pauses/resumes, R resets.
Mouse sliders and held pointer/touch buttons remain available. Python physics
calculates forward longitudinal motion; the scene interpolates telemetry for
presentation. Presets are illustrative, not calibrated manufacturer vehicles.

Optional customization lives in Validate → Vehicle & road: mass, motor
power/torque limits, friction, grade, initial speed/duration; battery capacity,
SOC, voltage, resistance/current limits, drive/regen efficiency and existing ADAS
settings. Apply & reset starts a new configuration. About Drive lists these
supported parameters without adding steering, lateral or suspension physics.

Example: accelerate, release to coast, then brake and inspect speed/SOC/power.
Outputs are simulated telemetry, charts and optional CSV/run metadata exports.
See [Drive controls and architecture](drive-experience.md).

## Explore Real Vehicle Data

**Minimum for replay: numeric timestamp and vehicle speed.** A CSV must have
explicit column/unit mappings, strictly increasing times, a declared measured or
synthetic origin and source identity. Optional supported signals include voltage,
current, SOC, motor torque/speed, brake force (not pedal position), road gradient,
recorded acceleration/power/position/energy and outside air temperature.

Choose **Import Vehicle Data** to open Analyse → Data Readiness. Upload CSV or
inspect a bundled recording. Alias recognition proposes columns, not units or
engineering truth. Review mappings, select units/origin and confirm. The check
explains supported calculations, missing samples, gaps and unresolved evidence.
If replay is supported, **Proceed to recorded replay** uses those exact confirmed
mappings and source bytes. Readiness does not silently repair the recording.

**Try Example Recording** proposes the genuine small VED trip 1561 window for
review. It is not silently replaced by a synthetic fixture. Its replay/signed
power calculations are available, energy is conditional, and physical-model
validation inputs are unavailable. Unknown current polarity remains unknown.

Electrical-only CSVs can be assessed for V/I inspection even without speed;
they cannot drive a recorded journey. Readiness's electrical AVAILABLE status
means valid samples can be inspected, not authenticated accuracy. Conditional
readiness is advisory: existing Replay may compute explicitly assumption-based
estimates (for example under an asserted polarity); unresolved readiness
conditions are retained in the handoff's limitations. Nothing becomes a physical
validation PASS.

Example: replay VED, click a speed graph to seek, inspect actual sample times and
threshold events, export a descriptive report. The original calibration workflow
remains in **Model experiments & calibration**.
See [readiness rules](data-readiness.md) and [recorded replay](real-world-replay.md).

## Test Engineering Models

**Built-in modes and scenarios need no external measurements.** Custom simulation
experiments need supported model parameters, initial conditions and scenario
configuration. The laboratory preserves vehicle/road/battery/controller settings,
virtual sensors/faults, diagnostic charts and exports. Reproducible batch scenarios
and HTML reports remain CLI workflows; clicking Open Test Laboratory does not
claim to have executed a batch automatically.

**Verification** checks software/models against mathematical equations or defined
requirements. **Physical validation** compares predictions with suitable
independent real measurements under documented conditions. The former does not
establish the latter. Physical validation needs measured inputs/reference outputs,
compatible timestamps/units, vehicle/operating evidence and an explicit supported
Phase 8 experiment. Source assertions are not independently authenticated here.

Examples: verify braking against an analytical reference; run an existing ADAS
scenario or inject a radar dropout; evaluate an explicit measurement experiment
in Analyse. Outputs are simulated traces, defined criterion results and engineering
reports. See [verification/scenarios](validation.md), [virtual sensors](virtual-sensors.md)
and [measurement model evaluation](vehicle-validation.md).

## Examples and formats

A: [basic-replay.csv](../examples/onboarding/basic-replay.csv) and
[matching replay config](../examples/onboarding/basic-replay.json) are a small
**synthetic** time/speed arithmetic fixture. B:
[electrical-analysis.csv](../examples/onboarding/electrical-analysis.csv) and
[matching config](../examples/onboarding/electrical-analysis.json) add synthetic
voltage/current/SOC with unknown polarity. They teach formats, not real vehicle
behavior. The Readiness UI provides attachment downloads for both files.

C uses the **existing Phase 8 format**, not a new universal validation schema:
[synthetic-battery-train.csv](../examples/validation/synthetic-battery-train.csv),
[Experiment JSON](../examples/validation/synthetic-battery-train.json),
[bounded fitting settings](../examples/validation/battery-calibration.json), and
[distinct synthetic holdout CSV](../examples/validation/synthetic-battery-holdout.csv)
with [its Experiment](../examples/validation/synthetic-battery-holdout.json).
Open Model experiments & calibration and select synthetic-battery-train, or use
the commands in the Phase 8 guide. This verifies software/known arithmetic; it is
not experimental vehicle evidence. Battery-current examples need current/voltage,
not the speed required by a replay workflow. JSON has a different purpose in the
two existing contracts: ReplayConfig vs Experiment. Arbitrary JSON telemetry
import is not supported.

## Local launch (Anaconda Prompt)

From the repository root:

```bat
python -m pip install -r requirements-report.txt
python -m uvicorn veus.studio.main:app --port 8770
```

Open http://localhost:8770. For the earlier dedicated venv, replace `python` with
`"%LOCALAPPDATA%\veus-venv\Scripts\python.exe"`. Python 3.12 is the tested cloud
runtime. Full tests: `python -m pytest -q`; playback-clock math:
`node --test tests/browser/replay-controller.test.cjs`. Optional Playwright checks
include `node tests/browser/guidance.cjs`, plus the existing Drive/Replay scripts.
The latter use a direct Drive URL so they still exercise the original workflows
without depending on a new visitor's welcome preference.

CSV bytes go to the running VEUS backend for parsing; these APIs do not persist
uploads to disk. Exported files are saved only through the user's download action.
The standalone app requires no cloud account. See
[execution evidence/screenshots](phase10-1-evidence/README.md) for actual checks.
