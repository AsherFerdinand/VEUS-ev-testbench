# Recorded EV replay and descriptive engineering analysis

Replay displays observations and derived quantities, not a vehicle simulation.
Playing measured speed does not validate predicted speed. Phase 8's VED battery
comparison remains **INCONCLUSIVE as physical validation**, with its numerical
failures retained. No new physics, controller, traffic or ADAS scenario is added.

## Run on Windows (Anaconda Prompt)

From the extracted repository folder:

```bat
python -m pip install -r requirements-report.txt
python -m uvicorn veus.studio.main:app --port 8770
```

Open http://localhost:8770, close/select the Drive garage, choose **Analyse**, then
**Recorded EV replay**. Trip 1561 loads by default on entering Analyse. Use Play,
Pause, Restart, the timeline, elapsed-time jump or graph clicks. Rates are 0.5×,
1×, 2× and 4×. Hover a graph to inspect an actual sample timestamp and value.
Select an event to seek to its start. Signals, Driving events, Trip insights and
Export are tabs, with thresholds/import settings collapsed below. The existing
measurement calibration workflow lives under **Model experiments & calibration**.

Offline equivalent (new output directory each time):

```bat
python -m veus.replay examples/replay/ved-10-1561.json datasets/ved/ved-10-1561.csv --output reports/replay-1561-001
```

Repeat with `ved-10-1558` for the other existing measured window. CLI exit 0 means
descriptive analysis completed, not that a vehicle model passed validation.
Exit 2 means invalid input/setup. Existing outputs are never overwritten.
If using the earlier dedicated environment, replace `python` in these commands
with `"%LOCALAPPDATA%\veus-venv\Scripts\python.exe"`.

## Genuine dataset and provenance

