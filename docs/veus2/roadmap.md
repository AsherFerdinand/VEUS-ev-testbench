# VEUS 2.0 redevelopment roadmap

Current milestone: **VEUS 3.0.0rc1 final integration and release preparation**, not a stable release. Foundation evidence remains historical.
The order below follows engineering dependencies rather than the number of tabs.

| Milestone                           | Concrete result                                                                                                                                                          | Evidence required before advancing                                                                                                                  |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0 · Foundation (this branch)        | Source/architecture audit, retained reference, independent shell, original anatomy, challenges, labelled prototypes, versioned illustrative design, existing tool access | Existing tests retained, new API/UI checks, real captures, measured footprint; no fake outputs                                                      |
| 1 · Vehicle and component contracts | Separate sourced catalogue records from user design intent; add configuration persistence, duplicate/import/compare and explicit mappings to existing models             | Source URL/date/conditions/units/uncertainty per value; invalid envelopes rejected; no technology-label performance inference                       |
| 2 · Deterministic Simulation Lab    | Reuse backend equations for constant-speed, gradients, acceleration and regen studies; separate scenario/run/result/replay contracts                                     | Match existing analytical traces and energy accounting; timestep sensitivity; reproducible source/config hashes; unsupported modes unavailable      |
| 3 · Sourced profiles and routes     | Urban/motorway/standardized cycle inputs, prescribed versus predictive feasibility, shared playback cursor                                                               | Compatible licences, untouched source profiles and units, gap/coverage policy; infeasible demands reported, not silently achieved                   |
| 4 · Controlled comparisons          | Baseline versus modified designs under identical conditions; bounded parameter sweeps and sensitivity                                                                    | Explicit objectives/units/constraints, matched scenario hashes, raw traces, failures/inconclusive outcomes retained                                 |
| 5 · Measurement UX replacement      | Question → signals → evidence → report in the new shell, replacing old DOM bindings                                                                                      | Import, source hashes, readiness, polarity/energy gates, selected event indices and exports match Phase 11; migration UI deletion only after parity |
| 6 · Additional engineering models   | Charging acceptance curves, thermal network, calibrated losses, cost/energy-tariff studies as independently scoped modules                                               | Independent model/data validation, documented uncertainty and units; component subtotal distinguished from complete production cost/retail price    |
| 7 · Optimization if justified       | Feasible constrained studies, then Pareto methods if multiple defensible objectives exist                                                                                | Verified objective functions, meaningful design bounds, evidence-backed costs/performance; do not add algorithms for appearance                     |

## Completed in VEUS 2.1

The vehicle/component contract step now includes 13 representative records, version 2
resolved snapshots, a bounded persistent local library, compatibility/specifications and
an explicit retained-model adapter. The shared cutaway has electrical, mechanical and
thermal layers. Commercial catalogue sourcing and full Optimization execution remain
future work. See [design engineering](design-engineering.md) and [current checkpoint](../PROGRESS.md).

## Unresolved evidence and models

- Chemistry/SOH is not a voltage curve, resistance or power-limit model. Ageing needs
  temperature/SOC/current histories, calibrated evolution and validation data.
- Charging time needs usable energy, initial/final SOC, battery acceptance versus
  SOC/temperature, supply/vehicle limits and losses; no constant-peak shortcut.
- Energy cost requires modelled demand, charging efficiency and separate editable
  home/public AC/DC tariffs, with region/date/uncertainty. No universal EUR/kWh.
- Thermal behaviour needs heat-generation and heat-transfer parameters, temperature
  states, cooling controls and independent reference experiments.
- Sourced component selection requires verified voltage/current/power/duty/thermal
  compatibility and uncertainty; illustrative foundation defaults cannot stand in.
- Nürburgring Nordschleife work is research only: obtain usable licences, geometry,
  elevation and provenance first. Longitudinal demand along a prescribed profile
  must never be presented as a credible predictive lap-time model.
- True physical validation still needs sufficient independent inputs, conditions and
  measured references. The existing Phase 8 finding remains **INCONCLUSIVE**.

No advanced ageing, commercial pricing, charging-curve simulation, track dynamics
or multi-objective optimizer is implemented in foundation. Review this milestone
before advancing to a new engineering phase.

Milestones 2 and 3 now have coupled experiment/profile execution, frozen exports,
source/coverage policies and verification evidence. See [Simulation Lab](simulation-lab.md)
and [profiles/routes](profiles-routes.md). The 2.5 checkpoint is retained as historical evidence.

2.3.3 Insights,2.4 controlled studies and2.5 measurement migration now have sequential
acceptance checkpoints. [Analysis contracts](engineering-analysis.md),
[measurement parity and limits](measurement-migration.md), [evidence](evidence-2.5/README.md).
Quantitative model/measurement residuals remain gated; no new physical validation.


2.6 checkpoints A→B→C are complete: optional mapped powertrain with exact legacy
compatibility, evidence-specific VED calibration readiness and deterministic illustrative
driving animation. See [equations](powertrain2.6.md), [validation/driving limits](validation-driving2.6.md)
and [verification/performance/captures](evidence-2.6/README.md).
Physical validation remains INCONCLUSIVE. The 2.6 implementation checkpoint is retained as historical evidence.


## VEUS 3.0 release candidate

A–D cover demonstrated UX/accessibility issues, snapshot consistency and async guards,
comparable performance/quality checks, then README/architecture/Windows/demo/release
preparation. No new physics model or major feature. Historical numerical/export contracts,
presets, source data and measurement safeguards remain. See [release readiness](../veus3/release-readiness.md)
and [evidence](../veus3/evidence/README.md). Root project licensing, clean Windows and
non-Chromium browser checks remain outstanding. No merge or release without explicit
authorization. Stop after 3.0 release preparation.


## Engineering refocus after 3.0 RC1

Four primary workspaces: Vehicle Architecture + configuration, Simulation Lab,
Measurements & Validation, optional EV Challenges. No new physics model or release.
One vehicle state, progressive controls, original-signal previews with retained consent,
and scenario-specific camera views. [Workflow and integrity boundaries](../refocus/workflow.md),
[evidence](../refocus/evidence/README.md). Stop after this refocus; no main merge or release.
