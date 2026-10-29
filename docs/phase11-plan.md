# Phase 11 plan before implementation

Base: feature/user-onboarding-data-readiness; historical baseline 177 Python and
9 playback-clock tests. Existing ReplayConfig/load_csv/analyse supply SI values,
valid interval masks, events and descriptive metrics; assess supplies the sole
readiness policy. Replay owns a separate browser clock; no physics changes needed.

1. Inspect the pinned VED archive already cached outside Git, its licence and
   extraction manifest. Seek full multi-minute single-vehicle/trip recordings,
   preserving source row values, with no concatenation or downsampling. Keep all
   old fixtures and 5000-row/2 MB limits. Document selection and reproducibility.
2. Add a shared recording catalogue backed by existing config/import metadata.
3. Build readiness-gated investigation over existing replay results: transparent
   event evidence, interval statistics, measured/derived/inferred qualifications,
   complete-window comparison metrics and strict readiness-gated energy display.
4. Add Investigate/Compare/Reports tabs alongside existing Analyse tools. Reuse
   the replay cursor/plots and event detector rather than duplicating them.
5. Export deterministic JSON, measured/derived CSV and portable case-study HTML,
   including source/config hashes, thresholds, selected events and software version.
6. Execute genuine-data case studies; test quality/polarity/comparison/report
   consistency and all existing Python/clock/browser regressions. Document real
   findings and limitations, then push only the requested feature branch.

No new physics, ADAS, traffic or causal/ML inference. Phase 8 physical validation
remains INCONCLUSIVE. A longer file may retain gaps; unknown travel stays unknown.
