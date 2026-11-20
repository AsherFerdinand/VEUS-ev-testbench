# VEUS 2.1 design engineering contracts

This is the authoritative location for the v2 catalogue, calculations, compatibility
and model adapter. Foundation v1 contracts remain available unchanged; the new
workbench uses `/api/workbench/v2`. These are illustrative engineering studies,
not manufacturer specifications or physical validation. Historical evidence is retained.

## Catalogue and reproducible designs

`veus/workbench/catalogue.py` contains 13 compact representative records across
battery, motor, inverter, onboard charger/charging envelope, DC/DC, reduction gearbox
and body/residual-system configurations. Each record has a stable identifier, kind,
label, technology, explicit parameter values and per-parameter unit, classification,
source ID, operating conditions and uncertainty description. Repeated source metadata
is stored once. Manufacturer/model remain null because no commercial specifications
were retrieved. Null peak durations and phase-current information remain null.

The sole quantitative source is **VEUS representative analytical assumptions**,
authored 2026-11-20, classified illustrative. It is not a vendor datasheet. Existing
source references and their blocked-access record remain in [sources.md](sources.md).
No new quantified claim is inferred from AFDC or another inaccessible source.
Technology labels LFP/NMC/PMSM/SiC do not alter losses or create performance gains.
Record alternatives deliberately keep explicit efficiencies independent of labels.

A design is a strict `VehicleDesignV2` snapshot with `schema_version: 2`, catalogue
version `representative-v1`, selected component IDs and resolved editable parameter
values. It does not embed the complete catalogue/source record. An ID may be `custom`
for edited inputs; retained IDs with differing resolved values are reported as
`catalogue_overrides`. Unknown IDs or mismatched kinds produce an incompatible
reference check; unknown versions/keys or non-finite inputs are rejected. Snapshot
values plus catalogue version preserve reproducibility when a selection is edited.

Version 1 imports are not automatically migrated: their body-mass boundary excludes only the battery and their component/torque/current inputs are missing. POST `/migrate` explains the required manual reconstruction instead of inventing values or double-counting mass. The original v1 API is retained.

GET `/design` returns complete illustrative defaults. GET `/schema` supplies JSON
Schema. GET `/catalogue` is cached once because records are immutable source code.
External design snapshots must include every resolved field, including explicit nulls for supported unknown values. Missing fields are rejected rather than silently filled from template defaults. GET `/schema` marks those fields required.

POST `/evaluate` accepts at most 64 KB of design JSON and returns its normalized
snapshot, canonical SHA256, checks, derived specifications, reference overrides and
simulation readiness. No result cache or unbounded simulation-history store exists.
A changed snapshot necessarily changes the configuration hash. No GPU or new package
is required; scalar arithmetic is not parallelized or vectorized unnecessarily.

## Mass boundary

The explicit mass sum is:

`m_total = m_body_residual + m_battery + m_motor + m_inverter + m_onboard_charger + m_dcdc + m_gearbox`.

`body.mass_excluding_components_kg` excludes **all six listed masses**, not only
battery mass. It includes wheels, suspension/chassis, wiring, BMS, thermal hardware,
auxiliary battery and all other unlisted systems. Therefore those residual systems
must not be added again. Onboard charger mass is vehicle hardware; the offboard DC
charger is not added to the vehicle. A missing component mass makes total mass and
power-to-weight unavailable; no zero/default substitution is made.

The default calculation is `1200 + 420 + 70 + 25 + 12 + 3 + 18 = 1748 kg`.
This is an accounting example, not a measured vehicle mass.

## Supported derived specifications

All engineering calculations live in `engineering.py`; JavaScript displays backend
outputs and does not independently implement these equations.

