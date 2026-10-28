# Phase 7 — virtual sensors and fault injection

These are deterministic 1D software sensor models, not radar hardware/perception
validation or production fault-tolerant ADAS. The existing physics, battery and
cruise/ACC/AEB equations are preserved. See phase7-plan.md for the pre-change plan.

## Data flow and compatibility

Physical state -> sampled virtual speed/radar -> queued communication delivery ->
measurement validation/freshness -> ADAS detection-delay history -> existing
controller (or explicit missing-data fallback) -> actuator-delay history -> plant.

RunConfig adds `sensors`, disabled by default. All original scenario files remain
valid and the eight recorded baseline scenario metrics are regression-checked
exactly. Enabled `ideal` mode samples every 0.01 s without noise/bias/latency/faults;
ideal defaults are enforced, so selecting ideal cannot silently ignore a fault.
Enabled `configured` mode uses the settings below. The dashboard, offline runner
and WebSocket clients use the same suite. No physical model file is modified.

The true speed/gap/closing speed and sensor values are different telemetry fields.
ACC/AEB decisions use sensor observations when enabled. The radar reports closing
speed **ego minus lead** (positive means approaching). Controller lead-speed
estimate is measured ego speed minus measured closing speed. A negative estimated
lead speed is explicitly inconsistent: no perfect lead speed is substituted.
Cruise requires the speed sensor only; ACC/AEB require both sensors. Plant gear
selection remains based on actual shaft/vehicle state, not an ADAS measurement.
Road-load feedforward uses the measured controller speed when sensors are enabled.

## Configuration

A scenario nests sensor settings inside its existing `config`:

```json
{
  "sensors": {
    "enabled": true,
    "mode": "configured",
    "seed": 42,
    "speed": {"sampling_hz": 100, "noise_std_ms": 0.05, "bias_ms": 0},
    "radar": {
      "sampling_hz": 20,
      "distance_noise_std_m": 0.5,
      "relative_speed_noise_std_ms": 0.1,
      "latency_s": 0.1,
      "stale_after_s": 0.3
    },
    "faults": [{
      "id": "radar-offset",
      "sensor": "radar",
      "fault": "bias",
      "start_time_s": 3,
      "duration_s": 4,
      "parameters": {"distance_bias_m": 10}
    }]
  }
}
```

This is a fragment of RunConfig, not a complete scenario file. Complete runnable
examples are in scenarios/sensors/. Fault IDs must be unique, times/durations
must be on the 0.01 s grid, and fault windows must end within the run horizon.
Fault windows are half-open: start <= simulation time < start + duration.
If collision ends a run early, unexecuted deactivations are not invented.

| Setting | Meaning / default |
|---|---|
| enabled / mode | false / configured; ideal requires default characteristics and no faults |
| seed | integer 0..2³²-1, default 42; local independent speed/radar RNG streams |
| sampling_hz | 1..100 Hz with periods exactly on the 0.01 s grid; default 100 |
| latency_s | nonnegative packet delay, default 0, up to 10 s per source |
| stale_after_s | maximum acquisition age at decision time, default 0.3 s |
| speed.noise_std_ms / bias_ms | Gaussian standard deviation / additive offset in m/s |
| radar.distance_noise_std_m / distance_bias_m | distance standard deviation / offset in metres |
| radar.relative_speed_noise_std_ms / relative_speed_bias_ms | closing-speed standard deviation / offset in m/s |

Negative speed/distance readings are retained as reported values but flagged
invalid, not clamped to zero. A missing lead produces invalid radar readings.
Noise parameters must be finite and nonnegative; biases may have either sign.
JSON unknown fields, mismatched fault parameters, invalid seeds, off-grid clocks
and unsupported ideal-mode settings are rejected. See sensors/config.py for
explicit magnitude limits. No synthetic out-of-range data is replaced with truth.

## Faults and overlap rules

Characteristics apply at acquisition. Scheduled faults add to those settings:

| Fault | Speed parameters | Radar parameters |
|---|---|---|
| noise | noise_std_ms | distance_noise_std_m, relative_speed_noise_std_ms |
| bias | bias_ms | distance_bias_m, relative_speed_bias_ms |
| latency | latency_s | latency_s |
| dropout | empty object | empty object |
| freeze | empty object | empty object |

