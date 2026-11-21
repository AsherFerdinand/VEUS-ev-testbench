# VEUS — EV Longitudinal Simulation & Measurement Analysis Workbench

Configure → Simulate → Analyze → Investigate Measurements.

## Three-minute engineering demonstration

1. Open **Vehicle Architecture**, inspect the interactive cutaway, then scroll to
   **Configure Your Vehicle** and select **S1**. The card selects a complete unsaved
   configuration; the body, basic values and Lab now share that same state. S1's
   illustrative defaults are 60 kWh usable, 145 kW continuous, 1,750 kg and Cd 0.25.
2. Click **Run Simulation**. Confirm the single model-limitations checkbox once for
   this browser session. Its explicit confirmation maps to all five existing backend
   flags; technical details remain expandable. It does not confirm measurement mappings.
3. Select **Urban** and run. Inspect achieved speed, battery DC power, SOC, distance,
   consumption and limits. A completed computation is not proof the requested cycle was
   feasible; infeasibility is labelled explicitly. The three graphs share replay time. A pending or failed new cycle blocks execution;
   the previous source is not silently reused.
4. Expand **Constant versus mapped motor efficiency** and compare the same design
   and full cycle. Differences reflect illustrative loss assumptions, not hardware
   improvements or physical validation. Export the frozen simulation/comparison JSON.
5. Open **Measurements & Validation** and select a bundled VED recording. Original
   speed and voltage/current plots load immediately using published mappings. Review
   the dataset name, source hash, duration, available channels and limitations.
6. Review and confirm the source mapping, then **Check readiness & investigate**.
   Select an actual detected event or use its interval. Export HTML/JSON/CSV evidence.
7. Open **Compare with Simulation** / validation readiness. S1 is not independently
   mapped to the measured Leaf: mass, tyres/aero/drivetrain, polarity, synchronization
   and uncertainty evidence remain insufficient. Residuals/fits stay null; physical
   validation remains **INCONCLUSIVE**.

No vehicle JSON export/reimport or custom CSV mapping is required for this example.
Save Vehicle and Export Configuration are optional reproducibility tools. Configuration
JSON contains resolved vehicle/battery/motor/drivetrain/aero assumptions; it is not
measurement data. The loss-model choice is a separate run option recorded in result
exports, preserving the existing vehicle JSON schema and library compatibility.

## Four workspaces and retained advanced functionality

- **Vehicle Architecture:** one shared original cutaway and configuration. Presets apply
  atomically; replacing unsaved edits requires confirmation. Saved records are never
  overwritten by a preset click. Basic fields are capacity, continuous power, total mass,
  drag and loss-model choice. Mass edits adjust residual body mass, not component masses.
- **Simulation Lab:** selected vehicle, five scenarios or a simple cycle selector, one
  acknowledgement and Run Simulation. **Advanced Simulation Settings** retains profiles,
  pinned cycles, custom CSV/route imports, units, missing-gradient policy, solver controls,
  electrical envelopes and individual consent flags. Imports remain explicitly reviewed.
- **Measurements & Validation:** original-source preview, mapping review, event/interval
  investigation, reproducible reports and explicit comparison-readiness gates. Preview
  is not consent, an investigation or a validated model result.
- **EV Challenges:** three bounded interactive examples (aero/speed, battery mass/capacity,
  regen/friction), using existing Python Lab/study APIs. The reference questions and
  sources remain expandable. No additional physics equations run in JavaScript.

Component catalogues, detailed limits/compatibility, model-adapter checks and an explicitly
labelled visual-only body override remain under **Advanced Configuration**. Comparisons,
sensitivity, daily cost and detailed calculations remain in **Advanced Analysis**; its
calculation modules load only when expanded. Configuration outputs show only matching
computed vehicle/loss-model snapshots; cycle-equivalent range requires an eligible full
Insights cycle. An unavailable result stays unavailable.

Old `?workspace=design` and `optimization` URLs redirect safely to configuration under
`?workspace=anatomy`; the retained `/engineering` toolset is unchanged. Browser Back and
in-page section links preserve the active workspace instead of restarting its analysis.

## Measurement selection defect and fix

The base implementation's selection handler fetched a recording payload and updated only
metadata. It did not call the analyser or install a replay clock/plot until a separate
confirmed investigation. Switching sources also retained the old result and enabled
exports; non-OK HTTP responses were parsed without an explicit status check.

Selection now clears the previous result/clock/plots/exports, validates HTTP status and
calls the existing `/api/replay/analyse` service for an original-signal preview. A request
identity check and abort controller prevent late responses replacing a newer selection.
Failure shows a dataset-specific, actionable message. Event/report processing still uses
its original confirmed case request and unchanged backend. Unknown current polarity
continues to block directional power/energy. Gaps and hashes remain unchanged.
See [actual before/after reproduction](evidence/measurement-reproduction.json).

## Camera and numerical boundaries

Cruise, braking and coasting use a horizontal side view. Mountain Climb uses a side view
with `atan(grade/100)` road orientation; the left-facing car and road rotate together.
Overtaking uses two top-down lanes and the existing deterministic traffic choreography:
lead position `70 + 8t` m, lateral cubic easing from actual relative gap and explicit
clearance thresholds. Neither view introduces lateral dynamics or a safety controller.

Wheel angle remains distance/radius, scenery uses travelled distance and seek reconstructs
without frame history. Road-marking paths are reused. Reduced motion disables decorative
rotation/pose while controls and telemetry remain synchronized. Numerical models, result
schemas, source datasets and report services are unchanged; software verification is not
physical vehicle validation.
