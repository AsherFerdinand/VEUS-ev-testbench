# Phase 8 plan and pre-implementation assessment

Base: feature/virtual-sensors-fault-injection (4289809); baseline 109 tests pass.
No physics equation, controller or Phase 7 fault policy will be replaced.

Existing RunConfig exposes mass, torque/power, friction, grade, electrical limits,
capacity/SOC and efficiencies. Cd, frontal area, wheel radius, rolling coefficient
and air density are currently dataclass defaults rather than RunConfig fields.
The validation adapter will supply these parameters explicitly to the existing
plant. Calibration will use Cd*A as one parameter, not claim to identify Cd and A
independently. Sensor-based scenarios and their existing report criteria remain.

Data discovery: VED (University of Michigan) README/licence and its Data folder
are accessible. Published signals include speed, battery current/voltage/SOC, but
not motor torque or brake demand; predictive motion validation is unsupported.
Two archives have verified HEAD sizes 82,723,769 and 93,662,910 bytes. A small
measured subset may support an explicitly limited electrical comparison only if
signs, vehicle identity, operating assumptions and independent runs are adequate.
Argonne D3 and EPA pages are blocked by the network proxy. No accuracy claim is
based on their uninspected data. Findings will be recorded in dataset-discovery.md.

Implementation sequence:
1. CSV ingestion with explicit column/unit/sign mapping, original-file hash,
   monotonic/unique times, missingness and sampling/gap checks. Explicit bounded
   interpolation only; do not impute unavailable propulsion/braking inputs.
2. Versioned experiments distinguish synthetic, calibration and measured validation.
   Dynamics replay uses independently supplied shaft torque, brake force and grade;
   initial speed is an initial condition, never a forced speed trajectory.
   Battery-current replay predicts voltage/energy/SOC from current. Energy replay
   predicts electrical consumption from measured shaft torque/speed, not speed fit.
3. Reuse the existing session/plant with an additive physical-input stepping API.
   Preserve the old API and defaults; add no new physical equations unnecessarily.
4. MAE/RMSE/max/bias/residuals with units, valid masks, coverage counts and optional
   uncertainty. Preserve missing values; no near-zero percentage error statistics.
5. Bounded deterministic calibration, explicit objective and sensitivity/rank
   checks. Use only supported parameters; preserve original model. Reject final
   validation data as training, duplicate hashes/run identities and weak/unexcited
   parameter combinations. Independent evaluation is separate from fitting.
6. Small independent analytical synthetic fixtures verify the pipeline; all
   synthetic outputs stay labelled. Add sensitivity sweeps, portable HTML/CSV/JSON
   reports, hashes/provenance and a compact Studio validation panel/API.
7. Full unit/integration/regression tests, browser/report checks and documented
   results. Experimental validation remains pending if an adequate independently
   measured dataset cannot be reproduced. No data/criteria fabrication.

Identifiability: motion needs known torque/braking/grade/mass/gear topology;
coasting excitation can identify rolling and drag area only with sufficient speed
range and fixed other parameters. Electrical V=Voc-RI may identify a local constant
Voc/R pair with current variation and stable SOC/temperature, not general OCV(SOC)
or thermal/aging behaviour. Capacity, resistance and power limits are not inferred
from SOH. Correlation or forced speed agreement is not physical validation.
