# Phase 2 Network Structure Search V3

Status: **algorithmic infrastructure, not territorial network selection**  
Canonical issue: **#27 RT-007**  
Branch: `phase2-network-structure-search-v3`

## Purpose

RT-005 showed that a reproducible search can still be wrong if the search space encodes an unsuitable planning formulation. RT-006 therefore separated legal road routing from passenger-stop design and produced a neutral alternative-corridor library. RT-007 adds the next layer: enumeration of abstract connected network structures without prescribing a topology family in advance.

This layer is deliberately upstream of passenger-stop materialisation, accessibility/equity evaluation, timetable design and operational robustness.

## Abstract graph contract

The structural core sees only:

- abstract terminal IDs;
- abstract terminal-pair link IDs;
- optional generic required terminal IDs;
- optional generic policy-group memberships.

It does **not** see settlement names, stop names, road geometry, passenger stop patterns, travel demand, accessibility, route kilometres, timetable values or recommendations.

One abstract link represents one terminal pair for which an upstream corridor layer can provide at least one admissible road connection. Parallel links for the same unordered terminal pair are rejected in this structural layer. Corridor variants remain an upstream/downstream routing detail and do not create duplicate topological edges.

## Generation before classification

The generator enumerates edge subsets deterministically, keeps only connected structures satisfying the explicitly supplied generic hard guards and only then computes topology diagnostics.

There is no generation branch saying "make a loop", "make a figure eight" or "make two branches".

The current descriptive taxonomy includes:

- `PATH`;
- `TREE_BRANCHING`;
- `CYCLE`;
- `UNICYCLIC_BRANCHING`;
- `BICYCLIC_ARTICULATED`;
- `BICYCLIC_NONARTICULATED`;
- `MULTICYCLIC`.

A `FIGURE_EIGHT_LIKE` flag is added only after generation when a bicyclic articulated graph has one articulation vertex of degree four and every other vertex has degree two. The flag is descriptive evidence, not an admission rule or preferred form.

## Structural dimensions remain separate

For every connected structure the core records separately:

- vertex count;
- edge count;
- cycle rank `m - n + 1`;
- maximum degree;
- number of leaves;
- number of branch vertices;
- articulation-vertex count and IDs;
- topology class;
- descriptive shape flags.

No weighted composite score is produced.

## Generic policy guards

The structural generator may receive:

- `required_terminal_ids`, for example a later hub requirement expressed by ID;
- `required_policy_groups`, with `terminal_policy_groups` describing which generic groups each terminal can satisfy.

The core does not know what those groups mean. A later territorial interface may use them for explicit policy decisions such as municipal coverage, but the structural algorithm itself remains unchanged.

Missing required terminals or required groups fail closed.

## Enumeration and technical caps

Connected-subgraph enumeration is exponential in the number of candidate pair links. RT-007 therefore exposes explicit technical controls:

- minimum and maximum number of edges examined;
- maximum number of edge subsets scanned;
- maximum number of accepted structures.

These have semantics:

`TECHNICAL_ENUMERATION_CONTROLS_NOT_POLICY_WEIGHTS`

If a cap is reached before the requested search is exhausted, the status becomes:

`BLOCKED_ENUMERATION_CAP_REACHED_FAIL_CLOSED`

and the partial structures are **not returned as a usable candidate pool**. This prevents a lexicographically early partial enumeration from being mistaken for a complete design search.

## Algorithmic audit

The RT-007 audit uses a deliberately controlled abstract five-vertex complete graph. This is a software fixture, not territorial evidence.

The same generator must produce, without topology-specific generation logic:

- paths;
- cycles;
- branching trees;
- unicyclic branching structures;
- articulated and non-articulated bicyclic structures;
- at least one `FIGURE_EIGHT_LIKE` structure.

Separate tests verify deterministic output, generic required-terminal and policy-group guards, rejection of parallel terminal pairs and fail-closed enumeration caps.

Fixture semantics are explicitly:

`CONTROLLED_ABSTRACT_FIXTURE_NOT_TERRITORIAL_DATA`

## What RT-007 does not authorize

A successful RT-007 audit does **not** authorize:

- a territorial route candidate;
- a complete passenger-stop pattern;
- a recommended topology;
- a figure-eight recommendation;
- a headway;
- a timetable;
- PRIMARY or RUNNER-UP selection;
- direct comparison with current-service accessibility.

A real territorial search remains blocked until the corrected multi-operator stop/terminal evidence is available and an audited interface maps that evidence into generic terminal IDs, pair links and policy-group memberships.

## Downstream architecture

The intended V3 sequence is:

1. corrected multi-operator physical stop / routing-terminal evidence;
2. RT-006 legal alternative corridor library;
3. RT-007 abstract connected network structures;
4. materialisation of complete passenger stop patterns on selected road corridors;
5. accessibility, equity, demand and S8 diagnostics;
6. timetable and operating-km evaluation;
7. robustness and simplicity diagnostics;
8. human-readable geographic Gate;
9. only then, if explicitly authorised, finalist selection.

This ordering prevents structural waypoints, passenger stops and topology labels from being conflated again.
