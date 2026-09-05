# Phase 2 RT-019 — Technical pair-query anchors and elementary corridor reduction V3

## Status of this document

This workstream defines a downstream interface. It does **not** select a network,
service terminus, capolinea, topology, timetable, headway, PRIMARY or RUNNER-UP.

Baseline: RT-018 PASS on `phase2-final-stop-materialization-v3`.

## Problem

The final 36-stop handoff deliberately states that the operational stop-place
file is not a routing-terminal list: stop existence does not imply terminal
status.

At the same time, RT-010 needs an explicit `routing_terminal_id` universe to
build complete directed pair requests, RT-006 needs graph-bound source/target
nodes to generate corridors, and RT-007/008 need a tractable undirected
structural graph.

Using only manually chosen termini would introduce a hidden geographic/topology
prior. Treating all 35 conventional stops as actual service termini would make
an unsupported policy claim and would create a very dense structural graph.

RT-019 separates those concepts.

## 1. Pair-query routing anchor ≠ service terminus

For conventional-service corridor discovery, every **route-ready**
`CONVENTIONAL_TPL` stop place is allowed to act as a technical pair-query
source/target.

The compatibility field name remains `routing_terminal_id` because RT-010 and
RT-006 already use it, but RT-019 freezes its meaning as:

> technical exhaustive road-routing query anchor, not passenger-service
> terminus/capolinea.

The stable ID is the final `stop_place_id`.

`SPECIAL_SERVICE` is not included automatically in the conventional query
anchor manifest.

On the RT-018 current-graph compatibility evidence this produces:

- 36 final stop places total;
- 35 conventional technical pair-query anchors;
- 1 special-service stop excluded from automatic conventional anchors;
- 35 × 34 = 1,190 complete directed pair requests;
- 595 unordered identity pairs.

The 1,190 requests are an anti-bias completeness device. They do not state that
1,190 route legs, 595 links or 35 service termini should exist.

## 2. RT-017 dependency

Current RT-018 graph attachment is a compatibility smoke only.

Before territorial use, all pair-query anchors must be rebound against the
frozen RT-017 border-neutral graph. If any conventional stop is no longer
route-ready under that graph, the anchor builder fails closed. It does not
silently drop the stop and shrink the pair universe.

RT-019 therefore does not materialize a real final elementary structural graph
before RT-017 PASS.

## 3. Elementary corridor definition

RT-006 can produce multiple admitted directional corridor alternatives for one
technical pair. RT-018 then materializes exact ordered existing-stop
occurrences on each corridor path.

For each admitted corridor alternative A→B:

- A must occur on the first path-node boundary;
- B must occur on the last path-node boundary;
- a conventional stop occurrence is *strictly intermediate* only when its
  `path_node_position` lies strictly between those boundaries;
- occurrences whose `stop_place_id` is A or B are not third stops, even if a
  loop revisits A or B;
- any other conventional stop-place occurrence makes the corridor
  **DECOMPOSABLE**;
- no such third occurrence makes it **ELEMENTARY**.

The classification is based only on exact RT-018 path occurrences. It does not
use Euclidean distance, stop names, municipality names, route names or manual
service areas.

Third-stop repetitions remain explicit in the audit. Ordered unique via-stop
IDs are also reported. A missing source or target boundary occurrence blocks
elementary status rather than being silently inferred.

## 4. Why decomposable corridors remain evidence

If an A→C corridor physically encounters B, the final stop-place layer already
makes B explicit. The A→C path is therefore not required as a *primitive*
structural edge.

This does not delete or invalidate A→C routing evidence. RT-019 retains every
corridor row and only changes which admitted paths are exposed to RT-009 as
primitive structural candidates.

This distinction also avoids treating an abstract structural-link boundary as a
forced passenger transfer. RT-007/008 enumerate physical network structures;
continuous passenger route/service construction remains downstream.

## 5. Multiple alternatives and directionality

Elementarity is evaluated **per corridor alternative**, not per pair and not
only on the shortest path.

Therefore:

- if A→B has three admitted alternatives and one is elementary, the A→B
  direction still has elementary availability;
- if B→A has no elementary admitted alternative, A–B is not an eligible
  reciprocal undirected structural link;
- directional asymmetry from one-way streets or different route geometry is
  preserved.

RT-019 delegates final undirected reciprocity semantics to the already validated
RT-009 adapter after filtering the corridor pool to elementary admitted paths.

## 6. Special service

Casa di Comunità remains part of the frozen 36-stop identity layer and remains
graph-attachable under RT-018. It is not an automatic conventional pair-query
anchor and its occurrence does not decompose a conventional corridor under the
default RT-019 contract.

No Cassina/Circolare Meratese interchange logic is introduced.

## 7. Determinism and fail-closed rules

RT-019:

- uses no random search;
- never chooses pairs by municipality, distance or name;
- preserves exact stop-place identity;
- rejects duplicate/blank identities;
- requires one graph epoch for the technical anchor manifest;
- fails if an allowed conventional stop is not route-ready;
- requires endpoint stop occurrences for elementary status;
- preserves all corridor evidence rows;
- uses RT-010 for complete directed pair identity;
- uses RT-009 for reciprocal structural-link eligibility.

## 8. Outputs

The audit materializes:

- `pair_query_anchor_manifest_v3.csv`;
- `complete_directed_pair_manifest_v3.csv`;
- controlled-fixture corridor elementarity evidence;
- controlled-fixture reciprocal pair audit;
- `elementary_corridor_reduction_v3_validation.json`.

The real territorial elementary corridor graph remains explicitly
`BLOCKED_PENDING_RT017_PASS_CORRIDOR_CORPUS` until Agent A freezes the RT-017
graph and Alpha reruns attachment, complete pair routing, corridor
materialization and RT-019 reduction on that epoch.

## Claims not authorized

This workstream does not authorize:

- service terminus/capolinea selection;
- route topology selection;
- a preferred figure-eight or any other topology family;
- network ranking or winner;
- timetable/headway selection;
- PRIMARY or RUNNER-UP.
