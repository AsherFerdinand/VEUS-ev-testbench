# Phase 10 pre-implementation plan

Base: feature/veus-drive-experience, 140 passing Python tests. Preserve physics,
controllers, Phase 8 INCONCLUSIVE evidence and all original APIs/scenario formats.

Existing architecture: dashboard.js owns one live simulation WebSocket and history;
drive.js interpolates that telemetry and renders Canvas scenery. workspaces.js
moves original panels, with validation.js operating independently in Analyse.
Phase 8 load_csv already verifies hashes, units, timestamps, missing values and
gaps. VED trip 1561 contains 111 genuine rows over 72.1 s, with speed, pack V/I,
SOC and outside temperature in the source. Current polarity remains unverified.
The small checked-in subsets and Apache-2.0 provenance are sufficient; no download
or new synthetic measurement is needed.

1. Add a replay-only configuration/analysis package using the existing importer.
   Preserve measured channels; put V*I, differentiated acceleration and integrated
   known-segment displacement in separate derived channels. Retain raw VED current
   sign rather than silently inheriting Phase 8's inversion hypothesis.
2. Build deterministic full-resolution metrics and configurable threshold events,
   with missing/gap coverage, unavailable-energy explanations and provenance hashes.
3. Extract the existing Canvas scenery into a reusable renderer without changing
   simulation state. Replay uses a generic silhouette and explicitly fictional
   background, never a loaded physics preset or GPS path.
4. Implement a separately testable JS replay clock, binary-search irregular sample
   lookup, bounded visual interpolation, seek/rates/pause/end and gap handling.
   Numeric readouts use actual sample timestamps, not fabricated interpolated data.
5. Add compact Replay/Model experiments tabs in Analyse, synchronous plots/cursors,
   event navigation, advanced settings/import and JSON/CSV/HTML exports. Keep Drive
   state independent; leaving Analyse releases/pause replay, leaving Drive pauses
   simulation through the existing policy.
6. Test ingestion/derivations/events/exports in Python, clock math in Node, and actual
   replay plus original Drive/calibration flows in Chromium. Record screenshots,
   measured results and limitations, then push only the new feature branch.

Distance/energy are not integrated through gaps or missing endpoints. Unknown
travel is never filled with zero or described as total distance; a separate
known-segment displacement drives the illustration. No model validation claim
follows from playing back measurements.
