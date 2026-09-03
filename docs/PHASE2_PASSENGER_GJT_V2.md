# Phase 2 Passenger GJT V2

## Purpose

Passenger GJT V2 connects empirically weighted work demand to the Phase 2 service-design tournament without fabricating a sub-municipal 2021 commuter origin distribution.

The primary empirical demand source is the ISTAT 2021 work commuting OD matrix. The certified S8 feeder subset contains 1,882 workers whose destination municipality is directly served by the official S8 pattern. `S8_DIRECT` is infrastructure addressability, not observed rail mode share.

## Three distinct layers

### Empirical journey universe

`empirical_journey_universe_v2.csv` contains only rows already marked `feeder_objective_eligible=true` in the certified S8 work-demand addressability table. The demand weight remains at the source-supported municipality-to-municipality resolution.

This table deliberately records:

- `source_resolution=MUNICIPAL_OD`;
- `spatial_allocation_status=MUNICIPAL_OD_ONLY_NO_SPATIAL_ALLOCATION`;
- `full_gjt_ready=false`.

It is therefore valid as an empirical demand universe, but not yet as a door-to-door GJT table.

### S8 work-direction weights

`s8_work_direction_weights_v2.csv` and its summary preserve the 1,882-worker S8-addressable subset only as empirical direction weights for hub interchange. They distinguish outbound `BUS_TO_RAIL` and return `RAIL_TO_BUS` directions toward Milano and Lecco.

These weights do not allocate workers to individual bus routes and do not imply observed S8 use.

### S8 passenger-support mask

The audited S8 Phasing V2 route universe is consumed through the fail-closed contract in `phase2_s8_work_transfer_utility_v2.py`.

`s8_route_passenger_support_v2.csv` records, for every unique route, whether public-service geometry supports:

- `RAIL_TO_BUS` from the Olgiate-Calco-Brivio hub;
- `BUS_TO_RAIL` back to the hub;
- a complete round-trip passenger interchange.

A vehicle-only return closure is never promoted to passenger `BUS_TO_RAIL` service.

`s8_scenario_passenger_support_v2.csv.gz` propagates those route-level facts into scenario-level route counts. It does not aggregate them into passenger utility and it does not assign the 1,882 workers to routes.

The support-mask contract therefore keeps:

- `passenger_demand_assigned_to_routes=false`;
- `passenger_utility_calculated=false`;
- `full_gjt_calculated=false`;
- `topology_ranked=false`;
- `service_policy_selected=false`.

## Full GJT components

A full passenger chain is admitted only after an upstream spatial allocation method has explicit evidence lineage. The GJT contract keeps bus IVT and rail IVT separate:

`GJT = w_bus_ivt*bus_IVT + rail_IVT + w_walk*(walk + transfer_walk) + w_wait*(wait + transfer_wait) + transfer_penalty*transfers + missed_connection_probability*missed_connection_cost`

Baseline and candidate records must contain exactly the same journey keys and empirical demand weights.

## Behavioural sensitivity

`config/phase2_passenger_gjt_sensitivity_v2.json` turns the published TAG ranges already adopted by Phase 2 into a full-factorial 81-case sensitivity grid:

- bus IVT weight: 1.0, 1.2, 1.4;
- walking weight: 1.5, 1.75, 2.0;
- waiting weight: 1.5, 2.0, 2.5;
- transfer penalty: 2, 6, 10 equivalent minutes;
- missed-connection cost multiplier: 1.0, applied to an explicit missed-connection cost rather than inventing a second penalty scale.

These are behavioural sensitivities, not empirical confidence intervals.

## Explicit non-claims

This workstream does not:

- infer worker origins from residential population shares;
- use nearest-stop or fuzzy stop assignment;
- interpret S8 addressability as rail ridership or modal share;
- assign the 1,882 S8-addressable workers to individual bus routes;
- combine fine walking catchments with municipal OD before a spatial-allocation contract exists;
- select a topology, stop set, headway, service policy or final recommendation.

The Access Equity V2 layer remains the fine-grained walking-access result until a defensible worker-origin allocation is introduced.

## Next integration boundary

The next safe step is a passenger-transfer opportunity layer for explicitly passenger-supported route/service combinations. It may use the empirical S8 direction weights to evaluate interchange quality, but it must keep route demand unassigned unless a separate evidence-backed route-choice or sub-municipal origin model is introduced.

A 2011 sub-municipal commuting pattern or 2021 section-level employed-resident distribution may be tested as sensitivity evidence, but neither may silently become a 2021 observed OD fact.
