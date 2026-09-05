# Phase 2 Corridor Reciprocity Contract V3

Status: **semantic interface workstream, not territorial network selection**  
Canonical issue: **#31 RT-009**  
Branch: `phase2-corridor-reciprocity-contract-v3`

## Purpose

RT-006 produces directional road-corridor evidence. RT-007 and RT-008 enumerate simple undirected structural links. RT-009 defines the only safe bridge between these representations for a later **bidirectional undirected** network search.

The key rule is that one legal A->B route is not evidence that B->A is feasible, and an absent B->A request is not evidence that B->A is impossible.

## Three questions per direction

For each ordered direction of an unordered terminal pair, RT-009 records separately:

1. whether the direction was explicitly requested/tested;
2. whether Gate D found a legal road route;
3. whether the RT-006 audited corridor union contains at least one admitted loopless corridor.

These states must never be collapsed.

## Eligibility statuses

Each unordered pair receives exactly one status:

- `UNTESTED_DIRECTION`: at least one direction was not explicitly requested;
- `NO_GATE_D_ROUTE_IN_DIRECTION`: both directions were requested but at least one has no legal Gate-D route;
- `NO_ADMITTED_CORRIDOR_IN_DIRECTION`: both have legal Gate-D routes but at least one has no RT-006-admitted corridor;
- `RECIPROCAL_BIDIRECTIONAL_CORRIDOR_AVAILABLE`: both directions were requested and each has at least one admitted corridor.

Only the final state emits an undirected structural link for RT-007/008-style bidirectional search.

## Not requested is not infeasible

The contract explicitly records:

`NOT_REQUESTED_IS_UNKNOWN_NOT_INFEASIBLE`

This prevents incomplete pair enumeration upstream from silently deleting possible network links.

## Corridor variants do not create structural parallel edges

RT-006 may retain multiple road-corridor variants for the same ordered terminal pair. RT-009 counts those variants as directional evidence but emits at most one structural link for the unordered terminal pair.

Road-corridor choice remains downstream. Structural topology therefore cannot be distorted merely because one terminal pair has more routing alternatives than another.

## Directional diagnostics remain separate

For each direction the adapter may record independently:

- admitted corridor count;
- minimum model running minutes among admitted corridors;
- minimum road distance among admitted corridors.

These are descriptive directional diagnostics. No asymmetry score, composite score or eligibility threshold is introduced here.

## Deterministic structural link identity

An unordered structural link ID is derived only from the sorted terminal IDs. Reversing source and target rows or reordering the input tables does not change the link identity or status.

Duplicate requests for the same ordered terminal pair are rejected rather than silently aggregated. Corridor rows referring to unknown pair IDs are rejected.

## Directional-only services remain outside scope

RT-009 authorizes only eligibility for a later **bidirectional undirected structural search**. It does not say that a one-direction-only corridor is useless in all transport design.

One-way circulators, direction-specific structures, asymmetric route variants and timetable operations require a separately audited directed-service formulation. They must not be smuggled into the undirected structural graph by weakening reciprocity.

## Explicit non-claims

RT-009 does not select:

- territorial routing terminals;
- settlements;
- passenger stops;
- road-corridor variants;
- topology;
- timetable or headway;
- PRIMARY or RUNNER-UP.

The real territorial link universe remains blocked until the upstream terminal inventory is corrected and the required directed pair requests are explicitly generated.
