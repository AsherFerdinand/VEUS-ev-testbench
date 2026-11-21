# Engineering Insights and Controlled Design Analysis

The 2.3.3/2.4 services compose the existing coupled Lab. They do not replace any
vehicle equations or silently calibrate parameters. Design Studio runs analyses
only on explicit request, preserving complete resolved snapshots and user assumptions.

## Insights contract and equations

`POST /api/workbench/v2/insights` accepts a complete `vehicle`, the five retained
model acknowledgements, `profile_id` (urban, motorway, pinned FASTSim UDDS/HWFET),
`dt_s`, acceleration target/duration, daily distance, tariff, optional charging
efficiency and optional driving days. The whole original cycle executes; it is
never trimmed to fit the budget. Fixed continuous power policy distinguishes
rated operation from a peak nameplate. Final acceleration speed and observed tick
time to target are not a maximum sustainable speed or physically validated performance.

Stored-energy depletion is terminal net battery energy **plus internal battery
heat**. Consumption is depletion / achieved distance × 100,000 in kWh/100 km.
Cycle-equivalent range is full usable model energy × 100 / stored consumption.
It is not remaining range at the initial SOC, an EPA/WLTP certificate or real-world
range. It assumes the same cycle demand over the full usable reservoir with the
existing constant OCV/efficiencies and no auxiliaries, temperature or ageing model.
Terminal consumption remains a separately labelled metric.

Extrapolations are inconclusive for incomplete/gapped source coverage, physically
infeasible requested movement, SOC endpoints at 0/1, achieved distance under 100 m,
nonpositive stored depletion, inconsistent SOC accounting or speed-tracking error
above .05 m/s. The 100 m threshold is a numerical/meaningfulness guard, not a
validation standard. Feasible prescribed tracking is near machine precision in
reference cases; .05 m/s allows small numerical error, not material cycle mismatch.
Regenerative acceptance clipping alone does not invalidate achievable friction
braking. Unavailable range/energy/cost is null with reasons, never an invented zero.

Daily stored energy = distance × consumption / 100. Grid energy = stored energy /
explicit charging efficiency. Cost = grid energy × user tariff. With unknown
charging efficiency, battery-energy cost is a separate proxy excluding charging
losses; grid energy/cost remain unavailable. Monthly estimates multiply by the
user's driving-day count. Editable default tariff/distance values are illustrative
user assumptions, not regional prices or a live tariff service.

Results include configuration/scenario/result hashes, exact full Lab requests,
source provenance, metrics with units/status/reasons and <=400 selected original
rows per run labelled **preview only**. Full traces can be reproduced through
`/api/lab/run` and existing exports using the preserved requests. No unbounded cache.
Frozen JSON/CSV/HTML exports validate integrity hashes and do not authenticate
client-provided content. One frozen browser result is invalidated or labelled stale
when active inputs change.

## Controlled studies

`POST /api/workbench/v2/design-analysis` uses `kind=compare|sensitivity|battery_size`,
`baseline`, optional `modified`, and one shared `conditions` object matching the
Insights settings without a vehicle. Scenario hashes include experiment, complete
profile/source/route and explicit initial SOC/friction/density; vehicle design
fields are excluded. Different driving conditions produce a warning and suppress
controlled differences. Changed fields and configuration hashes are retained.

Sensitivity uses two to five distinct explicit values plus the original baseline.
Supported fields are residual body mass, Cd, frontal area, rolling coefficient,
usable energy and continuous motor rating. Structural/incompatible and infeasible
points are retained with reasons. There is no optimizer or automatic winner.
Absolute difference = modified − baseline; percentage = 100 × difference /
abs(baseline), unavailable for a zero or unavailable baseline.

Battery-size studies require an explicit positive kg per usable kWh. Both pack
mass and usable energy change, with the original gross/usable ratio retained.
Voltage, resistance, current limits and efficiencies remain explicit held assumptions.
This is an illustrative trade-off, not a realistic pack-design model. Capacity-only
sensitivity deliberately holds mass fixed and is labelled accordingly.

Both services share two bounded CPU-work slots, reject excess concurrent work,
limit input bodies and reuse the Lab's <=12,000-tick experiments. Study results
contain <=six points, compact previews and original requests. Portable reports
include actual metrics, null/failed points, scenario/configuration hashes,
changed inputs, limitations and a small consumption plot.

[Checkpoints, examples and limited measurements](evidence-2.5/README.md).
