# Real-world EV investigation

Phase 11 adds descriptive Investigate, Compare and Reports views to Analyse.
Drive, the existing Replay interface, model experiments and Validate remain available.
No vehicle physics or ADAS algorithms change. Phase 8 physical validation remains
**INCONCLUSIVE**. Recorded telemetry is evidence about recorded samples, not proof
that the simulator represents the measured vehicle.

## Start an investigation

1. In Analyse → Investigate select a recording and **Load into Replay**. Open the
   recording library for source, licence, signal, coverage and limitation details.
   Alternatively import CSV and ReplayConfig JSON in Recorded EV replay, or use
   Data Readiness to confirm mappings and proceed to replay.
2. Review timestamp/speed units, source identity and electrical mappings. Confirm
   the checkbox and select **Check readiness & investigate**. This calls the existing
   readiness assessor; it does not authenticate an uploader's assertions.
3. Play or seek with the shared Replay transport. Speed and power plots share the
   same recorded-time cursor; expand additional signals for acceleration, voltage,
   current and SOC. Only available channels are drawn. The optional illustration
   uses the same cursor and is not a measured GPS trajectory.
4. Select an event to seek/highlight its interval. Inspect the detector rule,
   supporting sample indices, extrema, endpoint differences and limitations.
5. Compare the current recording with a catalogue entry or use **Import second
   recording** to select a CSV and compatible ReplayConfig JSON. Navigate the two
   plots independently. Optional normalized time means elapsed time divided by
   each recording's own duration; separate trips do not share a real-world origin.
6. In Reports enter a title and export HTML, JSON or CSV. Recording changes invalidate
   the previous investigation and require confirmation again.

Reports use the frozen source bytes/configurations, selected event indices and
settings. Exporting after changing title or comparison axis regenerates the case
and its hash. Catalogue entries are local checked-in data, not background downloads.

## Genuine recording catalogue

