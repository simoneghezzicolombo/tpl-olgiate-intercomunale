# Gate E pre-upstream readiness checklist

Completed before C/D PASS:

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

Still impossible to finalize before upstream PASS: production route-km, production pure running time, validated service days/trip counts, actual phasing and stop-level combined gaps, exact block/deadhead fleet, and final scenario budget comparison.
