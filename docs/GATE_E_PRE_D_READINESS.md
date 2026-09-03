# Gate E pre-D readiness

## Current verdict

**PROVISIONAL / BLOCKED_BY_GATE_D**

Gate A, Gate B and Gate C are formally PASS on their validated workstreams. Gate C PASS is consumed as pinned external upstream evidence from commit `dcc3e75ae3b4f4ea5170f48e85345b83620c5536`; the later Gate C branch commits are robustness/CI follow-ups and do not change the rule that Gate E must cite an exact validated artifact commit. Gate D remains the only structural upstream blocker for route kilometres and pure running times.

## What Gate C PASS now gives Gate E

Gate E may use the validated current-transit evidence as a baseline and coordination context. The pinned 2026-09-03 Gate C artifacts contain current official-operator bus timetable reconstructions for D184/D185 and a live official Trenord GTFS extraction for S8 at Olgiate-Calco-Brivio.

Gate E has a dedicated adapter, `scripts/gate_e_gate_c_baseline.py`, that reads those artifacts and emits source-grounded current-date metrics with Gate C lineage. It explicitly forbids annualization from a single service date and labels the output as not being a future service plan.

This is intentionally different from the future feeder design. Gate C PASS does **not** by itself determine future headways, service span, service days/year, dwell policy, recovery policy or vehicle blocks. Those remain either explicit planning assumptions in sensitivity analysis or future derived/model outputs with their own provenance.

## What is ready before Gate D

- deterministic forward service math by direction and operating band;
- observed headway audit from actual phased departures;
- theoretical and actual scheduled-fleet audits;
- C+D deterministic handoff builder;
- per-metric epistemic status and upstream lineage enforcement;
- pinned Gate C PASS integration in CI;
- source-grounded current-service baseline adapter;
- inverse operating-envelope mathematics;
- explicit sensitivity tools for budget/fleet/headway thresholds;
- legacy-output quarantine tests;
- PdB D184+D185 annual benchmark with the 1 km reconstructed component mismatch exposed rather than silently repaired.

## Inverse thresholds prepared for Gate D

`src/operating_envelope.py` and `scripts/gate_e_operating_envelope.py` can derive, from explicitly supplied planning assumptions:

- maximum cycle minutes compatible with a target directional headway and in-service vehicle count;
- maximum pure running time after separately reserving dwell and recovery;
- cycle slack/overrun;
- maximum whole directional cycles/year under a bus-km cap once a route length is known;
- maximum symmetric cycles/day/direction under a bus-km cap;
- maximum common route length under the 111,419 bus-km benchmark for an explicit operating-days/cycles policy.

These outputs are always labelled `SENSITIVITY_ONLY_NOT_PROJECT_RESULT` when driven by planning assumptions. Their purpose is to let Gate D route metrics be tested immediately against already-defined mathematical constraints, not to preselect a route.

## Exact remaining Gate D handoff

For every candidate/direction that is allowed to reach Gate E, Gate D must provide at minimum:

1. stable candidate/geometry identifier;
2. direction (`CW` / `CCW`);
3. validated `route_km` and epistemic status;
4. validated `pure_running_min` and epistemic status, including band dependence if applicable;
5. Gate D formal status;
6. exact Gate D artifact path;
7. exact Gate D commit SHA;
8. enough geometry linkage to prove that the measured distance/runtime refer to the same candidate used downstream.

Gate E will reject missing/duplicate/mismatched join keys and will not fall back to legacy `route_variants.csv` or hardcoded scenario outputs.

## What still cannot honestly be finalized

Until Gate D PASS, Gate E cannot issue production route-specific cycle times, bus-km totals, fleet requirements or budget deltas for the proposed network. Exact future passenger-facing combined gaps additionally require an actual proposed phased timetable rather than a harmonic-rate formula alone.
