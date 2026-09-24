# RT-031 Hamiltonian expressiveness diagnostic V3

## Purpose

This checkpoint asks a narrow structural question about the frozen reciprocal graph of 35 conventional stop places and 110 certified elementary structural links:

> Can the frozen graph contain a simple all-stop path, and can it contain a simple all-stop cycle, when elementary edge count is not capped at E4/E5/E6?

This is an **expressiveness diagnostic**, not a network proposal.

## Why this matters

RT-029 V4 proved that the complete certified E<=6 domain remains limited to 5–9 guaranteed passenger stops even after RT-030 corrects passenger-stop materialization. RT-031's lossless macro-contraction checkpoint then showed that most RT-029 Pareto survivors are topologically simple paths whose large elementary `edge_count` mostly represents ordinary stop-to-stop segmentation.

A Hamiltonian witness on the frozen 35-stop graph distinguishes graph-connectivity limits from limits created by the elementary-edge cap.

## Frozen substrate

The diagnostic consumes only `reciprocal_structural_links.csv` from certified RT-022:

- RT-022 run `34030321683`
- artifact `9988386073`
- artifact digest `sha256:1cab2e18eec4920cbdb348d0d9cd224c7516f8d62bc63b0eacf2a91f6fb134d7`
- run head `157badd6fc4aeaed4dcf19b08e37a48626b31b35`
- reciprocal-link CSV SHA256 `3c773163e1ffa792a72c0bda9ccd699b5be6666e01c9179a775f267baf97557a`
- exact graph: 35 vertices and 110 reciprocal structural links.

No additional stop, locality, road edge or route geometry is introduced.

## Deterministic exact search

The path and cycle solvers use deterministic depth-first exhaustive search with only necessary-condition pruning: remaining-graph connectivity, impossible remaining degree conditions and deterministic lexicographic tie-breaking. No randomization is used. Every positive witness is independently re-verified against the frozen reciprocal-link table.

Each witness must contain every one of the 35 stop identities exactly once. A Hamiltonian path contains 34 certified structural links. A Hamiltonian cycle contains 35 certified structural links including the closing edge.

## Interpretation boundary

A positive witness proves only structural-graph expressiveness. It does **not** establish a recommended passenger route, a shortest or operationally efficient line, a timetable, headway or cycle time, turn-continuous composition of independently certified elementary realizations, a final RT-031 search space or a winner.

An all-stop structural ordering must therefore never be presented as a proposed service merely because it exists.

## PASS meaning

`PASS_HAMILTONIAN_EXPRESSIVENESS_DIAGNOSTIC_NOT_NETWORK_SEARCH_PASS` means only that the frozen reciprocal structural graph has the all-stop structural expressiveness demonstrated by the certified witnesses. RT-031 remains open until a topology-neutral macro-search contract is separately defined and certified.
