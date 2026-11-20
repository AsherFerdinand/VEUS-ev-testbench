# Deterministic Simulation Lab

VEUS 2.2 adds a bounded coupled numerical experiment runner. It reuses the retained
longitudinal, motor, transmission and battery equations; these experiments do not
establish physical vehicle accuracy. Phase 8 physical validation remains INCONCLUSIVE.

## Contracts and execution

POST `/api/lab/run` accepts a complete resolved v2 vehicle snapshot, a versioned
experiment and the adapter acknowledgements. Omitted vehicle fields are rejected,
not filled by a default vehicle. Experiment kinds are `constant_speed`, `acceleration`,
`braking`, `gradient` and `coast`; the profile extension uses the same kernel.

All quantities use SI units. Explicit step size is 0.01–0.25 s, duration at most
1800 s, and at most 12,000 complete steps. Duration must be an integer multiple of
dt; no source or result trace is silently downsampled. The API runs numerical work
outside the event loop, permits at most two active runs and returns 429 when busy.
There is no retained simulation-result cache, background simulation or WebSocket.

The trace contains the initial state and every completed tick. Replay is a separate
frontend operation over this frozen trace and does not rerun the model. A changing
design/scenario cannot change an already frozen result. Configuration/request, model
version, parameters, acknowledgements, source provenance and canonical SHA256 are
included. There are no random variables or wall-clock timestamps in the numerical
result. Identical inputs/software yield identical results and hashes.

## Shared coupling and boundaries

`lab.kernel.CoupledKernel` uses `SimulationSession._energy_step` directly, without
calling the legacy session's gear selector, controller or sensors. Its injected
`LongitudinalSimulator` receives the selected mass, Cd, area, rolling resistance,
wheel radius, single fixed ratio, motor envelope, friction, density and grade.
The selected battery receives usable capacity, nominal OCV, resistance, SOC and
charge/discharge current limits. No legacy vehicle dimensions or gears are substituted.

`EnergyBattery.power_limits` now accepts optional terminal voltage/current/power
constraints. Calls without them preserve the existing battery contract. The lab
supplies the intersection of declared battery/inverter voltage ranges, inverter DC
current limit, inverter AC output power converted to DC using the explicit inverter
efficiency, and motor shaft power converted through the explicit forward efficiencies.
SOC/chemical-energy and existing stable-branch voltage limits still apply. These
are intersections, not replacements for the battery's internal voltage window.

The mechanical step supplies wheel forces. Drive work is divided by motor × inverter
× gearbox efficiency exactly once to obtain DC battery demand. Available DC power
bounds the same mechanical step through the retained monotonic torque bisection.
The cap also limits average shaft power over the interval, including acceleration
from zero speed; instantaneous torque–speed limits alone would not ensure that.

Regenerative braking uses the selected explicit **total reverse motor/inverter**
efficiency and gearbox efficiency once. It does not multiply the forward motor and
inverter efficiencies again. Charge acceptance and motor constraints limit recovery;
friction braking provides the remaining achieved braking work. Battery SOC=1 or
zero charge acceptance produces friction fallback, not fictitious recovered energy.
A declared zero discharge limit is useful for coast/brake experiments; a missing
essential resistance/current/efficiency remains unavailable and blocks execution.

Default power policy is conservative **continuous/rated** motor torque/power and
inverter continuous power. Peak operation requires an additional
`peak_envelope_without_thermal_model` acknowledgement. Any supplied motor/inverter
peak duration bounds the whole selected peak run; over-duration requests are rejected.
Unknown durations remain a stated limitation, never proof of sustained thermal duty.

## Actual versus requested quantities

Predictive acceleration uses the configured drive envelope; braking supplies explicit
force from the selected deceleration setting; coast supplies no drive or brake.
Constant-speed/gradient runs use deterministic bounded tracking with road-force
feedforward. No ACC/AEB or autonomous-driving logic is reintroduced.

`road_loads` in the dynamics module is the shared force-decomposition helper for
physics and demand analysis. Aerodynamic, rolling and gradient forces and integrated
work are separately recorded. Requested speed demand uses the target trace; actual
speed always comes from the constraint-aware physical step. An infeasible target
is not substituted into the simulated state.

The trace distinguishes `requested_dc_power_w`, requested target/distance and demand
feasibility from actual battery power, SOC, position and speed. Summary `requested_*`
energy/consumption belongs to the demand calculation; unprefixed consumption belongs
to **achieved movement**. Requested demand is not passed through a clipped battery
exchange and relabelled as requested energy. SOC always belongs to the actual run.
An unavailable or unachieved target time is null, never zero or an extrapolation.

Trace powers are interval-average values attached to the interval's end state;
acceleration/road forces describe the held step. `motor_power_w` and motor torque are
signed shaft quantities, negative during regeneration. `regen_power_w` is recovered
DC power; `regen_wheel_power_w` is the distinct mechanical regenerative wheel demand.
`friction_power_w` is brake heat. There are no auxiliary loads in this milestone.

