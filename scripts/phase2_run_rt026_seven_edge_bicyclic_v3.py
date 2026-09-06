#!/usr/bin/env python3
"""Run RT-026 exact seven-edge bicyclic feasibility diagnostic on frozen evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from src.phase2_network_structure_search_v3 import AbstractLink, structure_to_record
from src.phase2_seven_edge_bicyclic_feasibility_v3 import (
    enumerate_exact_seven_edge_bicyclic_policy_structures,
)

PASS_STATUS = "PASS_RT026_EXACT_SEVEN_EDGE_BICYCLIC_FEASIBILITY_DIAGNOSTIC_V3"
CORE_GROUPS = (
    "Brivio",
    "Calco",
    "La Valletta Brianza",
    "Olgiate Molgora",
    "Santa Maria Hoè",
)
EXPECTED_LINK_SHA = "009789fbaf2cf5434555075c1de6a6931bee3bbc0473580e26a79a82d827885d"
EXPECTED_RT022_STRUCTURE_SHA = "1d6ccd18a5707aa8e2e51b1eefcc9d27056678f0d5e260c9027d1414a1ddf8d7"


def canonical_frame_sha256(frame: pd.DataFrame, *, sort_by: list[str]) -> str:
    cols = sorted(str(c) for c in frame.columns)
    canonical = frame.loc[:, cols].copy().fillna("").sort_values(sort_by, kind="mergesort")
    return hashlib.sha256(
        canonical.reset_index(drop=True).to_csv(index=False, lineterminator="\n").encode("utf-8")
    ).hexdigest()


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"invalid boolean value: {value!r}")


def _parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--links", required=True, type=Path)
    p.add_argument("--stop-inventory", required=True, type=Path)
    p.add_argument("--rt022-audit", required=True, type=Path)
    p.add_argument("--out-dir", type=Path, default=Path("outputs/phase2/rt026_seven_edge_bicyclic_v3"))
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    links = pd.read_csv(args.links).fillna("")
    stops = pd.read_csv(args.stop_inventory).fillna("")
    rt022 = json.loads(args.rt022_audit.read_text(encoding="utf-8"))

    if rt022.get("complete") is not True:
        raise ValueError("RT-026 requires complete RT-022 evidence")
    if rt022.get("digests", {}).get("structure_universe_sha256") != EXPECTED_RT022_STRUCTURE_SHA:
        raise ValueError("RT-022 structure identity changed")

    required = {
        "structural_link_id",
        "terminal_a",
        "terminal_b",
        "eligible_for_bidirectional_undirected_structure",
    }
    missing = sorted(required - set(links.columns))
    if missing:
        raise ValueError(f"structural links missing columns: {missing}")
    links["eligible_for_bidirectional_undirected_structure"] = [
        _bool(value) for value in links["eligible_for_bidirectional_undirected_structure"]
    ]
    if len(links) != 110 or not links["eligible_for_bidirectional_undirected_structure"].all():
        raise ValueError("RT-026 requires exactly 110 eligible reciprocal structural links")
    if canonical_frame_sha256(links, sort_by=["structural_link_id"]) != EXPECTED_LINK_SHA:
        raise ValueError("frozen reciprocal structural-link digest mismatch")

    if len(stops) != 36 or stops["stop_place_id"].astype(str).duplicated().any():
        raise ValueError("frozen 36-stop inventory identity invalid")
    conventional = stops[stops["service_class"].astype(str).eq("CONVENTIONAL_TPL")].copy()
    if len(conventional) != 35:
        raise ValueError("RT-026 requires exactly 35 conventional terminals")
    if set(conventional["municipality"].astype(str)) != set(CORE_GROUPS):
        raise ValueError("terminal policy mapping changed")

    terminal_groups = {
        str(row.stop_place_id): (str(row.municipality),)
        for row in conventional.itertuples(index=False)
    }
    graph_terminals = set(links["terminal_a"].astype(str)) | set(links["terminal_b"].astype(str))
    if not graph_terminals.issubset(terminal_groups):
        raise ValueError("structural graph references terminal outside frozen conventional inventory")

    abstract_links = [
        AbstractLink(
            link_id=str(row.structural_link_id),
            u=str(row.terminal_a),
            v=str(row.terminal_b),
        )
        for row in links.sort_values("structural_link_id", kind="mergesort").itertuples(index=False)
    ]
    result = enumerate_exact_seven_edge_bicyclic_policy_structures(
        abstract_links,
        required_policy_groups=CORE_GROUPS,
        terminal_policy_groups=terminal_groups,
    )
    if not result["complete"]:
        raise AssertionError("RT-026 exact diagnostic returned incomplete result")

    rows = []
    for structure, duplicate_group in zip(
        result["structures"], result["duplicated_policy_groups"], strict=True
    ):
        record = structure_to_record(structure)
        record["duplicated_policy_group"] = duplicate_group
        record["structure_id"] = (
            "RT026_BICYCLE_" + hashlib.sha256(str(record["link_ids"]).encode("utf-8")).hexdigest()[:16].upper()
        )
        rows.append(record)
    universe = pd.DataFrame(rows).sort_values("structure_id", kind="mergesort").reset_index(drop=True)
    topology_counts = {str(k): int(v) for k, v in sorted(Counter(universe["topology_class"]).items())}
    duplicate_group_counts = {
        str(k): int(v) for k, v in sorted(Counter(universe["duplicated_policy_group"]).items())
    }
    figure8 = universe[universe["shape_flags"].astype(str).str.contains("FIGURE_EIGHT_LIKE")].copy()
    universe_sha = canonical_frame_sha256(universe, sort_by=["structure_id"])
    figure8_sha = canonical_frame_sha256(figure8, sort_by=["structure_id"]) if not figure8.empty else hashlib.sha256(b"").hexdigest()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    universe.to_csv(out / "exact_seven_edge_bicyclic_structure_universe.csv", index=False, lineterminator="\n")
    figure8.to_csv(out / "figure_eight_like_subset.csv", index=False, lineterminator="\n")

    audit = {
        "status": PASS_STATUS,
        "complete": True,
        "source_rt022_structure_universe_sha256": EXPECTED_RT022_STRUCTURE_SHA,
        "source_reciprocal_structural_links_sha256": EXPECTED_LINK_SHA,
        "counts": {
            "six_terminal_policy_vertex_sets_scanned": int(result["vertex_sets_scanned"]),
            "six_terminal_sets_with_at_least_seven_induced_links": int(
                result["vertex_sets_with_at_least_seven_induced_links"]
            ),
            "seven_edge_subsets_scanned": int(result["seven_edge_subsets_scanned"]),
            "bicyclic_structures": int(len(universe)),
            "figure_eight_like_structures": int(len(figure8)),
        },
        "topology_counts": topology_counts,
        "duplicated_policy_group_counts": duplicate_group_counts,
        "structure_universe_sha256": universe_sha,
        "figure_eight_like_subset_sha256": figure8_sha,
        "proof_semantics": result["proof_semantics"],
        "generation_semantics": result["generation_semantics"],
        "interpretation_boundary": result["interpretation_boundary"],
        "guards": {
            "full_edge7_universe_claimed": False,
            "bicyclic_preferred": False,
            "figure_eight_preferred": False,
            "primary_runner_up_selected": False,
            "service_terminal_selected": False,
            "topology_used_as_network_winner_prior": False,
        },
    }
    (out / "rt026_seven_edge_bicyclic_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