| Quantity                      | Equation                             | Units and assumptions                                                   |
| ----------------------------- | ------------------------------------ | ----------------------------------------------------------------------- |
| Total mass                    | Explicit sum above                   | kg; consistent residual boundary required                               |
| Gross/usable energy           | Declared explicit inputs             | kWh; no temperature/cycle derating                                      |
| Approximate charge capacity   | `Q ≈ 1000 E_kWh / V_nominal`         | Ah; nominal-voltage approximation, not measured coulomb capacity        |
| Peak motor power-to-weight    | `1000 P_peak_kW / m_kg`              | kW/t; nameplate ratio, not achieved acceleration                        |
| Required DC current           | `I = 1000 P_DC_kW / V_DC`            | A; separate defined positive-discharge electrical operating point       |
| Idealized driven-wheel torque | `T_wheel = T_motor × ratio × η_gear` | N·m; before tyre traction limit; constant explicitly assumed efficiency |
| Drag area                     | `CdA = Cd × A`                       | m²; no wind-tunnel/coast-down validation implied                        |

The operating-point DC current and wheel torque are separate scalar specification
checks. They do not imply the same motor speed or a solved coupled electrical/mechanical
operating state. Every output includes equation, inputs, units, assumptions and an
unavailability reason where applicable. Missing mass, peak power or efficiency makes
only dependent calculations unavailable; other supported quantities remain useful.
No range, acceleration prediction, consumption, charging time, cost or efficiency
improvement is generated.

## Structured compatibility

Each check has an ID, status and concise explanation. Statuses are
`compatible_within_checked_limits`, `warning`, `incompatible`, `insufficient_data`.
Overall status precedence is incompatible, insufficient data, warning, then checked.
An individual compatible check does not mean the entire hardware system is compatible.

Checks cover gross/usable energy, battery voltage ordering, battery-to-inverter and
motor-drive DC voltage containment, DC/DC and charging voltage ranges, rated/peak
power order, assumed motor electrical demand versus inverter AC output ratings,
gearbox input torque, defined DC operating voltage/current versus battery and inverter
DC ratings, and nominal-voltage charging current acceptance.

Motor powers are mechanical; inverter power fields are **AC output** ratings. Their
comparison uses the explicit assumed motor efficiency; technology labels never supply
that efficiency. DC current and motor phase current are not interchangeable. A phase
current check remains insufficient without torque-current/back-EMF/control maps.
Peak-rating durations are unknown in representative records and remain insufficient,
not inferred from continuous power or a marketing peak. A requested charging peak
above the declared nominal current acceptance creates a warning, not a claim that it
can be sustained. No charging curve or connector/safety validation is performed.

Structural type/range/version violations reject the document. Cross-component
incompatibilities are returned in structured checks so an infeasible design can be
inspected/saved without being silently replaced. Incompatible checks block adapter
preparation. Unknown inputs remain explicit, and necessary nameplate checks are not
sufficient for thermal, packaging, transient, safety or production compatibility.

## Explicit retained-model adapter

`adapter.py` constructs the existing `HighPerformanceVehicle`, `ElectricMotor`,
`Transmission`, `LongitudinalSimulator` and `EnergyBattery`. It does not modify or
copy their equations. It intentionally does not force a `RunConfig` mapping because
that legacy contract cannot preserve arbitrary Cd, frontal area, wheel radius and
reduction ratio. The actual retained model objects receive these values directly.

| Model input                                        | Mapping                                                                      |
| -------------------------------------------------- | ---------------------------------------------------------------------------- |
| Vehicle mass                                       | Explicit total mass above                                                    |
| Cd, frontal area, rolling resistance, wheel radius | Direct body fields                                                           |
| Motor maximum torque, power, speed                 | Explicit peak torque/power and maximum RPM; no unspecified defaults          |
| Transmission                                       | One selected reduction ratio, explicit mechanical efficiency, gear zero      |
| Road                                               | Friction/air density direct; `grade_rad = atan(grade_percent / 100)`         |
| Battery usable model reservoir                     | Explicit usable kWh as model chemical-energy capacity                        |
| Battery state and limits                           | Explicit initial SOC, nominal voltage, resistance, charge/discharge currents |
| Drive conversion assumption                        | Explicit motor efficiency × inverter efficiency                              |
| Regeneration conversion assumption                 | Explicit regeneration efficiency assumption                                  |

