#!/usr/bin/env python3
"""Build a no-weight hub-connected frontier with stop retention as preference."""
from __future__ import annotations

import argparse
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from phase2_rt029_v4_substrate import validate_walk_matrix
from scripts.phase2_compare_rt031_movement_portfolios_v3 import (
    pareto_indices, threshold_vectors, zipped_csv,
)
from src.phase2_rt031_data_guided_portfolios_v3 import service_surface
from src.phase2_rt031_network_connected_portfolios_v3 import (
    enumerate_network_connected_portfolios,
)


HUB_POOL_SHA256 = "b86b27f791b0b36f0e30997a96388c5763f46822411ea990bfeed3351cd8a65c"
GENERIC_POOL_SHA256 = "273109c45f899cb3c3170bd272a2d8e6aa00d4cb4e3a747caf3205e786cd5703"
WALK_SHA256 = "a47bbce413d056db185180173ab2f05dce0463cb626a2c81f4aff64de91b50c1"
HUB = "FROZEN::L00407"
HEADWAYS = (20, 30, 40, 60)
SPANS = (600, 720, 960)
ANNUAL_DAYS = 260


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(payload) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def load_pool(path, expected_sha, expected_root):
    if sha256(path) != expected_sha:
        raise ValueError("pinned physical-pool lineage drift")
    pool = json.loads(path.read_text(encoding="utf-8"))
    if (pool.get("contract") != "RT031_BUDGETED_PHYSICAL_CLOSED_WALK_SEARCH_V3"
            or pool.get("status") != "RESOURCE_LIMIT_INCOMPLETE"
            or pool.get("required_root_stop_id") != expected_root):
        raise ValueError("unexpected physical-pool contract boundary")
    return pool