University of Michigan [VED](https://github.com/gsoh/VED), Apache-2.0, pinned
commit `6baa4963782d515a67d32a5490bd5d11f5d9bf0d`. See
[provenance](../datasets/ved/full-recordings-provenance.json) and the
[dataset README](../datasets/ved/README.md). Vehicle 10 is identified upstream as a
2013 Nissan Leaf; the dashboard illustration remains generic.

| ID               | Rows | Duration s | Gaps >2 s | Valid speed interval coverage | Known-segment distance m |
| ---------------- | ---: | ---------: | --------: | ----------------------------: | -----------------------: |
| ved-10-1561-full |  534 |      460.4 |        23 |                      74.3918% |                2371.5911 |
| ved-10-1567-full |  367 |      370.3 |        34 |                      59.7353% |                1408.7005 |

Both provide time, speed, battery voltage, raw signed current, SOC and outside air
temperature. Outside air temperature is not battery temperature. These are complete
single-vehicle/trip groups **in the inspected first weekly archive member**, not a
claim that the dataset captures the entire physical journey. Every group row is
retained, with original numeric strings, timestamps and gaps. The two original short
fixtures (111 rows/72.1 s and 74 rows/50.4 s) remain unchanged.

Selection inspected every vehicle-10 trip in `VED_171101_week.csv`, then used the
first two chronological multi-minute groups; no event/residual-based filtering,
trip concatenation, truncation or downsampling. The 82.7 MB source archive stays
outside Git; only approximately 42 KB of additional projections are committed.
The optional extraction helper verifies the pinned archive hash, exact source line
ranges, vehicle/trip keys, row count and output hashes before writing:

```bash
# Optional acquisition tool; not required for the application or checked-in examples.
# Requires libarchive-c and native libarchive.
python scripts/extract_ved_recordings.py /path/to/VED_DynamicData_Part1.7z --output NEW_DIRECTORY
```

Archive SHA256:
`44d53754fd39e196171ec09f123604375d0248d5c06a97d6695ef0e22a948c61`.
The manifest records source lines 70952–71485 and 211402–211768, original time
ranges, DayNum values, row/byte counts and subset hashes. The extractor was actually
run against the cached archive and reproduced both checked-in projections byte for byte.

## Calculations and evidence

Existing `veus.replay` supplies SI conversion, interval validity, numerical
calculations and event detection. `veus.readiness` remains the sole capability policy.
Investigation adds evidence presentation and stricter energy gating, not new physics.

- Measured channels retain source meaning after configured unit conversion:
  km/h ÷3.6 → m/s, milliseconds ÷1000 → s, SOC percent ÷100 → fraction.
- Derived acceleration uses the existing finite-difference implementation within
  valid contiguous segments. Uneven sampling and speed noise can produce large
  peaks; these are not accelerometer observations or independently verified dynamics.
- Known-segment distance is trapezoidal integration of speed over valid intervals:
  `sum((v[i]+v[i+1])/2 * dt)`, in metres. Coverage is valid interval duration divided
  by recording duration. Gaps over the configured 2 s break integration and plots.
  Whole-window distance and average speed remain unavailable for these gappy files.
- Signed electrical power is `V*I` in watts. Current polarity is **unknown** in VED;
  sign is preserved, not interpreted as charge/discharge. Power magnitude is `abs(V*I)`.
- Discharge/received-energy integration is exposed only when existing readiness
  `energy_consumption` is **AVAILABLE**. Known polarity alone is insufficient.
  Conditional/unavailable readiness masks energy summaries, derived channels and
  CSV columns in investigation. Existing Replay's legacy API contract is preserved.
- SOC endpoint change is `(last-first)*100` percentage points when both original
  endpoints exist. It establishes neither battery health nor efficiency.
- Standstill duration sums qualifying detected episodes, not every unobserved second.
  High-power count uses existing threshold episodes; missing power is unavailable,
  not a fabricated zero. Both metrics retain coverage qualifications.

Existing default event rules: acceleration ≥2 m/s², deceleration ≤−2.5 m/s²,
standstill speed ≤0.1 m/s, electrical magnitude ≥50 kW, minimum episode 0.5 s.
Missing measurements and timestamp gaps are also inspectable. Configuration stores
exact thresholds. Investigation suppresses possible-regeneration interpretations
when energy readiness is unresolved; no second detector is introduced.

Default report selection chooses the first event of each available type in order
acceleration, deceleration, high electrical magnitude, standstill, up to three;
if none occur, it uses the first three quality events. Interactive selection can
choose any eligible event. This selection changes presentation, not detection.
Each insight contains source/elapsed interval, detector rule, actual supporting
indices, valid/missing counts, extrema and endpoint values. Gap events explicitly
leave unobserved evolution unknown. Increased speed together with increased power
magnitude is described only if both sampled endpoint differences support it. This
association cannot identify gradient, auxiliary loads, motor efficiency or cause.

Every comparison metric includes units, measured/derived classification, capability
status, definition and an unavailability reason. Missing operands produce no numeric
difference. Source/vehicle/run overlap is flagged: full trip 1561 overlaps its original
short window and is not independent evidence. No driving-efficiency ranking is made.

## Reproducible case study

```bash
python -m pip install -r requirements-report.txt
python -m veus.investigation --first ved-10-1561-full --second ved-10-1567-full --output NEW_CASE_DIRECTORY
```

See [the executed case and screenshots](phase11-evidence/README.md). The CLI writes
portable `report.html`, canonical `case-study.json`, `measurements-derived.csv`,
unchanged `original-N.csv` and `configuration-N.json`; nonempty output directories
are rejected. JSON records source/configuration hashes, existing readiness and
analysis fingerprints, selected events, thresholds, comparison settings, Python/
analysis library metadata and `veus-investigation-v1`. SHA256 covers canonical case
JSON before adding its own hash. Reproduction requires matching software/settings;
HTML plot rendering may vary by matplotlib/font version. Report plots use each
recording's elapsed seconds even when the comparison display preference is normalized.

CSV exports exactly one row per actual original sample, SI-converted measured
columns separate from derived columns, with source identity/hash, original source
timestamp and sample index. Missing values are blank. Plot interpolation never adds
exported measurement rows; unchanged originals are available in the CLI bundle.

## Architecture, bounds and limitations

`veus.investigation.catalogue` derives metadata through existing imports;
`analysis` wraps readiness/replay; `report` reuses engineering HTML/plot helpers;
`api` supplies `/api/investigation/catalogue`, `/recordings/{id}` and `/case-study`.
The legacy `/api/replay/datasets` still returns its two established entries; the
new shared catalogue exposes all four to the UI. HTML requests share the existing
plot lock. Optional report dependencies remain lazy.

The existing per-recording **2 MB, 5000-row and duration limits are unchanged**.
A paired request has an explicit 6 MB JSON-body cap for two base64-encoded inputs;
it is not a larger per-file allowance. No source is silently truncated. Event lists
show the first 200 episodes, clearly labelled; analysis/exports retain all events.
Shared cached canvas rendering separates static plots from cursor updates, caps
DPR at two and uses no new framework, GPU or ML dependency. Browser checks use
Chromium in the cloud; performance on the specified Windows laptop is not certified.

Unknown current polarity and incomplete coverage prohibit energy/regeneration and
whole-trip efficiency claims here. Signals are not independently time-synchronization
or sensor-accuracy validated. Reports are descriptive engineering case studies,
not physical model validation or safety evidence. Phase 8 remains INCONCLUSIVE.
