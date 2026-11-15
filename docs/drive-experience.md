# VEUS Drive: interaction and frontend architecture

VEUS is a simplified longitudinal EV simulation with an interactive 2D view.
This redesign changes presentation and input handling, not physics or controllers.
Real-world vehicle validation remains pending; see the Phase 8 evidence.

## Start a drive

Run the existing server from the repository directory, then visit localhost:8770:

```bat
python -m pip install -r requirements-report.txt
python -m uvicorn veus.studio.main:app --port 8770
```

Choose a vehicle card, press Run, then hold W or Arrow Up. Release to coast.
Use S or Arrow Down to brake, Space to pause/resume and R to reset. Escape closes
the garage or expanded chart. Mouse sliders provide continuous 0–100% demand;
hold buttons support pointer/touch input. On mobile the scene explains the touch
controls. Selecting another car starts a fresh run rather than transferring speed.

| Workspace | Purpose |
|---|---|
| Drive | Vehicle garage, scene, pedals, essential telemetry, speed/power plots |
| Analyse | Existing measurement import, calibration, holdout comparison, sensitivity, reports |
| Validate | Existing vehicle/battery/road/controller configuration, sensors/fault injection, all diagnostic charts, CSV/metadata exports, scenario/report CLI instructions |
| Settings | Vehicle colour and model/rendering limitations |

Navigation retains the same DOM objects, WebSocket session and analysis state.
Leaving Drive releases pedals and requests pause. Return and resume explicitly.
The existing backend routes and scenario JSON formats remain available. Batch
scenarios still use `python -m veus.testing`; navigation does not silently run them.
Advanced settings apply through the existing **Apply & reset** action. Entering an
engineering configuration changes the displayed specifications; an altered preset
is labelled Custom. Original acceleration/braking/coast modes remain in Validate.

## Illustrative vehicle configurations

| Preset | Body | Mass (kg) | Peak power (kW) | Torque (Nm) | Capacity (kWh) |
|---|---|---:|---:|---:|---:|
| Mica | Compact hatchback | 1350 | 100 | 220 | 42 |
| Linea | Sedan | 1800 | 150 | 300 | 60 |
| Velo | Performance coupe | 1700 | 250 | 450 | 72 |
| Terra | SUV | 2250 | 200 | 400 | 85 |

`GET /api/vehicles` returns complete validated RunConfig objects. Selection copies
the configuration to the existing form and resets the authoritative Python session;
these are not cosmetic-only swaps. All use the existing simplified equivalent
motor and two-ratio drivetrain. Driven axle topology and maximum vehicle speed
are not specified. Other unmodified road-load/electrical defaults remain shared,
so these presets do not establish realistic vehicle-category performance.
Default runs last 120 simulation seconds; advanced configuration can shorten them.

Four original, unbranded SVG silhouettes live in `static/vehicles/`. They were
created for this repository, use no downloaded artwork or manufacturer marks,
and are editable source assets. The displayed dimensions are illustrative.

## Modules and data flow

- `workspaces.js` constructs the navigation and Drive shell, then moves existing
  form/panel nodes into their workspaces before the original scripts attach.
- `dashboard.js` still owns the WebSocket, resolved configuration, complete
  telemetry history, charts, chart dialog and exports. It emits `veus:telemetry`
  and `veus:disconnect`. Hidden charts are skipped; charts redraw on workspace resize.
- `validation.js` retains independent measurement/calibration requests and reports.
- `drive.js` owns the garage, common keyboard/touch/pedal arbitration and Canvas
  rendering. `window.VEUS` exposes release/slider integration and bounded debug
  timing observations for browser regression tests, not model parameters.
- `drive.css` supplies responsive styling without a new frontend framework.
- `presets.py` supplies typed illustrative configurations. Core equations,
  controllers, virtual sensors and the 0.01 s physics step are unchanged.

