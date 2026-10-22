# Phase 1 engineering assumptions and validation

## Conventions and equations

All internal calculations use SI units; RPM and dashboard km/h are explicit
conversions. Forward speed is nonnegative. Positive motor torque drives forward;
positive brake force opposes motion. Grade angle is in radians, positive uphill.
Forward simulation rejects negative drive torque; regenerative energy is deferred.

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

- Battery SOC, energy and thermal states are not integrated. Forward dynamics
  is mechanical only; battery constraints do not yet limit drive force (Phase 2).
- Operating-point electrical coupling uses four unchecked fixed iterations and a
  voltage floor. A high-demand audit case (20 m/s, requested 20 m/s², SOC 0.9)
  left about 461 W terminal-power mismatch. Robust convergence and feasibility
  handling remain Phase 2; do not treat these outputs as energy validation.
- Operating-point acceleration remains requested rather than achieved. Use the
  forward simulator for achieved motion. Legacy total losses omit transmission.
- Motor overspeed now cuts torque; it is a simple policy without hysteresis.
- Legacy component parameter validation is incomplete beyond vehicle/motor.
- Friction brakes are ideal commands; no actuator lag, fade or regenerative split.
- No ADAS, sensor faults, scenario-file engine or requirement evaluator yet.
  The interactive dashboard provides basic plots, configuration and exports.
- No production safety, real-time timing, HIL or measured vehicle fidelity claim.

Next: Phase 2 power/energy consistency, SOC integration and electrical operating
limits; then controllers, scenario configuration, sensors, requirements evaluation,
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
