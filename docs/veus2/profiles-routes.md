# Driving profiles and route evidence (2.3)

The Simulation Lab uses the [coupled engine](simulation-lab.md), not separate cycle equations. Achieved speed/SOC/terminal energy remain separate from requested speed-trace demand in both operating modes. Predictive mode uses feedforward with tracking feedback; prescribed mode requests the inverse step demand, with a physically constrained companion trajectory. Neither mode forces impossible vehicle motion.

## Sources and provenance

The catalogue distinguishes original illustrative urban, motorway, stop-go and constant-reference traces from **FASTSim-distributed UDDS/HWFET references**. The latter are copied unchanged from NatLabRockies/fastsim commit `6a07d4d816c847d500315a4e5759e157853c563b`, under its Apache-2.0 distribution. Original licence and NOTICE, URLs, byte hashes, units and retrieval date are in `datasets/cycles/`. UDDS has 1370 samples over 1369 s (11990.433189 m trapezoidal demand distance); HWFET has 766 over 765 s (16506.817471 m). These distributions have not been independently compared with EPA originals and do not establish regulatory compliance. Their zero-grade channel is an assumed flat cycle, not surveyed terrain.

Source investigation is recorded in [source-investigation.json](evidence-2.3/source-investigation.json). Direct EPA/UNECE and geographic endpoints were blocked during this environment's investigation. No verified, licensed Nordschleife geometry, elevation and timed speed source was obtained. There is no Nürburgring dataset or lap-time claim. The included local-loop CSV is explicitly synthetic, near 0° latitude/longitude, with invented elevations solely to exercise the interface.

## Import contract

`POST /api/lab/import/profile` and `/import/route` take `{csv_base64, configuration}`. UTF-8 CSV is bounded to 2 MB, 5000 samples and 30 unique columns. Map column names explicitly (`time`, `speed`, `distance`, `latitude`, `longitude`, `elevation`, `grade`); choose s/ms, m/s or km/h, m/km and percent/fraction. Nonfinite samples, duplicates, decreasing indices, missing required values and out-of-range values are rejected. Original bytes are hashed; original index origin and unit choices are retained. Indices normalize to zero without resampling. Nothing fetches a user-supplied URL.

Timed speed profiles require time and speed. Geometry-only routes require distance, or the explicit `haversine_chords` distance policy with complete coordinates; derived chord length is not measured road distance. Optional time/speed channels allow a combined route file to supply a timed profile. Otherwise select a separate profile or an explicit constant-speed experiment. Missing coordinates/elevation remain null: time-only files have a time/distance display, never an invented map.

Speed and supplied grades interpolate linearly within adjacent valid samples. The derivative at a knot follows the next segment (last endpoint uses the preceding segment). Time gaps over `max_gap_s` (default 2 s) are rejected when encountered. Route gaps over `max_gap_m` (default 1500 m) remain uncovered. No loop, extrapolation, endpoint clamping or silent repair fills coverage. Elevation differences provide piecewise-constant grade if supplied grade is absent; provided grade takes precedence and disagreement is diagnosed. GPS/distance disagreement is reported, not silently reconciled. These simplified interpolants are unsuitable for coarse GPS corner reconstruction or abrupt elevation discontinuities.

By default unavailable grade/route coverage blocks execution. A user may explicitly select the constant-grade assumption; that assumption is recorded in trace flags and provenance. Predictive route position follows achieved distance; prescribed route position follows requested integral distance. Exported `route_basis`, `route_position_m` and `requested_position_m` make that distinction explicit. Coordinates are sampled source geometry, never measured vehicle GPS.

## Reproducible studies

Run `python scripts/lab_studies.py --output /tmp/veus-lab-studies`. It writes frozen input snapshots, hashes and summaries to JSON, full CSV traces and standalone HTML reports. [Recorded summaries](evidence-2.3/studies.json) contain exact parameters. Values below describe this illustrative model, not tested vehicle performance.

At 100 km/h on a flat road, mass 1748 kg, frontal area 2.2 m², density 1.225 kg/m³, Crr .012 and constant forward efficiencies .94 × .97 × .97, lowering Cd .28 → .22 changes aerodynamic force **291.127 → 228.742 N**, wheel power **13.803 → 12.070 kW**, terminal DC power **15.606 → 13.647 kW**, and consumption **15.606 → 13.647 kWh/100 km** (12.55% lower). Independent force balance `F=.5ρCdAv²+Crrmg`, `Pdc=Fv/η` agrees within 1e-9 kW. Internal heating is additional stored-energy depletion, not double-counted terminal consumption. No auxiliaries, wind, thermal effects or speed variation are included.

For the same design, predictive runs at dt=.1 s give:

| Profile | Distance km | Net terminal kWh/100km | Discharge kWh | Recovered kWh | Battery heat kWh | Conversion loss kWh |
|---|---:|---:|---:|---:|---:|---:|
| Illustrative urban | .8610 | 11.7301 | .14821 | .04721 | .00112 | .03945 |
| Illustrative motorway | 4.1667 | 16.2808 | .77790 | .09953 | .00656 | .13695 |
| Sourced HWFET reference | 16.5068 | 13.1776 | 2.32018 | .14497 | .01157 | .33664 |

Requested demand is feasible in these cases; tracking error is below 1e-12 m/s and no friction-brake energy is needed. Urban recovery is 31.9% of discharge versus 12.8% for this motorway trace. The urban trace's lower speeds reduce aerodynamic work, while repeated acceleration/braking increases reverse-conversion losses relative to distance. These are different traces and durations, not a controlled experiment isolating a single effect. The separate Cd experiment provides that controlled comparison. Retained Euler distance and mean-displacement work differ by O(dt); a small urban distance error remains even with essentially exact speed tracking. Physical validation is **INCONCLUSIVE**.
