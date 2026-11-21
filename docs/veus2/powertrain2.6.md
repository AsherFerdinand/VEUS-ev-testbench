# Optional motor efficiency map — Checkpoint A

`efficiency_model: "illustrative_map"` selects the new operating-point model in
Lab/Insights requests. Omit it or use null for the exact legacy constant model.
Null is omitted during serialization, preserving historical request hashes, results
and export bytes. No existing vehicle parameter, map-less numerical default or
historical report is reinterpreted. No dependency is added.

## Map, interpolation and operating region

`veus/model/efficiency_map.py` owns one small illustrative normalized map, with
separate motoring and regenerative grids. RPM fraction uses selected maximum motor
RPM; torque fraction uses selected continuous or explicitly supported peak rating.
These scales are explicit assumptions, not manufacturer maps, chemistry effects or
measurements. All grid values and scaling are frozen inline in mapped run provenance,
with a map ID/hash and region description. Returned metadata is copied so a caller
cannot mutate later map calculations through a result object.

Bilinear interpolation is permitted only within the RPM/torque grid and the retained
`ElectricMotor.max_available_torque` envelope: constant torque, then constant power,
then zero torque at maximum speed. No data are extrapolated. The illustrative reverse
motor torque limit is explicitly **70% of that selected envelope**. This is a declared
model assumption, not a measured regenerative rating. Unsupported achieved operating
points reject the run; unsupported ideal requested points are marked unavailable,
with requested energy totals null rather than a silently partial integral.

Grid coefficients at zero power do not imply standstill copper losses. Motor
phase-current, temperature, transient overload and thermal endurance remain unmodelled.
Mapped peak operation requires both motor and inverter peak durations to be supplied,
plus the existing acknowledgement; the run must fit their declared duration. Unknown
sustained peak capability is not invented. Legacy peak-policy behaviour is unchanged.

## Shared coupling and power balance

Small overridable hooks in `SimulationSession` retain the existing energy-step,
mechanical integration and torque bisection. Their constant implementations preserve
operation ordering and the old numerical result. Map mode supplies motor efficiency
at **actual delivered shaft torque/RPM**, including each candidate evaluated during
discharge limiting. A requested torque coefficient is never reused after clipping.

Motoring boundaries:

`P_wheel = P_shaft × η_gear`

`P_AC = P_shaft / η_motor(rpm, torque)`

`P_DC = P_AC / η_inverter`.

Regeneration reverses those boundaries:

`|P_shaft| = |P_regen,wheel| × η_gear`

`|P_AC| = |P_shaft| × η_motor,regen(rpm, torque)`

`|P_DC,recovered| = |P_AC| × η_inverter`.

Motor, inverter and gearbox efficiencies are applied once each. The mapped reverse
motor coefficient replaces the legacy combined reverse motor/inverter assumption;
that legacy factor is not multiplied again. Inverter efficiency remains the user's
explicit constant assumption in both directions; no inverter switching map is claimed.

Selected torque–speed, average shaft-power, inverter AC/DC/current/voltage, battery
current/SOC and fixed voltage-window constraints remain active. Motor and inverter
power caps are checked using the interpolated efficiency rather than the old constant
motor coefficient. Regenerative mechanical work is bounded by motor torque/power and
charge acceptance through a monotone bisection. Friction supplies remaining achieved
braking. Battery full/zero acceptance does not create fictitious recovered energy.

Mapped traces alone add `motor_rpm`, `motor_efficiency`, `inverter_efficiency`, signed
`motor_ac_power_w`, nonnegative motor/inverter/gear loss powers and their cumulative
joules. Existing signed shaft torque/power are retained. With the common convention
of positive power toward wheels, inverter loss is `P_DC - P_AC`, motor loss is
`P_AC - P_shaft`, and gearbox loss is `P_shaft - P_wheel`, in either flow direction.
Their sum agrees with the existing combined conversion-loss accounting. Battery
resistive heat remains separate. Initial diagnostic losses are zero because no
integration interval has elapsed.

Mapped summaries add separate component loss energies; map metadata/model choice are
present only for mapped runs. Insights previews retain the extra operating-point
fields and metadata; their preview-only sampling disclosure and full-run reproduction
hashes remain. Comparing maps at matched conditions measures **model-choice effects**,
not an improvement in a physical vehicle.

## Numerical and validation scope

The selected maps have monotone load-to-input/recovered-power behaviour within their
supported region, consistent with bounded coupling searches. Focused tests cover
independent bilinear arithmetic, no-extrapolation boundaries, retained torque/power/
maximum-speed envelope, copied provenance metadata, regeneration signs, component
loss sums, conservation residual, current/SOC/continuous limits, unknown peak-duty
rejection, deterministic urban cycling, exports and Insights passthrough. Legacy
fingerprint tests assert the exact old result hash and JSON/CSV/HTML bytes.

Existing fixed OCV/resistance, Euler-position versus mean-work displacement, no
auxiliaries and no thermal/ageing/phase-current map limitations persist. This adds an
optional illustrative motor operating-point model, not real-world calibration or
physical validation. Physical validation remains **INCONCLUSIVE**.

A discrete step can cross the motor RPM limit from a valid starting operating
point. Subsequent zero-torque coasting does not query or extrapolate the map:
shaft/AC conversion power is zero and efficiency is unavailable (`null`), with
`zero_power_outside_map_efficiency_unavailable` in the trace limits. This is a
time-step boundary effect, not permission to produce torque beyond the map.
Initially out-of-region speed remains rejected. All three illustrative presets
are checked over the default urban cycle and 30-second acceleration experiment.
