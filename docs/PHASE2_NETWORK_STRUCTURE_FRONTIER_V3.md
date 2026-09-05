# Phase 2 Network Structure Frontier V3

Status: **algorithmic scalability workstream, not territorial search**  
Canonical issue: **#29 RT-008**  
Branch: `phase2-network-structure-frontier-v3`

## Purpose

RT-007 validated topology-neutral connected-subgraph enumeration by exhaustively scanning edge subsets and rejecting disconnected ones. That exhaustive method is retained as the correctness oracle.

RT-008 changes only the search mechanics: it expands connected states from connected states, so disconnected subsets are never materialised as search states.

## Generation rule

Each single abstract link is a seed. A state is expanded only by adding an abstract link incident to at least one vertex already present in that state. Therefore every discovered state is connected by construction.

Duplicate edge sets reached through different expansion orders are deduplicated by their complete link-ID set.

The priority queue order is deterministic: edge count first, then lexicographic link-ID tuple.

## No topology prior

The frontier generator never consults:

- topology class;
- cycle rank;
- leaf count;
- branch count;
- articulation count;
- `FIGURE_EIGHT_LIKE` or any other descriptive shape flag.

Those quantities are computed only after a connected state has been generated and accepted under the same generic hard guards as RT-007.

The generator therefore does not prefer paths, cycles, trees, figure-eights or any other family.

## Generic hard guards

RT-008 preserves the RT-007 generic interface:

- `required_terminal_ids`;
- `required_policy_groups`;
- `terminal_policy_groups`;
- minimum and maximum edge count;
- technical search-state and output caps.

Required-terminal and group checks control whether a generated connected state is emitted, not whether it is allowed to expand. This prevents a future territorial group contract from changing the topology exploration rule.

## Exact oracle equivalence

On tractable fixtures, the connected-only generator is compared against RT-007's exhaustive subset oracle using complete structure signatures:

- selected link IDs;
- topology class;
- descriptive shape flags.

A PASS requires exact ordered equivalence, not just equal counts.

## Sparse-graph efficiency benchmark

The larger controlled fixture is a deterministic 2x5 ladder graph with 13 abstract links. With a maximum of seven selected links:

- RT-007 exhaustive oracle scans every edge subset in the requested size range, connected or not;
- RT-008 expands only unique connected states.

The audit requires exact structure equivalence and a connected-state burden below 20% of the exhaustive subset-scan burden.

Fixture semantics:

`CONTROLLED_ABSTRACT_FIXTURES_NOT_TERRITORIAL_DATA`

## Fail-closed caps

If the number of unique connected states discovered or expanded reaches the technical state cap before completion, or the output cap is exceeded, RT-008 returns the same fail-closed status used by RT-007:

`BLOCKED_ENUMERATION_CAP_REACHED_FAIL_CLOSED`

No partial structure pool is exposed as usable evidence.

## Search-efficiency diagnostics are not planning scores

RT-008 records separately:

- states discovered;
- states expanded;
- frontier expansion attempts;
- duplicate expansion attempts.

These describe computational search cost only. They are not route quality, social value, territorial coverage or topology scores.

## Explicit non-claims

RT-008 does not authorize:

- territorial terminal selection;
- passenger stop patterns;
- road-corridor choice;
- topology recommendations;
- timetable or headway selection;
- PRIMARY or RUNNER-UP;
- any weighted composite planning score.

A real territorial network search remains blocked until the corrected upstream routing-terminal evidence is available.
