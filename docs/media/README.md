# Actual VEUS media and publication checks

All animations show the running application at source commit
`deecbd7f7497a2bb095583d45036a4015be05a06`. No application code, physics,
telemetry, plot values or choreography were changed to create this documentation.

## Capture provenance

| Asset                      | Actual browser actions                                                                                                                                           |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `vehicle-architecture.gif` | Inspect battery/motor/inverter, scroll to configuration, select R1/X1/S1 and return to their updated cutaways.                                                   |
| `simulation-lab.gif`       | Select Traffic Light Braking, run S1, then replay at the application's **0.5×** rate. Speed, electrical power, SOC, wheels and plots use the real stored result. |
| `overtaking.gif`           | Run S1 acceleration/overtaking for 20 s with dt 0.05 s and replay at **2×**. Captured states include approach, outward lane change, pass, return and continue.   |

Captures use headless Chromium, a fresh browser-local library of the three original
presets, 1366×950 viewport, light theme and roughly five screenshots per second.
Interactions are ordinary UI selections, runs, scrolling and playback. Temporary demo
unsaved-edit confirmations were accepted; no user's browser storage was accessed.

Existing Pillow tooling resizes captures to 1100×765 and quantizes one shared 256-color palette
per GIF. GIF timing follows measured capture intervals, rounded to centiseconds;
identical adjacent frames can be coalesced. Encoding is checked for complete decoding,
8–15 s duration and size below 5 MiB each. Decoded samples are visually inspected.
No runtime dependency or application behaviour changes are involved.

[Capture manifest](capture-manifest.json) records source commit, timings, dimensions,
frame counts, byte sizes, checksums and captured replay stages. Resizing/palette encoding
is presentation processing, not fabricated application output. Original PNG frame series
and encoder scratch files remain outside the repository to avoid bloating Git.

## Still images

- `vehicle-architecture.png`: crop/resize of the previously verified refocus capture;
  the original is [here](../refocus/evidence/vehicle-architecture.png).
- `measurements.png`: resize of the verified original VED investigation capture
  [here](../refocus/evidence/measurements.png), preserving actual signal/event evidence.
- `vehicle-presets.png`: new browser element capture of the S1/R1/X1 selection cards.
- `simulation-lab.png`: new browser element capture of the computed side-view braking
  result and plots, after Stop/reset. It is a real initial replay position, not new data.
- `ev-challenges.png`: new browser viewport capture of the optional interactive examples.

## Verification scope

This is documentation/media publication only. The verified implementation and tests at
`deecbd7` are reused: 314 Python cases, 9 clock tests, 8 scene tests and 11 browser suites.
The [exact record](../refocus/evidence/verification.json) discloses the branding-only
assertion correction and targeted cycle-selection checks. No numerical or export
contract is modified or inferred from the GIFs.

Publication checks cover local GFM rendering, internal links and anchors, image/GIF
decoding and size, verified example numbers, dependency/launch paths and unchanged
application/test/dataset/dependency files. [Verification record](publication-checks.json).
Main publication is explicitly authorized; normal Git operations must respect server-side
protection. No force push, protection bypass, history rewrite, release or tag is authorized.

The project licence remains unresolved. Application screenshots use the existing original
VEUS artwork; no stock imagery or new third-party fonts were introduced. Runtime and
plotting packages retain their own licences. VED and FASTSim materials retain upstream
Apache-2.0 notices/provenance; their licences do not automatically license VEUS as a whole.
See [the licensing review](../veus3/release-readiness.md#licensing-and-third-party-materials).

Clean Windows installation and non-Chromium browser execution remain unverified.
Physical validation remains **INCONCLUSIVE**; visual lane changes are illustrative.
