# Gate F upstream input contract

This contract is deliberately data-free. It defines how Gate F will ingest outputs from B/C/D/E once those workstreams are validated.

## Core rule

`scenario_id` is the only join key. Gate F never joins on labels, route names or topology names. The scenario catalog is authoritative for the universe of alternatives. Gate D must assess road feasibility for the **entire** catalog. B/C/E must cover every Gate-D-eligible scenario. Missing eligible rows are a hard failure; silent inner-join row loss is forbidden.

## Scenario catalog

Required columns:

- `scenario_id`
- `scenario_name`
- `topology_family`
- `is_baseline`
- `scenario_epistemic_status`
- `scenario_source`

Exactly one baseline is required. `topology_family` is descriptive only and is never an objective or preference. Names such as "figure-8", "radial", "trunk-feeder" or "current" cannot affect Pareto results.

## Gate B fragment

Required for every eligible scenario:

- `population_covered_pct`
- `population_covered_pct__status`
- `population_covered_pct__source`
- `territories_served_count`
- `territories_served_count__status`
- `territories_served_count__source`

These must be scenario-specific outputs computed with the validated Gate B accessibility machinery. The current-service catchment alone is not sufficient evidence for a candidate scenario.

## Gate C fragment

Required for every eligible scenario:

- `s8_useful_connection_pct`
- `s8_useful_connection_pct__status`
- `s8_useful_connection_pct__source`

This metric must be based on source-grounded S8 service dates/times and scenario bus timetables. A hand-typed list of train or bus clock minutes is not admissible.

## Gate D eligibility fragment

Required for **every catalog scenario**:

- `road_feasible`
- `road_feasible__status`
- `road_feasible__source`

Road feasibility is a **constraint, not a Pareto objective**. A scenario that is not physically/operationally road-feasible is excluded before multi-objective comparison and is written to the exclusions audit. Benefits in other dimensions cannot compensate for road infeasibility.

## Gate E fragment

Required for every eligible scenario:

- `headway_combined_min`
- `headway_combined_min__status`
- `headway_combined_min__source`
- `annual_bus_km`
- `annual_bus_km__status`
- `annual_bus_km__source`
- `peak_buses_required`
- `peak_buses_required__status`
- `peak_buses_required__source`

Gate E currently uses the term `headway_combined_rate_equiv_min`. Before integration, the interface must either export the canonical alias above or Gate F must explicitly map that field while preserving the semantic warning `RATE_EQUIVALENT_NOT_MAX_GAP`. A rate-equivalent headway must never be described as a guaranteed maximum passenger wait.

## Accepted epistemic states

Production Gate F fragments accept `FACT`, `DERIVED`, `ESTIMATE`, `RECONSTRUCTED`, `MODEL OUTPUT` and `FIELD CHECK`. `ASSUMPTION` is reserved for explicit sensitivity work and is not accepted in the definitive production table. `PLACEHOLDER` and `INVALIDATED` are rejected.

## Assembly

Use:

```bash
python scripts/gate_f_build_inputs.py \
  --catalog <scenario_catalog.csv> \
  --gate-b <gate_b_fragment.csv> \
  --gate-c <gate_c_fragment.csv> \
  --gate-d <gate_d_fragment.csv> \
  --gate-e <gate_e_fragment.csv>
```

Outputs:

- `outputs/gate_f_scenario_metrics.csv`: eligible scenarios only, provenance-complete
- `outputs/gate_f/excluded_scenarios.csv`: explicit Gate D exclusions

No missing metric is imputed, defaulted or reconstructed by Gate F.
