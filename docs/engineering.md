# Engineering assumptions and validation

## Conventions and equations

All internal calculations use SI units; RPM and dashboard km/h are explicit
conversions. Forward speed is nonnegative. Positive motor torque drives forward;
positive brake force opposes motion. Grade angle is in radians, positive uphill.
The mechanical step rejects negative drive torque; the session models regenerative
energy separately by blending the delivered braking force.

- Normal force: `N = m g cos(grade)`; `g = 9.81 m/s²`.
- Aerodynamic resistance: `F_aero = 0.5 rho Cd A v²`, default rho 1.225 kg/m³.
- Rolling resistance while moving: `F_roll = Crr N`.
- Grade resistance: `F_grade = m g sin(grade)`.
- Wheel drive force: `F_drive = T_motor ratio efficiency / wheel_radius`.
- Motor torque ceiling: `min(T_max, P_max / omega)`; no drive at/above max RPM.
- Lumped tyre force limit: `mu N`. Drive consumes capacity first; friction braking
  uses the remaining capacity. No axle load transfer, slip dynamics or wheel inertia.
- Acceleration: `(F_drive - F_brake - F_aero - F_roll - F_grade) / m`.
- Explicit Euler: `v_next = v + a dt`, `x_next = x + v dt`.

At a stop, rolling resistance only opposes an incipient forward movement.
Negative acceleration at zero speed is suppressed: this forward-only model
implicitly holds the vehicle instead of simulating rollback. When a step crosses
zero speed, use `t_stop = -v/a` and `distance = v t_stop + 0.5 a t_stop²`, then
hold position for the rest of the step. Other steps use explicit Euler position.
Forces and acceleration in StepResult describe the start of the step; state is
at the end. Shorten timesteps to reduce Euler error. Transmission gear is selected
by the caller and held per step; the old inverse calculator retains its speed shift.
No driving-cycle claims should be inferred from this simplified model.

The cell model interpolates OCV from SOC and uses resistive sag, not detailed
chemistry or thermal dynamics. Pack resistance is `Ns Rcell / Np + Rbus`.
With discharge current positive: `Vterminal = Ns Voc - I Rpack`,
`Pterminal = Vterminal I`, `Pchemical = Pterminal + I² Rpack`.
The motor's simplified loss terms and inverter loss terms are uncalibrated.
Existing defaults have no measured vehicle validation or efficiency maps.

## Validation and reproducibility

Run `python -m pytest -q` from the checkout. Tests exercise independent analytical
force, torque, power and pack identities, constant-force motion, braking distance,
grade, friction, saturation, overspeed, invalid inputs, Euler convergence, legacy
operating-point behaviour and a complete dashboard telemetry loop.

The constant-force reference uses 1,000 kg, 1,000 N, zero drag/rolling resistance:
after 2 s, analytical velocity is 2 m/s and position is 2 m. Euler position is
1.9 m at dt=0.1 s and 1.95 m at dt=0.05 s: halving dt halves the error.
The braking reference is v0=10 m/s, braking force 2,000 N, mass 1,000 kg:
analytical stopping distance 25 m. A 0.1 s step is checked within 0.51 m.
The boundary-event case v0=1 m/s and a=-2 m/s² stops in 0.25 m within one step.

The existing cruise example at 33.33 m/s, zero acceleration and SOC 0.8 returns
59.56814668 kW pack terminal power. This regression preserves behaviour; it does
not establish physical calibration. The legacy launch is deterministic, ends at
9.5 s and 119.7 km/h, and contains 96 frames. The API test compares all frames
and the first repeated frame, in addition to checking both HTML routes.

## Known limitations and remaining work

- The interactive session now integrates battery energy/SOC and limits drive
  power; temperature, aging and SOC-dependent OCV remain unmodelled.
- Operating-point electrical coupling uses four unchecked fixed iterations and a
  voltage floor. A high-demand audit case (20 m/s, requested 20 m/s², SOC 0.9)
  left about 461 W terminal-power mismatch. Robust convergence and feasibility
  handling remain legacy-solver work; do not treat these outputs as energy validation.
- Operating-point acceleration remains requested rather than achieved. Use the
  forward simulator for achieved motion. Legacy total losses omit transmission.
- Motor overspeed now cuts torque; it is a simple policy without hysteresis.
- Legacy component parameter validation is incomplete beyond vehicle/motor.
- Brakes use ideal force commands with configurable pure actuation delay; no
  brake fade or detailed actuator dynamics. Regenerative/friction blending is modelled.