Readiness identifies incompatible checks or missing model inputs. If the required
mapping data exist, state is `requires_acknowledgement`; `ready` remains false until
all assumption IDs are supplied to POST `/adapter`:

- `illustrative_parameters`
- `constant_efficiency`
- `constant_ocv`
- `longitudinal_only`
- `unmodelled_thermal_charging`

The adapter returns `prepared_for_model_inspection`, mapped inputs and scope after
constructing real model objects. This is preparation **only**, not an executed Lab
experiment or a fully coupled vehicle runner. Mechanical dynamics and the retained
battery are separate objects; battery/inverter power limits are not yet coupled back
into a new design experiment. The next verified runner integration must enforce that
coupling rather than quietly claiming achieved motor performance.

The retained battery uses fixed OCV/resistance, chemical-energy SOC and its own fixed
voltage-window assumptions; declared pack voltage limits are compatibility inputs,
not a new electrochemical model. Minimum/maximum voltage labels do not change that
model. Motor thermal duty, continuous/peak duration, inverter phase maps, ageing,
charging curves, auxiliary demand, thermal behaviour, pack safety and physical accuracy
are unsupported. Explicit acknowledgement does not supply missing physical evidence.

## Specification comparison and persistence boundary

POST `/compare` accepts baseline/modified snapshots (128 KB aggregate cap), evaluates
both through the same calculation function and returns supported specifications,
unit-labelled differences and changed input parameters. A missing operand yields
null delta, never zero or a fabricated improvement. Comparison is of actual declared
specifications, not simulated outcomes, ranked efficiency or optimality.

The browser library holds bounded validated snapshot records and one active design;
its persistence policy and UI are documented in architecture/progress. The backend
adds no account/database/file-write service. Importing a saved record must pass the
same versioned validation. Preparing a model does not persist a simulation result.

## Verification

`tests/test_design_engineering.py` contains independent arithmetic references,
including exact 1500 kg mass accounting, 200/180 Ah approximations, 200 A DC current,
900 N·m wheel torque and 0.5 m² drag area. Tests cover null propagation, deterministic
hashes, strict schema/version/unit metadata, invalid envelopes and all four check
states, catalogue overrides/custom refs, API bounds/comparisons and acknowledgements.
An adapter test inspects actual retained model fields and independently checks one
force/acceleration step with non-default Cd/area/radius/ratio/grade. These are software
and equation checks, not physical vehicle validation. Phase 8 remains INCONCLUSIVE.

## Browser library and editing

Design Studio is loaded on demand. One shared active design is used across workspaces;
only saved records survive reload. The library is local to the browser origin
(including port), bounded to 16 records and 180 KB of UTF-8 JSON. It stores selected
IDs/catalogue version and resolved parameters, not duplicate source records or
calculated results. Renaming applies through Save; Duplicate creates a separate
snapshot; Delete/Reset ask for confirmation. Unsaved drafts do not replace the saved
record. Export JSON is the portable backup; clearing browser data removes local designs.

Stored envelope/version/size is checked before use, and active/restored or selected
snapshots are validated by the backend before engineering results are displayed.
Corrupt data is left untouched; blocked/full storage is reported and JSON export
remains available. Cross-browser synchronization/accounts are not implemented;
concurrent tabs use last saved state and users should avoid editing the same library
in multiple tabs. No automatic v1 mass-boundary conversion is attempted.

Input changes invalidate displayed status and are debounced 250 ms; a generation
guard/AbortController prevents stale results replacing current ones. Inactive editor
timers/requests are cancelled. Component catalogue data is cached once per session;
no periodic reevaluation, continuous rendering, background WebSocket or simulation
executes in Anatomy/Design. Compare returns actual parameter/specification differences
from the same backend equations; it is not a simulated outcome or efficiency ranking.
