# RT-031 macro-structure decoupling V3

## Status

This checkpoint is a **macro-contraction diagnostic**, not a new network search and not a final RT-031 PASS.

It tests whether the certified elementary structural graph can be transformed losslessly into a representation where ordinary degree-2 passenger stops do not increase topological complexity.

## Motivation

The certified RT-030 corpus adds only two non-vertex intermediate passenger-stop identities globally. Therefore the complete E4+E5+E6 domain is structurally capped at at most nine guaranteed passenger stops. Continuing to increase elementary `edge_count` therefore conflates two different concepts:

- network topology/branching complexity;
- passenger-stop segmentation along otherwise simple corridors.

RT-031 separates them.

## Contraction rule

For each connected structure:

1. rebuild its undirected elementary graph from frozen RT-023 structural-link endpoints;
2. recompute connectivity, vertex count, edge count and cycle rank rather than trusting labels;
3. identify every vertex of degree 2;
4. suppress degree-2 vertices from the **macro graph only**;
5. preserve those vertices in the ordered passenger-vertex sequence of the containing macro edge;
6. partition every elementary structural link into exactly one macro edge;
7. preserve cycle rank and branching degree sequence.

A degree-2 passenger stop is therefore never deleted from service evidence. It stops counting as a topological junction.

No municipality, stop name, desired locality, route ranking or service-terminal assumption is used by the contraction.

## Macro examples

- a path A-B-C-D-E becomes one `PATH_CORE` macro edge A→E carrying B/C/D as internal passenger vertices;
- a Y-shaped tree keeps its degree-3 junction and three macro arms;
- a cycle with a branch becomes a cyclic branching core with a loop macro edge plus its branch;
- a pure cycle is represented canonically as one `PURE_CYCLE_CORE` object without interpreting any stop as a service terminus.

## Production diagnostic contract

Inputs are the certified complete-through-E6 structure universes and frozen RT-023 realization catalog:

- E4 / RT-022: 88 structures;
- E5 / RT-024: 4,076;
- E6 / RT-025: 108,679;
- combined: 112,843;
- RT-023: 110 structural links / 288 directional realizations.

The production diagnostic must fail closed unless:

- structure IDs are unique;
- every structure is connected;
- declared vertex/edge/cycle-rank values reproduce from frozen link endpoints;
- every elementary link is visited exactly once by the macro-edge partition;
- total elementary-link membership before and after contraction is identical;
- input ordering cannot change canonical macro chains.

## Expected semantics

Outputs:

- `rt031_macro_structure_signatures.csv`
- `rt031_macro_edge_chains.csv`
- `rt031_macro_contraction_audit.json`

The macro-edge chain table retains the exact ordered passenger vertex sequence and elementary-link sequence. It is therefore reversible at the structural-link level.

The only valid positive status for this checkpoint is:

`PASS_MACRO_CONTRACTION_DIAGNOSTIC_NOT_SEARCH_PASS`

This means the decoupled representation is technically viable on the frozen corpus. It does not authorize new network selection, a macro-complexity cap or a winner.

## Initial local real-corpus finding

Before CI certification, the implementation reproduced all 112,843 structures and preserved exactly 672,806 elementary-link memberships. The resulting macro classes were:

- `PATH_CORE`: 19,572
- `TREE_BRANCHING_CORE`: 90,507
- `CYCLIC_BRANCHING_CORE`: 2,764

The current RT-029 V4 Pareto union is overwhelmingly macro-simple: 408/481 are `PATH_CORE`, 72 are single-degree-3 branching cores and only one has two degree-3 branch vertices. This is diagnostic evidence only and is not used to generate or rank structures.

## Next RT-031 work after this checkpoint

A later checkpoint must define how to search **directly** over macro structures while allowing arbitrarily many certified degree-2 passenger stops along macro edges. That search problem is deliberately not solved by this contraction diagnostic.
