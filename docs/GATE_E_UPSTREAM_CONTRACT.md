# Gate E upstream handoff contract

Gate E consumes a normalized `GATE_E_V2` CSV. `schemas/gate_e_inputs_v2.csv` is the authoritative machine header. Upstream agents do not need to adopt Gate E internals, but their handoff must make the following fields derivable without manual transcription of result values.

## Required from Gate C
For every service-day group and operating band used in a scenario, Gate C must provide or support: `band_start_time`, `band_end_time`, `direction`, `target_headway_min`, `daily_cycles`, `service_days_year`, `shared_stop_pattern_status` and the epistemic status of each value. Gate C must also provide its artifact path, commit SHA and formal gate status.

If dwell or recovery is inferred from timetable evidence, Gate C may provide it with status. If instead they are planning policy parameters, Gate E must label them `ASSUMPTION` and keep those runs in sensitivity mode.

## Required from Gate D
For every candidate/direction used by Gate E, Gate D must provide or support: `route_km`, `pure_running_min`, their epistemic statuses, the exact candidate identifier/geometry linkage, artifact path, commit SHA and formal gate status. If runtime varies by operating band, Gate D/C must make that band dependence explicit rather than forcing a single average.

## Join keys and integrity
At minimum the integrated records must be uniquely identified by `scenario_id`, `service_day_group`, `band_id`, `direction`. Gate E rejects duplicate/missing directional pairs and mismatched CW/CCW band boundaries.

The integration step must be deterministic. It must not copy values from legacy `outputs/route_variants.csv`, `outputs/service_simulation_scenarios.csv` or any other INVALIDATED/hardcoded artifact.

## Current coordination note
As of the Gate E pre-upstream audit, the Gate C workstream has an audit-oriented JSON output but not yet a finalized service-math handoff, while Gate D has no stable `outputs/gate_d` route-metrics handoff visible to Gate E. This document therefore defines needs without pretending those upstream artifacts already exist.
