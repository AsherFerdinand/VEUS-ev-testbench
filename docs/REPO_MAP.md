# Repository map

| Responsibility | Entry points | Verification / reference |
| --- | --- | --- |
| HTTP application / migration | `veus/studio/main.py`; `/`, `/engineering` | `test_workbench.py`, `test_drive.py`, `test_physics.py` |
| Workbench content / v1 contracts | `veus/workbench/api.py`, `schema.py`, `content.json` | `test_workbench.py`; `veus2/architecture.md` |
| v2 component/design engineering | `veus/workbench/catalogue.py`, `design.py`, `engineering.py`, `adapter.py` | `test_design_engineering.py`; `veus2/design-engineering.md` |
| Main frontend / navigation | `veus/studio/static/workbench/index.html`, `app.js`, `workbench.css` | `tests/browser/workbench.cjs` |
| Shared original vehicle rendering | `static/workbench/schematic.js`, `vehicle.css` | Workbench browser suite and representative screenshots |
| Design editor and bounded local library | `static/workbench/design-studio.js` | Workbench browser persistence/comparison/import tests |
| Coupled Simulation Lab | `veus/lab/{schema,kernel,runner,api,report}.py`; `static/workbench/lab.js/css` | `test_lab_kernel.py`, `tests/browser/lab.cjs`; `veus2/simulation-lab.md` |
| Profiles / routes / engineering studies | `veus/lab/profiles.py`, `datasets/cycles/`, `examples/lab/`, `scripts/lab_studies.py` | `test_lab_profiles.py`; `veus2/profiles-routes.md` |
| Longitudinal dynamics / battery | `veus/sim/dynamics.py`, `session.py`; `veus/model/` | `test_physics.py`, `test_energy.py`, `test_session.py`; `engineering.md` |
| Reproducible offline scenarios | `veus/testing/__main__.py`, `runner.py`, `schema.py`; `scenarios/` | `test_scenarios.py`, `test_validation.py`; `validation.md` |
| Measurement import / calibration | `veus/validation/` | `test_measurements.py`, `test_experiments.py`; `vehicle-validation.md` |
| Readiness / replay / investigation | `veus/readiness/`, `replay/`, `investigation/` | Corresponding Python tests and legacy browser suites |
| Genuine data and provenance | `datasets/ved/`, `examples/replay/` | Hash/provenance tests; `datasets/ved/README.md` |
| Retired primary UX, retained migration | `static/index.html`, old UI scripts/styles, `control/`, `sensors/` | Historical scenarios/browser suites; `veus2/audit.md` |

Read `PROGRESS.md` next. The roadmap is `veus2/roadmap.md`; do not create another.
Application changes must not overwrite historical evidence in phase-specific directories.
