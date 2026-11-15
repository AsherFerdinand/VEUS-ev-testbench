# VEUS Data Readiness Check

Readiness answers **what this data can support in the existing software**, under
explicit scope and assumptions. It is not a measurement certificate, model
validation verdict or automatic guarantee of trustworthy provenance. All Phase 8
physical-validation conclusions remain unchanged.

## User workflow

In Analyse → Data Readiness, inspect a bundled recording or upload a UTF-8 CSV.
Structural inspection returns headers, record count, three original preview rows,
source SHA-256 and alias suggestions. It does not validate engineering meaning.
Choose/correct columns, confirm units and declare measured/synthetic origin.
Review mapping signs: +1 retains a source sign, not a positive-discharge or
positive-propulsion assertion. Current polarity is a separate field, defaulting
to unknown. Confirm before **Check data readiness** runs the existing import rules.

Bundled mappings are proposed from their documented config, with units shown;
they still require confirmation. Uploaded aliases do not preselect units, even
when a column name contains a unit hint. Ambiguous aliases leave the column
unselected. Optional mappings stay in a collapsed section. Editing inputs clears
previous readiness and its proceed action; invalid data is never silently repaired.

Successful results include capability cards, concise explanations, further-data
suggestions and expandable quality/provenance. Proceed to replay is enabled only
with at least one valid adjacent speed interval. It passes the actual CSV bytes
and confirmed ReplayConfig to the existing analysis endpoint. It does not replace
or recalibrate the simulation. Export readiness JSON preserves the assessment,
configuration, registry requirements, assumptions and a deterministic hash.

## Import contract and quality

Time is numeric seconds or milliseconds. Time normalization subtracts the first
row explicitly, while the original origin is retained. ISO date strings are not
accepted. Time must be finite and strictly increasing, with at least two rows.
Duplicate/non-monotonic/missing times are rejected; duplicates are not removed or
averaged. Valid reports show duplicate count zero because the import contract
rejects other cases. Rejection messages explain the failed rule.

The shared Phase 8 `csv_structure` helper validates UTF-8/BOM, unique headers,
row lengths and row limits. Both inspection and `load_csv` use it; there is no
second incompatible parser. `load_csv` performs hash, unit, numeric/range,
missing-value and timestamp checks. Replay's shared `validate_window` applies
its existing sanity/window limits to readiness too. Import limits remain 2 MB,
5000 rows, one elapsed day and 3 MB JSON requests for these interactive tools.
Blank/NA/NaN/null field tokens remain missing; infinity and invalid numeric values
are rejected. Negative forward speed, nonpositive voltage, SOC outside 0..1 and
broad replay sanity violations are errors. No interpolation repairs samples.

Default gap limit is 2 s and is editable in Advanced evidence. The same rule is
preserved on handoff. Gaps/missing required values make partial inspection or
replay CONDITIONAL; complete-window energy/model-input readiness can be UNAVAILABLE.
All-missing signals do not count as valid just because a mapped header exists.
Disjoint V/I samples cannot produce signed power. No adjacent speed intervals
means no recorded motion; incomplete acceleration stencils cannot differentiate.

## Recognized versus supported

Supported canonical mappings come from the existing measurement schema:

| Meaning | Canonical field | Explicit accepted units |
|---|---|---|
| Time | time_s | s, ms |
| Speed | vehicle_speed_ms | m/s, km/h, mph |
| Voltage | battery_voltage_v | V |
| Signed current | battery_current_a | A |
| SOC | battery_soc | fraction, % |
| Motor torque | motor_torque_nm | Nm |
| Motor speed | motor_speed_rad_s | rad/s, rpm |
| Brake force | brake_force_n | N |
| Road grade | road_gradient_rad | rad, deg, % |
| Ambient air temperature | ambient_temperature_c | °C, C |
| Recorded acceleration | longitudinal_acceleration_ms2 | m/s2, m/s², g |
| Recorded power | battery_power_w | W, kW |
| Recorded position | position_m | m |
| Recorded energy | energy_wh | Wh, kWh |