- Simplified ADAS, scenario files and requirement reports are now available;
  virtual sensors and deterministic faults are now available; measured-vehicle
  validation remains future work.
  The interactive dashboard provides basic plots, configuration and exports.
- No production safety, real-time timing, HIL or measured vehicle fidelity claim.

Next: calibrated model evidence,
dashboard extensions and integration exports. Keep the existing models and public
example working while adding these capabilities incrementally.


## Interactive testbench increment

`SimulationSession` owns state, validated configuration and controls per client.
It advances ten deterministic 0.01 s steps per telemetry frame, with automatic
gear selection at 27.7 m/s. Manual commands or fixed acceleration/braking/coast
presets feed the same forward physics. Brake commands override throttle; full
brake requests m*g and tyre friction limits actual force. A zero-friction road
therefore cannot transmit drive or brake force. Aerodynamic and grade loads remain.

The WebSocket supports reset, start, pause and controls. Invalid configurations
are rejected without replacing the current run. Duration is bounded to 120 s.
No background simulation continues after disconnect. Playback is nominal 1×,
without unbounded catch-up after slow transport. End-state telemetry includes
forces, torque and power evaluated over the final integration interval. Initial
frames have zero force/power placeholders until stepping starts.

Exports are CSV end-state samples and JSON configuration/model metadata. This is
an initial export format, not the final integration schema. Manual input history
and exact source commit are not captured; no claim of complete run replayability.
The legacy /ws/telemetry endpoint and operating-point calculator are preserved.

Additional tests exercise configuration-dependent acceleration, reduced-friction
response, braking and coasting, repeatability, pause/reset, brake priority,
invalid inputs, completion timing, WebSocket errors and isolation across clients.


## Phase 2: interactive EV energy model

The interactive session uses EnergyBattery, separate from the preserved legacy
cell/pack operating-point calculator. Capacity is a chemical-energy reservoir;
SOC = stored_energy / capacity. Constant OCV is configurable (default 400 V).
Terminal power P = (Voc - I R) I is solved analytically on the high-voltage branch:
I = 2 P / (Voc + sqrt(Voc² - 4 R P)). Positive current means discharge.
Chemical power = Voc I; battery heat = I² R. Integrate chemical power at each
0.01 s step. Both charge/discharge current and remaining energy limit power.
Terminal voltage stays between 0.5 and 1.1 times OCV; these are illustrative
model constraints, not manufacturer cell safety limits.

Driving electrical energy = wheel drive work / (transmission_eta * drive_eta).
Recovered electrical energy = regen wheel work * transmission_eta * regen_eta.
The UI efficiencies represent motor/inverter conversion; transmission eta stays
0.97. This intentionally replaces uncalibrated legacy speed/current loss formulas
for the interactive path. It has no copper/stall loss or auxiliary consumption.

For a held-force physics step, wheel work uses the displacement integrated from
mean endpoint velocity over the moving portion of the step, including stopping
boundary events. This makes force work consistent with kinetic-energy change.
Position retains the documented explicit Euler approximation; it differs slightly
from this energy-integration distance and converges as the timestep decreases.
A bounded bisection reduces drive torque when requested step energy exceeds
battery capability. Regeneration is limited by actual tyre-limited brake work,
motor torque/power/RPM, battery charge current and available capacity. Friction
braking supplies the remainder, including when SOC is full or regen is disabled.
No automatic regeneration occurs while coasting.

The energy residual is initial battery plus initial kinetic energy minus current
battery/kinetic energy, battery heat, conversion losses, friction-brake heat and
road work. Road work includes signed gradient work (negative downhill). Stored
energy increases under regeneration but is bounded by the initial kinetic energy
and downhill work after losses. A small residual demonstrates numerical accounting,
not validation against a physical vehicle. The old inverse solver still uses its
legacy electrical iteration and should not be used as the Phase 2 energy reference.

Tests check analytic current/power identities with/without resistance, SOC/current/
voltage limits, empty-pack torque reduction, regeneration versus friction-only
stopping, full-pack friction fallback, low-friction/downhill runs, repeatability
and cumulative energy residual below 1e-5 J for the selected 5-second runs.


## Phase 3: cruise, ACC and AEB

