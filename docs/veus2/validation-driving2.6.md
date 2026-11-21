# VEUS 2.6 — validation readiness and driving scene

## Measurement evidence and calibration boundary

The new Measurements **Validation & calibration readiness** section audits the selected
original recording, complete vehicle snapshot and explicitly selected loss model.
`POST /api/workbench/v2/measurements/validation-readiness` reuses `investigate`;
legacy processing, current-sign gates, gaps and report services remain unchanged.
JSON/HTML assessment exports preserve the full request, source provenance, source hash,
model version/configuration hash, blockers, candidate values and assessment fingerprint.
Exports reject a modified assessment. Retained investigation/calibration tools remain linked.

The available Nissan Leaf VED recordings identify a published vehicle and provide time,
speed, voltage and signed current, but do not establish an independent mapping to an
S1/R1/X1 design. Published weight is generalized/binned, not a measured test mass.
Current polarity, synchronized V/I measurement boundary, tyre radius, aero inputs,
drivetrain/gear configuration and sensor uncertainty are insufficiently verified.
Channel availability supports descriptive investigation; it is not model validation.

Candidate-specific readiness covers rolling resistance, drag area, effective drivetrain
efficiency and battery resistance. Initial values come from the frozen design.
Calibrated values, bounds, objective/error and residuals remain null because the evidence
does not identify a defensible fit. Battery OCV/SOC/current excitation would additionally
be needed to identify resistance. No optimizer or real-data calibration result is claimed.
Optional calibration/evaluation intervals must both be present, finite, in coverage and
strictly disjoint, including shared boundary samples. This prevents an interval-overlap
error; it does not demonstrate independent experimental evidence or remove confounding.

`error_metrics` is a numerical paired-series helper, not a public evidence-authentication
API. Explicit compatible SI unit/mapping/alignment assertions are required; A/W/Wh also
require polarity. It reports simulated-minus-measured residuals, MAE, RMSE, mean bias,
min/median/max errors and valid paired-sample coverage. Missing/nonfinite pairs stay null.
Optional nonnegative signal uncertainty is supplied, never inferred from residuals.
Analytical tests verify the arithmetic and rejection gates. No measured/model overlay or
residual plot is produced for the unmatched VED case. Physical status is **INCONCLUSIVE**.

## Deterministic illustrative driving scene

`driving-scene-state.mjs` is pure: recorded time, achieved distance/speed/acceleration,
wheel radius and explicit scene parameters determine every pose. Seeking needs no prior
frames. The clock and engineering plots are unchanged; playback rate options are secondary.

Traffic position is `70 m + 8 m/s × t`, independent of ego motion. Relative gap drives
smooth cubic lane easing: approach/follow, outward transition from 45 to 18 m gap,
pass, then return after 12–45 m clearance. Lane width is 3.5 m. Heading follows the
analytic lateral rate, bounded to ±6°. This is illustrative traffic choreography,
not lateral dynamics, steering, sensing, an ACC controller or a safety guarantee.
A short or slow experiment may not complete the manoeuvre; no state is fabricated.

Wheel angle is `distance / wheel_radius × 180/π`; traffic uses its own travelled distance
and declared 0.32 m radius. SVG orientation reverses its drawing sign. A small speed-based
camera offset (0.15 s, capped 4 m) avoids frame history, with bounded acceleration pitch
and distance-based body heave. Perspective projection and road dimensions are visual
assumptions. Repeating road markings and layered scenery use camera distance. Original
S1/R1/X1 artwork is reused; wheel groups are transformed only in the Lab.

Reduced motion removes decorative wheel/pose/parallax effects while positions and
telemetry remain seekable. No animation frame runs while paused, stopped, completed or
inactive. Existing five experiments, gauge, battery, three plots and profile/route controls
remain. Eight pure scene tests and the advanced browser workflow cover direct seeks,
full stage sequence, wheel mapping, traffic, pause/rate/reset, responsiveness and cleanup.

See [powertrain equations](powertrain2.6.md) and [evidence](evidence-2.6/README.md).
