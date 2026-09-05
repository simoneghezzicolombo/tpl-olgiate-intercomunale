# Phase 2 Corridor Generator Restriction Audit V3

Status: **RT-006 design constraint confirmed**

## Finding

A standard K-shortest-path call on a simplified road-node graph is **not sufficient** for the canonical Phase-2 corridor generator.

The frozen Gate-D road model is directed and preserves turn restrictions using routing state. `src/phase2_frozen_graph.py` represents each Dijkstra state as:

```text
(current_node, previous_node, incoming_osm_way)
```

The transition from that state to an outgoing edge is checked by `transition_allowed()` against the Gate-D turn-rule index. The frozen artifact serializes 564 applicable node-level rules after source filtering, with 535 rule keys present on the graph.

Therefore two arrivals at the same physical road node can have different legal onward moves depending on the incoming way and previous node. Collapsing the model to a simple `node -> node` cost graph can create routes that are cheaper mathematically but illegal under the certified Gate-D road semantics.

## External algorithm audit consequence

`networkx.shortest_simple_paths()` is a mature, tested BSD-licensed implementation of Yen's K-shortest loopless-path method and is attractive as a reusable primitive. However:

- the function is not implemented for `MultiGraph`/`MultiDiGraph`;
- its default state is the graph node, not Phase-2's incoming-way routing state;
- using it directly on a simplified `DiGraph` would lose exactly the turn information Gate D was built to preserve.

The 2026 `AHolliday/transit_learning` implementation confirms that Yen-style K-shortest path pools are a useful TNDP route-generation pattern, but its benchmark graph assumptions are also simpler than the Brianza Gate-D road semantics.

## Required V3 corridor-generator contract

A canonical independent corridor pool must therefore satisfy all of the following:

1. use the exact frozen Gate-D bus-operable directed edges;
2. preserve parallel-edge identity where operationally relevant;
3. enforce one-way semantics already encoded in the directed graph;
4. enforce Gate-D node turn restrictions using incoming-way state;
5. return the exact ordered `edge_id` path, not only node IDs;
6. generate multiple loopless alternatives per relevant source/target pair;
7. use deterministic ordering and deterministic tie-breaking;
8. never use settlement names such as Arlate, Bernaga or Beverate as hidden mandatory waypoints unless they are part of an explicit policy scenario;
9. remain separate from passenger-stop selection;
10. be benchmarked against a public K-shortest-path fixture and against the existing Gate-D restriction-aware shortest-path result for the first path.

## Implementation options to benchmark

### Option A — state-expanded graph + mature Yen primitive

Build a derived routing-state graph whose vertices encode sufficient incoming-edge/way state to make legal turns local. Run `NetworkX shortest_simple_paths()` on that state graph, then project each path back to ordered Gate-D `edge_id`s.

Advantages:

- reuses a heavily tested Yen implementation;
- deterministic path ordering can be audited;
- avoids copying GPL route-generation code.

Risks:

- state graph may be substantially larger than the 104,071-node base graph;
- looplessness in state space is not automatically identical to no repeated physical road node;
- construction must prove equivalence to `transition_allowed()`.

### Option B — restriction-aware Yen wrapper around existing Gate-D shortest-path logic

Implement Yen's deviation/root-path logic locally, but use a generalized version of the existing restriction-aware Dijkstra as the spur-path oracle, supporting temporary banned edges/nodes while retaining incoming-way state.

Advantages:

- preserves existing audited Gate-D routing semantics directly;
- output remains exact Gate-D edge IDs;
- easier to compare first-path equality with existing reduced-path matrices.

Risks:

- more custom code must be tested;
- care is required when a spur path begins with an already established root path, because the spur's initial state must inherit the root path's incoming way and previous node.

### Option C — external routing engine as generator

Use an external road-routing engine to produce alternative bus paths.

Current verdict: **not preferred** unless it can ingest the same frozen edge/restriction semantics and produce reproducible edge-level lineage. Replacing the Gate-D road model would destroy an already certified part of the project without a demonstrated benefit.

## Provisional recommendation

Benchmark **Option B** first and Option A as an independent cross-check.

Reason: Phase 2 already has a deterministic, restriction-aware Dijkstra implementation and exact edge lineage. Extending that semantic core to K-shortest alternatives changes less of the certified stack than rebuilding routing in another engine.

This is still an audit recommendation, not yet a canonical generator. No candidate network is authorized until the K-shortest implementation passes equivalence, looplessness, determinism and public benchmark tests.
