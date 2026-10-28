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

Current is kept with its original sign in these files. Runtime import mapping
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
