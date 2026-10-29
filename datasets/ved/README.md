# Small measured VED projections (not synthetic)

Source: Geunseob Oh, David J. LeBlanc and Huei Peng, University of Michigan,
[Vehicle Energy Dataset](https://github.com/gsoh/VED), paper
[10.1109/TITS.2020.3035596](https://doi.org/10.1109/TITS.2020.3035596).
Upstream licence: Apache-2.0; full upstream text is in UPSTREAM-LICENSE.txt.

Modifications: selected rows and six relevant columns from the upstream CSV;
GPS/engine/fuel columns omitted. Retained numeric text values were not altered.
CSV packaging/line endings are a derived representation, not the original archive.
Trip 1558 is designated calibration; distinct trip 1561 is held out. Their source
row identities, archive/member hashes and selection rules are in provenance.json.
No large raw archive is committed. Read docs/dataset-discovery.md before reuse.

Current is kept with its original sign in these files. The Phase 8 validation import mapping
inverts it under an explicitly **unconfirmed** sign hypothesis. These experiments
cannot establish physical vehicle validity: propulsion/braking/grade, battery
thermal/synchronization and uncertainty evidence are missing. Dataset source
identity is genuine; operating-condition sufficiency is not assumed.

The application needs only these small CSVs. To reproduce extraction optionally,
download the pinned Part1 archive from the source and run:

```text
python scripts/extract_ved_subset.py path/to/VED_DynamicData_Part1.7z --output NEW_DIRECTORY
```

That separate acquisition helper requires libarchive-c and native libarchive;
they are **not application dependencies** and need not be installed on a Windows
laptop to run the checked-in examples. It checks the archive and subset hashes.

Phase 10 replay reuses these exact files with separate `examples/replay` settings.
Those imports retain raw current sign (+1 mapping) and unknown polarity, rather
than assuming the Phase 8 inversion hypothesis. Replay roles are descriptive
exploration only; original calibration/holdout experiment roles and findings are
unchanged. Replay additionally maps the measured outside air temperature; it is
not battery temperature. See [the replay guide](../../docs/real-world-replay.md).

## Phase 11 full member groups

`ved-10-1561-full.csv` (534 rows, 460.4 s) and `ved-10-1567-full.csv`
(367 rows, 370.3 s) retain every vehicle/trip row in the inspected first weekly
member. They are not concatenations and do not prove that an entire physical
journey was captured. Selection uses the first two chronological multi-minute
vehicle-10 groups, without event/residual filtering. The original short fixtures
remain unchanged; the full 1561 group overlaps the earlier short window.

[full-recordings-provenance.json](full-recordings-provenance.json) records pinned
source, exact source line ranges, timestamps, hashes, licence and modifications.
The six-column numeric strings retain source units and raw current sign. The
23/34 timestamp gaps remain present; unknown travel is not filled. Use separate
`examples/replay/*-full.json` configurations with unknown polarity. No energy,
regen, SOH or physical-validation conclusion follows.

Optional reproduction (libarchive-c + native libarchive, not app dependencies):

```text
python scripts/extract_ved_recordings.py path/to/VED_DynamicData_Part1.7z --output NEW_DIRECTORY
```

Only small CSV projections are committed. See the
[investigation guide](../../docs/real-world-investigation.md) and
[executed case](../../docs/phase11-evidence/README.md).
