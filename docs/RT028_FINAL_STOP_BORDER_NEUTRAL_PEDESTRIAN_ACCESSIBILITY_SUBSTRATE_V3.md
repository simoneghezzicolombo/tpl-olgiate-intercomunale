# RT-028 — final-stop border-neutral pedestrian accessibility substrate V3

## Scope

RT-028 produces one atomic, deterministic pedestrian-accessibility substrate: **population unit × each of the 36 frozen final stop places**. It does not evaluate any network candidate and it has no dependency on RT-022 or RT-023 candidate identities.

The downstream consumer may later aggregate this matrix by a candidate's served stops, but that aggregation, threshold analysis, equity analysis, ranking, Pareto screening and shortlist selection are explicitly outside RT-028.

## Ownership boundary

RT-028 MUST NOT:

- read candidate/backbone identities for evaluation;
- rank or score candidates;
- select PRIMARY, RUNNER-UP, winners or shortlist members;
- choose a topology or termini;
- compute 5/8/10/12-minute accessibility thresholds;
- reuse old territorial accessibility results;
- use a straight-line distance multiplied by a detour factor as a routing engine.

## Old Access Equity audit

The old `scripts/04_walk_network.py` implementation was audited before RT-028 implementation. It is not a graph-based pedestrian router: for every cell/stop pair it calls `calculate_distance_m(...)` directly on the coordinates, then converts that direct distance into standard and slope-adjusted time with `compute_walk_time(...)`. That territorial routing result is therefore rejected for RT-028.

The later Access Equity V2 code is reusable only at the aggregation-contract level: it deterministically unions certified unit memberships, prevents double-counting and computes threshold/equity summaries. Its runner consumes already-materialised proposed/existing walking memberships rather than constructing a new pedestrian graph itself. RT-028 therefore reuses none of the old catchment memberships or territorial accessibility outputs; it builds a fresh atomic graph-based population-unit × final-stop layer instead.

## Frozen population lineage

Population-unit semantics come from RT-016:

- compute commit: `3eaa227fc7a3cd3f82a9c3161ac4827bc32b862a`;
- validation artifact: `9971024216`;
- artifact digest: `sha256:2937c60aec0280ae1837bc3f763103d5ac45acd2e3b93a949cc75235b1152fe9`.

The validation artifact does not package the atomic population-unit CSV. RT-028 therefore rematerializes RT-016 from that frozen compute commit and its real-data inputs rather than inventing a replacement or importing a legacy territorial result.

The resulting population rows preserve `unit_id`, `population_weight_2025`, `population_scope` (`core`/`external`) and municipality identity. Municipality is metadata for equity analysis downstream; it is **not a pedestrian routing barrier**.

## Frozen stop lineage

The stop inventory is frozen at commit:

`ea30fbd18421164abaf2125033292cbe827e024d`

and file:

`outputs/phase2/network_design_method_audit_v3/master_stop_inventory_gpt_v3/existing_stop_places_operational_gpt_v5.csv`.

The compiler fails closed unless this universe is exactly:

- 36 final stop places;
- 35 `CONVENTIONAL_TPL`;
- 1 `SPECIAL_SERVICE`, exactly `SPECIAL::CASA_DI_COMUNITA_OLGIATE`.

All 36 are present in the atomic substrate. The later conventional-TPL screening stage may default to the 35 conventional stops; RT-028 does not make that downstream service-policy choice.

## Pedestrian graph and OSM snapshot

RT-028 acquires a dedicated pinned OSM snapshot from Overpass at:

`2026-09-06T12:00:00Z`.

The query envelope is derived deterministically from the union of rematerialized RT-016 population-unit coordinates and frozen final-stop coordinates, with a 500 m metric-equivalent buffer. The artifact records the full query, query SHA-256, endpoint used, bbox, snapshot timestamp and raw OSM SHA-256.

The snapshot requests:

- highway ways;
- barrier nodes and ways;
- railway ways;
- waterway ways;
- `natural=water` ways;
- `water=*` ways.

The pedestrian graph is built only from OSM highway ways that admit pedestrian travel. Motorway/trunk classes, construction/proposed/raceway ways, `foot=no/private`, and access-restricted ways without an explicit pedestrian override are excluded. `oneway:foot` is respected. Blocking barrier nodes are excluded from graph edges.

Municipal boundaries are never loaded as graph barriers.

## Routing and snapping

Network distances are obtained by Dijkstra on the directed pedestrian graph. The diagnostic walking speed is fixed at **4.8 km/h** for conversion of graph distance to seconds.

Population units and stops are attached to the nearest usable graph node only within a maximum **90 m connector**. These connector segments are not a substitute routing engine and never become a Euclidean fallback. Before a connector is accepted it is red-teamed against obstacle geometries from the same pinned OSM snapshot. A connector that crosses or runs through a railway, water or blocking barrier geometry is rejected.

The output contains explicit unreachable states. Examples include:

- no accessible graph node within the connector limit;
- connector blocked by a barrier;
- no routable node;
- disconnected graph components;
- invalid coordinates.

RT-028 never silently replaces an unreachable graph path with straight-line distance.

## Atomic output contract

`rt028_population_unit_stop_walk_matrix_v3.csv` contains one row for every population-unit × stop pair, including at minimum:

- population unit identity, weight, scope and municipality;
- stop identity, municipality and service class;
- snapped population and stop graph-node identities;
- connector distances;
- network walking distance when reachable;
- walking time in seconds and minutes when reachable;
- explicit `REACHABLE` / `UNREACHABLE` state and reason;
- walking-speed and connector-policy parameters;
- raw OSM snapshot SHA-256 and pedestrian-graph digest;
- RT-016, final-stop and OSM-query lineage.

Stable pair IDs and the canonical matrix digest are invariant to input row order.

## Independent WALK engine check

An R5/r5py WALK cross-check is optional under Issue #68. RT-012 **does** certify a deterministic `r5py 1.1.7` runtime, but its certification scope is the pinned upstream Helsinki sample fixture, not the RT-028 territorial graph. RT-028's certified territorial evidence is a pinned Overpass OSM XML snapshot, whereas r5py requires an OSM PBF input. No frozen, validated territorial XML-to-PBF conversion lineage exists in the repository.

Introducing a new XML-to-PBF preparation path only for the cross-check would therefore add an uncertified graph-preparation lineage instead of independently replaying the same frozen territorial input. The certified build records `NOT_RUN_TECHNICAL_BLOCKER`, preserves the RT-012 runtime certification and its limited fixture scope explicitly, and does not block the primary graph result.

No R5 result is fabricated, and RT-028 never averages the primary result with a second engine if they disagree.

## Downstream interface

Alpha may combine the completed matrix with candidate stop sets downstream. RT-028 itself deliberately exposes no candidate IDs, network topology, accessibility-threshold columns, scores, ranks, Pareto membership or shortlist decisions.
