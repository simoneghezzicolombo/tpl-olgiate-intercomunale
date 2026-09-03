# Gate E upstream handoff contract

Gate E consumes a normalized `GATE_E_V2` CSV. `schemas/gate_e_inputs_v2.csv` is the authoritative machine header. Upstream agents do not need to adopt Gate E internals, but their handoff must make the required values derivable without manual transcription.

Two normalized handoff headers are already published:

- Gate C -> E: `schemas/gate_c_to_e_v1.csv`
- Gate D -> E: `schemas/gate_d_to_e_v1.csv`

Once those two files exist, `scripts/gate_e_build_input.py` joins them deterministically into `GATE_E_V2` and immediately validates the resulting file. Duplicate keys, missing keys and C/D key mismatches are hard failures.

## Required from Gate C
For every service-day group and operating band used in a scenario, Gate C must provide or support: `band_start_time`, `band_end_time`, `direction`, `target_headway_min`, `daily_cycles`, `service_days_year`, `shared_stop_pattern_status` and the epistemic status of each value. Gate C must also provide its artifact path, commit SHA and formal gate status.

If dwell or recovery is inferred from timetable evidence, Gate C may provide it with status. If instead they are planning policy parameters, Gate E must label them `ASSUMPTION` and keep those runs in sensitivity mode.

## Required from Gate D
For every candidate/direction used by Gate E, Gate D must provide or support: `route_km`, `pure_running_min`, their epistemic statuses, the exact candidate identifier/geometry linkage, artifact path, commit SHA and formal gate status. If runtime varies by operating band, Gate D/C must make that band dependence explicit rather than forcing a single average.

## Join keys and integrity
The normalized handoffs are uniquely keyed by `scenario_id`, `service_day_group`, `band_id`, `direction`. Gate E requires the exact same key set in C and D, then requires exactly one CW and one CCW record per band. Mismatched band boundaries are rejected.

The integration step must not copy values from legacy `outputs/route_variants.csv`, `outputs/service_simulation_scenarios.csv` or any other INVALIDATED/hardcoded artifact.

Expected integration command after upstream handoffs exist:

```bash
python scripts/gate_e_build_input.py \
  --gate-c outputs/gate_c/service_math_handoff.csv \
  --gate-d outputs/gate_d/route_metrics_handoff.csv \
  --output outputs/gate_e_inputs.csv
```

Then Gate E can run `python scripts/10_service_simulation.py` on the validated integrated input.

## Current coordination note
As of this pre-upstream audit, the Gate C workstream has an audit-oriented JSON output but not yet a finalized service-math handoff, while Gate D has no stable `outputs/gate_d` route-metrics handoff visible to Gate E. This contract therefore defines and tests the integration path without pretending those upstream artifacts already exist.
