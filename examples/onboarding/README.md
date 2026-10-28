# Small labelled input templates

These examples are synthetic software-learning fixtures, not measured vehicles.
CSV bytes are UTF-8; numeric times are seconds; speed is km/h. Matching config JSON
contains explicit units, source classification and the exact CSV SHA-256.

A `basic-replay.csv/.json`: timestamp + speed only, an 8-row arithmetic example.
B `electrical-analysis.csv/.json`: adds voltage (V), signed current (A), SOC (%).
Polarity is deliberately unknown; the numbers do not establish discharge/regen.
Readiness checks make replay available and leave unsupported/evidence-dependent
analyses unavailable or conditional. Do not relabel these files as genuine data.

The UI provides CSV/config attachment downloads and manual mapping review.
The JSON files use the existing ReplayConfig format. They are not a generic
JSON telemetry format. Readiness can inspect time/V/I data even without speed,
but the recorded journey requires speed.

Example C reuses `examples/validation/synthetic-battery-train.csv/.json`, bounded
`battery-calibration.json`, and the distinct synthetic battery holdout pair.
It uses the existing Phase 8 Experiment format for current-input/voltage-reference
software verification/calibration, not ReplayConfig. Open Analyse → Model
experiments & calibration, choose synthetic-battery-train, and load the example.
The UI's example downloads include its reference/config/settings/holdout files.
No source files or criteria from the earlier phases are modified.

Genuine VED windows remain under datasets/ved with their upstream Apache-2.0
licence/provenance. See docs/user-onboarding.md and docs/data-readiness.md.
