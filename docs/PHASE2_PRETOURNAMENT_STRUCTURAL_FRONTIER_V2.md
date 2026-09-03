# Phase 2 Pre-Tournament Structural Frontier V2

## Purpose

This workstream joins three already certified Phase 2 evidence layers before any final candidate tournament:

1. **Access/Equity V2**, resident population within walking reach of the proposed public service;
2. **Territorial Commuting Addressability V2**, empirical municipal work-OD relations that the public route geometry can structurally connect;
3. **Service Policy Search V2**, whether at least one declared service policy is feasible under the validated reference production envelope.

It does **not** produce a winner, runner-up or service plan. Its purpose is to expose the non-dominated topology landscape without inventing a scalar score.

## Why population is central

The structural Pareto uses resident access as its first two dimensions:

- maximise the share of the located five-municipality population within 10 minutes' walking access;
- maximise the 10-minute coverage share of the worst-served municipality.

The first objective rewards serving more residents. The second prevents the total from hiding a severe territorial imbalance.

The third objective maximises the certified municipal work-OD mass that is structurally addressable by the public route geometry. Worker OD is therefore used to distinguish whether population access is connected in directions supported by observed workplace relationships. It is not interpreted as bus ridership.

The 1,882 S8-addressable workers do not enter this Pareto. S8 remains a separate later timing/interchange dimension.

## Pareto rule

All three structural objectives are maximised. Scenario A dominates scenario B only when A is at least as good on all three dimensions and strictly better on at least one.

There is:

- no weighted composite;
- no arbitrary `coverage + OD + equity` score;
- no tie-breaking rank;
- no family preference;
- no preference for one-line versus multi-line topologies.

Exact duplicate metric triplets are equivalent and all matching scenarios remain frontier members if the triplet itself is non-dominated.

## Reference-budget eligibility

Pareto membership is evaluated only among scenarios with at least one feasible policy in the certified `reference` envelope of **111,419 bus-km/year**.

This is explicitly `REFERENCE_BUDGET_SCREENING_ONLY`. It answers whether a topology is worth carrying forward under the validated current-production reference. It does not satisfy the final decision contract's requirement for an explicitly caller-declared normative budget and therefore does not select the eventual decision budget.

## Public versus optional-extension frontiers

Two frontiers are published:

### Public structural frontier

Uses only the base public routes and their base public stop set. This is the cleanest structural comparison because it does not assume that optional extensions operate.

### Public + extensions upper-bound frontier

Uses the same scenario with every optional extension anchor present. This is deliberately labelled an **upper-bound sensitivity**. It does not mean extensions operate on every trip, and it does not choose an extension share or timetable.

The union of the two frontiers is published for prioritisation. Membership in the union is not a final candidate selection.

## Why non-frontier scenarios are not deleted

A topology that is structurally dominated can still have advantages that this layer intentionally does not evaluate, including:

- shorter runtime enabling a better headway;
- a more useful service span or calendar at the same production envelope;
- lower fleet requirement;
- a better jointly feasible S8 clock phase;
- better reliability under perturbation;
- simpler public-facing operation.

For that reason `nonfrontier_pruning_authorized=false`. The later plan-level tournament may inspect the structural frontier first for efficiency, but it may not treat this file as proof that every non-frontier topology is incapable of winning after service and timing are applied.

## Service-policy extrema

The joined table carries descriptive reference-envelope fields such as minimum feasible headway, maximum feasible span and minimum fleet lower bound. These are independent extrema across the feasible policy set. They must not be read as one jointly attainable service plan unless the same `plan_id` is later materialised and checked.

These service extrema do not enter the structural Pareto.

## Explicit non-claims

This workstream does not:

- rank or select a topology;
- select a stop set as final;
- select a service policy;
- select the final decision budget;
- calculate full passenger GJT;
- allocate municipal workers to buildings, stops or routes;
- use the S8 feeder metric in Pareto dominance;
- select an S8 clock phase;
- construct a joint vehicle-block timetable;
- select a primary or runner-up;
- impose the later optional policy constraint of one public line.

## Outputs

- `outputs/phase2/pretournament_frontier_v2/scenario_structural_evidence_joined_v2.csv.gz`
- `outputs/phase2/pretournament_frontier_v2/public_structural_pareto_frontier_v2.csv`
- `outputs/phase2/pretournament_frontier_v2/public_plus_extensions_upper_bound_pareto_frontier_v2.csv`
- `outputs/phase2/pretournament_frontier_v2/structural_frontier_union_v2.csv`
- `outputs/phase2/pretournament_frontier_v2/pretournament_structural_frontier_v2_validation.json`

## Downstream boundary

The next stage must operate at `scenario_id + plan_id` resolution. It should materialise actual feasible service policies for the most relevant scenarios, then combine policy-specific frequency/span/production with passenger-access evidence and a jointly feasible S8 timing treatment. Only after robustness evaluation should the existing final tournament select primary and runner-up.
