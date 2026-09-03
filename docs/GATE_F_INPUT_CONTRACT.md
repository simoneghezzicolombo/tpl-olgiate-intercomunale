# Gate F upstream input contract

This contract is deliberately data-free. It defines how Gate F will ingest outputs from B/C/D/E once those workstreams are validated.

## Core rule

`scenario_id` is the only join key. Gate F never joins on labels, route names or topology names. The scenario catalog is authoritative for the universe of alternatives. Gate D must assess road feasibility for the **entire** catalog. B/C/E must cover every Gate-D-eligible scenario. Missing eligible rows are a hard failure; silent inner-join row loss is forbidden.

Every metric requires four pieces of metadata: epistemic `__status`, traceable `__source`, canonical `__unit` and explicit `__semantics`. Wrong units or semantics fail closed.

## Scenario catalog

Required columns: `scenario_id`, `scenario_name`, `topology_family`, `is_baseline`, `scenario_epistemic_status`, `scenario_source`. Exactly one baseline is required. `topology_family` is descriptive only and never enters Pareto mathematics.

## Gate B fragment

For every eligible scenario:

- `population_covered_pct`, unit `%`, semantics `PERCENT_OF_DEFINED_POPULATION_DENOMINATOR`;
- `territories_served_count`, unit `count`, semantics `COUNT_OF_DEFINED_TERRITORIAL_UNITS`;
- matching `__status` and `__source` columns.

These must be scenario-specific outputs from the validated Gate B accessibility machinery. The denominator/territorial-unit definition must remain documented upstream.

## Gate C fragment

For every eligible scenario:

- `s8_useful_connection_pct`, unit `%`, semantics `PERCENT_OF_DEFINED_S8_CONNECTION_DENOMINATOR`;
- matching `__status` and `__source`.

The denominator must be defined by Gate C. Hand-typed train or bus clock-minute arrays are not admissible.

## Gate D eligibility fragment

For every catalog scenario:

- `road_feasible`, unit `boolean`, semantics `HARD_ELIGIBILITY_CONSTRAINT`;
- matching `__status` and `__source`.

Road feasibility is a constraint, not a Pareto objective. A road-infeasible scenario is excluded before comparison.

## Gate E fragment

For every eligible scenario:

- `headway_combined_min`, unit `min`, semantics **exactly** `RATE_EQUIVALENT_NOT_MAX_GAP`;
- `annual_bus_km`, unit `bus-km/year`, semantics `ANNUAL_SCHEDULED_BUS_DISTANCE`;
- `peak_buses_required`, unit `vehicles`, semantics `SIMULTANEOUS_PEAK_VEHICLES`;
- matching `__status` and `__source`.

Gate E currently calls the first metric `headway_combined_rate_equiv_min`. Integration may alias that field to the canonical Gate F column only while carrying `RATE_EQUIVALENT_NOT_MAX_GAP`. It is a service-rate equivalent and **must never be described as a guaranteed maximum gap or passenger wait**.

## Epistemic states and estimates

Production Gate F fragments accept `FACT`, `DERIVED`, `ESTIMATE`, `RECONSTRUCTED`, `MODEL OUTPUT` and `FIELD CHECK`. `ASSUMPTION` is reserved for explicit sensitivity work and is not accepted in the definitive production table. `PLACEHOLDER` and `INVALIDATED` are rejected.

If an objective is `ESTIMATE`, a definitive recommendation additionally requires finite source-grounded `<metric>__lower` and `<metric>__upper` bounds. Gate F does not invent those bounds.

## Assembly

Use `scripts/gate_f_build_inputs.py` with explicit catalog/B/C/D/E fragment paths. It writes the canonical scenario table, explicit road-infeasible exclusions and a deterministic SHA256 assembly manifest. No missing metric is imputed, defaulted or reconstructed by Gate F.