def main(args):
    if args.max_movements != 2:
        raise ValueError("this certified run is explicitly bounded to two movements")
    if sha256(args.walk_matrix) != WALK_SHA256:
        raise ValueError("pinned walking-substrate lineage drift")
    hub_pool = load_pool(args.hub_pool, HUB_POOL_SHA256, HUB)
    generic_pool = load_pool(args.generic_pool, GENERIC_POOL_SHA256, None)
    current = json.loads(args.current_audit.read_text(encoding="utf-8"))
    if current.get("contract") != "RT031_CURRENT_EXACT_TARGET_COVER_RESOURCE_SYMMETRY_V3":
        raise ValueError("current benchmark contract drift")
    current_stops = tuple(current["current_exact_identity_subset"]["mapped_stop_place_ids"])
    if len(current_stops) != 11 or HUB not in current_stops:
        raise ValueError("current exact-identity benchmark drift")
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    cap = Decimal(str(policy["human_policy_decisions"]["annual_bus_km_cap"]))

    candidates = []
    for prefix, pool in (("hub", hub_pool), ("generic", generic_pool)):
        for raw in pool["candidates"]:
            row = dict(raw)
            row["candidate_id"] = prefix + "::" + str(raw["stop_set_id"])
            candidates.append(row)
    enumeration = enumerate_network_connected_portfolios(
        candidates, hub_stop_id=HUB, max_movements=args.max_movements)
    portfolios = enumeration.pop("portfolios")

    raw_walk = pd.read_csv(args.walk_matrix, dtype={"population_weight_2025": str})
    weight_map = (raw_walk[["population_unit_id", "population_weight_2025"]]
                  .drop_duplicates().set_index("population_unit_id")
                  ["population_weight_2025"].to_dict())
    substrate = validate_walk_matrix(raw_walk)
    exact_weights = [weight_map[value]
                     for value in substrate.population_meta["population_unit_id"]]
    access_vectors = threshold_vectors(
        [row["available_stop_ids"] for row in portfolios], substrate, exact_weights)
    current_stop_set = frozenset(current_stops)
    retention_counts = [
        len(current_stop_set.intersection(row["available_stop_ids"]))
        for row in portfolios
    ]
    vectors = np.empty((len(portfolios), 7), dtype=object)
    vectors[:, :6] = access_vectors
    vectors[:, 6] = [Fraction(count, len(current_stops)) for count in retention_counts]
    costs = [Decimal(row["total_distance_m"]) for row in portfolios]
    frontier_indices = pareto_indices(vectors, costs)
    fields = (
        "potential_core_share_5min", "potential_core_share_8min",
        "potential_core_share_10min", "potential_worst_municipality_share_5min",
        "potential_worst_municipality_share_8min",
        "potential_worst_municipality_share_10min",
    )
    for index, row in enumerate(portfolios):
        row["portfolio_id"] = "NC_" + hashlib.sha256(
            (";".join(row["source_walk_ids"]) + "|" + row["total_distance_m"]).encode()
        ).hexdigest()[:20]
        row.update({field: float(value)
                    for field, value in zip(fields, access_vectors[index])})
        row["exact_access_ratios"] = [str(value) for value in access_vectors[index]]
        row["retained_current_exact_stop_count"] = retention_counts[index]
        row["retained_current_exact_stop_share"] = str(vectors[index, 6])
        row["retained_current_exact_stop_ids"] = sorted(
            current_stop_set.intersection(row["available_stop_ids"]))

    current_result = current["all_movements_serve_olgiate_fs_portfolio"]["results"][1]
    current_vector = tuple(Fraction(value) for value in
                           current_result["same_substrate_access_comparison"]
                           ["current_exact_ratios"])
    benchmark_better = [
        index for index in frontier_indices
        if all(access_vectors[index, axis] >= current_vector[axis] for axis in range(6))
        and any(access_vectors[index, axis] > current_vector[axis] for axis in range(6))
    ]
    frontier = []
    for index in frontier_indices:
        row = dict(portfolios[index])
        row["service_surface"] = [{
            **service,
            "within_approved_reference_cap": Decimal(service["annual_bus_km"]) <= cap,
        } for service in service_surface(
            row["total_distance_m"], row["movement_count"], headways=HEADWAYS,
            spans=SPANS, annual_days=ANNUAL_DAYS)]
        frontier.append(row)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_fields = [
        "portfolio_id", "movement_count", "total_distance_m", *fields,
        "retained_current_exact_stop_count", "retained_current_exact_stop_share",
        "exact_access_ratios", "retained_current_exact_stop_ids",
        "available_stop_ids", "source_walk_ids",
    ]
    zipped_csv(args.output_dir / "rt031_network_connected_portfolios_v3.csv.gz",
               csv_fields, ({
                   **row,
                   "exact_access_ratios": json.dumps(row["exact_access_ratios"], separators=(",", ":")),
                   "retained_current_exact_stop_ids": json.dumps(row["retained_current_exact_stop_ids"], separators=(",", ":")),
                   "available_stop_ids": json.dumps(row["available_stop_ids"], separators=(",", ":")),
                   "source_walk_ids": json.dumps(row["source_walk_ids"], separators=(",", ":")),
               } for row in portfolios))
    frontier_path = args.output_dir / "rt031_network_connected_frontier_v3.json"
    frontier_path.write_bytes(canonical(frontier))
    audit = {
        "contract": "RT031_NETWORK_CONNECTED_STOP_RETENTION_PREFERENCE_FRONTIER_V3",
        "status": "PASS_POOL_SCOPED_NON_DECISIONAL_FRONTIER",
        **enumeration,
        "portfolio_count": len(portfolios),
        "frontier_count": len(frontier),
        "pareto_dimensions": [
            *({"field": field, "direction": "max"} for field in fields),
            {"field": "retained_current_exact_stop_share", "direction": "max"},
            {"field": "total_distance_m", "direction": "min"},
        ],
        "current_stop_retention_required": False,
        "current_stop_retention_preference": True,
        "retention_semantics": (
            "EXACT_STOP_IDENTITY_SHARE_ONLY_NOT_DIRECTIONAL_OCCURRENCE_OR_ORDERED_SERVICE_EVENT"),
        "current_exact_stop_identity_count": len(current_stops),
        "current_exact_stop_ids": list(current_stops),
        "preference_has_weight": False,
        "preference_used_as_candidate_filter": False,
        "frontier_retention_count_distribution": {
            str(count): sum(row["retained_current_exact_stop_count"] == count
                            for row in frontier)
            for count in sorted(set(row["retained_current_exact_stop_count"]
                                    for row in frontier))
        },
        "current_exact_access_ratios": [str(value) for value in current_vector],
        "frontier_no_worse_than_current_all_six_and_strict_any_count": len(benchmark_better),
        "service_surface": {
            "uniform_headway_min_per_movement": list(HEADWAYS),
            "span_minutes": list(SPANS),
            "annual_service_days": ANNUAL_DAYS,
            "annual_bus_km_cap_reference": str(cap),
            "frequency_used_as_candidate_filter": False,
            "annual_bus_km_used_as_candidate_filter": False,
            "cap_is_annotation_not_elimination": True,
        },
        "enumeration_scope_limit": {
            "maximum_movement_count": args.max_movements,
            "larger_movement_count_impossibility_claimed": False,
            "reason": "EXACT_INITIAL_NETWORK_LEVEL_EXPANSION_BOUND",
        },
        "upstream_limits": [{
            "pool": name, "search_status": pool["status"],
            "expanded_states": pool["expanded_states"],
            "pending_heap_entries": pool["pending_heap_entries"],
            "individual_walk_distance_envelope_m": pool["distance_budget_m"],
            "candidate_domain_complete": False,
        } for name, pool in (("hub_rooted", hub_pool), ("generic", generic_pool))],
        "municipal_od_spatially_downscaled": False,
        "demand_weighted_gjt_computed": False,
        "empirical_missed_connection_probability_computed": False,
        "weighted_score": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "input_sha256": {
            "hub_physical_pool": HUB_POOL_SHA256,
            "generic_physical_pool": GENERIC_POOL_SHA256,
            "walk_matrix": WALK_SHA256,
            "current_audit": sha256(args.current_audit),
            "policy": sha256(args.policy),
        },
        "output_sha256": {
            "portfolio_csv_gz": sha256(args.output_dir / "rt031_network_connected_portfolios_v3.csv.gz"),
            "frontier_json": sha256(frontier_path),
        },
    }
    (args.output_dir / "rt031_network_connected_frontier_v3_audit.json").write_bytes(
        canonical(audit))
    print(json.dumps(audit, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--hub-pool", type=Path, required=True)
    parser.add_argument("--generic-pool", type=Path, required=True)
    parser.add_argument("--walk-matrix", type=Path, required=True)
    parser.add_argument("--current-audit", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-movements", type=int, default=2)
    main(parser.parse_args())