`/ws/simulation` remains authoritative. At nominal 1× playback it delivers frames
about every 0.1 s; network/load can slow playback. Numbers and graphs show received
telemetry, not predicted future values. The Canvas interpolates positions between
two received samples, with roughly one-update visual latency. Interpolation is
clamped to the endpoints and never extrapolates. A reset, pause, collision or
completion snaps to the received position. No velocity integration, propulsion
model, controller or clock runs in JavaScript.

The road scale is **5 CSS pixels per simulated metre** at each viewport size.
Reference ego-front and lead-rear anchors are 245/260 and 15/260 of the displayed
145 px SVG width. Lead anchor separation is `gap_m * 5`; an off-screen lead is
identified with a distance readout instead of being clamped to a false position.
Cars are enlarged for legibility and their outlines are not a geometrically
scaled vehicle model. Both share the illustrative side-view baseline, which does
not represent lateral coordinates or real road geometry. Wheels rotate from
received displacement using the model's nominal 0.355 m radius; this is cosmetic.
Distant hills use 0.06/0.14 of road displacement, buildings 0.4, trees 0.7 and
foreground 1.2. All movement stops when position stops. No steering, drifting,
suspension, thermal model or safety certification is implied.

## Input policy and connection behavior

Brake demand overrides throttle if both are requested. Holding keyboard/pointer
buttons requests 100%; sliders permit intermediate demand. Releasing a key/button
recomputes held demand; releasing all inputs sets both to zero. Browser key repeat
is ignored. A 50 ms input check sends only changed demand through the existing
`controls` command, not requests on every rendering frame. The sliders reflect the
applied demand, including zero throttle under brake priority.

Typing in inputs, textareas, selects or editable content does not invoke driving
shortcuts. Focus loss, workspace changes, page hiding, garage opening, reset and
pause release held inputs. Auto modes disable manual pedals. Hidden pages request
pause and cancel animation; visible pages resume rendering but not simulation.
If telemetry is absent for 1.5 s during a running connection, the frontend releases
inputs and requests pause; until then the last received position is held after
interpolation ends. This is a UI guard, not a guaranteed network watchdog or
production vehicle control function. Socket closure discards that connection's
backend session, disables driving controls and marks primary readouts unavailable;
last scene/history remain for inspection. Reconnect requires reload and a new run.

## Rendering and resource limits

requestAnimationFrame separates drawing from simulation frequency. Canvas pixel
ratio is capped at 2, and SVG assets are small. Rendering skips the scene outside
Drive and is canceled while the page is hidden. The timing ring holds at most 300
observations. Telemetry history is bounded by the configured <=120 s run, nominally
1201 unique samples, and cleared on reset. No texture library, game engine or
production dependency was introduced. Browser testing needs optional Playwright
and Chromium; it is separate from application installation.

## Browser regression

With the server running and optional Playwright installed in your Node environment:

```bat
npm install --no-save playwright
npx playwright install chromium
node tests/browser/drive.cjs
```

Optional environment variables: `VEUS_URL`, `VEUS_SCREENSHOTS`, `PLAYWRIGHT_MODULE`
and `CHROMIUM_PATH`. The script tests real inputs, all configuration mappings,
workspace preservation, calibration and independent evaluation, focus release,
manual/ACC mode changes, touch/pointer pedals, disconnection and layout at
1920×1080, 1366×768, 820×1180 and 390×844. A clearly isolated renderer-only test
injects synthetic sample events to check interpolation bounds and no extrapolation;
it does not modify Python state or supply physical validation evidence.

See [executed evidence and screenshots](phase9-evidence/README.md) for actual
results. Short headless cloud measurements are not Windows integrated-GPU
benchmarks, long-session memory proofs or a guaranteed 60 FPS claim.

## Phase 10 compatibility note

The scenery renderer now lives in shared `scene.js`; Drive still owns its original
simulation telemetry interpolation and controls. Analyse now defaults to Recorded
EV replay, with the existing workflow under Model experiments & calibration.
Replay has its own clock/state and never sends simulation commands. The generic
recorded vehicle illustration does not load a Drive physics preset. See the
[recorded replay guide](real-world-replay.md).
