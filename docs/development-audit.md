# Validation and reporting audit (before implementation)

The current checkout was inspected before this increment. It contains 55 automated
tests, Python dataclass physical models, a transport-independent SimulationSession,
pure controller objects, and FastAPI/static JavaScript dashboard adapters. No
external services, GPU or additional vehicle hardware is needed. The existing
model/controller/API separation is reusable; no replacement architecture is needed.

## Existing modules and evidence

- model/: vehicle loads, motor torque/power, transmission, legacy cell/pack/inverter,
  and a separate constant-OCV EnergyBattery used by the interactive session.
- sim/dynamics.py: fixed-step forward mechanical model; explicit Euler position,
  explicit velocity update and special stopping-event handling.
- sim/session.py: per-tick gear/controller/energy orchestration, fixed 0.01 s
  timestep and 0.1 s telemetry, validated RunConfig and Controls.
- control/longitudinal.py: proportional cruise, PD headway ACC, latched TTC AEB.
- studio/: HTTP/static assets and per-WebSocket sessions. Legacy telemetry remains.
- tests/: analytical force/pack identities, Euler convergence, braking, controller
  reference scenarios, battery limits, energy accounting and HTTP/WebSocket tests.

The 55-test baseline is run before modifications. Coverage breadth includes the
main workflows, but there was no measured coverage artifact, coasting analytical
trajectory, repeatable reference-plot generator, scenario file schema, offline
batch runner, persisted pedal schedule or automated engineering report.

## Physical and numerical limitations

- Parameters are illustrative, not identified from vehicle measurements. Tests
  verify equations/software; they do not demonstrate real-world validation.
- One-dimensional forward-only dynamics; no slip, axle load transfer or rollback.
- Lumped friction limit, ideal friction/regen blending, constant conversion
  efficiencies; no brake fade, thermal effects, auxiliary consumption or calibration.
- Constant battery OCV/resistance and chemical-energy SOC; legacy inverse solver
  has independent approximate loss formulas and unchecked electrical iteration.
- Explicit Euler position has first-order error; work uses a different,
  mean-velocity displacement for energy consistency. Collision/stop/delay times
  are quantized; impact speed must be labelled at first detected overlap, not an
  interpolated crash prediction. TTC is undefined when not closing.
- ACC has no AEB overlay; AEB is a simple latched threshold, not a safety guarantee.
- Existing 0.1 s dashboard frames can miss per-tick TTC extrema and brake events.
  A batch runner must record 0.01 s ticks, with event definitions stated explicitly.
- RunConfig mixes plant/controller/run settings but is already validated and
  stable. Reuse it inside a stricter scenario model rather than breaking clients.
- No scenario-level requirements, INCONCLUSIVE policy, source/config fingerprints,
  raw batch evidence, or report exit-status contract existed.

## Increment plan

1. Add independent analytical acceleration/braking/coast/gradient/energy references,
   convergence bounds and reproducible plots. Retain all baseline checks.
2. Expose an additive per-physics-tick session API; preserve advance() frame semantics.
3. Add JSON scenario/configuration/result models, timed manual commands, batch
   execution and tick-level metrics. Preserve resolved defaults and source identity.
4. Add explicit criteria with rationale, PASS/FAIL/INCONCLUSIVE, CSV/JSON evidence
   and standalone HTML reports. Expected collisions remain visible; never call
   a failed avoidance requirement a safety pass.
5. Define a future SOH estimate exchange interface only. No automatic mapping of
   SOH to resistance, voltage or allowable power; document required calibration.
6. Run unit/integration/regression tests, example batches, coverage and CLI failure
   checks. Publish numerical evidence separately from any real-world claim.

## Executed follow-up

The implementation preserves the dashboard and adds an offline per-tick runner.
See [executed evidence](verification/README.md) for measured test/coverage results,
analytical plots and scenario failures. These are software verification outcomes,
not measured-vehicle validation.
