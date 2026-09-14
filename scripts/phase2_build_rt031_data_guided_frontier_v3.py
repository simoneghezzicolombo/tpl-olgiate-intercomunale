#!/usr/bin/env python3
"""Build a no-weight hub-serving portfolio frontier without current-stop retention."""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import pandas as pd

from phase2_rt029_v4_substrate import validate_walk_matrix
from scripts.phase2_compare_rt031_movement_portfolios_v3 import (
    pareto_indices,
    threshold_vectors,
    zipped_csv,
)
from src.phase2_rt031_data_guided_portfolios_v3 import (
    enumerate_hub_portfolios,
    service_surface,
)


POOL_SHA256 = "b86b27f791b0b36f0e30997a96388c5763f46822411ea990bfeed3351cd8a65c"
WALK_SHA256 = "a47bbce413d056db185180173ab2f05dce0463cb626a2c81f4aff64de91b50c1"
HUB = "FROZEN::L00407"
HEADWAYS = (20, 30, 40, 60)
SPANS = (600, 720, 960)
ANNUAL_DAYS = 260


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(payload) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def main(args):
    if sha256(args.pool) != POOL_SHA256 or sha256(args.walk_matrix) != WALK_SHA256:
        raise ValueError("pinned expanded-pool/walk lineage drift")
    pool = json.loads(args.pool.read_text(encoding="utf-8"))
    if pool.get("contract") != "RT031_BUDGETED_PHYSICAL_CLOSED_WALK_SEARCH_V3":
        raise ValueError("unexpected physical pool")
    if pool.get("status") != "RESOURCE_LIMIT_INCOMPLETE":
        raise ValueError("upstream search completeness boundary changed")
    if pool.get("required_root_stop_id") != HUB:
        raise ValueError("Olgiate-rooted physical search required")
    current = json.loads(args.current_audit.read_text(encoding="utf-8"))
    if current.get("contract") != "RT031_CURRENT_EXACT_TARGET_COVER_RESOURCE_SYMMETRY_V3":
        raise ValueError("current benchmark contract drift")
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    cap = Decimal(str(policy["human_policy_decisions"]["annual_bus_km_cap"]))

    enumeration = enumerate_hub_portfolios(
        pool["candidates"], hub_stop_id=HUB, max_movements=args.max_movements)
    portfolios = enumeration.pop("portfolios")
    raw_walk = pd.read_csv(args.walk_matrix, dtype={"population_weight_2025": str})
    weight_map = (raw_walk[["population_unit_id", "population_weight_2025"]]
                  .drop_duplicates().set_index("population_unit_id")["population_weight_2025"].to_dict())
    substrate = validate_walk_matrix(raw_walk)
    exact_weights = [weight_map[value] for value in substrate.population_meta["population_unit_id"]]
    vectors = threshold_vectors(
        [row["available_stop_ids"] for row in portfolios], substrate, exact_weights)
    costs = [Decimal(row["total_distance_m"]) for row in portfolios]
    frontier_indices = pareto_indices(vectors, costs)
    fields = (
        "potential_core_share_5min",
        "potential_core_share_8min",
        "potential_core_share_10min",
        "potential_worst_municipality_share_5min",
        "potential_worst_municipality_share_8min",
        "potential_worst_municipality_share_10min",
    )
    for index, row in enumerate(portfolios):
        row["portfolio_id"] = "DG_" + hashlib.sha256(
            (";".join(row["source_walk_ids"]) + "|" + row["total_distance_m"]).encode()
        ).hexdigest()[:20]
        row["exact_access_ratios"] = [str(value) for value in vectors[index]]
        row.update({field: float(value) for field, value in zip(fields, vectors[index])})

    current_result = current["all_movements_serve_olgiate_fs_portfolio"]["results"][1]
    current_vector = current_result["same_substrate_access_comparison"]["current_exact_ratios"]
    frontier = []
    for index in frontier_indices:
        row = dict(portfolios[index])
        row["service_surface"] = [
            {
                **service,
                "within_approved_reference_cap": Decimal(service["annual_bus_km"]) <= cap,
            }
            for service in service_surface(
                row["total_distance_m"],
                row["movement_count"],
                headways=HEADWAYS,
                spans=SPANS,
                annual_days=ANNUAL_DAYS,
            )
        ]
        frontier.append(row)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_fields = [
        "portfolio_id", "movement_count", "total_distance_m", *fields,
        "exact_access_ratios", "available_stop_ids", "source_walk_ids",
    ]
    zipped_csv(
        args.output_dir / "rt031_data_guided_portfolios_v3.csv.gz",
        csv_fields,
        (
            {
                **row,
                "exact_access_ratios": json.dumps(row["exact_access_ratios"], separators=(",", ":")),
                "available_stop_ids": json.dumps(row["available_stop_ids"], separators=(",", ":")),
                "source_walk_ids": json.dumps(row["source_walk_ids"], separators=(",", ":")),
            }
            for row in portfolios
        ),
    )
    frontier_path = args.output_dir / "rt031_data_guided_frontier_v3.json"
    frontier_path.write_bytes(canonical(frontier))
    audit = {
        "contract": "RT031_DATA_GUIDED_HUB_PORTFOLIO_FRONTIER_V3",
        "status": "PASS_POOL_SCOPED_NON_DECISIONAL_FRONTIER",
        **enumeration,
        "portfolio_count": len(portfolios),
        "frontier_count": len(frontier),
        "pareto_dimensions": [
            *({"field": field, "direction": "max"} for field in fields),
            {"field": "total_distance_m", "direction": "min"},
        ],
        "service_surface": {
            "uniform_headway_min_per_movement": list(HEADWAYS),
            "span_minutes": list(SPANS),
            "annual_service_days": ANNUAL_DAYS,
            "annual_bus_km_cap_reference": str(cap),
            "frequency_used_as_candidate_filter": False,
            "annual_bus_km_used_as_candidate_filter": False,
            "cap_is_annotation_not_elimination": True,
        },
        "current_exact_id_subset_role": "BENCHMARK_ONLY_NOT_RETENTION_CONSTRAINT",
        "current_exact_access_ratios": current_vector,
        "upstream_limit": {
            "search_status": pool["status"],
            "expanded_states": pool["expanded_states"],
            "pending_heap_entries": pool["pending_heap_entries"],
            "individual_walk_distance_envelope_m": pool["distance_budget_m"],
            "candidate_domain_complete": False,
        },
        "municipal_od_spatially_downscaled": False,
        "demand_weighted_gjt_computed": False,
        "empirical_missed_connection_probability_computed": False,
        "weighted_score": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "input_sha256": {
            "physical_pool": POOL_SHA256,
            "walk_matrix": WALK_SHA256,
            "current_audit": sha256(args.current_audit),
            "policy": sha256(args.policy),
        },
        "output_sha256": {
            "portfolio_csv_gz": sha256(args.output_dir / "rt031_data_guided_portfolios_v3.csv.gz"),
            "frontier_json": sha256(frontier_path),
        },
    }
    (args.output_dir / "rt031_data_guided_frontier_v3_audit.json").write_bytes(canonical(audit))
    print(json.dumps(audit, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", type=Path, required=True)
    parser.add_argument("--walk-matrix", type=Path, required=True)
    parser.add_argument("--current-audit", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-movements", type=int, default=4)
    main(parser.parse_args())
