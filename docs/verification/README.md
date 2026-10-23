# Executed verification evidence

Source execution commit: `1024fe5d35ea8b0dab6e33cec3456e3949bbf479` (clean working tree).
The later evidence commit changes documentation/artifacts only. These results
come from execution, not invented reference performance figures.

- 81 automated tests passed; one existing Starlette/httpx deprecation warning.
- Statement coverage: 97.32%; branch coverage: 87.17%; combined: 95.52% (rounded 96%).
- Eleven analytical reference traces passed their justified error bounds.
- Eight example scenarios: six PASS, two FAIL. Batch exit status: 1 as specified.
- Standalone report rendering checked in Chromium: all nine embedded images
  loaded, criteria/metrics present, no JavaScript dependency or page errors.
- Dry-only batch separately returned exit 0. Dependency consistency check passed.

[Open the example report after downloading the repository](report.html).
[Analytical comparison plot](physics-reference.png) · [Reference errors](physics.json) · [Scenario metrics](summary.csv).

The full raw telemetry, original/resolved scenarios and provenance are generated
by the commands in [the validation guide](../validation.md). Large raw CSV files
are not committed here; the report embeds its plots and all resolved settings.

| Scenario | Outcome | Minimum gap (m) | Impact ego speed (km/h) | Response after lead event (s) |
|---|---|---:|---:|---:|
| acc_following | PASS | 35.007 | N/A | N/A |
| cruise_tracking | PASS | N/A | N/A | N/A |
| emergency_stationary | PASS | 16.986 | N/A | 0.520 |
| lead_braking_60 | PASS | 9.971 | N/A | 1.960 |
| lead_braking_delayed | FAIL | -0.079 | 37.416 | 2.470 |
| lead_braking_dry | PASS | 5.123 | N/A | 1.960 |
| lead_braking_low_grip | FAIL | -0.124 | 73.306 | 1.960 |
| manual_brake_schedule | PASS | N/A | N/A | N/A |

The delayed case fails both avoidance and its 2.0 s response budget. The
low-grip case reproduces a known collision but still FAILS avoidance.
Impact speeds are sampled at first detected overlap, not crash predictions.
No measured vehicle data, road testing, regulatory validation or production
ADAS safety claim is implied.
