# Current checkpoint

- **VEUS 2.6 complete**, on `feature/veus-2.0-engineering-workbench`; baseline `ae636e4`.
  Stop after 2.6. No main merge, stable release or Phase 3.0.
- **A:** optional illustrative motor efficiency maps, explicit torque/RPM/regen envelope,
  continuous/known-duty peak limits, separate conversion losses and frozen map provenance.
  Same-design/full-cycle comparison UI and JSON export. Omitted/null map selection retains
  exact legacy numerical and export fingerprints. Focused gate: 50 Python checks + browser.
- **B:** VED evidence audit, candidate-specific calibration readiness, disjoint held-out
  interval guards, compatible paired-error helper and provenance-rich JSON/HTML reports.
  Missing independent vehicle inputs/polarity/synchronization keep fit values and residuals
  null. **Physical validation INCONCLUSIVE**. Focused gate: 7 Python checks + browser;
  exact old measurement JSON/CSV/HTML parity retained.
- **C:** perspective SVG road, distance-based scenery/wheels, independently positioned
  traffic, smooth deterministic illustrative overtaking, bounded pose/camera and secondary
  playback rates. Seek reconstructs directly; reduced motion and inactive cleanup retained.
  Original three bodies, speedometer, battery and synchronized plots preserved.
- Final regression: **314 Python, 9 clock, 8 scene tests and 9 browser suites passed**.
  One existing Starlette/httpx deprecation warning. Full Python run once after focused gates.
- Essential performance: initial subresources 98,233→98,289 B; startup RSS44,172→44,408 KiB.
  Separate same-server legacy/map Insights medians105.6/150.5 ms; map diagnostics enlarge
  payload. Shared-cloud samples, not a laptop guarantee. No static background requests,
  sockets or pending application timers/frames; short server idle samples have tick noise.
- Evidence: [checkpoints, comparison, reports, performance and two actual captures](veus2/evidence-2.6/README.md).
  Equations: [powertrain](veus2/powertrain2.6.md); [validation/driving contracts](veus2/validation-driving2.6.md).
- Limits: illustrative maps and traffic, fixed OCV/resistance, constant inverter efficiency,
  no auxiliaries/thermal/ageing/phase-current model. Finite-step RPM crossing has explicit
  zero-power/unavailable-efficiency handling; no extrapolation. Unmatched VED inputs do
  not support a defensible calibration. No physical safety or real-vehicle range claim.
