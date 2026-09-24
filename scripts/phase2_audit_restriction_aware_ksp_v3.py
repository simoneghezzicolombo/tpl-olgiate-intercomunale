#!/usr/bin/env python3
"""Audit V3 restriction-aware K-shortest paths on the frozen Gate-D graph.

This is an algorithm audit only. It checks two distinct contracts:

- every sampled historical Gate-D shortest edge sequence is exactly reproduced
  as routing evidence in the edge-state representation, including legal paths
  that revisit a physical node;
- every path emitted for future corridor generation is physically loopless.

No network, stop pattern, topology, headway or winner is selected here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from src.phase2_reduced_path_matrix import load_frozen_graph_inputs
from src.phase2_restriction_aware_ksp import (
    build_restriction_aware_state_context,
    k_shortest_loopless_paths,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FROZEN = ROOT / "outputs/phase2/frozen_gate_d"
DEFAULT_OUT = ROOT / "outputs/phase2/network_design_method_audit_v3/restriction_aware_ksp_v3"
SEED_PATHS = "reduced_transfer_seed_paths.csv.gz"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def select_audit_pairs(seed_paths: pd.DataFrame, n_pairs: int = 8) -> pd.DataFrame:
    """Choose deterministic source-grounded audit pairs, never design waypoints."""
    frame = seed_paths.copy().sort_values(
        ["source_anchor_id", "target_anchor_id"], kind="mergesort"
    )
    selected_keys: list[tuple[str, str]] = []

    preferred = [
        ("gate_d:BEVERATE", "gate_d:SAN_ZENO"),
        ("gate_d:SAN_ZENO", "gate_d:BEVERATE"),
    ]
    available = set(zip(frame.source_anchor_id.astype(str), frame.target_anchor_id.astype(str)))
    for key in preferred:
        if key in available and key not in selected_keys:
            selected_keys.append(key)

    rail = frame[
        frame["source_anchor_id"].astype(str).eq("rail:S01514")
        | frame["target_anchor_id"].astype(str).eq("rail:S01514")
    ]
    for row in rail.itertuples(index=False):
        key = (str(row.source_anchor_id), str(row.target_anchor_id))
        if key not in selected_keys:
            selected_keys.append(key)
        if len(selected_keys) >= n_pairs:
            break

    remaining = frame.copy()
    remaining["edge_count_num"] = pd.to_numeric(remaining["edge_count"], errors="raise")
    remaining = remaining.sort_values(
        ["edge_count_num", "source_anchor_id", "target_anchor_id"],
        ascending=[False, True, True],
        kind="mergesort",
    )
    for row in remaining.itertuples(index=False):
        key = (str(row.source_anchor_id), str(row.target_anchor_id))
        if key not in selected_keys:
            selected_keys.append(key)
        if len(selected_keys) >= n_pairs:
            break

    lookup = {
        (str(row.source_anchor_id), str(row.target_anchor_id)): row
        for row in frame.itertuples(index=False)
    }
    rows = [lookup[key]._asdict() for key in selected_keys if key in lookup]
    out = pd.DataFrame(rows)
    if len(out) < min(4, n_pairs):
        raise ValueError(f"Too few frozen seed pairs for KSP audit: {len(out)}")
    return out.sort_values(
        ["source_anchor_id", "target_anchor_id"], kind="mergesort"
    ).reset_index(drop=True)


def repeated_nodes(nodes: list[str]) -> list[str]:
    counts = Counter(nodes)
    return sorted(node for node, count in counts.items() if count > 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frozen", type=Path, default=DEFAULT_FROZEN)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--pairs", type=int, default=8)
    ap.add_argument("--max-raw-state-paths", type=int, default=20000)
    args = ap.parse_args()

    if args.k < 2:
        raise ValueError("Audit requires k >= 2")
    args.out.mkdir(parents=True, exist_ok=True)

    nodes, edges, rules, anchors = load_frozen_graph_inputs(args.frozen)
    seed_path_file = args.frozen / SEED_PATHS
    if not seed_path_file.exists():
        raise FileNotFoundError(seed_path_file)
    seed_paths = pd.read_csv(seed_path_file, compression="gzip", dtype=str)
    required_seed = {
        "source_anchor_id",
        "target_anchor_id",
        "source_graph_node_id",
        "target_graph_node_id",
        "distance_m",
        "running_minutes_model",
        "edge_count",
        "path_edge_ids",
        "turn_restrictions",
    }
    missing = sorted(required_seed - set(seed_paths.columns))
    if missing:
        raise ValueError(f"Frozen seed-path file missing columns: {missing}")
    if set(seed_paths["turn_restrictions"].astype(str)) != {"ENFORCED_GATE_D_VIA_NODE"}:
        raise ValueError("Frozen seed-path turn-restriction contract changed")

    selected = select_audit_pairs(seed_paths, args.pairs)
    context = build_restriction_aware_state_context(edges, rules)

    output_rows: list[dict] = []
    pair_rows: list[dict] = []
    for pair_index, seed in enumerate(selected.itertuples(index=False), start=1):
        result = k_shortest_loopless_paths(
            context,
            str(seed.source_graph_node_id),
            str(seed.target_graph_node_id),
            k=args.k,
            max_raw_state_paths=args.max_raw_state_paths,
        )
        if not result["certified_shortest_present"]:
            raise AssertionError(
                f"KSP lost certified reachability for {seed.source_anchor_id}->{seed.target_anchor_id}"
            )
        certified = result["certified_path"]
        assert certified is not None

        frozen_edge_ids = str(seed.path_edge_ids).split(";") if str(seed.path_edge_ids) else []
        certified_edge_exact = certified["edge_ids"] == frozen_edge_ids
        runtime_delta = abs(
            float(certified["running_minutes_model"]) - float(seed.running_minutes_model)
        )
        distance_delta = abs(float(certified["distance_m"]) - float(seed.distance_m))
        if not certified_edge_exact or runtime_delta > 1e-9 or distance_delta > 1e-6:
            raise AssertionError(
                "Certified routing path does not reproduce frozen Gate-D seed path: "
                f"{seed.source_anchor_id}->{seed.target_anchor_id}, "
                f"edge_exact={certified_edge_exact}, runtime_delta={runtime_delta}, "
                f"distance_delta={distance_delta}"
            )
        if not result["certified_state_path_representable"]:
            raise AssertionError(
                f"Frozen Gate-D path not representable in state graph: {seed.source_anchor_id}->{seed.target_anchor_id}"
            )
        if abs(float(result["first_state_path_runtime_delta_min"])) > 1e-12:
            raise AssertionError(
                f"State graph shortest runtime changed Gate-D cost: {seed.source_anchor_id}->{seed.target_anchor_id}"
            )
        if not result["tie_band_complete"]:
            raise AssertionError("KSP deterministic tie band was not completed")

        paths = result["paths"]
        pair_id = f"AUDIT_PAIR_{pair_index:02d}"
        frozen_repeated = repeated_nodes(certified["physical_nodes"])
        pair_rows.append(
            {
                "pair_id": pair_id,
                "source_anchor_id": str(seed.source_anchor_id),
                "target_anchor_id": str(seed.target_anchor_id),
                "source_graph_node_id": str(seed.source_graph_node_id),
                "target_graph_node_id": str(seed.target_graph_node_id),
                "frozen_edge_count": int(seed.edge_count),
                "certified_exact_frozen_edge_sequence": certified_edge_exact,
                "certified_state_path_representable": bool(
                    result["certified_state_path_representable"]
                ),
                "certified_physical_loopless": bool(
                    result["certified_shortest_physical_loopless"]
                ),
                "certified_repeated_physical_node_count": len(frozen_repeated),
                "certified_repeated_physical_nodes": ";".join(frozen_repeated),
                "certified_runtime_min": f"{float(certified['running_minutes_model']):.9f}",
                "certified_distance_m": f"{float(certified['distance_m']):.6f}",
                "loopless_alternatives_returned": len(paths),
                "loopless_rank1_runtime_penalty_min": (
                    ""
                    if result["loopless_shortest_runtime_penalty_min"] is None
                    else f"{float(result['loopless_shortest_runtime_penalty_min']):.9f}"
                ),
                "loopless_rank1_distance_penalty_m": (
                    ""
                    if result["loopless_shortest_distance_penalty_m"] is None
                    else f"{float(result['loopless_shortest_distance_penalty_m']):.6f}"
                ),
                "raw_state_paths_examined": int(result["raw_state_paths_examined"]),
                "state_generator_exhausted": bool(result["state_generator_exhausted"]),
                "certified_runtime_delta_min": runtime_delta,
                "certified_distance_delta_m": distance_delta,
            }
        )

        seen_paths: set[tuple[str, ...]] = set()
        for path in paths:
            key = tuple(path["edge_ids"])
            if key in seen_paths:
                raise AssertionError("Duplicate KSP edge sequence within one OD pair")
            seen_paths.add(key)
            if not path["physical_loopless"]:
                raise AssertionError("Physically cyclic path survived corridor KSP filter")
            output_rows.append(
                {
                    "pair_id": pair_id,
                    "source_anchor_id": str(seed.source_anchor_id),
                    "target_anchor_id": str(seed.target_anchor_id),
                    "source_graph_node_id": str(seed.source_graph_node_id),
                    "target_graph_node_id": str(seed.target_graph_node_id),
                    "rank": int(path["rank"]),
                    "running_minutes_model": f"{float(path['running_minutes_model']):.9f}",
                    "distance_m": f"{float(path['distance_m']):.6f}",
                    "edge_count": len(path["edge_ids"]),
                    "physical_node_count": len(path["physical_nodes"]),
                    "physical_loopless": "true",
                    "is_exact_certified_gate_d_path": str(
                        tuple(path["edge_ids"]) == tuple(certified["edge_ids"])
                    ).lower(),
                    "provenance": str(path["provenance"]),
                    "edge_ids": ";".join(path["edge_ids"]),
                    "physical_nodes": ";".join(path["physical_nodes"]),
                    "decision_role": "ALGORITHM_AUDIT_ONLY_NOT_CANDIDATE_NETWORK",
                }
            )

    paths_out = args.out / "gate_d_ksp_audit_paths_v3.csv"
    pairs_out = args.out / "gate_d_ksp_audit_pairs_v3.csv"
    validation_out = args.out / "restriction_aware_ksp_v3_validation.json"
    pd.DataFrame(output_rows).sort_values(
        ["pair_id", "rank"], kind="mergesort"
    ).to_csv(paths_out, index=False)
    pd.DataFrame(pair_rows).sort_values("pair_id", kind="mergesort").to_csv(
        pairs_out, index=False
    )

    cyclic_pairs = [row for row in pair_rows if not row["certified_physical_loopless"]]
    loopless_certified_pairs = [row for row in pair_rows if row["certified_physical_loopless"]]
    path_frame = pd.DataFrame(output_rows)
    validation = {
        "status": "PASS_RESTRICTION_AWARE_KSP_AUDIT_V3",
        "contract": "EDGE_STATE_YEN_CERTIFIED_GATE_D_EQUIVALENCE_PLUS_LOOPLESS_CORRIDOR_FILTER_NOT_NETWORK_SELECTION",
        "inputs": {
            "frozen_dir": str(args.frozen.relative_to(ROOT)),
            "frozen_seed_paths": str(seed_path_file.relative_to(ROOT)),
            "frozen_seed_paths_sha256": sha256(seed_path_file),
            "graph_edges_sha256": sha256(args.frozen / "graph_edges.csv.gz"),
            "turn_rules_sha256": sha256(args.frozen / "turn_rules.csv.gz"),
        },
        "parameters": {
            "k": args.k,
            "audit_pair_count_requested": args.pairs,
            "audit_pair_count_used": len(pair_rows),
            "max_raw_state_paths_per_pair": args.max_raw_state_paths,
            "pair_sampling": "FROZEN_SEED_AUDIT_ONLY_PREFERRED_ASYMMETRY_AND_RAIL_THEN_LONGEST_EDGE_COUNT",
        },
        "state_graph": context.stats,
        "routing_equivalence": {
            "certified_pairs_checked": len(pair_rows),
            "certified_physical_loopless_pairs": len(loopless_certified_pairs),
            "certified_physical_cyclic_pairs": len(cyclic_pairs),
            "cyclic_pair_ids": [row["pair_id"] for row in cyclic_pairs],
            "interpretation": (
                "A physically cyclic certified path remains valid Gate-D routing evidence "
                "but is excluded from corridor candidates; this is not a route recommendation."
            ),
        },
        "checks": {
            "state_vertex_count_equals_directed_edge_count": context.stats["state_vertices"] == len(edges),
            "turn_restrictions_reject_at_least_one_transition": context.stats["turn_transitions_rejected"] > 0,
            "all_certified_paths_exact_frozen_edge_sequence": all(
                row["certified_exact_frozen_edge_sequence"] for row in pair_rows
            ),
            "all_certified_paths_state_representable": all(
                row["certified_state_path_representable"] for row in pair_rows
            ),
            "all_certified_runtime_deltas_le_1e_9": all(
                float(row["certified_runtime_delta_min"]) <= 1e-9 for row in pair_rows
            ),
            "all_certified_distance_deltas_le_1e_6": all(
                float(row["certified_distance_delta_m"]) <= 1e-6 for row in pair_rows
            ),
            "all_output_corridor_paths_physical_loopless": (
                not path_frame.empty and set(path_frame["physical_loopless"].astype(str)) == {"true"}
            ),
            "loopless_certified_paths_remain_exact_rank1": all(
                bool(
                    not path_frame[
                        (path_frame["pair_id"] == row["pair_id"])
                        & (path_frame["rank"] == 1)
                        & (path_frame["is_exact_certified_gate_d_path"] == "true")
                    ].empty
                )
                for row in loopless_certified_pairs
            ),
        },
        "guards": {
            "candidate_network_generated": False,
            "corridor_selected": False,
            "passenger_stop_pattern_selected": False,
            "new_stop_generated": False,
            "topology_selected": False,
            "headway_optimised": False,
            "winner_selected": False,
            "manual_settlement_waypoints_used_for_design": False,
        },
        "outputs": {
            "paths": str(paths_out.relative_to(ROOT)),
            "paths_sha256": sha256(paths_out),
            "pairs": str(pairs_out.relative_to(ROOT)),
            "pairs_sha256": sha256(pairs_out),
        },
    }
    if not all(validation["checks"].values()):
        validation["status"] = "FAIL_RESTRICTION_AWARE_KSP_AUDIT_V3"
    validation_out.write_text(
        json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if validation["status"].startswith("FAIL"):
        raise SystemExit(validation["status"])
    print(json.dumps(validation, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
