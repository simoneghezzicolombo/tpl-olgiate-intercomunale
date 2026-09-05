#!/usr/bin/env python3
"""Audit scalable single-way corridor replacements on frozen Gate-D evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from src.phase2_corridor_replacement_v3 import generate_way_replacement_corridors

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FROZEN = ROOT / "outputs/phase2/frozen_gate_d"
DEFAULT_MATRIX = ROOT / "outputs/phase2/reduced_path_matrix_v2/reduced_path_matrix.csv"
DEFAULT_OUT = ROOT / "outputs/phase2/network_design_method_audit_v3/corridor_replacement_v3"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def select_audit_pairs(matrix: pd.DataFrame, count: int) -> pd.DataFrame:
    required = {
        "origin",
        "destination",
        "runtime_min",
        "distance_km",
        "origin_graph_node_id",
        "destination_graph_node_id",
    }
    missing = sorted(required - set(matrix.columns))
    if missing:
        raise ValueError(f"Reduced path matrix missing columns: {missing}")
    frame = matrix.copy()
    frame = frame[
        frame["origin"].astype(str).str.startswith("existing:")
        & frame["destination"].astype(str).str.startswith("existing:")
        & frame["origin_graph_node_id"].astype(str).ne(frame["destination_graph_node_id"].astype(str))
    ].copy()
    frame["runtime_num"] = pd.to_numeric(frame["runtime_min"], errors="coerce")
    frame["distance_num"] = pd.to_numeric(frame["distance_km"], errors="coerce")
    frame = frame.dropna(subset=["runtime_num", "distance_num"])
    frame = frame.sort_values(
        ["runtime_num", "distance_num", "origin", "destination"],
        ascending=[False, False, True, True],
        kind="mergesort",
    )
    # Audit stress sample only: longest frozen existing-stop OD records. This is
    # not a design preference and never enters candidate-network scoring.
    return frame.head(count).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=3)
    parser.add_argument("--frozen-dir", type=Path, default=DEFAULT_FROZEN)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    if args.pairs < 1:
        raise ValueError("--pairs must be >= 1")

    edges_path = args.frozen_dir / "graph_edges.csv.gz"
    rules_path = args.frozen_dir / "turn_rules.csv.gz"
    edges = pd.read_csv(edges_path, dtype=str)
    rules = pd.read_csv(rules_path, dtype=str)
    matrix = pd.read_csv(args.matrix, dtype=str)
    selected = select_audit_pairs(matrix, args.pairs)
    if len(selected) != args.pairs:
        raise ValueError(f"Only {len(selected)} eligible audit pairs available")

    pair_rows: list[dict] = []
    path_rows: list[dict] = []
    all_replacements_loopless = True
    all_exclusions_respected = True
    all_runtime_penalties_nonnegative = True
    all_baselines_match_matrix = True
    any_replacement = False

    for idx, row in enumerate(selected.itertuples(index=False), start=1):
        pair_id = f"AUDIT_OD_{idx:02d}"
        source = str(row.origin_graph_node_id)
        target = str(row.destination_graph_node_id)
        result = generate_way_replacement_corridors(edges, rules, source, target)
        if not result["certified_baseline_present"]:
            raise AssertionError(f"Frozen matrix pair {row.origin}->{row.destination} became unreachable")
        baseline = result["certified_baseline"]
        matrix_runtime = float(row.runtime_num)
        matrix_distance_m = float(row.distance_num) * 1000.0
        runtime_delta = float(baseline["running_minutes_model"]) - matrix_runtime
        distance_delta = float(baseline["distance_m"]) - matrix_distance_m
        pair_matches = abs(runtime_delta) <= 1e-9 and abs(distance_delta) <= 1e-3
        all_baselines_match_matrix = all_baselines_match_matrix and pair_matches

        replacements = result["replacement_corridors"]
        any_replacement = any_replacement or bool(replacements)
        pair_rows.append(
            {
                "pair_id": pair_id,
                "origin": row.origin,
                "destination": row.destination,
                "origin_graph_node_id": source,
                "destination_graph_node_id": target,
                "matrix_runtime_min": f"{matrix_runtime:.9f}",
                "certified_runtime_min": f"{float(baseline['running_minutes_model']):.9f}",
                "runtime_delta_min": f"{runtime_delta:.12f}",
                "matrix_distance_m": f"{matrix_distance_m:.6f}",
                "certified_distance_m": f"{float(baseline['distance_m']):.6f}",
                "distance_delta_m": f"{distance_delta:.6f}",
                "baseline_physical_loopless": str(bool(baseline["physical_loopless"])).lower(),
                "baseline_distinct_way_count": result["baseline_distinct_way_count"],
                "replacement_queries_run": result["replacement_queries_run"],
                "replacement_queries_unreachable": result["replacement_queries_unreachable"],
                "replacement_queries_physically_cyclic": result["replacement_queries_physically_cyclic"],
                "unique_loopless_replacement_corridors": len(replacements),
            }
        )
        path_rows.append(
            {
                "pair_id": pair_id,
                "record_type": "CERTIFIED_BASELINE",
                "rank": 0,
                "excluded_baseline_osm_way_ids": "",
                "runtime_min": f"{float(baseline['running_minutes_model']):.9f}",
                "distance_m": f"{float(baseline['distance_m']):.6f}",
                "runtime_penalty_min": "0.000000000",
                "physical_loopless": str(bool(baseline["physical_loopless"])).lower(),
                "path_edge_ids": ";".join(baseline["edge_ids"]),
                "provenance": baseline["provenance"],
            }
        )
        baseline_ways = set(baseline["osm_way_ids"])
        for candidate in replacements:
            excluded = set(candidate["excluded_baseline_osm_way_ids"])
            respected = excluded.isdisjoint(set(candidate["osm_way_ids"]))
            all_exclusions_respected = all_exclusions_respected and respected
            all_replacements_loopless = all_replacements_loopless and bool(candidate["physical_loopless"])
            all_runtime_penalties_nonnegative = (
                all_runtime_penalties_nonnegative
                and float(candidate["runtime_penalty_min"]) >= -1e-12
            )
            if not excluded.issubset(baseline_ways):
                raise AssertionError("Replacement provenance references a way absent from baseline")
            path_rows.append(
                {
                    "pair_id": pair_id,
                    "record_type": "SINGLE_BASELINE_WAY_REPLACEMENT",
                    "rank": candidate["replacement_rank"],
                    "excluded_baseline_osm_way_ids": ";".join(candidate["excluded_baseline_osm_way_ids"]),
                    "runtime_min": f"{float(candidate['running_minutes_model']):.9f}",
                    "distance_m": f"{float(candidate['distance_m']):.6f}",
                    "runtime_penalty_min": f"{float(candidate['runtime_penalty_min']):.9f}",
                    "physical_loopless": "true",
                    "path_edge_ids": ";".join(candidate["edge_ids"]),
                    "provenance": candidate["provenance"],
                }
            )

    args.out.mkdir(parents=True, exist_ok=True)
    pairs_path = args.out / "corridor_replacement_audit_pairs_v3.csv"
    paths_path = args.out / "corridor_replacement_audit_paths_v3.csv"
    pd.DataFrame(pair_rows).to_csv(pairs_path, index=False, lineterminator="\n")
    pd.DataFrame(path_rows).to_csv(paths_path, index=False, lineterminator="\n")

    checks = {
        "all_certified_baselines_exact_reduced_matrix": all_baselines_match_matrix,
        "at_least_one_loopless_replacement_corridor_observed": any_replacement,
        "all_emitted_replacements_physical_loopless": all_replacements_loopless,
        "all_emitted_replacements_respect_excluded_baseline_ways": all_exclusions_respected,
        "all_emitted_replacement_runtime_penalties_nonnegative": all_runtime_penalties_nonnegative,
        "all_audit_pairs_executed_complete_single_baseline_way_set": all(
            row["baseline_distinct_way_count"] == row["replacement_queries_run"] for row in pair_rows
        ),
    }
    status = "PASS_CORRIDOR_REPLACEMENT_AUDIT_V3" if all(checks.values()) else "FAIL_CORRIDOR_REPLACEMENT_AUDIT_V3"
    validation = {
        "status": status,
        "contract": "COMPLETE_SINGLE_BASELINE_OSM_WAY_REPLACEMENT_SET_NOT_K_SHORTEST_NOT_NETWORK_SELECTION",
        "parameters": {
            "audit_pair_count": args.pairs,
            "audit_pair_selection": "LONGEST_FROZEN_EXISTING_STOP_OD_RECORDS_FOR_STRESS_AUDIT_ONLY_NOT_DESIGN_PREFERENCE",
        },
        "inputs": {
            "graph_edges_sha256": sha256(edges_path),
            "turn_rules_sha256": sha256(rules_path),
            "reduced_path_matrix_sha256": sha256(args.matrix),
        },
        "checks": checks,
        "counts": {
            "replacement_queries_run": int(sum(row["replacement_queries_run"] for row in pair_rows)),
            "unique_loopless_replacements": int(sum(row["unique_loopless_replacement_corridors"] for row in pair_rows)),
            "unreachable_single_way_replacements": int(sum(row["replacement_queries_unreachable"] for row in pair_rows)),
            "physically_cyclic_single_way_replacements_rejected": int(sum(row["replacement_queries_physically_cyclic"] for row in pair_rows)),
        },
        "guards": {
            "k_shortest_exhaustiveness_claimed": False,
            "candidate_network_generated": False,
            "passenger_stop_pattern_selected": False,
            "named_service_area_forced": False,
            "topology_selected": False,
            "winner_selected": False,
        },
        "interpretation": (
            "This primitive is a deterministic corridor-diversification tool. It exhausts one-way removals "
            "from the certified baseline only; it does not claim to enumerate general K-shortest paths and "
            "does not select a network."
        ),
        "outputs": {
            "pairs_sha256": sha256(pairs_path),
            "paths_sha256": sha256(paths_path),
        },
    }
    validation_path = args.out / "corridor_replacement_v3_validation.json"
    validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2, sort_keys=True))
    if status.startswith("FAIL"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
