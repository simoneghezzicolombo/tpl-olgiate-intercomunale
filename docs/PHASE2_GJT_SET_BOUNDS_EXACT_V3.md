# Phase 2 fixed-event fine-origin GJT set bounds V3

## Status

`PASS_PHASE2_EXACT_FEEDER_S8_SET_BOUNDS_V3`

Certified evidence commit: `c90232d13fa9e4acde6f3e9732b9a0ec62a89aef`

Workflow run: `33892440844`

Contract: `PHASE2_FIXED_EVENT_FINE_ORIGIN_SET_IDENTIFICATION_BOUNDS_V3`

## Purpose

This artifact set-identifies generalized feeder-to-S8 cost without inventing fine worker locations, passenger weights or a departure-time distribution. It is evidence enrichment only. It is not expected daily GJT, a demand-weighted improvement metric, a ranking or a final-selection surface.

## Exact temporal semantics

Each BUS_TO_RAIL itinerary is conditioned on one fixed frozen S8 departure event. An infeasible itinerary remains infeasible for that event. It is never rebound to the next train.

Only exact Stage-D public trips are used. Passenger hub-return events must lie in the declared `[span_start, span_end)` service span. Technical vehicle closure is never passenger service. For a public closed route, only the next explicit public hub occurrence can support BUS_TO_RAIL.

Direct station access is available only through the certified EX_039 pedestrian catchment inherited by `rail:S01514`.

No origin bus wait is imputed. In particular, the historical `uniform_headway/2` screening assumption is not used.

## Sensitivity envelope

The historical 243-case feeder-GFA ranges are reused only as non-empirical sensitivity axes.

`station_transfer_walk_min` is exhaustively enumerated at 1.5, 2 and 3 minutes because it changes itinerary feasibility. Conditional on a fixed rail event and a fixed station-transfer walk, the remaining four positive coefficients multiply nonnegative components and do not change feasibility. Every feasible itinerary cost is coordinate-wise nondecreasing in those four coefficients. Taking the minimum across feasible itineraries and then extrema across admissible fine origins preserves monotonicity.

Therefore the full 243-case lower/upper envelope is exactly represented by six cases: the all-low and all-high coefficient corner at each of the three station-transfer-walk values. Regression tests compare the six-case reduction with the full 243-case oracle, including a fixture where the best route changes across the grid.

The optimized fixed-event bus-component selector is independently checked against an all-opportunity brute-force oracle.

## Real-data result

The build evaluates 6,000 certified Stage-D exact timetables, five origin municipalities and both S8 directions, yielding 60,000 timetable × municipality × direction rows.

Key result from the persisted validation:

- finite upper-bound rows: 0
- unbounded upper-bound rows: 60,000
- rows with no finite lower bound: 16,990
- direct-walk lower witnesses: 24,000
- bus lower witnesses: 19,010
- timetables with no public BUS_TO_RAIL opportunity: 918
- total unreachable origin × fixed-rail-event × station-walk states: 4,479,523,293

The all-unbounded upper result is not converted into a penalty or silently narrowed. It means the full event-agnostic temporal envelope is too broad to support interval dominance or a point estimate with current evidence.

## Decision boundary

The artifact must not be relabelled as full GJT or `demand_weighted_gjt_improvement_min`. It must not reopen the already certified technical sufficiency gate merely because legacy V2 GJT fields remain unavailable.

A robust interval-dominance rule of the form `upper(A) < lower(B)` cannot discriminate alternatives on this full envelope because every upper bound is unbounded. No alternative is pruned or ranked by this stage.

The remaining identifiability requirements for a narrower expected or decision-weighted GJT are:

1. an empirical or explicitly policy-declared departure-time distribution/window;
2. a certified destination-to-S8-direction mapping before any OD-weighted aggregation;
3. a complete comparable current-service GJT if a true improvement metric is required;
4. an empirical delay distribution only if probabilistic reliability is required.
