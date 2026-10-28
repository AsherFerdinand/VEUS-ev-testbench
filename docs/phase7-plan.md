# Phase 7 architecture review and implementation plan

Baseline: branch veus-interactive-testbench at d1b2964. The repository separates
model physics, controllers, SimulationSession orchestration, typed offline
scenarios/results, reporting, and FastAPI/vanilla JavaScript adapters. Physics
state is calculated by sim/dynamics.py and sim/session.py; ACC/AEB currently use
Observation objects built from _observation() ground truth. Detection delay holds
observations; actuator delay holds commands. Reports record every 0.01 s tick;
the dashboard gets ten-tick frames. Existing verification has 81 tests and eight
scenarios, including two known avoidance failures, which must remain visible.

Smallest additive changes:
1. sensors/config.py and sensors/virtual.py: validated settings/fault schedules,
   seeded sampling, timestamped packets, latency, freeze/dropout and event logs.
2. RunConfig gains a default-disabled sensor suite; no physical model changes.
   Session supplies sensor measurements to existing algorithms; detection and
   actuation delays retain their distinct positions after sensor delivery.
3. Explicit stale/missing-data fallback: comfort braking, or continued latched
   emergency braking. No ideal-data substitution or claimed fault diagnosis.
4. Additive telemetry includes true/measured values, age, validity, error, fault
   IDs and the controller's delayed input health. Typed results/metrics and report
   plots gain error statistics and like-for-like ideal-baseline comparisons.
5. Dashboard exposes compact sensor configuration and truth/measured plots using
   existing JavaScript. Original scenario JSON remains valid; examples go in a
   separate scenarios/sensors directory so the original eight-case suite is intact.
6. Tests cover sensor clocks, seeded randomness, fault boundaries/overlap, stale
   fallback, reset, ideal equivalence, report evidence and browser interactions.

Configuration and fallback semantics will be documented in virtual-sensors.md.
This is deterministic one-dimensional software verification, not sensor hardware
or production ADAS validation. No heavyweight dependency or new frontend framework.
