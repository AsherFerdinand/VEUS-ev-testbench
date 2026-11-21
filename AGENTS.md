# VEUS development guide

## Mission and boundaries
- VEUS is an Electric Vehicle Engineering Workbench: Understand · Design · Simulate · Optimize.
- Continue on `feature/veus-2.0-engineering-workbench`. Do not merge main, rewrite history or publish a stable release unless explicitly requested.
- Preserve user edits. Start with `git status --short`, `docs/PROGRESS.md`, `docs/REPO_MAP.md`, and targeted symbol searches.
- `docs/veus2/roadmap.md` is the authoritative roadmap; do not repeat the foundation audit.
- Keep calculations in Python. Reuse `model/`, `sim/`, `testing/` and measurement readiness/import/report services.
- `veus/lab/` owns coupled experiments and bounded profile/route execution; preserve requested versus achieved demand and explicit source/grade coverage.
- Workbench Insights/studies reuse Lab runs; measurements delegate to retained investigation services. Preserve sequential evidence gates and unknown-polarity/model-comparison restrictions.
- `veus/workbench/` owns design/catalogue/compatibility/calculation/adapter contracts. Never infer efficiency or electrical parameters from technology labels.
- `static/workbench/` owns the five-workspace shell and shared original SVG. Use one active design state; load editor code on demand.
- Preserve `/engineering` and its assets until essential replacement workflows pass equivalence. Do not add manual-driving or ADAS features.

## Environment and commands
- Repository: `/workspace/VEUS-ev-testbench`; Python: `/workspace/.venvs/veus/bin/python`.
- Install only if needed: `python -m pip install -r requirements-dev.txt`.
- Launch: `python -m uvicorn veus.studio.main:app --port 8770`.
- Targeted checks first; full suite once integrated: `python -m pytest -q`.
- Clock checks: `node --test tests/browser/replay-controller.test.cjs`.
- Browser suites: `tests/browser/engineering-workflow.cjs`, `tests/browser/vehicle-classes.cjs`, `tests/browser/workbench.cjs`, `drive.cjs`, `replay.cjs`, `guidance.cjs`, `investigation.cjs`, `lab.cjs`.
- Optional browser tooling: set `PLAYWRIGHT_MODULE`, `CHROMIUM_PATH`, `VEUS_URL`, `VEUS_SCREENSHOTS`; legacy suites use `/engineering`.
- Git's managed proxy may require `git -c protocol.version=0 ...`; preserve proxy/CA/auth settings. Never extract tokens.

## Engineering integrity
- Strict versioned schemas; finite values, explicit SI units, assumptions and mass boundaries.
- Keep missing data null/unavailable. Separate structural validity, compatibility, warnings and insufficient evidence.
- Catalogue metadata must distinguish illustrative, specified, estimated and measured values. Never invent manufacturer specifications or access dates.
- Keep resolved parameters and catalogue version/IDs for reproducibility; labels do not determine performance.
- Verify equations with independent analytical cases, not duplicated implementation tests.
- An adapter must expose direct/derived/unsupported mappings and required acknowledgements; never silently substitute a default vehicle.
- No unsupported range, charging time, ageing, cost, lap-time or optimization claims.
- Preserve VED original files, provenance, gaps and unknown-current-polarity safeguards.
- Physical validation remains INCONCLUSIVE absent sufficient independent reference evidence.

## Efficiency and workflow
- No new runtime dependency, frontend framework, 3D engine or build system without demonstrated need.
- No background simulation, polling, WebSockets or continuous animation in static design workspaces.
- Bound storage/caches/imports and clean inactive subscriptions. Respect reduced motion and keyboard accessibility.
- Do not reread whole unchanged modules or repeatedly regenerate equivalent captures/reports.
- Use at most two narrowly scoped implementation agents when useful; define ownership/interfaces first. No nested delegation.
- Keep temporary captures, raw datasets and tools outside Git; retain only representative evidence.
- Measure comparable pre/post footprint, startup/RSS, idle and interaction metrics; disclose sampling limitations.
- Distinguish source-tree, frontend-transfer, installed-environment and Git-history sizes.
- Update the single `docs/PROGRESS.md` at meaningful checkpoints; keep summaries concise.

## Authoritative references
- Navigation: `docs/REPO_MAP.md`.
- Current status and next actions: `docs/PROGRESS.md`.
- Foundation decisions/migration: `docs/veus2/audit.md`, `architecture.md`.
- Design/calculation/adapter equations: `docs/veus2/design-engineering.md`.
- Model assumptions: `docs/engineering.md`; verification: `docs/validation.md`.
- Measured-data limits: `docs/data-readiness.md`, `docs/real-world-investigation.md`.
