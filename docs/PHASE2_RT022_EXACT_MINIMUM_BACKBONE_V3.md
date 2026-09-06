# RT-022 exact minimum-backbone scope V3

The first real RT-022 run proved the upstream territorial corpus is valid but the generic RT-008 connected frontier is too broad for the 110-link graph. It hit the 100,000-state technical cap and correctly failed closed.

This scope replaces no territorial evidence. It changes only the combinatorial enumeration strategy.

There are five frozen core municipality policy groups. Every RT-022 routing terminal belongs to exactly one of those groups. Therefore any connected structure covering all five groups needs at least four edges. At exactly four edges it must use exactly five vertices, one terminal from each municipality.

The exact enumerator consequently:

1. takes one terminal from each required municipality;
2. builds the induced set of already-admitted reciprocal structural links among those five terminals;
3. enumerates every four-link subset;
4. keeps it only when all five selected terminals are present and the structure is connected;
5. classifies topology only after generation.

No PATH, tree, loop, figure-eight, hub-spoke or other topology label is used to generate or prune candidates. The fact that an accepted four-edge/five-vertex connected graph has cycle rank zero is a mathematical consequence of the minimum-edge scope, not a topology preference.

This is a complete universe only for the **minimum-edge policy-backbone scope**. It does not claim that larger five-plus-edge structures have been enumerated or are inferior. They can be staged later if downstream evaluation shows the minimum backbone set is insufficient.

The real runner is `scripts/phase2_run_rt022_minimum_backbone_v3.py`. It preserves the frozen RT-021, RT-018, RT-019 and RT-009 lineage and uses no synthetic territorial evidence.