Energy accounting uses the retained held-acceleration mean displacement, while
position uses retained Euler integration except exact within-step stopping. Their
O(dt) difference is explicit; reported positional distance is not silently replaced
by the work-integration distance. Stop and target times are observed simulation tick
times with dt resolution. The conservation residual includes battery chemical energy,
kinetic energy, battery heat, conversion loss, friction heat and signed road work.
Downhill gradient work can be negative because gravity supplies energy.

## Results, export and scope

Summaries include achieved distance/speed, target/stop metrics where attained, SOC,
consumed/recovered/net battery energy, kWh/100 km over achieved nonzero distance,
road-work splits, conversion/heat terms, requested-demand metrics and conservation
residual. Units accompany summary fields. No zero-distance consumption is fabricated.

POST `/api/lab/export` accepts the frozen result and `json`, `csv` or `html`. It checks
version, canonical hash, matching request snapshots and complete time-grid structure,
then serializes without recalculating the experiment. The unkeyed hash is an integrity
fingerprint, **not authentication** that a client-provided result was produced by VEUS.
CSV preserves every simulation tick; portable HTML uses local inline SVG plotting
and includes configuration/provenance/limitations. No PDF dependency is added.

CLI: `python -m veus.lab request.json --output NEW_DIRECTORY`. A new output directory
is required; request JSON plus the three exports are saved. The API request cap is
2 MB; frozen export requests are bounded at 24 MB. Oversized inputs fail explicitly.

This remains a simplified forward-only, lumped-traction, constant-efficiency/OCV
model. Motor phase-current/back-EMF maps, standstill copper losses, inverter switching
maps, thermal/peak-duty dynamics, auxiliary demand, tyre slip, ageing, charging curves
and physical calibration are unavailable. A source profile is not regulatory
certification and a prescribed trace is not a lap-time prediction.

## Verification

Checkpoint A was executed before profile/route implementation: five experiment types,
selected nondefault geometry and exact constant-force acceleration, independent
2450 W drag-only steady-speed demand, battery/inverter current and terminal-voltage
limits, average shaft power, mass/grade effects, zero/full SOC, no-regen/zero-acceptance
friction fallback, signed regenerative power boundaries, deterministic results,
complete exports and frozen-hash checks. Existing energy/session/physics tests also
passed: **54 passing tests** at the checkpoint. Additional strict external snapshot
and profile checks extend that suite. These are equation/software checks, not physical
validation. Final execution evidence is recorded by the integration coordinator.

## Profile and route extension (2.3)

The same `LabRequest` accepts strict parent-owned `ProfileData` and `RouteData`.
Time-profile samplers provide piecewise-linear target speed, finite interval target
acceleration and any supplied grade. There is no repeat/clamp beyond source time
coverage and no interpolation across a declared time gap. A combined route carrying
validated time/speed arrays resolves through the same profile contract; geometry
alone is not a driving-speed trace. Geometry can accompany an explicitly configured
constant-speed experiment.

Predictive mode requests profile acceleration plus deterministic speed-error
feedback. Prescribed mode requests the force needed to reach the next target speed
at the next time step. Both go through exactly the same physical constraints and
never assign the requested speed into the achieved state. Requested demand uses
finite target Δv/dt and interval-mean target speed, independent of achieved battery
exchange. Original source arrays, units, licence, source hash and classifications
remain in the frozen profile/route snapshots.

Routes apply grade using achieved distance in predictive mode and requested profile
integral in prescribed mode. `route_position_m` and `route_basis` identify that index
separately from achieved `position_m`. Route geometry is supplied/simulated scenario
context, never measured GPS output from the vehicle model. Missing latitude,
longitude or elevation stays null. Unknown/exhausted route grade rejects `require`
policy; an explicitly chosen `experiment_constant_assumption` uses the declared
experiment grade and adds a trace flag. It never quietly substitutes a flat profile
grade for missing route grade. The source importer/samplers own distance derivation,
unit conversion and source-gap policies; the runner does not duplicate them.

Requested energy feasibility is separated from requested **motion** feasibility.
A battery unable to accept charge does not imply that friction braking cannot meet
the requested deceleration. `requested_regen_recovery_limited` identifies that case;
`requested_motion_feasible` tests movement constraints. The combined requested-demand
flag includes ideal recovery capability and must not be described as motion alone.
Trace `unmet_dc_power_w` is the instantaneous excess beyond the available electrical
power envelope, not target-minus-achieved kinetic energy.

The runner reports maximum and RMS tracking error in m/s, timestep duration per active
limit, contiguous `limit_intervals`, and deterministic findings with numerical values
and units. Work/energy findings refer to achieved model results; constraints and
recovery findings never infer a real-world causal mechanism. HTML exports include
requested/achieved speed lines and those findings, with complete JSON/CSV retaining
every simulation tick and source snapshot. Source import/research scope belongs in
the coordinator's profile documentation and pinned dataset records, not duplicated here.
