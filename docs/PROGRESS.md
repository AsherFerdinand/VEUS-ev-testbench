# Current checkpoint

- Milestone: **VEUS 2.3 complete**, development branch only; no stable release or main merge.
- Branch: `feature/veus-2.0-engineering-workbench`; implementation `301e916` (subsequent checkpoint metadata only), preceding checkpoint `f49fe7c`.
- Delivered: one coupled retained-model kernel; constant-speed, acceleration, braking/regen, gradient and coast experiments; fixed selected gearing/vehicle snapshot; separate requested demand and achieved motion; explicit continuous/acknowledged-peak policy and electrical/traction limits.
- Profiles/routes: four illustrative profiles, pinned FASTSim-distributed UDDS/HWFET, bounded explicit-unit CSV imports, missing-data/coverage/grade policy and synthetic route telemetry. No verified Nordschleife data or lap-time claim.
- UI: lazy functional Lab, active saved design, one cached plot/shared replay clock, route/cutaway view, immutable frozen result identity, actual JSON/CSV/HTML exports. Replay never reruns the solver. Obsolete Lab prototype removed.
- Checkpoint A: 54 coupled/legacy tests passed **before** implementing profiles/routes. Checkpoint B and final regression evidence: `veus2/evidence-2.3/README.md`.
- Architecture: `veus/lab/` owns contracts/kernel/runs/profiles/reports/API/CLI. Shared changes are optional battery-envelope arguments and extracted road-force decomposition; existing defaults/controllers and `/engineering` remain compatible.
- Reproduction: `python scripts/lab_studies.py --output /tmp/veus-lab-studies`; exact snapshots/summaries recorded. Cd .28→.22 gives 15.606→13.647 kWh/100km at 100 km/h; illustrative urban/motorway 11.730/16.281 kWh/100km. These are model results, not measured efficiency.
- Dependencies unchanged; repeated pre/post startup/RSS/frontend/idle and Lab execution/playback measurements are recorded without laptop guarantees.
- Agent use: two scoped implementation agents (coupled kernel and Lab UI); coordinator handled ingestion, sources, integration, studies and final checks; no nested delegation.
- Limitations: constant OCV/efficiencies, no auxiliaries/thermal/ageing/phase-current maps, forward-only longitudinal motion, Euler position versus mean-work displacement O(dt), unverified peak duty. FASTSim cycles not independently checked against regulatory originals; route fixture is synthetic. Physical validation remains **INCONCLUSIVE**.
- Stop here after 2.3. Full Optimization, battery SOH, charging curves and lateral/track prediction remain future work.
