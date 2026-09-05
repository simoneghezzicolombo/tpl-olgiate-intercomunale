#!/usr/bin/env python3
"""Algorithmic RT-008 audit: connected-only search versus RT-007 oracle."""
from __future__ import annotations

import json
from pathlib import Path

from src.phase2_network_structure_frontier_v3 import (
    enumerate_connected_structures_frontier,
)
from src.phase2_network_structure_search_v3 import (
    AbstractLink,
    enumerate_connected_structures,
)

OUT = Path(
    "outputs/phase2/network_structure_frontier_v3/"
    "network_structure_frontier_v3_validation.json"
)


def k5_links():
    nodes = ["A", "B", "C", "D", "E"]
    links = []
    counter = 0
    for index, u in enumerate(nodes):
        for v in nodes[index + 1 :]:
            counter += 1
            links.append(AbstractLink(f"L{counter:02}", u, v))
    return links


def ladder_links(columns=5):
    links = []
    counter = 0
    for row in ["T", "B"]:
        for index in range(columns - 1):
            counter += 1
            links.append(
                AbstractLink(
                    f"L{counter:02}", f"{row}{index}", f"{row}{index + 1}"
                )
            )
    for index in range(columns):
        counter += 1
        links.append(AbstractLink(f"L{counter:02}", f"T{index}", f"B{index}"))
    return links


def signature(result):
    return [
        (item.link_ids, item.topology_class, item.shape_flags)
        for item in result["structures"]
    ]


def main():
    k5 = k5_links()
    exhaustive = enumerate_connected_structures(
        k5,
        max_edges=6,
        max_subsets_scanned=2_000,
        max_structures=2_000,
    )
    frontier = enumerate_connected_structures_frontier(
        k5,
        max_edges=6,
        max_states=2_000,
        max_structures=2_000,
    )
    if signature(exhaustive) != signature(frontier):
        raise SystemExit("RT-008 K5 equivalence against RT-007 oracle failed")

    ladder = ladder_links(5)
    ladder_exhaustive = enumerate_connected_structures(
        ladder,
        max_edges=7,
        max_subsets_scanned=10_000,
        max_structures=10_000,
    )
    ladder_frontier = enumerate_connected_structures_frontier(
        ladder,
        max_edges=7,
        max_states=10_000,
        max_structures=10_000,
    )
    if signature(ladder_exhaustive) != signature(ladder_frontier):
        raise SystemExit("RT-008 ladder equivalence against RT-007 oracle failed")

    ratio = (
        ladder_frontier["states_expanded"]
        / ladder_exhaustive["subsets_scanned"]
    )
    if ratio >= 0.20:
        raise SystemExit(f"connected-only efficiency target not met: {ratio}")

    cap_probe = enumerate_connected_structures_frontier(
        k5,
        max_edges=6,
        max_states=20,
        max_structures=2_000,
    )
    if cap_probe["complete"] or cap_probe["structures"]:
        raise SystemExit("RT-008 cap probe did not fail closed")

    payload = {
        "status": "PASS_RT008_CONNECTED_ONLY_STRUCTURE_ENUMERATION_V3",
        "issue": "RT-008",
        "fixture_semantics": "CONTROLLED_ABSTRACT_FIXTURES_NOT_TERRITORIAL_DATA",
        "k5_exhaustive_subsets_scanned": exhaustive["subsets_scanned"],
        "k5_frontier_states_expanded": frontier["states_expanded"],
        "k5_structure_count": frontier["structure_count"],
        "k5_exact_signature_equivalence": True,
        "ladder_exhaustive_subsets_scanned": ladder_exhaustive["subsets_scanned"],
        "ladder_frontier_states_expanded": ladder_frontier["states_expanded"],
        "ladder_structure_count": ladder_frontier["structure_count"],
        "ladder_exact_signature_equivalence": True,
        "ladder_state_ratio_vs_exhaustive": ratio,
        "cap_fail_closed": True,
        "random_search": False,
        "topology_generation_filter": False,
        "weighted_composite_score": False,
        "territorial_candidate_claim": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
