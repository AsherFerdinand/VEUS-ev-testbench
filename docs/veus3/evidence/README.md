# VEUS 3.0.0rc1 integration evidence

Base: `b3d98321391d798884711411410b503cf45cc384`; feature branch only.
Checkpoints A–D completed sequentially. No physics/model/dependency/schema change;
application release metadata is intentionally updated separately.

## Focused checkpoints and final regression

- A: [30 real browser layouts](audit-A.json): five workspaces × light/dark ×
  1440/820/390 px, no page errors or horizontal overflow. [Keyboard/draft/return checks](release-A.json).
- B: [Saved snapshot integration and explicit validation selection](release-B.json).
  The delayed-evaluation bug was demonstrated [before](race-before.json) and fixed
  [after](race-after.json). Older responses cannot overwrite new input. Rejected
  assessment retries disable old exports; navigation during a request cleans up.
  Five focused existing measurement-parity/comparison Python tests also passed.
- C: Existing performance tools ran once before/after; all pending static application
  timer/frame counts and background requests/WebSockets were zero. `pip check` passed;
  no dependency or precision change. No unsupported performance optimization was added.
- D: README/current architecture/Windows instructions/release checklist and screenshot
  links reviewed. One new Design Studio capture; the other five representative views
  reuse previously verified evidence. Windows/browser/licence gaps are disclosed.
- [Final verification](verification.json): **314 Python**, **9 clock + 8 scene**, and
  **10 browser suites** (9 baseline + release integration) passed. Full Python/final
  applicable browser suites run once after A–D; focused runs are separate. No assertions
  weakened. An existing Starlette/httpx testclient deprecation warning remains.

## Comparable performance

Same Python environment, Linux host, existing `scripts/measure_workbench.py --v2 --insights`
and `tests/browser/performance.cjs`; first of four samples excluded. Browser/server runs
use their own metrics; initial bytes are decoded subresource bodies, not compressed
transfer. Startup RSS is server process memory; browser task fraction is not total CPU.

| Metric (median) | Before | After |
| --- | ---: | ---: |
| Initial subresource bodies, bytes | 98,289 | 100,319 |
| Startup server RSS, KiB | 44,388 | 44,392 |
| Post-evaluation RSS, KiB | 49,936 | 49,944 |
| Startup, s | 0.446 | 0.455 |
| Complete-design evaluation, ms | 1.627 | 1.589 |
| Legacy full urban + acceleration Insights, ms | 118.7 | 116.2 |
| Initial browser load including network-idle wait, ms | 688 | 643 |
| Browser idle main-thread task fraction, % | 0.096 | 0.092 |
| Server idle CPU, 1 s sample, % | 0 | 0 |

[Server before](performance-before.json) / [after](performance-after.json);
[browser before](browser-before.json) / [after](browser-after.json).
The roughly 2 KB initial increment is contextual guidance and shared UX styles.
Differences in tiny/cloud samples are not speedup claims. Zero sampled CPU does not
prove that a real process consumes no CPU. No laptop or clean-Windows performance claim.

`audit-A.json` additionally records individual page-readiness times for five workspaces;
these are single, sequential fresh-navigation observations after A, not an isolated
before/after benchmark. They include differing lazy-load/network work and should not
be compared as relative workspace efficiency. Final integration evidence records
representative endpoint observations without extra benchmark repetitions.

## Run the checks

```bash
python -m pytest -q
node --test tests/browser/replay-controller.test.cjs tests/browser/driving-scene-state.test.mjs
```

Set `PLAYWRIGHT_MODULE`, `CHROMIUM_PATH`, `VEUS_URL` and `VEUS_CAPTURE=0` as appropriate
for optional browser tools. Modern suites: `workbench`, `vehicle-classes`, `lab`,
`engineering-workflow`, `advanced`, `release`. Legacy `drive`, `replay`, `guidance`,
`investigation` use VEUS_URL ending `/engineering`. Run them serially; timing assumptions
in retained driving tests make heavy concurrent CPU load unhelpful.

No new browser/runtime dependency was added. Tool versions/host scope and verification
hashes are recorded in verification.json. [Release limitations](../release-readiness.md).

## Actual application views

- [New 3.0 RC1 Design Studio](design-studio.png): S1/R1/X1 selector, saved-state label,
  contextual simulation link and original cutaway. Captured from Chromium, 1440×1100.
- [EV Anatomy](../../veus2/evidence-2.1/complete-cutaway-light.png),
  [Engineering Insights](../../veus2/evidence-2.5/engineering-insights.png),
  [Simulation Lab](../../veus2/evidence-2.6/overtaking-lane-change.png),
  [Design Comparison](../../veus2/evidence-2.5/design-comparison.png),
  [Measurements investigation](../../veus2/evidence-2.5/measurements-investigation.png).
  Reused genuine captures; older version labels are retained, not relabelled as new output.

Physical validation is **INCONCLUSIVE**. Release preparation does not establish legal
licensing, cross-platform installation or real-vehicle accuracy.
