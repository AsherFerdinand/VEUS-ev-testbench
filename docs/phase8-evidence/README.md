# Phase 8 executed evidence

Report execution commit: `3001d0b` (clean working tree). The following evidence
commit adds documentation/artifacts only. Python 3.12.14, NumPy 2.5.4 and
Matplotlib 3.10.7; exact hashes, configurations, fitted parameters, software
versions and provenance are in [summary.json](summary.json).

**Real-world vehicle validation remains pending.** Genuine measured VED records
were obtained, but the available conditions do not qualify predictive motion
validation or physical electrical acceptance. These are small exploratory windows,
not evidence of representative full-drive-cycle accuracy.

| Experiment | Original held-out RMSE | Calibrated held-out RMSE | Criterion | Outcome |
|---|---:|---:|---:|---|
| Synthetic battery | 12.1404 V | <1e-10 V | 0.001 V | PASS, synthetic only |
| Synthetic coast, two parameters | 0.385989 m/s | 0.0266573 m/s | 0.02 m/s | FAIL, synthetic only |
| VED vehicle 10, trip 1561 | 21.7862 V | 7.89089 V | 2 V | Numerical FAIL; overall INCONCLUSIVE |

Use the machine-readable summary for exact battery metrics. The coast training
RMSE is approximately 0.00227 m/s, yet its held-out criterion fails. Correlated
parameters and finite grid resolution restrict recovery; a training fit does not
establish transferability. Acceptance criteria were not weakened.

The VED fit on trip 1558 estimates constant Voc approximately 386.618 V and local
R approximately 0.075454 ohm, with training voltage RMSE approximately 2.654 V.
These coefficients depend on an unconfirmed current-sign hypothesis. Pack
conditions, synchronization and measurement uncertainty are unknown; the held-out
trip differs in SOC. The 2 V target is an illustrative development criterion,
not an instrument specification or externally validated standard. These results
do not validate a global resistance/OCV map, SOC model or safety behavior.

For the declared synthetic coasting sensitivity ranges, RMS speed spans rank:
grade offset 6.334 m/s, rolling resistance 1.899 m/s, drag area 0.680 m/s,
mass 0.217 m/s. This is an original-model one-at-a-time range study. The ranking
depends on specified ranges and operating conditions; it is not identification.

Standalone HTML reports (download the repository and open locally):

- [Measured VED held-out comparison](ved-holdout.html)
- [Synthetic battery held-out comparison](battery-holdout.html)
- [Synthetic coasting comparison and sensitivity plots](coast-holdout.html)

## Checks executed

- All 134 automated tests pass, preserving the original 109-test baseline.
- All 11 analytical reference traces pass.
- Original ADAS batch: six PASS, two FAIL (delayed braking and low grip collide).
- Sensor batch: four PASS, three FAIL (radar latency/bias collide; speed bias
  fails tracking). These failures remain unchanged, with batch exit code 1.
- Browser: synthetic calibration followed by distinct-run evaluation, actual
  measured-data INCONCLUSIVE/FAIL classification, HTML export and mobile layout
  pass, with no JavaScript page errors.
- Optional reporting libraries are not required to import the driving app;
  a subprocess import-blocking regression test verifies this.
- CSV subsets reproduce byte for byte from the pinned VED archive using the
  optional extraction helper. Source/configuration artifact hashes were checked.
- Dependency consistency, changed-file Python lint, JavaScript syntax and
  whitespace checks pass. Repository-wide lint also finds three pre-existing
  unused imports in unrelated files; those files were preserved.
- One existing Starlette/httpx deprecation warning remains in the test suite.

Coverage: 94.75% statements, 82.58% branches, 92.11% combined.
Coverage details are in [coverage-summary.json](coverage-summary.json). Coverage
is an implementation check, not evidence of physical validity.

## Reproduction

See [the Windows/CLI guide](../vehicle-validation.md), including commands for
synthetic fits, held-out evaluation and sensitivity. For measured experiments:

```bat
python -m veus.validation calibrate examples/validation/ved-10-1558.json datasets/ved/ved-10-1558.csv --settings examples/validation/battery-calibration.json --output reports/ved-fit-001
python -m veus.validation evaluate examples/validation/ved-10-1561.json datasets/ved/ved-10-1561.csv --calibration reports/ved-fit-001/calibration.json --output reports/ved-holdout-001
```

Both measured commands intentionally return exit code 1 for INCONCLUSIVE.
The calibration artifact is still saved. Run the second command separately,
not through a success-only shell chain. Exit 2 indicates invalid inputs/setup.
Use a new output directory each time; previous results are never overwritten.
Large raw archives are excluded from Git. Dataset acquisition, licence, exact
row selection, hashes and suitability limits are documented in
[dataset discovery](../dataset-discovery.md) and [the VED subset record](../../datasets/ved/README.md).
