# Future NASA battery SOH project integration

`veus/model/soh_interface.py` defines data contracts and a Protocol, not a working
NASA estimator or calibrated battery model. No NASA data was downloaded, fitted
or validated in this increment. VEUS does not implement the separate SOH project.

CapacitySOHEstimate exchanges dataset/battery identity, estimator version, timezone-
qualified measurement time, cycle index, capacity SOH fraction, reference Ah,
test temperature/discharge rate and optional uncertainty interval. The interval
has no implied confidence probability; the estimator must document its meaning.
This schema describes **capacity** SOH relative to a stated capacity reference,
not an interchangeable power-health or internal-resistance SOH. Ratios slightly
above 1 may be legitimate relative to a nominal baseline; bounds are data-contract
checks, not physical battery safety limits.

BatteryParameterProvider.parameters(estimate, context) is a future calibrated
adapter. Context includes SOC, temperature, requested current and pack topology.
Its result must supply independently justified energy capacity, OCV, resistance,
charge/discharge current limits, calibration identity and evidence reference.
There is intentionally no automatic `R = R_new / SOH`, voltage scaling, power
scaling, or `capacity_kWh = nominal_kWh * SOH` implementation. The SOH contract
cannot be passed directly to EnergyBattery as an electrical parameter set.

Before implementing an adapter, obtain and validate:

1. Exact dataset provenance, battery chemistry, nominal/measured capacity definition,
   units, discharge cutoffs, cycle conventions and train/test separation.
2. Capacity-versus-temperature/rate and aging data; Ah-to-Wh conversion needs
   voltage-versus-SOC/load integration, not only an Ah capacity ratio.
3. OCV(SOC, temperature, age) characterization independent of loaded voltage.
4. Pulse/current-transient resistance or equivalent-circuit identification across
   SOC/temperature/age; uncertainty and out-of-distribution handling.
5. Independent manufacturer/cell-test voltage, thermal, charge-acceptance and
   current/power constraints; SOH alone does not determine these limits.
6. Cell-to-pack series/parallel scaling, cell imbalance and limiting-cell behaviour,
   BMS protection policy, thermal model and cooling assumptions.
7. Held-out experimental voltage/current/energy/temperature measurements with
   error metrics and uncertainty propagation from SOH into scenario outcomes.

A future adapter should reject unsupported operating conditions and missing
calibrations, preserve calibration IDs in every scenario/report, and avoid claiming
transfer from NASA bench cells to this illustrative EV pack without supporting
measurements. Existing dashboard defaults and batch scenarios remain independent
of any SOH estimate until that evidence and adapter exist.
