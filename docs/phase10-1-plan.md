# Phase 10.1 pre-implementation plan

Base: feature/real-world-ev-replay. Preserve 161 Python tests, 9 replay-clock tests,
all simulation/replay APIs and Phase 8 INCONCLUSIVE physical-validation evidence.

Current frontend: workspaces.js constructs navigation; dashboard.js owns the live
WebSocket; drive.js manages presets/inputs; replay.js owns independent Analyse tabs
and clock. The Drive garage currently opens automatically. Guidance must suppress
that modal while Welcome is active without preventing direct Drive use.

1. Add a nonmodal Welcome workspace, explicit workflow actions, persistent local
   preference with storage-failure fallback and direct-workspace URL support.
   Keep existing workspace navigation and advanced tools intact.
2. Share existing CSV structural parsing between inspection and load_csv rather
   than writing another parser. Extract replay window sanity checks for reuse.
   Inspection suggests aliases only; mapping/unit/source confirmation is explicit.
3. Add a typed central capability registry and readiness evaluator. Separate
   column recognition, mapped/validated observations, partial quality and asserted
   engineering assumptions. Unsupported motor efficiency/regen-specific totals
   stay UNAVAILABLE; complete Phase 8 configuration/evidence are required before
   any physical-validation input set can be classified AVAILABLE.
4. Build an Analyse readiness tab with bundled/uploaded input, manual corrections,
   concise capability cards, quality details and an explicit handoff to existing
   Replay or model experiments. Do not change old analysis requirements or infer
   propulsion/braking from speed.
5. Supply small labelled basic/electrical synthetic templates plus links/downloads
   for the existing Phase 8 experiment format. Improve README and workflow docs.
6. Test registry rules, mapping/units, missing/gaps/polarity and provenance; run
   full regressions and browser checks for onboarding, direct entry, readiness,
   Drive and Replay at laptop/mobile sizes. Save screenshots and push the feature
   branch only; no merge to main.

AVAILABLE means ready for the named software calculation under stated scope,
not physical validity, safety certification or authenticated measurement metadata.
