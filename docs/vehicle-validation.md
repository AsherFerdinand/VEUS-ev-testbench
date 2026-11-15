# Measurement validation and calibration framework

**Physical vehicle validation is still pending.** Phase 8 provides an end-to-end
framework, analytical synthetic verification and exploratory comparisons with
genuine VED measurements. It does not establish real-vehicle accuracy or safety.
Read dataset-discovery.md for what was actually obtained and what remains unknown.

## Architecture and evidence classes

`validation/measurements.py` imports immutable CSV bytes into explicit SI channels.
`experiments.py` defines validated experiment/parameter contracts and adapts the
existing plant/session. `calibration.py` provides bounded fitting, local parameter
observability checks, independent-run guards and one-at-a-time sensitivity.
`report.py`, `__main__.py` and `api.py` provide offline reports and Studio adapters.
The existing physics equations, controllers, sensors and scenarios are preserved;
SimulationSession.step() only gains optional independent physical input arguments.

Reports distinguish:

- **Analytical verification:** existing eleven reference traces and convergence checks.
- **Synthetic pipeline demonstration:** generated analytical CSV fixtures, never real data.
- **Calibration study:** fitting designated training data, never a validation result.
- **Experimental validation:** only for measured validation-role data with explicit
  provider assertions of input verification and vehicle identity/specifications.
  Software cannot authenticate those assertions or certify physical adequacy.
- **Measured-data exploratory comparison — validation pending:** actual measurements
  with unverified operating conditions, including the supplied VED experiments.

Evidence status and numerical acceptance are separate. An unverified measurement
study remains overall INCONCLUSIVE even if a numerical criterion passes; observed
numerical failures are still displayed. Synthetic tests remain synthetic after
fitting. No correlation-only or forced-speed accuracy claim is made.

## Windows workflow (Anaconda Prompt)

From the latest extracted checkout containing README.md:

```bat
"%LOCALAPPDATA%\veus-venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
"%LOCALAPPDATA%\veus-venv\Scripts\python.exe" -m pytest -q
```

Synthetic battery calibration, followed by independent synthetic holdout:

```bat
"%LOCALAPPDATA%\veus-venv\Scripts\python.exe" -m veus.validation calibrate examples\validation\synthetic-battery-train.json examples\validation\synthetic-battery-train.csv --settings examples\validation\battery-calibration.json --output reports\battery-fit-001
"%LOCALAPPDATA%\veus-venv\Scripts\python.exe" -m veus.validation evaluate examples\validation\synthetic-battery-holdout.json examples\validation\synthetic-battery-holdout.csv --calibration reports\battery-fit-001\calibration.json --output reports\battery-holdout-001
start "" reports\battery-holdout-001\report.html
```

Replace experiment/data paths with `examples\validation\ved-10-1558.json` /
`datasets\ved\ved-10-1558.csv` for exploratory measured calibration, and trip 1561
for held-out evaluation. Keep the same battery settings file. These measured runs
correctly return exit 1 / INCONCLUSIVE because operating evidence is incomplete.
The held-out numerical 2 V target also fails; do not loosen it to hide that result.

Coastdown software demonstration and sensitivity:

```bat
python -m veus.validation calibrate examples/validation/synthetic-coast-train.json examples/validation/synthetic-coast-train.csv --settings examples/validation/coast-calibration.json --output reports/coast-fit-001
python -m veus.validation evaluate examples/validation/synthetic-coast-holdout.json examples/validation/synthetic-coast-holdout.csv --calibration reports/coast-fit-001/calibration.json --sensitivity examples/validation/coast-sensitivity.json --output reports/coast-holdout-001
```

Use the explicit virtual-environment Python path above if `python` points to a
different environment. Every output directory must be new or empty. Exit 0 means
PASS, 1 means FAIL/INCONCLUSIVE, 2 means input/setup error. Reports preserve errors
rather than turning a failed fit or held-out comparison into a passing process.
No SciPy/ML/GPU is used. NumPy and the existing Matplotlib reporting dependency
are optional for reporting/calibration; the ordinary driving dashboard still
loads without them. Python 3.12 is tested; on Python 3.11 install the requirements
files rather than assuming the Linux 3.12 lockfile pins are all compatible.

## CSV import and preprocessing

Each experiment maps explicit column names, units and sign (1 or -1). Supported
signals are time, speed, acceleration, motor torque/speed, positive brake force,
voltage/current/SOC, gradient, position, terminal power and net energy. Examples
are in examples/validation. CSV is UTF-8, comma-delimited, dot-decimal; numeric
relative timestamps use s or ms. Absolute numeric time may be shifted to the
first sample by the explicitly recorded `zero_time` policy. No hidden lag fitting.

