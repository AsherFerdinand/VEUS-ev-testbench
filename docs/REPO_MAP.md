# Repository map

| Responsibility | Entry points | Verification / reference |
| --- | --- | --- |
| HTTP application / migration | `veus/studio/main.py`; `/`, `/engineering` | `test_workbench.py`, `test_drive.py`, `test_physics.py` |
| Workbench content / v1 contracts | `veus/workbench/api.py`, `schema.py`, `content.json` | `test_workbench.py`; `veus2/architecture.md` |
| v2 component/design engineering | `veus/workbench/catalogue.py`, `design.py`, `engineering.py`, `adapter.py`, `presets.py` | `test_design_engineering.py`, `test_vehicle_presets.py`; `veus2/design-engineering.md` |
| Main frontend / navigation | `veus/studio/static/workbench/index.html`, `app.js`, `workbench.css` | `tests/browser/workbench.cjs` |
| Shared original vehicle rendering | `static/workbench/schematic.js`, `vehicle.css`, `vehicle-appearance.js` | Workbench browser suite and representative screenshots |
| Design editor and bounded local library | `static/workbench/design-studio.js`; `tests/browser/vehicle-classes.cjs` | Workbench browser persistence/comparison/import tests |
| Coupled Simulation Lab | `veus/lab/{schema,kernel,runner,api,report}.py`; `static/workbench/lab.js/css`, lazy `lab-scene.js` | `test_lab_kernel.py`, `tests/browser/lab.cjs`; `veus2/simulation-lab.md` |
| Profiles / routes / engineering studies | `veus/lab/profiles.py`, `datasets/cycles/`, `examples/lab/`, `scripts/lab_studies.py` | `test_lab_profiles.py`; `veus2/profiles-routes.md` |
| Engineering Insights / controlled studies | `veus/workbench/insights.py`, `design_analysis.py`; lazy `engineering-insights.js`, `design-analysis.js` | `test_insights.py`, `test_controlled_analysis.py`; `veus2/engineering-analysis.md` |
| Modern Measurements / legacy parity | `veus/workbench/measurements.py`; lazy `measurements.js/css`; retained investigation/replay/readiness services | `test_measurement_migration.py`, `tests/browser/engineering-workflow.cjs`; `veus2/measurement-migration.md` |
| Longitudinal dynamics / battery | `veus/sim/dynamics.py`, `session.py`; `veus/model/` | `test_physics.py`, `test_energy.py`, `test_session.py`; `engineering.md` |
| Reproducible offline scenarios | `veus/testing/__main__.py`, `runner.py`, `schema.py`; `scenarios/` | `test_scenarios.py`, `test_validation.py`; `validation.md` |
| Measurement import / calibration | `veus/validation/` | `test_measurements.py`, `test_experiments.py`; `vehicle-validation.md` |
| Readiness / replay / investigation | `veus/readiness/`, `replay/`, `investigation/` | Corresponding Python tests and legacy browser suites |
| Genuine data and provenance | `datasets/ved/`, `examples/replay/` | Hash/provenance tests; `datasets/ved/README.md` |
| Retired primary UX, retained migration | `static/index.html`, old UI scripts/styles, `control/`, `sensors/` | Historical scenarios/browser suites; `veus2/audit.md` |

2.6 additions: `model/efficiency_map.py` supplies optional mapped losses;
`workbench/powertrain_comparison.py` compares identical designs/cycles;
`workbench/validation_readiness.py` audits evidence and exports readiness reports;
`static/workbench/driving-scene-state.mjs` owns pure visual reconstruction.
Focused tests: `test_powertrain_maps.py`, `test_powertrain_comparison.py`,
`test_validation_readiness_26.py`, `tests/browser/{advanced.cjs,driving-scene-state.test.mjs}`.
References: `veus2/powertrain2.6.md`, `veus2/validation-driving2.6.md`, `veus2/evidence-2.6/README.md`.

3.0 release preparation: `veus/__init__.py` / FastAPI application version3.0.0rc1;
`tests/browser/release.cjs` covers saved/draft guidance and async snapshot/export guards.
Current architecture: `veus2/architecture.md`; setup: `windows-installation.md`;
release review: `veus3/release-readiness.md`; evidence: `veus3/evidence/README.md`.
No model/schema/dependency version changes.

Read `PROGRESS.md` next. The roadmap is `veus2/roadmap.md`; do not create another.
Application changes must not overwrite historical evidence in phase-specific directories.
