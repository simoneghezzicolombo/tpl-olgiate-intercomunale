# RT-024 exact five-edge topology-neutral structural layer V3

RT-024 extends the certified RT-022 minimum-edge universe by exactly one edge.
It enumerates **all connected five-edge structural subgraphs** of the frozen
110-link reciprocal structural graph that cover all five core policy groups.

The generation algorithm has no topology-family filter. It starts from every
single structural link, repeatedly adds any incident link and canonicalises the
resulting link-id set. Every connected edge subset has a deletion order down to
a single edge, so reversing such an order proves that this expansion generates
the complete connected exact-edge layer. Duplicate expansion histories collapse
to one canonical link set.

Topology labels are applied only after generation. Therefore PATH,
TREE_BRANCHING and any cyclic forms are descriptive outcomes, not search priors.

RT-024 does not select service termini, create passenger stop patterns, rank
candidates, choose PRIMARY/RUNNER-UP, add stops, set frequencies or modify the
RT-022/RT-023 ownership boundary.

The certified scope is **edge_count = 5 only**. Structures with six or more
links remain possible and are not declared inferior.
