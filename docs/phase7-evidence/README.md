# Phase 7 executed evidence

Implementation execution commit: `ad747de2d476c8a5ffe9f3a1403df7eaa52f5cea` (clean tree).
The subsequent evidence commit changes documentation/artifacts only.

- 109 tests passed, including all 81 baseline tests; one existing Starlette/httpx deprecation warning.
- Python coverage: 97.73% statements, 89.09% branches, 96.05% combined.
- The original eight scenarios retain their exact recorded metrics: six PASS, two FAIL.
- All 11 analytical reference traces passed; physics and controller equations were not rewritten.
- Seven new sensor scenarios: four PASS, three FAIL. Correct sensor-batch exit code: 1.
- Browser checks passed for dropout fallback, event times, resolved metadata/CSV export,
  sensor reset/ideal mode and mobile layout; no JavaScript page errors.
- The standalone sensor report rendered all 15 embedded plots without page errors.
- Dependency consistency, Python lint and JavaScript syntax checks passed.

[Sample standalone HTML report](report.html) (open after downloading the repository).
[Raw summary metrics](summary.csv) · [Truth versus biased radar plot](radar-positive-bias.png).

| Scenario | Outcome | Minimum true gap (m) | AEB time (s) | Impact ego speed (km/h) |
|---|---|---:|---:|---:|
| frozen-radar | PASS | 3.148 | 7.000 | N/A |
| ideal-radar | PASS | 5.123 | 4.960 | N/A |
| radar-dropout | PASS | 7.888 | 7.000 | N/A |
| radar-latency | FAIL | -0.001 | 5.270 | 10.482 |
| radar-noise | PASS | 6.012 | 4.920 | N/A |
| radar-positive-bias | FAIL | -0.032 | 5.360 | 29.323 |
| speed-sensor-bias | FAIL | 200.000 | N/A | N/A |

Radar bias and radar latency cause collision-avoidance failures. The speed-bias
case fails true-speed tracking without colliding. Dropout/freeze use the explicit
fallback and avoid collision in these particular configurations; that is not a
general safety guarantee. Injection labels are not automatic fault diagnosis.

Generate full raw telemetry, actual fault-event logs and ideal baseline CSVs
using the commands in [the sensor guide](../virtual-sensors.md). These files are
generated afresh rather than committed in bulk. The HTML embeds all plots.

Modified implementation groups: sensors/config.py and virtual.py; session
orchestration; testing schema/runner/report; FastAPI state adapter; static
dashboard controls/plots; seven scenarios and tests/test_sensors.py. The old
physical models, controller equations, original scenario files and baseline
test expectations were preserved. See phase7-plan.md for the pre-change plan.

Remaining limitations: one-dimensional uncalibrated sensor models, quantized
clocks, simple missing-data policy, no timestamp-spoofing model, sensor range,
fault diagnosis, hardware communication or measured vehicle/sensor validation.