Conversions include km/h or mph to m/s, rpm to rad/s, SOC % to fraction, gradient
% to atan(percent/100) radians, degrees to radians and kW/kWh to W/Wh. Battery
current/power are positive during discharge and negative during charge/regen.
Motion is forward-only; drive torque and friction-brake force are nonnegative.
Signed shaft torque is accepted only by the separate energy-replay adapter.

SHA-256 must match the source CSV before use. Duplicate headers/timestamps,
nonmonotonic/nonfinite times, nonfinite values, invalid ranges and unsupported
units are rejected. Empty/NA/NaN/null measurement cells become explicit missing
values and are counted. Original data are not overwritten or cleaned silently.
Sampling min/median/max, irregularity and gaps are recorded. CSV is bounded to
10 MB / 100,000 rows; select documented short operating windows for laptop use.

Default input policy is previous-sample hold, not a driver reconstructed from
speed. Optional linear input interpolation is an explicit approximation that must
be justified in the experiment assumptions. No extrapolation, interpolation
across a configured large gap, or interpolation through missing endpoint values
is allowed. If required drive/brake/current inputs are unavailable, simulation
is rejected; the program does not invent a control input. A chosen gap threshold
is not proof that unobserved transients were small.

Predictions are aligned to original observation times. Comparison interpolation
is bounded linear interpolation of numerical predictions, or exact-grid-only
`none`; measured values are not filled. The final timestamp must align to the
chosen simulation step. Windows are limited to 1..120 s, matching the current
simulation scope. `derive_acceleration` optionally creates a finite-difference
speed-derived output reference with no crossing of gaps; it is not independent
accelerometer evidence. Energy references may be derived from measured V*I using
trapezoidal integration; missing intervals make cumulative energy unavailable
rather than silently treating power as zero.

## Reproducing operating conditions without circular validation

**Dynamics:** requires independently supplied drive shaft torque, positive brake
force and measured grade, plus a fixed known gear ratio, mass, wheel radius and
road-load parameters. A level-road assumption must be explicitly selected and
stated. Cd*A is one parameter: Cd and A cannot be uniquely identified separately
from longitudinal coast data. Initial speed/position can come from the first
measurement; future speed is predicted from forces, never imposed. The first
sample is excluded from error metrics. Battery limits can constrain delivered
power as in the existing model. Unknown actual gear/brake/gradient conditions make
real prediction claims unsupported. Negative measured drive torque must be
translated through a separately justified brake/regen model; it is not guessed.

**Battery-current replay:** independently measured current drives the existing
constant-OCV/resistance battery relation V=Voc-I*R. Voltage, terminal power, energy
and SOC can be evaluated without forcing voltage. Chemical stored energy evolves
with Voc*I. Initial measured SOC may be used only as an initial condition. This
cannot identify general OCV(SOC,T), hysteresis, aging, temperature or capacity
without further evidence. Inputs outside current/voltage/energy limits are
rejected rather than silently clipped to make outputs look better.

**Energy replay:** measured motor shaft torque and speed supply mechanical power.
Predicted electrical power is Pshaft/drive_eta in motoring, Pshaft*regen_eta in
regeneration. Speed is not an independently predicted output of this experiment
and cannot be selected as a comparison. Auxiliary/stall/thermal loads are absent.
Use this only when the reference signals and limitations justify it. Transmission
losses already precede a shaft-power input and are not applied twice.

Dynamics reuses the existing fixed-step plant. Cd*A is implemented as Cd=drag_area,
A=1 for the identical drag product; this is not a measured Cd estimate. Gear
ratios are held fixed, not inferred from speed. The explicit grade-offset field
is an experiment-condition sensitivity perturbation, not a fitted default grade.
Position retains explicit Euler and existing stopping-event handling. Battery
work uses the existing mean-velocity work integration. These numerical limitations
remain; compare steps and reference bounds before interpreting tiny residuals.

## Metrics and uncertainty

Residual = prediction minus measurement. Metrics are MAE, RMSE, max absolute error,
mean signed bias and absolute bias, with valid/total counts and coverage. Units
are explicit SI/Wh; no near-zero percentage division or correlation-only verdict.
Initial-condition samples do not count as prediction validation. Missing outputs
remain missing; insufficient coverage yields INCONCLUSIVE.

