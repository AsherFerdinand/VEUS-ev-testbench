# VEUS 2.0 foundation audit and decision record

Audit precedes implementation. The Phase 11 branch is `2caf8f4`; README portfolio
work is `bf53d6a`. Remote main `1c4560b` is its merge, with an identical source tree.
Baseline: main, preserving all completed work. Local `archive/veus-pre-2.0` points to
`bf53d6a`; original feature/docs refs and evidence remain. Develop only on
`feature/veus-2.0-engineering-workbench`; no stable release or main merge.

## Dependency and responsibility audit

| Module/files                                                                                  | Decision                                  | Reason and migration boundary                                                                                                                                                                                                                              |
| --------------------------------------------------------------------------------------------- | ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `model/`, `sim/dynamics.py`, `sim/solver.py`, `sim/session.py`                                | RETAIN                                    | SI dynamics, force limits, battery/SOC/regen and numerical solvers; existing contracts and verification remain applicable. No new physics in foundation.                                                                                                   |
| `testing/`, `scenarios/`, physics/energy/scenario tests                                       | RETAIN                                    | Deterministic offline experiments, reference solutions, failure criteria and portable reporting.                                                                                                                                                           |
| `validation/`                                                                                 | RETAIN                                    | Measured import, bounded calibration, sensitivity, physical-suitability gates. Phase 8 remains INCONCLUSIVE.                                                                                                                                               |
| `readiness/`, `replay/`, `investigation/`, `datasets/ved`, examples                           | RETAIN                                    | Genuine data, hashes/licences, gap-aware calculations and polarity gates. New shell links existing tools during migration.                                                                                                                                 |
| `control/`, `sensors/`, associated scenario/tests                                             | RETIRE from primary UX; RETAIN dependency | Session and offline runner import these. Deletion would break useful regression/verification. They remain in explicit migration tools, not new workspace navigation.                                                                                       |
| `studio/main.py` root routing                                                                 | REFACTOR                                  | New independent shell at `/`; previous application at `/engineering` and `/engineering/`. HTTP/WebSocket APIs remain stable.                                                                                                                               |
| `static/index.html`, `workspaces.js`, `dashboard.js`, `drive.js`, `scene.js`, vehicle sprites | RETIRE from default application           | Tightly coupled shared DOM, canvas/session state, imports and historical browser tests. Keep as an isolated migration entry point until engineering replacements are verified; do not load them in the new shell.                                          |
| `static/guidance*`, `replay*`, `recording-plots.js`, `investigation*`, `validation.js`        | REFACTOR later; RETAIN migration tools    | Working ingestion, evidence and export flows must remain accessible. Extract headless service/cursor interfaces before replacing DOM bindings.                                                                                                             |
| Legacy keyboard handlers, manual pedals, landscapes, ADAS controls                            | RETIRE from default application           | No UI or WebSocket simulation connection in new shell. Migration tools expose historical controls explicitly, with retirement notice.                                                                                                                      |
| Root `README.md`                                                                              | REFACTOR                                  | Explain foundation status and preserved Phase 11 capabilities separately; keep portfolio history and evidence.                                                                                                                                             |
| New workbench contracts/content/UI                                                            | ADD                                       | Typed versioned design envelope, sourced explanatory content, original schematic, accessible six-workspace UX; no invented simulation results.                                                                                                             |
| Third-party dependencies                                                                      | RETAIN                                    | NumPy is used in calibration, Matplotlib in reports, FastAPI/Pydantic in APIs; no demonstrated unused runtime package. Add none.                                                                                                                           |
| Deleted code/files                                                                            | REMOVE: none                              | No obsolete frontend file was proven isolated: the old DOM/scripts jointly support essential ingestion, calibration and regression. Safe removal in this phase is removal from the default page's loading graph, rather than breaking the migration route. |

No useful tests are deleted. Two HTML-route tests are migrated to assert the exact
previous contract at `/engineering` instead of `/`; new tests assert new root and
absence of legacy scripts. The four existing browser suites default to `/engineering` (their assertions are unchanged); use `VEUS_URL` to override the host/port.
This is an explicit route-contract change, not weakened engineering assertions.

## Architectural weaknesses and constraints

The old shell moves DOM nodes among workspaces; dashboard.js owns both controls and
render state. Replay and investigation share transport elements and global events.
There is no safe single-file deletion of the driving shell while reusing these UI
bindings. Backend RunConfig combines plant, controllers and timing. A new design
schema must not silently become RunConfig or imply new chemistry/thermal fidelity.

The mechanical model is longitudinal and forward-only with lumped traction,
constant efficiencies and explicit numerical assumptions. The energy battery uses
fixed OCV/resistance. There are no validated thermal, ageing, charging-curve, tyre
slip, lateral/track dynamics, pricing or component efficiency-map models. Generic
technology labels cannot identify electrical model parameters. Telemetry replay is
not physical validation; VED sign convention, gaps and unobserved conditions remain.

## Measured baseline

Baseline existing Python tests and Node clock tests are rerun; exact outputs and
source/dependency hashes are in `evidence/`. Environment size is measured as summed
file bytes, not installed wheel download size or a comparison with other software.
Startup/import/RSS snapshots describe one cloud Linux environment with a warm
filesystem; no laptop performance or statistical speedup claim is warranted.

## Implementation sequence

1. Record baseline/ref and audit. Define independent shell, content and configuration contracts.
2. Add EV Anatomy and Challenges, original SVG and accessible annotation/flow behaviour.
3. Add design schema validation and illustrative design interaction; label all
   simulation/optimization replacement actions unavailable. Link working migration tools.
4. Exercise new UI, import validation, deep links, themes, keyboard and responsive
   behaviour; rerun existing engineering/API/clock/browser regressions.
5. Capture six workspace concepts and light/dark evidence; compare measured footprint,
   document limitations, commit/push foundation for review. Stop before production simulation migration.

The [per-file disposition inventory](retirement-matrix.json) records every existing
tracked `veus/` source/asset from the baseline. No existing source or evidence file is
physically deleted. New additions are `veus/workbench/` and
`veus/studio/static/workbench/`; route-contract changes in two tests are documented
above, with every original engineering assertion retained on the migration route.
