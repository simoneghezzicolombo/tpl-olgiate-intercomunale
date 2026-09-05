#!/usr/bin/env python3
"""Audit the V3 restriction-aware K-shortest corridor primitive on frozen Gate D.

This is an algorithm audit, not candidate-network generation.  It builds one
edge-state graph from the exact frozen Gate-D edge/rule artifacts, runs a small
deterministic sample of already-certified seed OD pairs, and requires rank 1 to
match the exact historical Gate-D edge sequence and cost.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from src.phase2_reduced_path_matrix import load_frozen_graph_inputs
from src.phase2_restriction_aware_ksp import build_restriction_aware_state_context, k_shortest_loopless_paths

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
    """Choose deterministic source-grounded audit pairs, not design waypoints."""
    frame = seed_paths.copy()
    frame = frame.sort_values(["source_anchor_id", "target_anchor_id"], kind="mergesort")
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

    # Fill from longest certified seed paths first to exercise more transitions,
    # with stable source/target tie-breaking.  This is an audit sampling rule,
    # not a corridor preference or network-ranking rule.
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
        (str(r.source_anchor_id), str(r.target_anchor_id)): r
        for r in frame.itertuples(index=False)
    }
    rows = [lookup[key]._asdict() for key in selected_keys if key in lookup]
    out = pd.DataFrame(rows)
    if len(out) < min(4, n_pairs):
        raise ValueError(f"Too few frozen seed pairs for KSP audit: {len(out)}")
    return out.sort_values(["source_anchor_id", "target_anchor_id"], kind="mergesort").reset_index(drop=True)


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
        paths = result["paths"]
        if not paths:
            raise AssertionError(f"KSP returned no path for certified pair {seed.source_anchor_id}->{seed.target_anchor_id}")
        rank1 = paths[0]
        frozen_edge_ids = str(seed.path_edge_ids).split(";") if str(seed.path_edge_ids) else []
        edge_exact = rank1["edge_ids"] == frozen_edge_ids
        runtime_delta = abs(float(rank1["running_minutes_model"]) - float(seed.running_minutes_model))
        distance_delta = abs(float(rank1["distance_m"]) - float(seed.distance_m))
        if not edge_exact or runtime_delta > 1e-9 or distance_delta > 1e-6:
            raise AssertionError(
                "Rank-1 KSP path does not exactly reproduce frozen Gate-D seed path: "
                f"{seed.source_anchor_id}->{seed.target_anchor_id}, edge_exact={edge_exact}, "
                f"runtime_delta={runtime_delta}, distance_delta={distance_delta}"
            )
        if not result["certified_first_path_exact_edge_ids"]:
            raise AssertionError("KSP did not preserve certified Gate-D Dijkstra at rank 1")
        if not result["tie_band_complete"]:
            raise AssertionError("KSP deterministic tie band was not completed")

        pair_id = f"AUDIT_PAIR_{pair_index:02d}"
        pair_rows.append(
            {
                "pair_id": pair_id,
                "source_anchor_id": str(seed.source_anchor_id),
                "target_anchor_id": str(seed.target_anchor_id),
                "source_graph_node_id": str(seed.source_graph_node_id),
                "target_graph_node_id": str(seed.target_graph_node_id),
                "frozen_edge_count": int(seed.edge_count),
                "alternatives_returned": len(paths),
                "raw_state_paths_examined": int(result["raw_state_paths_examined"]),
                "state_generator_exhausted": bool(result["state_generator_exhausted"]),
                "rank1_exact_frozen_edge_sequence": edge_exact,
                "rank1_runtime_delta_min": runtime_delta,
                "rank1_distance_delta_m": distance_delta,
            }
        )
        seen_paths: set[tuple[str, ...]] = set()
        for path in paths:
            key = tuple(path["edge_ids"])
            if key in seen_paths:
                raise AssertionError("Duplicate KSP edge sequence within one OD pair")
            seen_paths.add(key)
            if not path["physical_loopless"]:
                raise AssertionError("Physically cyclic path survived KSP filter")
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
                    "provenance": str(path["provenance"]),
                    "edge_ids": ";".join(path["edge_ids"]),
                    "physical_nodes": ";".join(path["physical_nodes"]),
                    "decision_role": "ALGORITHM_AUDIT_ONLY_NOT_CANDIDATE_NETWORK",
                }
            )

    paths_out = args.out / "gate_d_ksp_audit_paths_v3.csv"
    pairs_out = args.out / "gate_d_ksp_audit_pairs_v3.csv"
    validation_out = args.out / "restriction_aware_ksp_v3_validation.json"
    pd.DataFrame(output_rows).sort_values(["pair_id", "rank"], kind="mergesort").to_csv(paths_out, index=False)
    pd.DataFrame(pair_rows).sort_values("pair_id", kind="mergesort").to_csv(pairs_out, index=False)

    validation = {
        "status": "PASS_RESTRICTION_AWARE_KSP_AUDIT_V3",
        "contract": "EDGE_STATE_YEN_WITH_CERTIFIED_GATE_D_DIJKSTRA_RANK1_NOT_NETWORK_SELECTION",
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
        "checks": {
            "state_vertex_count_equals_directed_edge_count": context.stats["state_vertices"] == len(edges),
            "turn_restrictions_reject_at_least_one_transition": context.stats["turn_transitions_rejected"] > 0,
            "all_rank1_paths_exact_frozen_edge_sequence": all(r["rank1_exact_frozen_edge_sequence"] for r in pair_rows),
            "all_rank1_runtime_deltas_le_1e_9": all(float(r["rank1_runtime_delta_min"]) <= 1e-9 for r in pair_rows),
            "all_rank1_distance_deltas_le_1e_6": all(float(r["rank1_distance_delta_m"]) <= 1e-6 for r in pair_rows),
            "all_output_paths_physical_loopless": all(r["physical_loopless"] == "true" for r in output_rows),
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
    validation_out.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if validation["status"].startswith("FAIL"):
        raise SystemExit(validation["status"])
    print(json.dumps(validation, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
