# Phase 2 Complete Directed Pair Coverage V3

Status: **routing-test-universe infrastructure, not network selection**  
Canonical issue: **#33 RT-010**  
Branch: `phase2-complete-directed-pairs-v3`

## Purpose

RT-009 distinguishes an untested reverse direction from an infeasible reverse direction. RT-010 prevents the upstream cause of that ambiguity from being hidden: selective or incomplete pair requests.

For any future validated routing-terminal universe, the canonical mode creates the complete ordered non-self pair manifest before corridor generation begins.

## Complete pair universe

For `N` unique routing terminal IDs, the manifest contains exactly:

`N * (N - 1)`

directed requests.

Every unordered terminal pair therefore has one A->B request and one B->A request. Pair IDs are deterministic and directional.

The canonical generator does not consult distance, geography, settlement identity, topology, demand, accessibility, road-corridor count or any planning score while deciding which pair requests exist.

## Technical scale cap

`max_directed_pairs` is a resource guard only.

If the complete manifest would exceed the cap, RT-010 returns:

`BLOCKED_COMPLETE_PAIR_MANIFEST_EXCEEDS_TECHNICAL_CAP`

and an empty manifest. It does not truncate the terminal list, return the lexicographically first pairs or sample the search space.

Any future scalable screening alternative would require its own audited contract rather than silently changing the meaning of a complete pair universe.

## Execution-completeness audit

After RT-006 processes a pair manifest, RT-010 compares the result table to the original manifest and checks:

- one result row for every requested pair ID;
- no duplicate result pair IDs;
- no unrequested result pair IDs;
- exact source/target identity match for each pair ID.

A missing pair-result row means:

`MISSING_OUTPUT_IS_INCOMPLETE_EXECUTION_NOT_NO_ROUTE`

This is distinct from an explicitly returned result whose Gate-D route status is false.

## Why this matters downstream

RT-009 can only certify reciprocal structural-link availability if both directions were genuinely tested. With a complete RT-010 manifest plus a complete-execution PASS, every unordered terminal pair has an explicit directional result in both directions. RT-009 may then distinguish true no-route / no-admitted-corridor states from successful reciprocity without ambiguity caused by missing requests.

## Explicit non-claims

RT-010 does not claim that:

- every directed pair has a legal route;
- every reciprocal pair becomes a structural link;
- every structural link belongs in a network;
- every supplied routing terminal is a passenger stop;
- any topology or route is preferred.

RT-010 is only a completeness contract for the routing test universe.
