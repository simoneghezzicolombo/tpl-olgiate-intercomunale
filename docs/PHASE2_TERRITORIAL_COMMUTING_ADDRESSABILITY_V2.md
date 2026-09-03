# Phase 2 Territorial Commuting Addressability V2

## Purpose

This workstream adds the full certified ISTAT 2021 work-commuting OD inventory to the Phase 2 structural scenario universe without pretending that municipal OD weights are observed bus passengers.

The certified five-municipality work universe contains **8,754 resident workers**. The previously isolated **1,882 S8-addressable workers** remain a separate feeder reference and are not the territorial demand denominator.

## What is measured

For every one of the 100,000 Phase 2 structural scenarios, the builder asks a deliberately limited question:

> For which empirical municipal work OD relations does the public-service route graph contain at least one directed structural path between an anchor in the origin municipality and an anchor in the destination municipality?

The resulting worker mass is named **structurally addressable municipal-OD mass upper bound**. It is not named served demand, ridership, captured demand or passengers.

Two variants are retained per scenario:

1. base public routes only;
2. base public routes plus optional extension routes.

Adding optional extensions is required to be monotonic: it may increase or leave unchanged structural addressability, but may never reduce it.

## Direction and transfers

Public route direction is preserved from `unique_route_cycles_v2.csv`. Only consecutive anchors in the public route sequence create passenger-service edges.

A public route may legitimately repeat an anchor, including the Olgiate-Calco-Brivio hub at the start and end of a closed loop. These repeated anchors are retained. By contrast, duplicate route IDs inside a scenario route list are rejected.

Transfers are structurally permitted only where public routes share the exact same anchor. This is an upper-bound graph statement, not proof of a feasible timed transfer.

Vehicle-only technical closures are not passenger edges because they do not appear in the public anchor sequence.

## OD scope and semantics

The source is `outputs/phase2/s8_work_demand_addressability.csv`, certified by `outputs/phase2/od_2021_demand_profile_validation.json` as `ISTAT_2021_WORK_COMMUTING_ONLY`.

The four source categories are retained separately:

- `SELF`;
- `OTHER_CORE`;
- `S8_DIRECT`;
- `OTHER_EXTERNAL`.

`S8_DIRECT` remains only an infrastructure-addressability category. It is not observed rail modal share and receives no privileged weight in the territorial metric.

### SELF OD

Municipal OD cannot identify where a resident lives and works inside the same municipality. Therefore `SELF` rows are retained in the published OD inventory but excluded from scenario structural scoring.

Counting a SELF row merely because a scenario contains one anchor in that municipality would be too permissive and would manufacture submunicipal access evidence that the source does not contain.

## Structural footprint

Only destination municipalities represented by enabled routing-anchor lineage in the certified V2 routing-anchor universe are structurally scorable. OD rows whose workplace municipality lies outside that search footprint remain in the full inventory but do not enter the scenario denominator.

This prevents the metric from penalising a local bus design for not directly reaching every external workplace municipality in the full national OD matrix.

## Explicit non-claims

This workstream does not:

- assign any of the 8,754 workers to a bus route or stop;
- infer bus use or modal share;
- allocate municipal workers to buildings, census sections or residential population shares;
- combine worker OD with fine-grained walking catchments;
- calculate timetable feasibility or passenger GJT;
- select a clock phase, service policy, topology, primary recommendation or runner-up;
- combine the S8 feeder metric into the territorial metric.

The worker weights are empirical municipal workplace-commuting weights only.

## Role in the final tournament

This layer is one input to the eventual tournament, alongside rather than instead of:

- **Access/Equity V2**, which measures how much resident population can reach the service on foot and how evenly that access is distributed across the five municipalities;
- **S8 feeder/interchange**, which measures rail-interchange quality for the S8-addressable component without treating 1,882 workers as route demand;
- **service-policy and operational feasibility**, which constrain headway, span, fleet and annual bus-km;
- later passenger-utility/robustness integration.

No hidden weighted composite score is introduced here.

## Outputs

The certified build materialises:

- `outputs/phase2/territorial_demand_v2/territorial_work_od_universe_v2.csv`;
- `outputs/phase2/territorial_demand_v2/scenario_territorial_commuting_addressability_v2.csv.gz`;
- `outputs/phase2/territorial_demand_v2/territorial_commuting_addressability_v2_validation.json`.

The validation report records certified lineage, the full 8,754-worker inventory, the structurally scorable footprint mass, scenario maxima and how many optional-extension scenarios increase structural addressability.