Aliases include timestamp/time/time_s/Timestamp(ms), speed/vehicle_speed/speed_kmh,
voltage/pack_voltage, current/pack_current, soc/state_of_charge/soc_pct,
motor_torque/torque_nm, motor_speed/motor_rpm, grade/road_slope,
ambient_temp/outside_temperature and the actual VED headers. Matching ignores
case/outer whitespace for proposing candidates, not for modifying source headers.
Manual mapping handles other names. A source column cannot be mapped twice as
an independent input and a different output.

Throttle/accelerator_pedal and brake/brake_pedal are recognized as **unsupported
pedal channels** and explained, not falsely advertised as torque or brake force.
No pedal-to-force conversion, torque polarity, sensor calibration, measurement
accuracy or synchronization is inferred. Motor T/omega presence does not enable
an unimplemented efficiency estimator. Recorded power can still be inspected in
Replay, but the signed-V×I capability specifically requires joint V/I samples.

## Central capability registry

`veus/readiness/registry.py` supplies typed identifiers, display names, descriptions,
required/optional signals, quality conditions, required assumptions, workspace,
implemented status and scope explanations. The API evaluator and browser use the
same registry; the browser does not maintain a second requirements table/rules
engine. Advanced requirement details show the registry entries used by the result.

States:

- **AVAILABLE:** mapped valid samples and the named calculation's quality/evidence
  requirements are supplied. This is narrowly scoped software readiness.
- **CONDITIONAL:** a useful partial calculation is possible, or an important
  assumption/configuration/evidence condition is unresolved.
- **UNAVAILABLE:** required mappings/samples/conditions are invalid or absent,
  the supplied experiment lacks a needed reference, or the backend does not
  implement the analysis. Related columns alone do not override this.

| Capability | Required inputs and conditions |
|---|---|
| Recorded replay | Time/speed and a valid adjacent speed interval; partial samples/gaps are conditional, not fabricated motion |
| Speed/acceleration | Time/speed with a complete local secant-difference stencil; noise remains a limitation |
| Voltage inspection | Time and valid voltage samples; missing portions/gaps conditional |
| Signed current inspection | Time and valid current samples; polarity is not needed just to inspect a signed number |
| Signed electrical power | Time and jointly valid V/I; no discharge/regen interpretation, and no claim that co-located fields prove synchronization |
| Electrical energy | Complete joint V/I/time coverage with no large gaps; known evidenced polarity plus documented synchronization and measurement quality |
| Regeneration-specific energy | UNAVAILABLE in current backend; charging origin cannot be established just from V/I/deceleration |
| Motor efficiency | UNAVAILABLE in current measured-data backend; torque/speed/pack V/I do not isolate motor-boundary losses |
| Longitudinal validation inputs | Complete time/speed/drive-torque/brake-force/grade window, nonnegative mapped drive torque, measured origin, explicit compatible Phase 8 experiment and documented conditions/quality/conventions |

Regeneration-specific energy and motor efficiency stay unavailable even when all
related fields are supplied. Descriptions explain software and evidence boundaries.
No new mechanical-power, efficiency, physics or traffic algorithm is added.

## Engineering assertions and physical experiment guard

Known current polarity requires explicit evidence notes. Checked synchronization,
measurement quality, operating conditions and torque convention assertions require
nontrivial evidence notes as well; they are uploader claims, not authenticated facts.
For physical-model input readiness, use independent measured data rather than a
synthetic fixture. All required input/reference samples must be complete and the
existing plant expects nonnegative drive torque plus separate brake force.

