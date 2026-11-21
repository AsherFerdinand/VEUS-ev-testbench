# VEUS 3.0.0rc1 release readiness

**Candidate prepared for engineering review; not approved for a public/stable release.**
Feature branch: `feature/veus-2.0-engineering-workbench`, base `b3d9832`.
No merge to main, release publication, repository-visibility change or branch-protection
change is part of this milestone. Application version is 3.0.0rc1; historical schema,
model and export versions are preserved.

| Area | Evidence / status | Remaining action |
| --- | --- | --- |
| Regression | 314 Python, 9 clock, 8 scene tests and 10 browser suites pass; [verification](evidence/verification.json) | Re-run on the intended release platform after any further code change. |
| UX/accessibility | Five workspaces × light/dark × 1440/820/390 px; keyboard tabs/return links, draft state, native labels/focus, reduced motion and responsive baseline suites | Independent assistive-technology review; no accessibility certification claimed. |
| Engineering integration | Complete saved snapshot reaches Insights/Lab; explicit validation model selector; delayed evaluation cannot overwrite a newer edit; failed retry clears stale export | No new physical validation. |
| API/export compatibility | Existing routes/contracts, model hashes, exact historical numerical/JSON/CSV/HTML and measurement parity checks pass | Application OpenAPI version intentionally changes to 3.0.0rc1. |
| Saved designs | Existing bounded v2 library/import/persistence tests pass; explicit draft/saved labels; v1 manual reconstruction policy retained | Export browser-local designs before moving origin/PC. |
| Determinism | Legacy/map calculations and direct-seek/clock tests preserved | Floating-point portability outside tested Python/platform not certified bit-for-bit. |
| Measurement safeguards | Source hashes, original gaps/units/mappings and polarity gates preserved; null residuals/fits for unmatched VED data | Independently verified mass, tyres/aero/drivetrain, V/I polarity, synchronization and uncertainty. |
| Dependencies | No dependency files changed; installed environment `pip check` passes | Dependency/security and Windows-wheel availability review before distribution; pip check is not a vulnerability audit. |
| Installation | Actual package path and dependency files documented; Linux execution works | **Clean Windows installation remains unverified.** Follow [Windows checklist](../windows-installation.md) on a real PC. No Windows/WSL emulation claim. |
| Browser support | Actual headless Chromium workflows pass | **Firefox, Safari and Edge not tested.** Mobile widths are Chromium emulation, not physical-device tests. |
| Performance | One comparable before/after run using existing tools; no material runtime/memory regression; static idle callbacks/requests absent | Shared-cloud sampling is not a laptop guarantee; [measurements](evidence/README.md). |
| Documentation/demo | README, architecture, Windows instructions and six genuine views; one new screenshot, five reused | Review final wording/screenshots against target audience. |
| Licence/third-party material | Upstream dataset licences/provenance retained; no project licence invented | **Root project licence absent: owner decision required before an open-source release.** See below. |

## Licensing and third-party materials

No root `LICENSE`, `COPYING` or equivalent project licence was found in the tracked tree.
Do not infer that GitHub availability or upstream data licences license the VEUS application.
This milestone does not choose a licence, change ownership or grant new rights.

- VED projections retain [upstream Apache-2.0 text](../../datasets/ved/UPSTREAM-LICENSE.txt),
  [attribution/modification notes](../../datasets/ved/README.md) and source hashes/provenance.
- FASTSim-derived cycles retain [licence](../../datasets/cycles/UPSTREAM-LICENSE.txt) and
  [notice](../../datasets/cycles/UPSTREAM-NOTICE.txt). Their usage does not grant a licence
  to the rest of VEUS.
- The modern workbench reuses its existing original SVG vehicle geometry and local
  system-font stack. No new external image, font, rendering library or stock illustration
  was introduced. Demonstration PNGs are actual application captures.
- Runtime/test/plotting packages remain third-party dependencies with their own licences.
  A distribution-wide legal/security audit has not been performed; review obligations
  for the intended packaging/distribution rather than treating `pip check` as legal review.

## Engineering limitations

Illustrative presets/maps and scene choreography are not independently validated vehicle
data. Models retain fixed OCV/resistance, constant inverter efficiency and simplified
longitudinal integration, without thermal/ageing/auxiliary/charging/lateral dynamics.
Cycle-equivalent range and user-tariff costs have explicit assumptions. No real-data
calibration, certified range, production ADAS, collision-avoidance or safety claim.

## Review before any authorized release

1. Review the feature branch and its test/evidence files; preserve the numerical/export contracts.
2. Complete a clean Windows install/start/test run and test intended browsers.
3. Resolve the project licence and review third-party distribution obligations.
4. Confirm installation instructions, source provenance and limitation language.
5. Obtain explicit repository-owner authorization for any merge or GitHub release.

Physical validation remains **INCONCLUSIVE** regardless of release-preparation status.


## Subsequent engineering refocus

The current UI has four workspaces and a unified Architecture/configuration surface;
old routes remain compatible. [Current checks and captures](../refocus/evidence/README.md)
supersede the five-workspace UX observations above. Numerical/report contracts and
licensing/Windows/non-Chromium/physical-validation limitations remain unchanged.
No main merge or GitHub release is authorized by this refocus.