The demonstration reuses the existing small University of Michigan Vehicle Energy
Dataset (VED) projections. Authors: Geunseob Oh, David J. LeBlanc, Huei Peng;
[dataset](https://github.com/gsoh/VED), [paper](https://doi.org/10.1109/TITS.2020.3035596).
The pinned upstream commit is `6baa4963782d515a67d32a5490bd5d11f5d9bf0d`.
Upstream Apache-2.0 licence and redistribution/selection provenance are retained in
[datasets/ved](../datasets/ved/README.md). No new raw archive download is needed.

| Window | Rows | Elapsed duration | Source CSV |
|---|---:|---:|---|
| Vehicle 10, trip 1561 (default) | 111 | 72.1 s | 5373 bytes |
| Vehicle 10, trip 1558 | 74 | 50.4 s | 3574 bytes |

These are selected short windows, not complete trips. Vehicle 10 is identified by
upstream static records as a 2013 Nissan Leaf, but the illustration is a generic
unbranded EV, not a calibrated Leaf model. No illustrative Drive preset is loaded
by replay. The landscape is fictional, not a geographic reconstruction.
The CSV is the existing projection; original numeric text and current sign are
retained. Config/source hashes and exact upstream source rows are embedded in
metadata. Time conversion subtracts the first timestamp explicitly; original
source times are recovered with `elapsed + time_origin_s`, not invented UTC dates.

Available measurements: timestamp (ms), vehicle speed (km/h), pack voltage (V),
signed pack current (A), SOC (%) and outside air temperature (°C). The replay
importer converts to SI speed m/s and SOC fraction; temperature remains °C.
Outside air temperature is not battery temperature. Available derived channels
are acceleration, signed electrical V×I and speed-integrated displacement.
Propulsion torque, brake demand, road gradient, measured GPS distance, pack
temperature, measurement uncertainty and channel synchronization evidence are
unavailable. No such signals are fabricated.

**Current polarity is unverified.** Phase 8's exploratory experiments inverted the
source current under an explicit hypothesis. These separate replay configurations
use source sign `+1`, `current_sign: unknown`, and do not alter those experiments
or evidence. Negative V×I is displayed as a signed product, not labelled regen or
charging. Descriptive recorded-data analysis has no physical PASS/FAIL verdict.

## Data ingestion, quality and units

`veus.replay.analysis` calls the existing `veus.validation.measurements.load_csv`.
There is no second CSV parser. A compatible ambient-temperature channel (C/°C)
was added to the canonical measurement schema; existing behavior is preserved.
Required replay channels are time and measured speed; electrical/SOC/temperature
channels are optional. An explicit config supplies source identity, licence,
measured/synthetic kind, expected SHA-256, column/unit/sign mapping, gap threshold,
current polarity assertion/evidence, analysis thresholds and limitations.

Imports reject missing mapped columns, malformed/duplicate headers, duplicate or
non-increasing timestamps, missing/non-finite times, non-finite numbers,
unsupported units, negative forward speed, nonpositive voltage and SOC outside
0..1. Blank/NA/NaN/null field tokens remain null, not zero. Replay additionally
checks broad configurable sanity limits: speed 120 m/s, voltage 2000 V, absolute
current 5000 A, measured acceleration 100 m/s²; ambient -100..100 °C and mapped
power ±10 MW. These are import guards, not vehicle operating limits. Inspect
source/units before changing them. An implausible differentiated acceleration may
still be caused by noisy/quantized data; it is not ground-truth acceleration.

Interactive windows are limited to 2 MB, 5000 rows and one elapsed day, with a
3 MB JSON request cap. The API streams request bytes up to its cap before parsing.
Use a documented smaller source window for larger inputs. No analytical
resampling, smoothing or downsampling is performed: all retained rows are used.
Original CSV bytes stay unchanged. Reports export converted measured columns
separately from derived columns. Config assertions are not authenticated.

## Calculations and gap policy

For valid adjacent timestamps `t_i`, speed `v_i`, interval `dt`:

- Displacement increment: `(v_i + v_(i+1)) / 2 * dt` in metres. This assumes
  piecewise-linear speed between samples, not a measured GPS trajectory.
- At an intermediate visual time `u` after the left sample, displacement is
  `x_i + v_i*u + (v_(i+1)-v_i)*u²/(2*dt)`. This makes visual speed follow the
  speed interpolant rather than linearly interpolating cumulative distance.
- Acceleration: `(v_(i+1)-v_(i-1))/(t_(i+1)-t_(i-1))`, a two-neighbour secant;
  endpoints use one-sided differences. This is not a higher-order unequal-grid
  derivative or a filtered accelerometer estimate. Noise/quantization may be
  amplified. Any missing or oversized interval in its stencil yields null.
- Electrical power: samplewise `V_i * I_i`, preserving mapped current polarity.
  A mapped measured power channel can be shown when V/I are unavailable, with a
  measured label. A measured power column is not silently treated as derived V×I.
- Average speed: complete-window speed integral divided by elapsed duration,
  rather than the arithmetic mean of irregular samples. Peaks are available
  sample extrema or derivative extrema, not claims about unsampled peaks.

Intervals longer than config `max_gap_s` (default 2 s), or with missing endpoint
speed, contribute no **known-segment** displacement. Unknown travel is excluded,
not asserted to be zero. Total distance/average speed become unavailable for
incomplete speed coverage; known-segment distance and coverage are reported
separately. The scene holds displacement during an unknown interval and resumes
only from known segments; it never fills a gap with fabricated motion.

Numeric telemetry uses the preceding actual row and shows its recorded timestamp.
No resampled measurement is presented as an observation. Within a timestamp gap,
readouts are unavailable; exact endpoint samples remain inspectable. Smooth scene
movement is visual interpolation only, with no extrapolation beyond the recording.
The live derived distance is evaluated at playback time, separately from the
sample-valued readouts. Graph hover always reports the nearest actual row,
including null values; graph click seeks to elapsed time. Plot lines connect
observations visually and break across gaps/nulls.

Energy integration requires an explicitly evidenced current-sign assertion and
complete joint V/I/timestamp coverage. Signed power is adjusted to discharge-
positive, then positive/negative areas are integrated with exact zero-crossing
splits of the piecewise-linear sampled-power approximation, converted J/3600 to
Wh. Received electrical energy is not automatically regenerative energy. The
regeneration-specific total remains unavailable without evidence of charging
origin. VED's unknown polarity disables used/received energy and possible-regen
classification. No percentage errors or predictive accuracy scores are produced.

## Transparent events

Default minimum episode duration is 0.5 s; it is the last minus first qualifying
sample timestamp, not an extrapolated duration. Missing samples and large gaps
break episodes. A singleton can qualify only when duration threshold is zero.
Every event retains elapsed/source start/end times, supporting signals, threshold
rule, observed/derived/inferred classification and a data-quality qualification.

| Event | Default rule | Interpretation |
|---|---|---|
| Strong acceleration | derived acceleration ≥2 m/s² | Inferred from noisy speed samples |
| Strong deceleration | derived acceleration ≤−2.5 m/s² | Inferred, not a brake-demand observation |
| Standstill | measured speed ≤0.1 m/s | Observed sample threshold episode |
| High electrical magnitude | abs(power) ≥50 kW | Magnitude, not discharge demand under unknown polarity |
| Possible regenerative braking | known sign, discharge-positive V×I ≤−1000 W and derived acceleration ≤−0.1 m/s² | Inferred possibility; no charging-source proof |
| Timestamp gap | adjacent interval > max_gap_s | Observed availability issue, unknown travel |
| Missing measurements | one or more mapped null fields | Availability issue, not a diagnosed sensor failure |

Thresholds are configurable in Advanced analysis or JSON. Rules are not ML.
Only the first 200 events are listed in the browser, with an explicit total;
exports retain the complete list. Over 10000 episodes requires narrowing the
window/settings rather than silently truncating the analysis.

## Architecture and independent state

- `veus/replay/analysis.py`: typed config, shared import, full-resolution derived
  series, metrics, threshold events and deterministic analysis fingerprints.
- `api.py`: whitelisted bundled recordings, bounded custom import and HTML export.
  Report rendering shares the existing matplotlib lock with Phase 8.
- `report.py` / `__main__.py`: standalone plots, CSV/JSON/HTML artifacts and CLI.
- `scene.js`: the extracted Phase 9 Canvas renderer. Callers supply displacement,
  silhouette and optional lead gap; it owns no simulation or replay clock.
- `drive.js`: existing simulation interpolation/controls, now delegates drawing.
- `replay-controller.js`: independently unit-tested wall-clock playback with
  recorded timestamps, binary-search lookup, speed changes, end/gap/seek state.
- `replay.js` / `replay.css`: Analyse tabs, generic replay scene, sample readouts,
  cached full-resolution plots/cursors, event navigation and exports.

Replay never sends WebSocket control commands. Existing workspace policy releases
and pauses Drive on leaving it. Leaving Analyse, hiding the page or opening model
experiments pauses replay; returning does not auto-resume either clock. Replay
rates/seeks do not change simulation time/configuration. Drive can resume its own
session afterward. Data imports/threshold changes reset the replay clock only.
The global connection/status badge describes the live Drive session; the separate
Replay badge describes recorded playback. Browser timers may throttle in the
background, so replay pauses explicitly on page hiding.

The scene runs requestAnimationFrame while playing; readouts and cursors update
at most about 12.5 Hz. Plot geometry is cached until data, selection or size
changes; each playback update draws only the cached plot plus cursor. Plots use
the full retained resolution. Canvas DPR is capped at 2; display geometry never changes the analysis. No heavyweight rendering or ML dependency is added.

## Reproducible exports

Browser exports: summary JSON, events CSV, metadata/settings JSON, full-resolution
analysis JSON and standalone HTML. The server recomputes HTML from unchanged
source bytes/config and requires the same analysis fingerprint before download.
The CLI additionally saves original.csv, configuration-input.json, canonical
configuration.json, analysis.json, summary.json, events.json/csv,
standardised-measured.csv and derived.csv with elapsed and source timestamp columns.

Source SHA-256 identifies exact CSV bytes. Config/analysis hashes use sorted,
indented UTF-8 JSON with a final newline, ASCII escaping and finite numbers;
integral floats (including negative zero) normalize to integers so equivalent
browser serialization of opaque provenance does not change the identity.
`analysis_sha256` hashes the whole analysis before inserting that field itself.
No wall-clock generation time enters the deterministic calculation. Algorithm
version, source identity, mappings, settings, units, limitations and provenance
travel with the result. The documentation evidence records execution commit and
tested software versions; changing the dataset or thresholds changes the hash.
A hash establishes byte/content identity, not truth of source metadata.

## Tests and limits

Run `python -m pytest -q` for all Python regressions and
`node --test tests/browser/replay-controller.test.cjs` for playback math.
Optional Playwright/Chromium browser checks:

```bat
node tests/browser/replay.cjs
node tests/browser/drive.cjs
```

Install optional Playwright as described in the Drive guide; the app does not need
Node. Test-only synthetic fixtures are explicitly labelled and never substituted
for the real VED example. See [executed evidence and screenshots](phase10-evidence/README.md)
for actual results and metrics. Short cloud browser observations do not prove
Windows integrated-GPU performance or long-session memory behavior. Missing
conditions prevent predictive speed validation; full physical EV validation,
uncertainty propagation, GPS paths, thermal/SOH calibration and traffic remain
outside this recorded-data analysis workflow.
