# Phase 2 Stage D — Exact timetable optimizer V2

## Scope

This workstream implements Stage D from `PHASE2_SERVICE_DESIGN_SPEC.md` on the lossless Stage-D Input Manifest V2. It does not select a budget, calendar, recovery value, topology, primary recommendation or runner-up.

## Exact search contract

For every one of the 5,345 unique `scenario + headway + span` daily timing problems, every route receives an independent integer phase in `0..headway-1`. The complete Cartesian phase domain is enumerated. No heuristic search, beam search, random search, threshold pruning, cross-scenario elimination or route-set equivalence is allowed.

The Stage-D input manifest proves that the largest domain contains 3,600 phase vectors and that the complete real domain contains 6,758,835 vectors. Route×headway×span transfer tables may be memoized because this only avoids repeated arithmetic. Every declared problem and every declared phase vector remains in the exhaustive optimization.

An independent recursive brute-force oracle must reproduce the winning phase vector and objective key for every real Stage-D problem.

## S8 objective

The objective preserves the declared S8 phasing hierarchy while replacing the old repeating-pulse approximation with explicit first/last daily bus trips and the frozen 74 official S8 events:

1. maximise the minimum mean transfer quality across the supported route × sensitivity-profile × rail-direction × connection-type cells;
2. maximise the unweighted mean of those cells;
3. choose the lexicographically lowest route-specific phase vector only after the substantive S8 dimensions tie.

The continuous transfer-quality function is the certified logistic make/miss transition multiplied by exponential preferred-wait decay. `RAIL_TO_BUS` is evaluated only for public services starting at the hub. `BUS_TO_RAIL` exists only where the public route itself returns to the hub. A technical vehicle closure never becomes a passenger event.

Passenger demand weights, topology weights and current-service continuity do not enter the phase objective. Continuity is retained unchanged for the fifth final recommendation tie-break defined in the normative specification.

## Explicit timetables and blocks

The selected route-specific phases generate explicit public departures with start-inclusive, end-exclusive service-span semantics. Public hub returns are emitted only for public routes that actually return to the hub. Vehicle hub returns use the certified closed cycle runtime for every route, including the technical closure of an open public route.

For each recovery sensitivity of 5, 10 and 15 minutes, every departure becomes an exact vehicle occupation interval from departure until `cycle_runtime + recovery`. A deterministic interval-partitioning algorithm computes the minimum number of simultaneously required vehicles and the block assignment. Vehicles may interline at the hub when the exact timing permits it. No recovery value is selected in this stage.

## Reliability stress

The output reports deterministic bus-to-rail missed-connection stress at nominal timing and at +5, +10 and +15 minutes of bus runtime delay. These magnitudes are an explicit engineering stress set aligned to the already-declared operational sensitivity scale. They are not an empirical delay distribution, are not converted to a probability forecast and do not enter phase selection. The broader robustness tournament remains downstream.

## PASS criteria

Stage D is PASS only if CI proves all of the following on the real persisted lineage: 5,345 problems represented, all 16,883 Stage-C budget-qualified contexts retained, all 6,758,835 phase vectors evaluated, brute-force oracle equivalence on all 5,345 problems, 74 S8 events with 37 per direction, explicit public timetables materialised, exact vehicle blocks evaluated for recovery 5/10/15, deterministic byte-for-byte rebuild, no random/synthetic search and no hidden weighted composite score.
