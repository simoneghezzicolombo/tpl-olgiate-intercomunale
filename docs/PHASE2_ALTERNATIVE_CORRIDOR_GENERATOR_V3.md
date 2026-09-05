# Phase 2 Alternative Corridor Generator V3

Status: **PASS as routing/corridor-generation infrastructure, not network selection**  
Canonical issue: **#22 RT-006**  
Branch: `phase2-efficient-alternative-corridors-v3`

## Purpose

RT-005 showed that the previous search could be computationally reproducible while still asking the wrong planning question. The V3 corridor work therefore separates three objects that must not be conflated:

1. legal road routing on the frozen Gate-D graph;
2. alternative road corridors;
3. passenger stop patterns and service design.

This workstream concerns only the first two. It does not create, rank or validate passenger stops and remains separate from the stop-source completeness work in draft PR #21.

## Why the exhaustive K-shortest implementation is not the production engine

`src/phase2_restriction_aware_ksp.py` builds an edge-state graph and uses exact `networkx.shortest_simple_paths` enumeration. It remains valuable as an independent correctness oracle because it makes the turn-restriction state explicit and can enumerate exact alternatives on small graphs.

On the frozen real Gate-D graph, however, workflow run `33962581611` spent about **29 minutes 36 seconds** in the real-graph equivalence step and was cancelled by its 30-minute CI timeout before it could complete the audit. Exact full-state Yen is therefore retained as an oracle and regression tool, not treated as the production corridor generator.

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

Every transition is checked by the existing `transition_allowed` function. Penalties can therefore change which legal route is explored, but cannot make an illegal movement legal.

## Two different loop contracts

A crucial distinction discovered during the K-shortest audit is preserved:

- Gate D answers **what is the shortest legal road path?** A legal turn restriction can, in rare cases, imply a maneuver that revisits a physical road node.
- The corridor generator answers **what paths are admissible as candidate bus corridors?** A path that revisits a physical road node is rejected from the corridor pool.

A cyclic certified shortest path is therefore not deleted or rewritten. It remains routing evidence, while a loopless alternative can become the first corridor-admissible path.

This distinction was confirmed on the frozen real graph. Regression fixture `FIXTURE_04` (`gate_d:CAPRINO` → `gate_d:SAN_ZENO`) has a certified shortest path that revisits a physical node, while the bounded generator found two loopless admitted alternatives. The identifiers are routing regression fixtures only and do not certify a passenger stop at San Zeno.

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

## Generator audit result

Workflow run **`33963864083`** is PASS.

The focused audit produced:

- 10 bounded-generator / exact-oracle bridge tests PASS;
- 9 frozen Gate-D regression tests PASS;
- 5/5 real-graph OD fixtures PASS;
- exact Gate-D baseline edge sequence preserved on all five fixtures;
- 41 generated paths examined;
- 13 corridors admitted;
- deterministic repeat on the frozen graph PASS;
- real-graph generation audit completed in **9.922 seconds** excluding the repeat check;
- slowest fixture completed in **4.187 seconds**.

The uploaded evidence artifact is `9968799015`, with ZIP SHA256 `63da31238e4105880adff56d08e58b2e4dc8926c0f33fd4836bb84ab78cba767`.

## Technical exploration controls

The generator exposes:

- `max_alternatives`;
- `max_generation_rounds`;
- `penalty_increment`;
- `max_runtime_factor`;
- `max_shared_runtime_fraction_allowed`.

Their semantics are explicitly:

`TECHNICAL_EXPLORATION_PARAMETERS_NOT_POLICY_WEIGHTS_OR_THRESHOLDS`

They control how widely the algorithm searches. They do not encode social preference, territorial priority or an optimal bus-network definition.

## Parameter sensitivity

Because one technical configuration must not become canonical by accident, `scripts/phase2_audit_alternative_corridor_sensitivity_v3.py` evaluates a deterministic grid:

- penalty increment: `0.10`, `0.20`, `0.35`;
- runtime envelope: `1.25`, `1.50` times the Gate-D shortest runtime;
- overlap envelope: `0.75`, `0.90`;
- three admitted alternatives maximum per setting;
- ten generation rounds maximum.

This yields **12 configurations × 5 frozen fixtures**.

Workflow run **`33964236575`** is PASS and its evidence is persisted. Across the grid:

- 12/12 configurations passed;
- the certified Gate-D baseline remained exact in every configuration;
- the deduplicated union contains **25 admitted fixture paths**;
- **21** of those are non-baseline alternatives;
- no technical configuration was selected as the preferred one.

The union contract is:

`UNION_ACROSS_TECHNICAL_EXPLORATION_SETTINGS_NOT_FREQUENCY_WEIGHTED_NOT_RANKED`

A path appearing under many settings may be described as search-stable, but its appearance frequency is explicitly **not** a quality score, probability, vote or recommendation.

## Neutral corridor-library interface

`src/phase2_corridor_library_v3.py` provides the downstream batch interface. It accepts only:

- an upstream routing-terminal table;
- an upstream requested-pair table;
- one or more technical exploration settings.

It deliberately does not decide which terminals should exist, does not assume that a routing terminal is a passenger stop and does not choose which terminal pairs form the network. The same road path found under different settings is stored once, with appearance metadata kept separately.

The corridor-library CI run **`33964217624`** is PASS. Its contract is:

- `ROUTING_CORRIDOR_LIBRARY_INTERFACE_NOT_NETWORK_SELECTION`;
- `UPSTREAM_ROUTING_TERMINALS_NOT_ASSUMED_TO_BE_PASSENGER_STOPS`;
- `UPSTREAM_REQUESTED_PAIRS_NOT_AUTOMATIC_TOPOLOGY`;
- `DEDUPLICATED_UNION_ACROSS_TECHNICAL_SETTINGS_NOT_RANKED`.

This is the interface that the corrected multi-operator stop work can feed later without changing the road-routing algorithm.

## Independent correctness checks

The V3 tests use two layers.

### Small controlled graphs

The bounded generator is compared directly with the exact state-graph Yen oracle on tractable graphs, including a turn-restriction case. This verifies that the efficient search preserves the legal shortest route and can recover known legal alternatives.

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

RT-006 therefore closes only the **road-corridor generation infrastructure**. The next workstream must define and audit how routing terminals and alternative corridors may be assembled into candidate network structures without hard-coding the old double-loop/figure-eight topology. Passenger stops, accessibility/equity, timetables, operations and robustness remain later, separate stages.