An optional existing Phase 8 **Experiment JSON** must use `kind: dynamics`,
validation-role measured references, asserted verified input metadata with vehicle
identity/specifications, the identical CSV hash/dataset/run/vehicle ID and the
same unit/time mapping. Measured grade and a defined initial speed (or a valid
first speed sample) are required. Comparison outputs must include a kinematic
reference and actually be available under the existing Phase 8 preparation rules.
A missing explicit comparison reference makes the capability UNAVAILABLE without
suppressing other readiness cards. No experiment means CONDITIONAL if all its
signal prerequisites are present. A matching experiment with all supplied
assertions can be AVAILABLE **to take forward for evaluation**, not an evaluated
PASS. This check does not run physics, fit parameters or overturn earlier findings.

Required comparisons, initial/model configurations and evidence remain in the
existing Experiment contract. There is no new universal model-validation schema.
Other existing Phase 8 experiments (for example battery-current calibration)
remain accessible in Model experiments & calibration; the registry's longitudinal
physical-input card is not their generic substitute.

A readiness handoff retains original source/provenance/limitations and appends
unresolved conditional explanations to replay limitations. It does not silently
change a supplied current convention or weaken legacy Replay behavior. Existing
Replay can display assumption-based energy estimates under a declared known sign;
the readiness evidence state still distinguishes that from an established reliable
interpretation. Negative pack power is never automatically regeneration-specific
energy, even when a sign convention is supplied.

## Expected example assessments

- **Genuine VED trip 1561:** replay, speed/acceleration, voltage/current inspection
  and signed V×I AVAILABLE; energy CONDITIONAL (unknown polarity and missing
  measurement/sync evidence); regen-specific energy, motor efficiency and
  longitudinal physical validation UNAVAILABLE.
- **Synthetic template A:** replay and speed/acceleration AVAILABLE; electrical
  capabilities UNAVAILABLE due to absent V/I. Synthetic origin remains explicit.
- **Synthetic template B:** replay/electrical inspection/signed power AVAILABLE;
  energy CONDITIONAL until sign and quality assumptions are supplied, not inferred
  from the illustrative values. Physical-model validation remains unavailable.
- **Time/V/I without speed:** V/I inspection and joint signed power can be
  AVAILABLE; replay UNAVAILABLE. This is not the same result as a speed dataset.
- **Speed gaps/missing rows:** replay/derivatives may be CONDITIONAL or UNAVAILABLE
  depending on valid intervals/stencils. No full-window distance is invented.

Templates and the genuine VED source are described in [the workflow guide](user-onboarding.md).
The Readiness template downloads include CSV/config A/B and the unchanged Phase 8
synthetic battery reference, fitting settings and distinct holdout artifacts C.

## APIs, state and reproduction

- GET `/api/readiness/capabilities`: the central registry.
- POST `/api/readiness/inspect`: `{csv_base64}`; suggestions only.
- POST `/api/readiness/assess`: `{csv_base64, configuration, mappings_confirmed:true}`;
  confirmation is mandatory. ReadinessConfig contains source, preprocessing,
  current_sign/sign_evidence, assertions/evidence_notes, limits/limitations,
  optional provenance and optional existing Experiment.
- GET `/api/readiness/templates/{known-name}/{known-artifact}`: whitelisted
  attachment downloads, with no arbitrary filesystem access.

Quality results retain record count, elapsed duration, valid/missing sample counts,
strict timestamp status, zero duplicates for an accepted import, original units/
mappings, gap list, source classification, provenance and evidence. Source SHA-256
identifies exact input bytes. The assessment fingerprint uses the existing
normalized sorted canonical JSON function before inserting its own hash field.
It includes registry requirements and assertions so changes are reproducible.
No wall-clock generation date is used. Uploads are parsed in memory, not persisted
by these APIs; source/evidence claims can still be wrong and hashes do not prove
truth. The welcome preference stores only a local browser flag, never CSV data.

Tests cover proposals, explicit manual mapping, units/time rejection, signal
quality and disjoint/missing/gap conditions, evidence/polarity, unsupported analyses,
matching/missing-reference model inputs and real VED provenance. Browser tests
exercise first/returning/direct navigation, storage failure, readiness-to-replay,
error handling, download and laptop/mobile layouts. See
[actual execution evidence](phase10-1-evidence/README.md).
