# Phase 10 executed evidence

Implementation commit: `01b78c2` (clean tree during final Python, Node, browser and
CLI runs). The following commit adds this evidence directory only. Python 3.12.14,
Pydantic 2.14.1, Matplotlib 3.10.7; browser checks used headless system Chromium
through Playwright on Linux cloud. No new application dependency was introduced.

**This is recorded-data replay and descriptive analysis, not physical model
validation. Phase 8's INCONCLUSIVE findings and numerical failures are unchanged.**

## Measured data and actual results

Default example: University of Michigan VED, vehicle 10, trip 1561, the existing
111-row window over 72.1 s. Timestamp intervals range from 0.1 to 1.1 s (irregular,
median 0.9 s). This is a small selected window, not the full journey. Source,
licence, source rows and SHA-256 are preserved in the configuration and metadata.

| Quantity | Result | Meaning |
|---|---:|---|
| Speed-integrated distance | 493.157351 m | Derived from all valid speed intervals, not GPS |
| Maximum recorded speed | 53.0500 km/h | Observed sample maximum |
| Time-weighted average speed | 24.6237 km/h | Complete-window speed integral / duration |
| Maximum abs(V×I) | 25.54875 kW | Signed electrical magnitude; no discharge/regen assertion |
| Electrical used/received energy | Unavailable | Current polarity remains unverified |
| Regeneration-specific energy | Unavailable | Charging origin also lacks independent evidence |
| Default supported event | Standstill, 71.5–72.1 s | Measured speed <=0.1 m/s, duration >=0.5 s |

Actual source measurements: timestamp, speed, pack voltage, signed current, SOC
and outside air temperature. Derived quantities: speed integral, secant-difference
acceleration and signed V×I. No simulated speed or preset physics is substituted.
The approximately 10.78 m/s² peak differentiated estimate is sampling/noise
sensitive and is not presented as a validated accelerometer measurement.

[Standalone default HTML analysis](report.html) (download and open locally)
· [Default summary and provenance](summary.json)
· [Default event CSV](events.csv)
· [Exact canonical default config](configuration.json)

## Screenshots and thresholds

The browser screenshot demonstrates **0.2 m/s² acceleration threshold**, rather
than the default 2 m/s²; other thresholds remain at their defaults. This produces
seven threshold episodes on the same unmodified measured data. It does not imply
that all seven meet the default rule or that inferred acceleration is noise-free.
The cursor is at 35 s, while numeric readouts show the preceding actual 34.6 s
sample; the hover annotation can refer to the nearest different actual sample.
That distinction is intentional and labelled in the UI.

[Exact screenshot settings](screenshot-settings.json)
· [Screenshot analysis summary/fingerprint](screenshot-summary.json)

![VED replay on a laptop](replay-laptop.png)

[Mobile screenshot](replay-mobile.png)

The illustrated car is generic and the landscape fictional. Distance is derived
longitudinal travel, not a mapped GPS journey. No illustrative Drive vehicle
configuration is applied to the measured recording.

## Checks actually executed

- **161 Python tests pass**, including all 140 Phase 9 tests and 21 replay cases.
- **9 Node playback-clock tests pass**: elapsed clock, pause/resume, rate changes,
  clamped seeks/restart/end, irregular row lookup, partial speed integration,
  gap/null handling, stationary intervals and separate controller instances.
- Python coverage: **95.12% statements, 83.73% branches, 92.65% combined**. This
  is not JavaScript coverage or evidence of physical accuracy.
- The actual Replay browser regression passes with no page errors, including
  all five export types: summary JSON, events CSV, metadata/settings JSON,
  full-resolution JSON and standalone HTML.
- Browser interactions verify play/pause, 4× elapsed progression, jump/timeline
  state, graph click/actual-row hover, event navigation and end/restart behavior.
- An explicitly synthetic custom CSV exercises missing speed and a large timestamp
  gap in the browser. Missing readouts remain unavailable, unknown travel is
  excluded and its badge states SYNTHETIC. The default remains genuine VED data.
- Replay rate/seek/analysis/export commands do not change Drive WebSocket time,
  position or configuration. Drive resumes its independent session afterward.
- The original Drive browser regression also passes: all preset mappings,
  keyboard/pointer controls, priority/release, pause/reset, workspaces, calibration
  and holdout UI, disconnection, interpolation and responsive controls.
  Its navigation now selects the explicit Model experiments tab; original
  assertions are retained.
- Resolutions checked: 1920×1080, 1366×768, 820×1180 and 390×844; no horizontal
  overflow and visible playback controls. No source values are downsampled for
  analysis or plots.
- Standalone HTML's embedded plots render. CLI source/config/analysis hashes were
  independently recomputed and match saved artifacts. A regression covers
  browser conversion of integer-valued provenance floats without identity drift.
- Changed Python lint, JavaScript syntax, dependency consistency and whitespace
  checks pass. One existing Starlette/httpx deprecation warning remains.

[Coverage details](coverage-summary.json) · [Clock output](clock-tests.txt)
· [Replay browser output](replay-browser.json) · [Drive regression output](drive-browser.json)

The automated synthetic fixtures test numerical/software behavior and never serve
as measured vehicle evidence. Existing physics, ADAS algorithms, scenario formats,
acceptance criteria and Phase 8 calibration/evaluation evidence were preserved.

## Performance and limitations

The bundled recordings are only a few kilobytes. Imports are bounded at 2 MB /
5000 rows / one day; JSON requests at 3 MB. Binary-search row lookup and cached
full-resolution chart backgrounds avoid recalculating analysis on animation
frames. Scenery uses the existing lightweight Canvas/SVG renderer, with a 2× DPR
cap. Playback rendering stops when paused/hidden and is separate from physics.

Successful short cloud browser interactions demonstrate functionality, not a
Windows integrated-GPU FPS benchmark, prolonged heap soak or guaranteed real-time
playback. No replay FPS guarantee is made. Existing Drive's timing observation is
retained as a short headless measurement only.

Current polarity, channel synchronization, pack temperature and instrument
uncertainty are unknown. Propulsion/braking/grade inputs are absent. Prediction
comparison is disabled with a reason; the existing Phase 8 experiments remain
accessible separately. Received electrical energy is not automatically regenerative
energy, even for an imported recording with an asserted known current sign.
No new physics, ADAS scenarios, traffic, thermal/SOH model or physical-validation
claim is introduced.

## Reproduce

```bat
python -m pip install -r requirements-report.txt
python -m uvicorn veus.studio.main:app --port 8770
```

Open http://localhost:8770, then Analyse → Recorded EV replay.

```bat
python -m veus.replay examples/replay/ved-10-1561.json datasets/ved/ved-10-1561.csv --output reports/replay-1561-001
python -m pytest -q
node --test tests/browser/replay-controller.test.cjs
```

The Node browser scripts additionally need optional Playwright/Chromium. See the
[technical replay guide](../real-world-replay.md) for installation, explicit
rules, custom-import configuration, artifact hashes and environmental limits.
