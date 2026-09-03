# Gate E pre-upstream readiness checklist

This checklist is retained as historical evidence of work completed before upstream gates closed.

**Current status:** Gate A, B and C are PASS. Gate E is now **PROVISIONAL / BLOCKED_BY_GATE_D**. The authoritative current readiness note is `docs/GATE_E_PRE_D_READINESS.md`.

Completed before Gate C PASS:

- deterministic cycle/headway/bus-km/vehicle-hour formulas;
- explicit CW, CCW and conditional combined headway semantics;
- multi-band and service-day-group support;
- per-metric epistemic status validation;
- C/D artifact + commit lineage validation;
- exact rejection of PLACEHOLDER/INVALIDATED and production ASSUMPTION;
- lower-bound fleet semantics, avoiding false exact-fleet claims;
- PdB 111,419 benchmark arithmetic audit with 1 km component discrepancy exposed;
- machine-readable V2 input template;
- validation-only and benchmark-only runner modes;
- formula-only sensitivity engine requiring explicit assumption grids;
- adversarial tests for non-finite values, invalid times, asymmetric directions, multi-band aggregation, hidden assumptions and missing upstream input;
- lightweight Gate E CI workflow.

Added after Gate C PASS:

- pinned consumption of the validated Gate C PASS artifacts;
- source-grounded current-service baseline adapter that explicitly forbids annualization from one service date;
- observed headway and scheduled-fleet tools ready for actual proposed departures;
- inverse runtime/frequency/budget operating envelopes for immediate Gate D screening;
- explicit legacy-output invalidation manifest and quarantine regression tests.

Still impossible to finalize before Gate D PASS: production route-km, production pure running time, route-specific cycle time, route-specific annual bus-km, final fleet requirement, final scenario budget comparison and any final recommendation.
