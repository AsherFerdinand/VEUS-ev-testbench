# Phase 10.1 executed evidence

Implementation: `852fd9b` (clean tree for final Python/browser checks). The
subsequent evidence commit adds this directory only. This phase changes guidance,
CSV inspection reuse and software readiness; no physics/controller equations,
scenario formats, calibration requirements or Phase 8 conclusions are replaced.

## Implemented experience

- Nonmodal **VEUS — Explore. Analyse. Validate.** Welcome with all three workflows,
  requirements, primary/secondary actions and normal navigation always available.
- A local one-bit startup preference, explicit return navigation, direct workspace
  URLs and graceful storage-blocked behavior. The garage does not cover Welcome.
- Collapsible workspace explanations, with verification distinct from physical
  validation and only supported vehicle customization listed.
- Inspect → propose → manually correct → confirm → validate → assess → proceed
  workflow for bundled or uploaded CSVs. Units are not inferred for uploads.
- Central typed capability registry used by API assessment and UI requirements.
  Column presence, mapped quality and uploader evidence are treated separately.
- Quality/provenance details, additional-data explanations and readiness JSON export.
- Labelled synthetic A/B downloads and unchanged Phase 8 reference/config/settings/
  holdout example C. Beginner README sections preserve earlier technical evidence.

## Example assessments actually executed

| Capability | Genuine VED 1561 | Synthetic A: time/speed | Synthetic B: electrical |
|---|---|---|---|
| Recorded replay | AVAILABLE | AVAILABLE | AVAILABLE |
| Speed/acceleration | AVAILABLE | AVAILABLE | AVAILABLE |
| Voltage inspection | AVAILABLE | UNAVAILABLE | AVAILABLE |
| Signed current inspection | AVAILABLE | UNAVAILABLE | AVAILABLE |
| Signed V×I | AVAILABLE | UNAVAILABLE | AVAILABLE |
| Electrical energy | CONDITIONAL | UNAVAILABLE | CONDITIONAL |
| Regen-specific energy | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE |
| Motor efficiency | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE |
| Longitudinal physical-validation inputs | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE |

VED retains 111 genuine rows over 72.1 s and its existing source/licence/hash.
Energy is conditional because polarity and measurement/synchronization evidence
remain unresolved. Torque/brake-force/grade inputs are missing, so replay does
not unlock physical validation. Synthetic A/B keep their explicit synthetic origin;
they are software demonstrations, not experimental vehicle data.

[Actual browser VED assessment](ved-readiness.json)
· [Synthetic A assessment](basic-replay-readiness.json)
· [Synthetic B assessment](electrical-analysis-readiness.json)

Additional policy tests show that time/V/I data without speed supports electrical
inspection but not replay; gaps/missing data change readiness; all-missing fields
and disjoint samples do not count as valid. Unsupported motor efficiency stays
unavailable even with related columns. A synthetic policy fixture emulates a
provider's complete evidence/config assertions only to test the guard. Its
AVAILABLE input-readiness result is explicitly not measured validation evidence.
A missing reference output in an optional experiment disables that capability
without suppressing other readiness checks.

## Screenshots

Actual Chromium screenshots, not mockups. Mapping controls collapse after a
successful check; quality and detailed engineering requirements are progressive
disclosures rather than default parameter tables.

![Welcome and workflows](welcome-laptop.png)

![Genuine VED readiness](readiness-laptop.png)

[Mobile Welcome](welcome-mobile.png) · [Mobile readiness](readiness-mobile.png)

## Tests and checks

- **177 Python tests pass**, preserving all 161 Phase 10 tests and adding 16
  readiness cases, including parametrized rejection checks.
- **9 playback-clock tests pass**, unchanged from Phase 10.
- Python coverage: **95.21% statements, 83.93% branches, 92.76% combined**.
  This measures Python software, not browser coverage or physical accuracy.
- Actual guidance browser regression passes: first/returning visitors, primary
  workflow actions, input requirements, local preference reset, direct Drive
  entry without onboarding, blocked storage fallback, genuine/synthetic origin,
  explicit confirmation, manual units/column mapping, duplicate timestamp
  rejection, readiness-to-replay handoff and JSON download.
- Guidance checked at 1366×768 and 390×844 with no horizontal overflow or page errors.
- Original Drive and Replay browser regressions both pass, including keyboard/
  pointer safety, preset mappings, calibration/holdout, disconnection, replay
  clock/seek/events/exports and separate simulation/replay state. They now enter
  through the documented direct Drive URL; their original functional assertions
  are retained. Existing four-resolution checks remain in those scripts.
- Shared CSV structural parsing and shared replay sanity/window checks pass the
  existing ingestion/replay regressions. No duplicate parser repairs raw data.
- Changed Python lint, JavaScript syntax, dependency consistency and whitespace
  checks pass. The existing Starlette/httpx deprecation warning remains.

[Coverage](coverage-summary.json) · [Clock output](clock-tests.txt)
· [Guidance browser](guidance-browser.json) · [Drive browser](drive-browser.json)
· [Replay browser](replay-browser.json)

## Limitations and interpretation

AVAILABLE is readiness for a named existing software operation under its declared
scope, not proof of sensor accuracy, synchronization, provenance truth, physical
model validity or automotive safety. Evidence checkboxes are uploader assertions
requiring notes; the app cannot authenticate them. Complete physical-input
readiness also requires a compatible explicit Phase 8 dynamics Experiment and
its actual independent reference outputs; no comparison is run by readiness.

Unknown polarity stays unknown. No pedal-to-torque/force conversion, measured
motor-efficiency estimator or regeneration-specific energy total is added.
Conditional explanations are retained on replay handoff without changing legacy
Replay's explicitly assumption-based calculations. VED physical validation stays
INCONCLUSIVE, with earlier numerical failures preserved.

Storage-blocked browsers may see Welcome again after reload, but navigation stays
available. Preference data is one local flag, not an account or uploaded dataset.
These short headless cloud checks do not establish Windows laptop FPS or extended
memory behavior. Interactive import limits and existing numerical/model limits
remain documented in the workflow/readiness guides.

## Run locally

From the repository folder in Anaconda Prompt:

```bat
python -m pip install -r requirements-report.txt
python -m uvicorn veus.studio.main:app --port 8770
```

Open http://localhost:8770, or http://localhost:8770/?workspace=drive for direct entry.

```bat
python -m pytest -q
node --test tests/browser/replay-controller.test.cjs
```

Optional browser scripts require Playwright/Chromium; no Node or new runtime
package is needed to use VEUS itself. See [user onboarding](../user-onboarding.md)
and [readiness definitions](../data-readiness.md) for exact workflows, templates,
contracts and local preference behavior.