A comparison may specify a uniform bounded output uncertainty in the same unit.
The metric interval is max(0,metric-u)..metric+u. PASS requires its upper bound
below the threshold; FAIL requires its lower bound above; overlap is INCONCLUSIVE.
This is a conservative norm/bias bound, not a statistical confidence interval.
Input uncertainty and model-form error are not automatically propagated. Unknown
instrument uncertainty stays unknown, including the supplied VED studies.

For applicable braking runs, measured onset is the first positive recorded brake
force. Distance uses measured position, or explicitly labelled trapezoidal speed
integration if position is absent. The predicted stop threshold is 0.05 m/s;
event timing is sampled, not a continuous crash/stop reconstruction. Reaction
distance is excluded. The event error is unavailable without a complete stop and
known interval. Speed, acceleration, position, SOC, power and net-energy output
errors are computed only when their independent references exist.

## Calibration and independent evaluation

Only calibration-role data can be fitted. Parameters have explicit bounds and
must be supported by the experiment: rolling resistance/drag area for dynamics,
Voc/R for local current-voltage replay, drive efficiency for shaft-energy replay.
Mass, grade, capacity and other confounding quantities are not silently fitted.

Current-voltage fitting uses NumPy least squares with bounded acceptance: a
solution outside declared physical bounds is rejected, not clipped and advertised
as an estimate. Other supported cases use deterministic bounded grid refinement.
Search settings, initial/fitted parameters, objective RMSE, history/evaluations and
local identifiability evidence are recorded. Grid precision and correlated
parameters can limit recovery even on exact fixtures; a good training fit does
not prove unique physical parameters or good independent performance.

Normalised design/sensitivity columns must have full rank and condition number
<=100. Zero/unexcited or dependent directions return NOT_IDENTIFIABLE. This is a
local numerical guard under fixed assumptions, not proof of global uniqueness.
Finite instrument precision/confounding can invalidate a plausible regression.
Never interpret VED's local resistance coefficient as a globally validated pack
resistance map. Original model/configuration objects remain unchanged.

A fitted artifact is applied only to validation-role data. Duplicate byte hashes
and same dataset/run identities are rejected even under different filenames.
Known vehicle IDs must match; unknown identity cannot inherit a known-vehicle
calibration. Only the fitted parameter names transfer: independently declared
fixed conditions in the held-out experiment are preserved. Metadata cannot detect
an author deliberately relabelling the same run; independence needs source audit.
No random neighbouring-sample train/test split is presented as independent data.

The held-out experiment produces original/calibrated predictions against the
same reference, including deterioration or criterion failure. It never adjusts
parameters in response to held-out residuals. A further fit needs a new declared
training study and another independent validation run.

## Sensitivity is not fitting

One-at-a-time low/high sweeps hold all other inputs fixed. Dynamics supports
mass, drag area, rolling resistance, drive efficiency and grade offset; electrical
replay supports Voc/R or drive efficiency as appropriate. RMS/final prediction
span and plots show output influence over the **declared ranges**. Rankings depend
on those ranges and operating conditions, not only physical importance. No
interaction/global identifiability claim is made. The study is deterministic and
does not update model parameters or reuse validation outputs to fit them.

## Studio and artifacts

Expand **Model Validation**. Load a supplied experiment or a matching JSON/CSV,
edit the validated model/experiment JSON, and select evaluation or training-only
calibration. Upload/retain/clear a calibration artifact explicitly. Optional
sensitivity uses the declared settings ranges. The panel shows provenance/evidence
class, original/calibrated errors, report plots/residuals and an HTML export.
CSV bytes must match the declared hash; loading a new file does not silently
rewrite provenance. The report iframe is sandboxed. No heavy frontend framework.

Offline outputs include unchanged original.csv, SI standardised.csv,
experiment.json (resolved config with hash), original experiment-input.json,
report.json/html, residual CSVs and calibration.json where applicable. Source and
configuration hashes, software versions and source provenance are retained.
HTML embeds plots and needs no server/CDN. The canonical calibration content hash
identifies JSON content, not the source file's whitespace formatting. A ZIP without
Git metadata reports absent commit identity rather than inventing it.

## Known limits and next evidence needed

The framework is verified with independent analytical synthetic trajectories and
known error-metric results, not a real-vehicle ground truth generated by VEUS.
No measured driving torque/brake/grade dataset has yet qualified the full dynamics.
The small VED windows are real data but have unconfirmed current sign, unknown pack
temperature/synchronization/uncertainty and different SOC. Physical acceptance
therefore remains pending despite improvement in a held-out voltage residual.
See dataset-discovery.md. NASA SOH integration remains a separate, evidence-based
future adapter; SOH is not used to invent voltage, resistance or power limits.
