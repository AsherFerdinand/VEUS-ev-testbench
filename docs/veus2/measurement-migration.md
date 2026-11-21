# Measurements migration, VEUS 2.5

The five-workspace UI now provides Import → Readiness → Signals → Events →
Comparison → Export. `measurements.js` calls the same investigation/readiness
services used by `/engineering`. `/api/workbench/v2/measurements/case-study` is a
bounded worker wrapper around the existing `veus.investigation.api.perform`.
No importer, unit conversion, event detector or numerical report calculation was rewritten.

Built-in sources include the original VED Leaf windows and complete trip groups.
CSV input retains raw bytes, SHA256, source metadata, explicit column/unit mapping
and polarity evidence. Existing configuration JSON and combined replay payloads
remain supported. Header inspection proposes mappings; it does not confirm units,
signal signs or data validity. Primary and comparison inputs require explicit review.
Synthetic origin remains distinct from user-asserted measured origin. Missing
optional channels remain unavailable. Imports are bounded to the retained 2 MB /
5000-row replay contract; unknown units, invalid times and hash mismatches fail.

The dashboard uses original speed and voltage/current samples, not synthetic
replacement traces. Signed power is withheld when current polarity is unknown.
Gaps break plot lines; no missing journey or samples are interpolated into existence.
One retained replay clock synchronizes both plots, sample/source-time readout and
event selection. Event indices refer to the original detector; selected-event
investigation is recomputed through the legacy service with explicit indices.
Readiness and limitations remain visible. Pausing/inactivation cancels owned frames;
there is no polling or background simulation.

Exports use the frozen source/configuration/event request that produced the shown
case, even after the selected next input changes. JSON preserves full case evidence;
CSV preserves all original analysed rows and hashes; HTML uses the retained report
pipeline. UI event/interval selection does not silently crop exported measurements.

## Comparison boundaries

Two recordings can be compared **descriptively** by the retained service. Different
trips, conditions, coverage and vehicles are not controlled efficiency rankings.
Measured versus simulated comparison is explicitly readiness-gated. The selected
model snapshot, recording hash, elapsed-time interval, coverage, alignment statement
and missing inputs are returned. No parameter fitting or forced alignment occurs.

The available VED inputs do not independently establish propulsion/brake inputs,
road gradient, channel calibration or current polarity, nor a verified mapping
between an illustrative S1/R1/X1 snapshot and the measured Leaf. Consequently the
model residuals remain **null / INCONCLUSIVE**. A visual replay or a user assertion
is not physical validation; no fabricated current, power, range or Leaf model
comparison is supplied. This limited capability is intentional and must not be
reported as a completed quantitative physical-validation study.

## Verified parity

Identical inputs to old and new endpoints produce identical JSON, CSV and HTML,
including source hashes, readiness, event indices, selected events and calculated
quantities. Focused tests cover absent signals, invalid mapping units, unknown
polarity, selected intervals and gated model comparisons; browser checks import
raw genuine VED CSV plus its original JSON configuration and preserve source hash
and 534 samples. Two-recording exports retain 534 +367 rows. `/engineering` and all
useful legacy processing/tests remain. Historical Phase 8 physical validation is
**INCONCLUSIVE**. [Evidence](evidence-2.5/README.md).