Controllers live in `veus/control/longitudinal.py`, independent of the plant/API.
A command is desired longitudinal acceleration. Speed feedback is proportional:
`a_speed = 0.7 (v_target - v_ego)`. ACC selects the smaller of speed feedback and
`a_gap = 0.3 (gap - (d0 + h v_ego)) + 0.9 (v_lead - v_ego)`.
Comfort acceleration/deceleration limits clip these commands. No integral term,
jerk limit or actuator dynamics beyond a pure delay is included. Road-load
feedforward converts the acceleration request to wheel force; actual motor,
friction and battery limits can prevent the requested acceleration being achieved.

AEB mode uses speed control until `TTC <= threshold` or `gap <= d0`.
TTC is `gap / (v_ego - v_lead)` only when closing speed > 1e-6 m/s. Otherwise
it is undefined/null; the graph leaves missing segments. AEB latches emergency
braking until reset, requesting m*g friction/regen brake force before tyre limiting.
It does not automatically reaccelerate after a stop. ACC has no AEB overlay in
this increment. A successful scenario is not proof of collision avoidance elsewhere.

Each physics tick observes exact plant speed/gap and a prescribed lead vehicle.
Detection delay stores observation history; actuator delay stores acceleration
commands, both rounded to 0.01 s. Before a detection history fills, the initial
observation is held. Before an actuator history fills, propulsion/braking is zero
(coasting). Optional virtual sensors now precede that history; noise, dropout and scheduled
faults are described in virtual-sensors.md. No sensor range model is included.
The detection timestamp precedes actuator delay; telemetry reports applied
controller state separately. Settings apply on reset, not live during a run.

The lead position is its rear bumper; ego position is its front bumper. Initial
gap is bumper-to-bumper. Lead speed is constant for ACC. In AEB, lead position
is integrated analytically with constant deceleration after the configured brake
time, stopping at zero speed. Ego position retains fixed-step explicit Euler.
Minimum gap is sampled at every physics tick. If gap <= 0, record collision and
stop the run without faking zero vehicle speed or simulating crash dynamics.
Result timing/gaps are therefore discretization-dependent; no safety certification
or quantified detection accuracy is implied.

Reference runs (default 1,800 kg EV, 30 s, 80 km/h target): cruise ends within
0.05 km/h of target; ACC starting at 80 km/h follows a 60 km/h lead and converges
within 0.1 km/h and 0.2 m of the desired headway gap. AEB starting with both at
80 km/h, gap 35 m, lead braking at 3 s / 6 m/s², friction 0.9 triggers at 4.96 s
and stops with minimum gap about 5.12 m. Friction 0.1 produces a collision in the
same scenario. These are outputs of this illustrative model, not measured data.
Tests also verify TTC domains, command limits, latch/reset, delayed responses,
analytical lead stopping, collision restart rejection and continued energy balance.


## Offline verification and reporting

The incremental audit is in development-audit.md. The offline batch runner now
records every physics tick using the additive SimulationSession.step() API;
advance() retains the existing ten-tick dashboard behaviour. Versioned scenario
and result contracts, analytical reference trajectories, explicit requirement
criteria, and report artifact/metric definitions are documented in validation.md.
The separate SOH project boundary is documented in soh-integration.md. This
increment does not change controller algorithms or claim measured validation.

## Phase 8 measurement experiments

The measurement adapter reuses the longitudinal plant with explicit physical
inputs; live controllers and virtual sensor timing remain unchanged. CSV source
bytes and experiment hashes distinguish measurements from synthetic references.
Training-only bounded calibration and guarded independent evaluation are separate
from analytical verification. See [the model validation guide](vehicle-validation.md),
[dataset assessment](dataset-discovery.md), and [executed evidence](phase8-evidence/README.md).
No full measured-vehicle dynamics validation has yet qualified. The VED voltage
comparison remains exploratory because operating conditions are incomplete.

## Phase 9 interactive workspaces

Drive adds a bounded telemetry-interpolated Canvas view, illustrative vehicle
presets and keyboard/pointer input over the existing WebSocket controls.
Analyse and Validate preserve engineering capabilities. No core physics or
controller equations change. See [frontend architecture and input policy](drive-experience.md)
and [browser execution evidence](phase9-evidence/README.md).

## Phase 10 recorded EV analysis

Replay reuses the canonical importer and extracted Canvas renderer, with a
separate recorded-time clock and no simulation commands. Measured columns remain
separate from derived speed integrals, acceleration and signed V×I. Coverage,
unknown polarity, missing measurements and source/config hashes remain explicit.
See [recorded-data architecture and calculations](real-world-replay.md) and
[executed evidence](phase10-evidence/README.md). No physical validation conclusion
changes because observations can be replayed.
