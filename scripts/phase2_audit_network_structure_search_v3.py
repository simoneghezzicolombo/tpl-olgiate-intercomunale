#!/usr/bin/env python3
"""Algorithmic audit for RT-007 network-structure search V3.

The fixture is deliberately abstract and controlled. It is not territorial data
and must never be interpreted as a candidate transport network.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from src.phase2_network_structure_search_v3 import AbstractLink, enumerate_connected_structures


OUT = Path("outputs/phase2/network_structure_search_v3/network_structure_search_v3_validation.json")


def complete_five_vertex_graph() -> list[AbstractLink]:
    vertices = ["A", "B", "C", "D", "E"]
    links: list[AbstractLink] = []
    counter = 0
    for index, u in enumerate(vertices):
        for v in vertices[index + 1 :]:
            counter += 1
            links.append(AbstractLink(f"L{counter:02}", u, v))
    return links


def main() -> None:
    result = enumerate_connected_structures(
        complete_five_vertex_graph(),
        max_edges=6,
        max_subsets_scanned=2_000,
        max_structures=2_000,
    )
    if result["status"] != "PASS_COMPLETE_ABSTRACT_STRUCTURE_ENUMERATION":
        raise SystemExit(f"unexpected enumeration status: {result['status']}")

    structures = result["structures"]
    class_counts = Counter(item.topology_class for item in structures)
    required_classes = {
        "PATH",
        "CYCLE",
        "TREE_BRANCHING",
        "UNICYCLIC_BRANCHING",
        "BICYCLIC_ARTICULATED",
        "BICYCLIC_NONARTICULATED",
    }
    missing = sorted(required_classes - set(class_counts))
    if missing:
        raise SystemExit(f"topology-neutral emergence audit failed; missing {missing}")

    figure_eight_count = sum(
        "FIGURE_EIGHT_LIKE" in item.shape_flags for item in structures
    )
    if figure_eight_count < 1:
        raise SystemExit("figure-eight-like structure did not emerge from generic enumeration")

    cap_probe = enumerate_connected_structures(
        complete_five_vertex_graph(),
        max_edges=6,
        max_subsets_scanned=5,
        max_structures=2_000,
    )
    if cap_probe["complete"] or cap_probe["structures"]:
        raise SystemExit("enumeration-cap probe did not fail closed")

    payload = {
        "status": "PASS_RT007_ABSTRACT_NETWORK_STRUCTURE_SEARCH_V3",
        "issue": "RT-007",
        "fixture_semantics": "CONTROLLED_ABSTRACT_FIXTURE_NOT_TERRITORIAL_DATA",
        "contract": result["contract"],
        "topology_semantics": result["topology_semantics"],
        "subsets_scanned": result["subsets_scanned"],
        "structure_count": result["structure_count"],
        "topology_class_counts": dict(sorted(class_counts.items())),
        "figure_eight_like_count": figure_eight_count,
        "required_classes_present": sorted(required_classes),
        "cap_fail_closed": True,
        "weighted_composite_score": False,
        "random_search": False,
        "territorial_candidate_claim": False,
        "passenger_stop_pattern_claim": False,
        "network_winner_claim": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
