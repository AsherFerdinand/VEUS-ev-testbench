# Current checkpoint

- Milestone: **VEUS 2.3.1 cockpit redesign complete**, feature branch only; no main merge or stable release.
- Branch: `feature/veus-2.0-engineering-workbench`; baseline `e6522a3` (2.3).
- UI: five scenario cards, original lightweight VEUS Arrow SVG, achieved-distance road motion, configured-gradient mountains, explicitly illustrative overtaking reference and red-at-zero braking-light event.
- Instrumentation: fitted speed arc/digital speed, SOC-fill battery with signed power/constraint colours and replay-driven energy flow; exactly three synchronized cached telemetry plots; Play/Pause, Stop and seek.
- Configuration: existing vehicle/conditions/acknowledgements in collapsible settings; separate Profile/Route mode preserves sources, CSV imports, coverage safeguards and frozen exports. No default/physics-contract changes.
- Integrity: all five golden experiment hashes match 2.3 exactly. `veus/lab/`, physics/model modules, dependency manifests, source datasets and numerical results are unchanged.
- Verification: 267 Python tests and 9 clock tests pass. Browser regression results, comparable limited measurements and exactly three captures: `veus2/evidence-2.3.1/README.md`.
- Workflow: one implementation agent (coordinator only), focused UI checks then one full Python checkpoint; no external research or new dependencies. Obsolete signal/rate controls, cutaway rendering and sidebar skin replaced.
- Limits: original fictional body/scenery do not add lateral, overtaking-safety or traffic-light-control physics. Constant OCV/efficiencies, no auxiliaries/thermal/ageing/phase-current maps; Euler-position O(dt) and existing source limitations persist. Physical validation remains **INCONCLUSIVE**.
- Stop after verified/pushed 2.3.1. Do not begin 2.4 without a new request.
