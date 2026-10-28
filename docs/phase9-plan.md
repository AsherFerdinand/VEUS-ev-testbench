# Phase 9 implementation plan

Base: feature/vehicle-validation-calibration. Preserve the 134-test baseline.

The current single HTML page and dashboard.js own one WebSocket session, typed
RunConfig settings, telemetry charts and exports. validation.js owns independent
measurement experiments. Keep these interfaces and all existing form IDs.

1. Add workspace navigation and move existing engineering DOM into Validate and
   measurement tools into Analyse; add a compact default Drive shell.
2. Supply four explicitly illustrative presets through a backend read-only API.
   Selection updates existing config fields and resets the same simulation.
3. Render original SVG silhouettes over a lightweight Canvas landscape. Interpolate
   between telemetry position samples with one-update latency, never extrapolate
   or integrate physics in JavaScript. Fixed 5 px/m logical scale for road/lead.
4. Add keyboard/touch controls using the existing controls messages, brake priority,
   bounded sending, input release on focus/workspace/socket changes and pause.
5. Preserve complete charts, configuration, sensor diagnostics and exports. Add
   compact speed/power plots in Drive and links to reproducible scenario/report CLI.
6. Test presets, actual browser keyboard/focus/disconnect behavior, interpolation,
   workspace persistence and laptop/mobile layout. Run full Python regressions,
   capture screenshots, document performance observations and limitations.

No physics/controller equations, simulation frequency or scenario criteria change.
No branded artwork or manufacturer accuracy claims. New branch only, no main merge.
