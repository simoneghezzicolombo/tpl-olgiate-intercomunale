# Phase 2 RT-029 E4+E5+E6 Candidate Evaluation V4

## Status

`PASS_PREPARED_WAITING_PASSENGER_STOP_REALIZATION` is the only authorised readiness verdict before Agent A publishes a certified passenger-stop realization artifact.

This V4 supersedes the 88-structure E4-only RT-029 implementation as the prepared downstream evaluator. The old E4 run remains a diagnostic/regression result only and must not be described as a final shortlist.

## Structural decision domain currently complete

The certified topology-neutral structural layers already complete on the same frozen reciprocal-link graph are:

- RT-022 E4: 88 structures;
- RT-024 E5: 4,076 structures;
- RT-025 E6: 108,679 structures;
- total E4+E5+E6: 112,843 structures.

V4 validates all three exact layers together, preserves `edge_count`/`structural_layer`, requires disjoint `structure_id` values and fails closed on cycle-rank or contract drift.

This does **not** declare E=6 to be a final complexity cap. RT-026 is only a partial E7 bicyclic diagnostic and RT-027 does not provide a safe E7 link reduction. A genuinely final topology-neutral choice therefore still needs either a separately justified maximum-complexity decision contract or a complete later E7 search.

## Passenger-stop boundary

RT-029 V4 deliberately does not infer passenger service from `vertex_ids`.

The canonical decision scenario is `GUARANTEED_PASSENGER_STOPS`, derived only from a separate certified Agent-A realization artifact with one row for every RT-023 `realization_id` and an ordered passenger-stop sequence for that exact directional realization.

Required identity fields:

- `realization_id`;
- `structural_link_id`;
- `direction`;
- `alternative_ordinal`;
- `ordered_passenger_stop_place_ids` or the accepted alias `ordered_passenger_stop_ids`.

The passenger artifact must match the full RT-023 realization identity exactly. The first and last passenger stops must preserve RT-023 source and target endpoints. `SPECIAL_SERVICE` cannot enter automatic candidate stop sets.

For each link-direction component:

- the intersection across admissible realization alternatives forms the guaranteed passenger-stop set;
- the union forms a diagnostic possible set;
- only the guaranteed set can feed Pareto evaluation.

Structural vertices are retained separately as `VERTEX_ONLY_DIAGNOSTIC`; they are never auto-added to the decision stop pattern except insofar as the certified passenger realization itself guarantees those endpoint stops.

## Exact deduplication fast path

Accessibility depends on the passenger stop set, not on the structure ID. V4 therefore:

1. composes passenger stops from the certified atomic realizations;
2. hashes canonical stop sets into deterministic `stop_set_id` values;
3. evaluates RT-028 accessibility/equity once per unique stop set;
4. joins those results back to all 112,843 structures;
5. retains RT-023 operating-burden envelopes per structure.

The currently observed 8,595 unique `vertex_ids` sets is reported only as a readiness diagnostic. It is **not hardcoded** and is not assumed to equal the future number of full passenger stop sets.

## RT-028 final pin and municipality identity

Only final RT-028 artifact `9991182904` / run `34039162932` is valid downstream.

The final RT-028 population lineage contains inherited display mojibake in some `population_municipality_name` values while the ISTAT municipality codes remain stable. V4 therefore uses `population_municipality_code` as the calculation/equity identity. A narrowly scoped reversible UTF-8/Latin-1 repair is allowed for display labels only and is counted in the audit. Municipality names never define equity groups.

## Accessibility and equity

RT-028 walking routing is never re-run here. For each unique passenger stop set, V4 takes the minimum certified RT-028 walking time to any selected conventional stop.

Unreachable population remains in all coverage denominators.

For `ALL`, `CORE` and `EXTERNAL`, outputs include reachable/unreachable share, 5/8/10/12-minute population shares and reachable-only weighted mean/median/P90/P95 walking time.

Core-municipality diagnostics use ISTAT municipality codes and derive threshold-specific minimum municipality coverage and max-min gap.

## Operating burden

RT-023 alternatives are not selected. For every required structure, V4 sums link-direction component minima and maxima for:

- `distance_m`;
- `running_minutes_model`.

These remain realization-burden envelopes, not a timetable, cycle time, annual kilometre estimate or cost model.

## Pareto and exact reduction

There is no weighted composite score and no total ranking.

Four separate threshold-specific frontiers are prepared at 5, 8, 10 and 12 minutes. Decision dimensions remain:

- maximize core reachable population share;
- maximize threshold-specific core coverage;
- maximize minimum core-municipality threshold coverage;
- minimize reachable-population weighted P90 walking time;
- minimize minimum bidirectional realization distance.

Before the general Pareto pass, structures sharing exactly the same decision `stop_set_id` may be removed only when they have strictly worse minimum realization distance. Because every other Pareto dimension is identical within the same stop set, this is an exact dominance reduction, not heuristic pruning. Ties are preserved.

The full territorial Pareto run is intentionally gated until the certified Agent-A passenger-stop realization artifact exists.

## Territorial legibility

Issue #74 is downstream mandatory interpretability, not optimization. RT-029 V4 does not penalize or prune candidates for Bernaga-type anomalies, sparse stop patterns or visual surprise. A candidate may remain Pareto-nondominated and still require a legibility review before `FINALIST_READY` promotion.

No output from this workstream may select PRIMARY/RUNNER-UP.
