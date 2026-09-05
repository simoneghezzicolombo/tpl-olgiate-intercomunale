# Phase 2 Alternative Corridor Generator V3

Status: **algorithmic audit workstream, not network selection**  
Canonical issue: **#22 RT-006**  
Branch: `phase2-efficient-alternative-corridors-v3`

## Purpose

RT-005 showed that the previous search could be computationally reproducible while still asking the wrong planning question. The V3 corridor work therefore separates three objects that must not be conflated:

1. legal road routing on the frozen Gate-D graph;
2. alternative road corridors;
3. passenger stop patterns and service design.

This workstream concerns only the first two. It does not create, rank or validate stops and does not depend on the stop-source completeness work running separately in draft PR #21.

## Why the exhaustive K-shortest implementation is not the production engine

`src/phase2_restriction_aware_ksp.py` builds an edge-state graph and uses exact `networkx.shortest_simple_paths` enumeration. It is valuable as an independent correctness oracle because it makes the turn-restriction state explicit and can enumerate exact alternatives on small graphs.

On the frozen real Gate-D graph, however, the corresponding CI audit remained in the real-graph equivalence step for hours. Exact full-state Yen is therefore retained as an oracle and regression tool, not treated as the production corridor generator.

## Production-search architecture

`src/phase2_alternative_corridor_generator_v3.py` follows a bounded alternative-route architecture:

1. compute the shortest legal route using the existing certified Gate-D `restriction_aware_one_to_many` Dijkstra;
2. preserve this route unchanged as `CERTIFIED_GATE_D_SHORTEST` routing evidence;
3. assign deterministic temporary penalties to edges already used by generated routes;
4. rerun a stateful Dijkstra using the same Gate-D turn-restriction semantics;
5. retain true running time and true distance independently from the penalized exploration cost;
6. reject duplicate sequences, physically cyclic bus corridors, excessive technical detours and excessive technical overlap;
7. repeat only for a bounded number of search rounds.

This is conceptually aligned with mature road-routing practice such as GraphHopper's edge-based alternative routing: turn costs require edge-based traversal, and practical alternative generation is bounded and filtered rather than an unbounded enumeration of every simple path.

## Turn-restriction state

The generator uses the same routing state required by Gate D:

`(current_node, previous_node, incoming_osm_way)`

Every transition is checked by the existing `transition_allowed` function. Therefore penalties can change which legal route is explored, but cannot make an illegal movement legal.

## Two different loop contracts

A crucial distinction discovered during the K-shortest audit is preserved:

- Gate D answers **what is the shortest legal road path?** A legal turn restriction can, in rare cases, imply a small maneuver that revisits a physical road node.
- The corridor generator answers **what paths are admissible as candidate bus corridors?** A path that revisits a physical road node is rejected from the corridor pool.

A cyclic certified shortest path is therefore not deleted or rewritten. It remains routing evidence, while a loopless alternative can become the first corridor-admissible path.

## Metrics are separate, not a composite score

The generator records separately:

- true Gate-D running minutes;
- true Gate-D road distance;
- temporary penalized search cost;
- runtime factor versus the certified shortest route;
- shared directed-edge runtime versus already admitted alternatives;
- physical-node-loop status;
- turn legality;
- provenance and generation round.

There is no weighted score combining these dimensions.

## Technical exploration controls

Current audit parameters include:

- `max_alternatives`;
- `max_generation_rounds`;
- `penalty_increment`;
- `max_runtime_factor`;
- `max_shared_runtime_fraction_allowed`.

Their semantics are explicitly:

`TECHNICAL_EXPLORATION_PARAMETERS_NOT_POLICY_WEIGHTS_OR_THRESHOLDS`

They control how widely the algorithm searches during the audit. They do not encode social preference, territorial priority or an optimal bus-network definition. Sensitivity should be examined before any later canonical design search.

## Independent correctness checks

The V3 tests use two layers.

### Small controlled graphs

The bounded generator is compared directly with the exact state-graph Yen oracle on tractable graphs, including a turn-restriction case. This verifies that the new efficient search preserves the legal shortest route and can recover known legal alternatives.

### Frozen real Gate-D graph

`scripts/phase2_audit_alternative_corridor_generator_v3.py` selects deterministic OD fixtures from the frozen Gate-D seed-path evidence. These OD records are used only as routing regression fixtures, not as a stop universe or route prescription.

For each fixture the audit requires:

- exact certified baseline edge sequence;
- exact baseline runtime within `1e-9` minutes;
- exact baseline distance within `1e-6` metres;
- legal turn transitions;
- no physical-node loop in admitted corridors;
- no admitted corridor faster than the certified shortest route;
- deterministic repeated output on a real-graph fixture.

The workflow has a bounded CI timeout so a theoretically correct but operationally unusable search cannot silently become the production generator.

## Explicit non-claims

This workstream does **not** authorize any of the following:

- complete K-shortest enumeration;
- optimal network;
- recommended corridor;
- passenger stop pattern;
- topology winner;
- headway winner;
- PRIMARY;
- RUNNER-UP.

Every output remains `ALTERNATIVE_POOL_NOT_NETWORK_RECOMMENDATION` until it is later combined with the corrected multi-operator stop inventory, territorial service contract, accessibility/equity evidence, operations and robustness under a separately audited design-search contract.
