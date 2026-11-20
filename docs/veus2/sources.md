# Engineering content and source catalogue

The machine-readable content lives in `veus/workbench/content.json`. Ten components
and eight challenges cite identifiable sources, with no invented statistics or
manufacturer specifications. Original SVG geometry was created for VEUS; the user's
EV cutaway, architecture, annotation, navigation and telemetry images informed the
information structure, not copied artwork or proprietary screen assets.

| Reference                                                                                                         | Scope                                                                   | Evidence classification                                                   |
| ----------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| [DOE AFDC: All-electric vehicle components](https://afdc.energy.gov/vehicles/how-do-all-electric-cars-work)       | Battery, motor, inverter, DC/DC, onboard AC conversion, thermal systems | Established component roles; not a product specification                  |
| [DOE AFDC: Electric vehicles](https://afdc.energy.gov/vehicles/electric)                                          | Technology overview and qualitative design context                      | Established qualitative principles, not quantified technology performance |
| [DOE AFDC: Charging infrastructure](https://afdc.energy.gov/fuels/electricity-infrastructure)                     | AC/DC charging distinction and infrastructure                           | Reference terminology, not a battery acceptance curve                     |
| [VEUS equations and limitations](../engineering.md)                                                               | Road loads, energy boundaries and model limitations                     | Explicit illustrative software assumptions                                |
| [SOH integration contract](../soh-integration.md)                                                                 | Additional parameters/evidence beyond capacity SOH                      | Future interface, not an ageing estimator                                 |
| [University of Michigan VED](https://github.com/gsoh/VED) and [retained provenance](../../datasets/ved/README.md) | Genuine vehicle-10 measurements                                         | Measured dataset; polarity/coverage limits retained                       |

## Source review scope

Repository sources were inspected. The VED page was successfully retrieved on
2026-11-20. The cloud proxy returned HTTP 403 for the three DOE AFDC domains/URLs,
so no retrieval/publication date or current webpage contents are claimed for them.
These are established reference citations, not newly authenticated specifications;
see [source-access.json](evidence/source-access.json) for actual attempts. Public
citations need review when a component catalogue or quantified claim is added.
No unsupported numerical industry statistics are used here.

Each future product/component record must distinguish measured, manufacturer-specified,
estimated, illustrative and research-stage information. Record manufacturer/model
when applicable, source URL, publication/retrieval date, units, operating conditions,
uncertainty and applicable compatibility envelope. Null or unavailable data must not
be filled with guessed specifications. A label such as LFP, SiC or 800 V must not
be translated into an efficiency improvement without a defined model and evidence.

The foundation has no commercial component records, supplier cost estimates or
technology performance rankings. Tariffs and vehicle inputs in Design Studio are
explicitly illustrative user-editable assumptions, not source-backed market values.
