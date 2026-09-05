#!/usr/bin/env python3
"""Controlled RT-009 audit for directional-to-undirected reciprocity semantics."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.phase2_corridor_reciprocity_v3 import build_reciprocal_structural_links

OUT = Path(
    "outputs/phase2/corridor_reciprocity_v3/"
    "corridor_reciprocity_v3_validation.json"
)


def main() -> None:
    pairs = pd.DataFrame(
        [
            ("P_AB", "A", "B", True),
            ("P_BA", "B", "A", True),
            ("P_AC", "A", "C", True),
            ("P_CD", "C", "D", True),
            ("P_DC", "D", "C", False),
            ("P_EF", "E", "F", True),
            ("P_FE", "F", "E", True),
        ],
        columns=[
            "pair_id",
            "source_routing_terminal_id",
            "target_routing_terminal_id",
            "gate_d_route_found",
        ],
    )
    corridors = pd.DataFrame(
        [
            ("P_AB", "C_AB_1", True, 8.0, 5000.0),
            ("P_AB", "C_AB_2", True, 8.5, 5200.0),
            ("P_BA", "C_BA_1", True, 8.2, 5100.0),
            ("P_AC", "C_AC_1", True, 5.0, 3000.0),
            ("P_CD", "C_CD_1", True, 6.0, 3500.0),
            ("P_EF", "C_EF_1", True, 7.0, 4000.0),
            ("P_FE", "C_FE_LOOP", False, 6.5, 3900.0),
        ],
        columns=[
            "pair_id",
            "corridor_id",
            "admissible_for_corridor_pool",
            "running_minutes_model",
            "distance_m",
        ],
    )

    result = build_reciprocal_structural_links(pairs, corridors)
    audit = result["pair_audit"]
    links = result["structural_links"]
    statuses = dict(zip(
        [f"{a}|{b}" for a, b in zip(audit["terminal_a"], audit["terminal_b"])],
        audit["eligibility_status"],
    ))

    expected = {
        "A|B": "RECIPROCAL_BIDIRECTIONAL_CORRIDOR_AVAILABLE",
        "A|C": "UNTESTED_DIRECTION",
        "C|D": "NO_GATE_D_ROUTE_IN_DIRECTION",
        "E|F": "NO_ADMITTED_CORRIDOR_IN_DIRECTION",
    }
    if statuses != expected:
        raise SystemExit(f"unexpected reciprocity statuses: {statuses}")
    if len(links) != 1 or links.iloc[0]["terminal_a"] != "A" or links.iloc[0]["terminal_b"] != "B":
        raise SystemExit("eligible structural-link set is incorrect")

    reversed_result = build_reciprocal_structural_links(
        pairs.iloc[::-1].reset_index(drop=True),
        corridors.iloc[::-1].reset_index(drop=True),
    )
    cols = [
        "structural_link_id",
        "terminal_a",
        "terminal_b",
        "eligibility_status",
        "eligible_for_bidirectional_undirected_structure",
    ]
    if audit[cols].to_dict("records") != reversed_result["pair_audit"][cols].to_dict("records"):
        raise SystemExit("row-order determinism audit failed")

    payload = {
        "status": "PASS_RT009_DIRECTIONAL_RECIPROCITY_CONTRACT_V3",
        "issue": "RT-009",
        "fixture_semantics": "CONTROLLED_ABSTRACT_FIXTURE_NOT_TERRITORIAL_DATA",
        "unordered_pairs_audited": len(audit),
        "eligible_structural_links": len(links),
        "status_counts": audit["eligibility_status"].value_counts().sort_index().to_dict(),
        "not_requested_is_unknown_not_infeasible": True,
        "both_directions_admitted_required": True,
        "multiple_corridor_variants_collapse_to_one_structural_link": True,
        "row_order_deterministic": True,
        "directional_only_service_authorized": False,
        "weighted_composite_score": False,
        "territorial_candidate_claim": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
