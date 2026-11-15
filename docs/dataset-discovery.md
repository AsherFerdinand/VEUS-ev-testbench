# Dataset discovery and suitability assessment — Phase 8

**Full physical vehicle validation remains pending.** Genuine public measurements
were obtained, but their missing operating-condition evidence prevents the broad
claim requested in the long-term project objective. Numerical improvements below
are exploratory electrical comparisons, not validation of predicted vehicle speed.

## Accessible source: University of Michigan Vehicle Energy Dataset (VED)

- Publisher/research: Geunseob Oh, David J. LeBlanc and Huei Peng, University of
  Michigan. [Repository](https://github.com/gsoh/VED), [paper DOI](https://doi.org/10.1109/TITS.2020.3035596).
- Source snapshot: `6baa4963782d515a67d32a5490bd5d11f5d9bf0d` (read-only Git lookup).
- README, LICENSE, repository/Data listing and direct archive/static-file HEAD
  requests returned HTTP 200. Licence text is Apache-2.0 and is retained under
  datasets/ved/UPSTREAM-LICENSE.txt; attribution/selection notice is in that folder.
- Publisher describes 383 vehicles, including three pure EVs, all 2013 Nissan
  Leafs with advertised 24 kWh batteries. Static sheet identifies vehicle 10 as
  EV with generalized weight 3500 lb. This is a fleet weight bin, not measured
  curb-plus-payload mass. Transmission detail is unavailable in that row.
- Relevant published signals: Timestamp(ms), Vehicle Speed[km/h], HV Battery
  Current[A], HV Battery Voltage[V], HV Battery SOC[%], OAT[DegC]. OAT is outside
  air temperature, **not battery temperature**. There is no motor shaft torque,
  propulsion/brake demand, gear ratio or measured road gradient in the listed
  dynamic columns. Coordinates cannot substitute for independently known grade.
- Sampling is irregular OBD logging, not a verified fixed-frequency instrument.
  In selected trip 1558: 74 rows over 50.4 s, intervals 0.1..1.1 s, median 1.0 s.
  Trip 1561: 111 rows over 72.1 s, intervals 0.1..1.1 s, median 0.9 s. Other
  inspected portions had gaps up to 9.6 s; those gaps were not silently filled.

### Download budget and preservation

| Upstream file | Verified size | Action |
|---|---:|---|
| Data/VED_DynamicData_Part1.7z | 82,723,769 bytes | Downloaded once outside the Git checkout; streamed only the needed CSV member |
| Data/VED_DynamicData_Part2.7z | 93,662,910 bytes | HEAD checked; not downloaded |
| Data/VED_Static_Data_PHEV&EV.xlsx | 9,763 bytes | Downloaded and inspected using standard ZIP/XML reading |

Part1 SHA-256: `44d53754fd39e196171ec09f123604375d0248d5c06a97d6695ef0e22a948c61`.
This is the hash of the retrieved pinned source, not a fabricated publisher checksum.
The unchanged archive remains outside the repository. Only two small projections
are committed: 3,574 and 5,373 bytes. Source row numbers, member, hashes and time
windows are preserved in datasets/ved/provenance.json. GPS/unrelated columns are
omitted; retained measurement values are unchanged. Selection used sampling
continuity before fitting, not residual size. The second trip was not used to fit.

### Suitability decision

**Predictive motion validation: unsupported.** Speed alone does not identify
propulsion, braking, grade, payload, tyre conditions or drivetrain losses. VEUS
never forces the measured speed trace and labels that agreement predictive.

**Local electrical model exploration: possible, but not qualified physical
validation.** Two independent trips provide current/voltage/SOC. The importer
explicitly inverts reported current to a discharge-positive convention. This is
an unconfirmed hypothesis consistent with the inspected load/voltage behaviour,
not a sign definition located in publisher documentation. Pack temperature,
current/voltage acquisition uncertainty/synchronization and BMS definitions are
unknown. Trip SOC differs substantially (roughly 96% versus 71%), violating a
strong constant-OCV transfer assumption. Both experiments therefore retain
`inputs_verified: false` and overall INCONCLUSIVE evidence status.

A training-only local Voc/R regression and distinct-trip comparison demonstrate
framework operation on real measurements. They cannot validate the whole EV,
identify globally physical resistance/OCV maps, or establish ADAS safety.

## Other credible candidates

| Candidate | Access evidence | Signals/units/sampling/licence/size | Decision |
|---|---|---|---|
| [Argonne D3 Downloadable Dynamometer Database](https://www.anl.gov/taps/d3-downloadable-dynamometer-database) | Proxy returned 403 before origin | File-specific contents, usage terms and size not verified here; no files downloaded | Potential future controlled-test source, not selected or claimed inspected |
| [EPA dynamometer drive schedules](https://www.epa.gov/vehicle-and-fuel-emissions-testing/dynamometer-drive-schedules) | Proxy returned 403 before origin | Current downloadable files/licences/sizes unverified here | Prescribed speed schedules are not independent measured vehicle response; unsuitable alone for predictive validation |

A network-policy rejection is not evidence that a public dataset does not exist
or that the user needs credentials. No restricted data, multi-gigabyte download
or unverified permission bypass was used. No experimental uncertainty, licence
permission or source sampling frequency was invented when unavailable.

## What is needed for qualified validation

Obtain a documented torque/brake/grade/mass/gear dataset for motion prediction,
or a battery dataset with confirmed current polarity, synchronization, pack
capacity definition, initial state, temperature and voltage/current uncertainty.
Keep distinct runs for calibration and held-out evaluation. Reassess model scope
before asserting inputs verified; that field is a provider assertion, not software
authentication. Report failed criteria and model inadequacy without tuning on the
held-out trip. Calibrating a constant-OCV model across different SOC is not a
substitute for identifying OCV(SOC,T) and dynamic impedance from experiments.
