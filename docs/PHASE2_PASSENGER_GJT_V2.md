# Phase 2 Passenger GJT V2

## Purpose

Passenger GJT V2 connects empirically weighted work demand to the Phase 2 service-design tournament without fabricating a sub-municipal 2021 commuter origin distribution.

The primary empirical demand source is the ISTAT 2021 work commuting OD matrix. The certified S8 feeder subset contains 1,882 workers whose destination municipality is directly served by the official S8 pattern. `S8_DIRECT` is infrastructure addressability, not observed rail mode share.

## Two distinct layers

### Empirical journey universe

`empirical_journey_universe_v2.csv` contains only rows already marked `feeder_objective_eligible=true` in the certified S8 work-demand addressability table. The demand weight remains at the source-supported municipality-to-municipality resolution.

This table deliberately records:

- `source_resolution=MUNICIPAL_OD`;
- `spatial_allocation_status=MUNICIPAL_OD_ONLY_NO_SPATIAL_ALLOCATION`;
- `full_gjt_ready=false`.

It is therefore valid as an empirical demand universe, but not yet as a door-to-door GJT table.

### Full GJT components

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
- combine fine walking catchments with municipal OD before a spatial-allocation contract exists;
- select a topology, stop set, headway, service policy or final recommendation.

The Access Equity V2 layer remains the fine-grained walking-access result until a defensible worker-origin allocation is introduced.

## Next integration boundary

After S8 Phasing V2 is audited, Passenger GJT V2 can consume service-policy/S8 outputs and build passenger components. Any sub-municipal allocation must be declared as either evidence-backed or an explicit sensitivity assumption. A 2011 sub-municipal commuting pattern or 2021 section-level employed-resident distribution may be tested as sensitivity evidence, but neither may silently become a 2021 observed OD fact.