Overlapping biases add. Independent noise standard deviations combine in
quadrature: sqrt(base_std² + sum(fault_std²)). Latencies add. Dropout dominates
freeze, which dominates fresh noisy/biased acquisition. Overlapping freezes
share the reference captured when the first freeze activates, until no freeze
remains. Freeze captures the most recent valid delivered packet, including its
original acquisition timestamp. With no previous valid packet, freeze is invalid.
A frozen packet does not gain a fresh timestamp; freshness checks can reject it.

Dropout produces an invalid packet with null values at each scheduled sample.
Previously acquired in-flight packets can still arrive; a fault does not magically
cancel packets already in transit. Packets are accepted in generation order;
late older packets are discarded rather than resurrected after a latency change.
Frozen packets have a new generation time but retain old acquisition time.
Sampling holds the last delivered packet between acquisitions. Recovery occurs
on a fresh delivered sample, not necessarily at fault-window end.

All scheduling uses physics ticks, never wall-clock time. Reset constructs a new
suite with fresh packet queues, freeze state, event logs and seeded RNGs. Identical
configuration/seed reproduces measurements and controller trajectories in the
same software environment. Noise sequences also depend on sampling and fault
schedules; changing a schedule can change subsequent draws. Independent streams
prevent a change in speed sampling from consuming the radar RNG stream.

## Timing, health and fallback

Sampling delay is sample/hold age. Communication latency is packet transport
age. Existing detection_delay_s stores already-delivered observations; existing
actuation_delay_s stores computed commands. None is a substitute for another.
Acquisition age is checked again after detection delay. Thus excessive combined
age invokes fallback, even if a packet was fresh enough when first received.
Choose stale thresholds consciously; 1 Hz sampling with a 0.3 s maximum age will
be stale for much of each second. Latency can make every reading stale.

Sensor status is valid, delayed, fault-active, stale, unavailable or disabled.
Fault-active means a scheduled injector event is active, **not automatic fault
detection**. Injection activity, packet validity, frozen flag and age are separate
fields: a biased reading may remain valid; a late packet can outlast its fault.
Communication-delayed readings can still be usable within the age limit.

Missing/stale/inconsistent required observations invoke configured comfort
braking. Already-latched AEB continues emergency braking and does not clear on
sensor loss. Recovery resumes the existing controller, unless AEB remains latched.
Fallback commands pass through actuator delay and physical limits; no instantaneous
or guaranteed safe stop is implied. This is a chosen illustrative policy, not an
ISO 26262 safety mechanism. There is no bias diagnosis, fault isolation or redundant
sensor voting. The fallback does not use truth to calculate a replacement input.

Telemetry separates decision input health from applied input health (commands
may still be in actuator delay). Measured values/timestamps describe the frame
end; applied forces/commands describe the preceding physics interval. A newly
invalid frame-end measurement may therefore precede fallback by one integration
interval, plus any configured detection/actuation delay. Controller input age
and measured inputs refer to the actual delayed decision observation.

## Dashboard workflow

Select ACC or AEB. Expand **Sensors & Fault Injection**, enable sensors, configure
noise/bias, sampling, latency, maximum age and optional dropout/freeze event.
Click **Apply & reset**, then **Run**. Settings are applied only on reset. The
**Reset sensor settings** button restores defaults and disables sensors; apply
and reset to use them. Ideal mode requires reset/default characteristics.

True/measured speed and following-gap plots share the existing expand controls.
Solid cyan is truth; dashed amber is **valid** measured data. Missing/stale values
are gaps, not zero. Raw rejected values remain in CSV alongside validity flags.
The status panel shows sensor ages, active injection IDs, latest actual activation/
deactivation time, and decision/applied controller health. Metadata exports include
resolved server configuration and executed fault events. Fault labels are supplied
by the injector, not detected by the controller.

## Offline robustness suite and reports

In Anaconda Prompt, from the updated checkout:

```bat
"%LOCALAPPDATA%\veus-venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
"%LOCALAPPDATA%\veus-venv\Scripts\python.exe" -m pytest -q
"%LOCALAPPDATA%\veus-venv\Scripts\python.exe" -m veus.testing run scenarios\sensors --output reports\sensors-001
start "" reports\sensors-001\report.html
```

Use a new output directory. Sensor cases are in a subdirectory so running
`run scenarios` still executes the original eight files. The new suite has seven
cases: ideal radar, noise, positive bias, latency, dropout, freeze and speed bias.
Acceptance criteria remain scenario-specific; failed avoidance/tracking objectives
are not changed merely because the fault reproduces an expected failure.

Configured sensor runs automatically execute a like-for-like ideal-sensor baseline,
with only sensor characteristics/faults replaced. The original plant, controller,
legacy delay settings, control schedule and horizon are preserved. Reports retain
baseline configuration/metrics and ideal-baseline-telemetry.csv. Ideal and faulted
runs can have different executed horizons due to collision; minimum-gap comparisons
use each full executed trajectory and state both horizons explicitly.

Additional artifacts include sensor-events.json/csv and sensors.png. Events record
actual injection activation/deactivation, not observer fault detection. result.json
contains baseline metrics without embedding large telemetry arrays. Baseline raw
CSV is saved separately. Existing source/config hashes and provenance are preserved.

## Error and robustness metrics

Sensor error is reported measurement minus current ground truth, so sampling and
latency contribute to error alongside noise/bias. MAE and maximum absolute errors
use valid tick measurements only (including the initial sample); unavailable,
stale and rejected measurements are excluded, never replaced with zero. Relative-
speed errors use the closing-speed sign convention. Reported validity fractions
include every recorded tick, including stopped and initial-acquisition intervals.

Read error statistics **together with unavailability and fallback fractions**.
A frozen sensor can have a small valid-only MAE while being unusable for a large
part of the run. Controller fallback fraction counts applied commands whose input
health is stale, unavailable or inconsistent, including latched emergency braking.
A valid sensor packet can still yield an inconsistent lead-speed reconstruction.

Minimum-gap delta = faulted minimum gap minus ideal minimum gap. A negative delta
means reduced separation. AEB delay relative to ideal = faulted detection time
minus ideal detection time, and is null if either detection never occurs. ACC
true target-speed error is a separate metric: it is meaningful as a criterion
only when the lead is not intentionally limiting ego speed. The speed-bias case
uses a distant lead moving faster than the target for that reason. Undefined
metrics remain INCONCLUSIVE if required by a criterion. Collision and impact-speed
sampling retain the original report semantics; no crash interpolation is implied.

## Worked example: overestimated radar gap

Run scenarios/sensors/ideal-radar.json and radar-positive-bias.json. Both start
at 80 km/h with a 35 m gap; the lead brakes at 3 s with 6 m/s² deceleration. The
faulted radar adds 10 m over [3,7) s. Executed development results:

| Metric | Ideal radar | Positive radar bias |
|---|---:|---:|
| AEB detection time | 4.96 s | 5.36 s |
| Minimum true separation | 5.123 m | -0.032 m (first overlap) |
| Collision | No | Yes |
| Ego speed at first overlap | N/A | 29.323 km/h |
| Maximum valid distance error | 0 m | 10 m |
| Outcome | PASS | FAIL |

The 0.40 s later trigger and collision are reported, not hidden by loosening the
avoidance criterion. The small negative gap is tick-level overlap, not crash
penetration physics. Other faults need not be worse in every metric: dropout
fallback starts braking earlier in the supplied case, while biased speed causes
about 7.1 km/h true-speed tracking error. These are simulated model outcomes only.

## Remaining limitations

No camera, 3D radar, range/range-rate correlation, multipath, object association,
weather, clock drift, packet corruption or real hardware. No vehicle-data calibration,
production fault detection or safety certification. Gaussian models are illustrative;
negative speed/distance and negative reconstructed lead speed are rejected explicitly.
Freeze retains acquisition time; a sensor that lies about timestamps is not modelled.
Sampling/fault clocks are quantized to 0.01 s. Existing ideal-force brake dynamics,
constant-OCV energy model, explicit Euler position error and TTC-threshold AEB
limitations remain. Passing software tests does not establish physical validation.
