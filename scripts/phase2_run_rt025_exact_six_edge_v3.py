#!/usr/bin/env python3
"""Build the exact six-edge RT-025 structural layer from certified RT-022 evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from src.phase2_exact_edge_policy_structures_v3 import enumerate_exact_edge_policy_structures
from src.phase2_network_structure_search_v3 import AbstractLink, structure_to_record

PASS_STATUS = "PASS_RT025_EXACT_SIX_EDGE_TOPOLOGY_NEUTRAL_STRUCTURAL_LAYER_V3"
CORE_GROUPS = (
    "Brivio",
    "Calco",
    "La Valletta Brianza",
    "Olgiate Molgora",
    "Santa Maria Hoè",
)
EXPECTED_RT022_STATUS = "PASS_EXACT_MINIMUM_TOPOLOGY_NEUTRAL_TERRITORIAL_BACKBONE_UNIVERSE"
EXPECTED_RT022_LINKS = 110
EXPECTED_CONVENTIONAL = 35
EXPECTED_EDGE_COUNT = 6
EXPECTED_RT022_STRUCTURE_SHA = "1d6ccd18a5707aa8e2e51b1eefcc9d27056678f0d5e260c9027d1414a1ddf8d7"
EXPECTED_LINK_SHA = "009789fbaf2cf5434555075c1de6a6931bee3bbc0473580e26a79a82d827885d"


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"invalid boolean value: {value!r}")


def canonical_frame_sha256(
    frame: pd.DataFrame, *, sort_by: list[str], columns: list[str] | None = None
) -> str:
    selected = sorted(str(c) for c in frame.columns) if columns is None else [str(c) for c in columns]
    missing = sorted((set(selected) | set(sort_by)) - set(frame.columns))
    if missing:
        raise ValueError(f"canonical digest frame missing columns: {missing}")
    canonical = frame.loc[:, selected].copy().fillna("")
    if sort_by:
        canonical = canonical.sort_values(sort_by, kind="mergesort")
    payload = canonical.reset_index(drop=True).to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _structure_record(structure) -> dict[str, object]:
    record = structure_to_record(structure)
    payload = str(record["link_ids"]).encode("utf-8")
    record["structure_id"] = "RT025_STRUCT_" + hashlib.sha256(payload).hexdigest()[:16].upper()
    return record


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--links", required=True, type=Path)
    parser.add_argument("--stop-inventory", required=True, type=Path)
    parser.add_argument("--rt022-audit", required=True, type=Path)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("outputs/phase2/rt025_exact_six_edge_v3"),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    links = pd.read_csv(args.links).fillna("")
    stops = pd.read_csv(args.stop_inventory).fillna("")
    rt022 = json.loads(args.rt022_audit.read_text(encoding="utf-8"))

    if rt022.get("status") != EXPECTED_RT022_STATUS or rt022.get("complete") is not True:
        raise ValueError("RT-025 requires certified complete RT-022 evidence")
    if rt022.get("digests", {}).get("structure_universe_sha256") != EXPECTED_RT022_STRUCTURE_SHA:
        raise ValueError("RT-022 minimum structure identity changed")
    if int(rt022.get("counts", {}).get("reciprocal_elementary_structural_links", -1)) != EXPECTED_RT022_LINKS:
        raise ValueError("RT-022 reciprocal structural-link count changed")

    required_link_columns = {
        "structural_link_id",
        "terminal_a",
        "terminal_b",
        "eligible_for_bidirectional_undirected_structure",
    }
    missing = sorted(required_link_columns - set(links.columns))
    if missing:
        raise ValueError(f"RT-022 structural links missing columns: {missing}")
    links["eligible_for_bidirectional_undirected_structure"] = [
        _bool(value) for value in links["eligible_for_bidirectional_undirected_structure"]
    ]
    if len(links) != EXPECTED_RT022_LINKS or not links["eligible_for_bidirectional_undirected_structure"].all():
        raise ValueError("RT-025 expects exactly 110 eligible reciprocal RT-022 links")
    if links["structural_link_id"].astype(str).duplicated().any():
        raise ValueError("duplicate structural_link_id in RT-022 handoff")

    calculated_link_digest = canonical_frame_sha256(links, sort_by=["structural_link_id"])
    if calculated_link_digest != EXPECTED_LINK_SHA:
        raise ValueError("RT-022 reciprocal structural-link digest mismatch")

    required_stop_columns = {"stop_place_id", "municipality", "service_class"}
    missing = sorted(required_stop_columns - set(stops.columns))
    if missing:
        raise ValueError(f"canonical stop inventory missing columns: {missing}")
    if len(stops) != 36 or stops["stop_place_id"].astype(str).duplicated().any():
        raise ValueError("RT-025 requires the frozen unique 36-stop inventory")
    conventional = stops[stops["service_class"].astype(str).eq("CONVENTIONAL_TPL")].copy()
    if len(conventional) != EXPECTED_CONVENTIONAL:
        raise ValueError("RT-025 requires exactly 35 conventional terminals")
    if set(conventional["municipality"].astype(str)) != set(CORE_GROUPS):
        raise ValueError("conventional terminal mapping does not cover exactly the five core groups")

    terminal_groups = {
        str(row.stop_place_id): (str(row.municipality),)
        for row in conventional.itertuples(index=False)
    }
    graph_terminals = set(links["terminal_a"].astype(str)) | set(links["terminal_b"].astype(str))
    if not graph_terminals.issubset(terminal_groups):
        raise ValueError("structural link graph references terminal outside frozen conventional inventory")

    abstract_links = [
        AbstractLink(
            link_id=str(row.structural_link_id),
            u=str(row.terminal_a),
            v=str(row.terminal_b),
        )
        for row in links.sort_values("structural_link_id", kind="mergesort").itertuples(index=False)
    ]
    result = enumerate_exact_edge_policy_structures(
        abstract_links,
        exact_edge_count=EXPECTED_EDGE_COUNT,
        required_policy_groups=CORE_GROUPS,
        terminal_policy_groups=terminal_groups,
    )
    if not result.get("complete"):
        raise AssertionError("exact six-edge enumerator returned incomplete result")

    structures = pd.DataFrame([_structure_record(item) for item in result["structures"]])
    structures = structures.sort_values("structure_id", kind="mergesort").reset_index(drop=True)
    topology_counts = {str(k): int(v) for k, v in sorted(Counter(structures["topology_class"]).items())}
    vertex_counts = {str(k): int(v) for k, v in sorted(Counter(structures["vertex_count"]).items())}
    cycle_counts = {str(k): int(v) for k, v in sorted(Counter(structures["cycle_rank"]).items())}
    figure_eight_like_count = int(structures["shape_flags"].astype(str).str.contains("FIGURE_EIGHT_LIKE").sum())
    bicyclic_count = int(structures["topology_class"].astype(str).str.startswith("BICYCLIC").sum())
    structure_digest = canonical_frame_sha256(structures, sort_by=["structure_id"])

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    structures.to_csv(out / "exact_six_edge_topology_neutral_structure_universe.csv", index=False, lineterminator="\n")

    audit = {
        "status": PASS_STATUS,
        "complete": True,
        "graph_epoch_id": str(rt022.get("graph_epoch_id", "")),
        "source_rt022_status": rt022["status"],
        "source_rt022_structure_universe_sha256": EXPECTED_RT022_STRUCTURE_SHA,
        "source_reciprocal_structural_links_sha256": calculated_link_digest,
        "counts": {
            "reciprocal_structural_links": int(len(links)),
            "conventional_terminals": int(len(conventional)),
            "exact_six_edge_structures": int(len(structures)),
            "bicyclic_structures": bicyclic_count,
            "figure_eight_like_structures": figure_eight_like_count,
        },
        "topology_counts": topology_counts,
        "vertex_count_distribution": vertex_counts,
        "cycle_rank_distribution": cycle_counts,
        "connected_state_counts_by_edge_count": result["connected_state_counts_by_edge_count"],
        "connected_states_at_target_before_policy_filter": result["connected_states_at_target"],
        "exact_edge_count": EXPECTED_EDGE_COUNT,
        "structure_universe_sha256": structure_digest,
        "generation_semantics": result["generation_semantics"],
        "completeness_semantics": result["completeness_semantics"],
        "technical_parameters": result["technical_parameters"],
        "guards": {
            "enumeration_cap_used": False,
            "topology_filter_used": False,
            "service_terminal_selected": False,
            "primary_runner_up_selected": False,
            "municipality_used_as_routing_filter": False,
            "larger_edge_counts_enumerated": False,
            "larger_structures_declared_inferior": False,
        },
    }
    (out / "rt025_exact_six_edge_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
