#!/usr/bin/env python3
"""Build the exact pool-scoped no-weight frontier for up to three movements."""
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
    pareto_indices, threshold_vectors,
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
FIELDS = (
    "potential_core_share_5min", "potential_core_share_8min",
    "potential_core_share_10min", "potential_worst_municipality_share_5min",
    "potential_worst_municipality_share_8min",
    "potential_worst_municipality_share_10min",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(payload) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def load_pool(path: Path, expected_sha: str, expected_root):
    if sha256(path) != expected_sha:
        raise ValueError("pinned physical-pool lineage drift")
    pool = json.loads(path.read_text(encoding="utf-8"))
    if (pool.get("contract") != "RT031_BUDGETED_PHYSICAL_CLOSED_WALK_SEARCH_V3"
            or pool.get("status") != "RESOURCE_LIMIT_INCOMPLETE"
            or pool.get("required_root_stop_id") != expected_root):
        raise ValueError("unexpected physical-pool contract boundary")
    return pool


def exact_row_vector(row, current_count: int):
    return tuple(Fraction(value) for value in row["exact_access_ratios"]) + (
        Fraction(int(row["retained_current_exact_stop_count"]), current_count),)


def dominates(vector_a, cost_a, vector_b, cost_b) -> bool:
    return (cost_a <= cost_b
            and all(a >= b for a, b in zip(vector_a, vector_b))
            and (cost_a < cost_b
                 or any(a > b for a, b in zip(vector_a, vector_b))))


def main(args):
    if args.max_movements != 3:
        raise ValueError("this expanded certified lane is explicitly bounded to three movements")
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
    current_stop_set = frozenset(current_stops)
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    cap = Decimal(str(policy["human_policy_decisions"]["annual_bus_km_cap"]))

    candidates = []
    for prefix, pool in (("hub", hub_pool), ("generic", generic_pool)):
        for raw in pool["candidates"]:
            row = dict(raw)
            row["candidate_id"] = prefix + "::" + str(raw["stop_set_id"])
            candidates.append(row)

    enumeration = enumerate_network_connected_portfolios(
        candidates, hub_stop_id=HUB, max_movements=args.max_movements,
        materialize_portfolios=False, compact_final_states=True,
        pareto_prune_final_states=True)
    compact_states = enumeration.pop("compact_final_states")
    universe = enumeration.pop("stop_universe")
    if (not enumeration["within_supplied_pool_pareto_complete_for_monotone_stop_union_objectives"]
            or not enumeration["final_pareto_preprune_applied"]):
        raise AssertionError("exact compact Pareto-sufficient enumeration contract failed")
    if len(compact_states) != enumeration["final_state_count_after_pareto_preprune"]:
        raise AssertionError("compact-state count drift")
    print(json.dumps({
        "stage": "exact_connected_domain_prepruned",
        "states": len(compact_states),
        "states_before_final_preprune": enumeration["final_state_count_before_pareto_preprune"],
    }, sort_keys=True), flush=True)

    # Decode only the exact final-preprune survivors. Strings are references to
    # the fixed universe, so this avoids allocating the million-row dictionary
    # representation used by the original two-movement lane.
    stop_sets = [
        tuple(stop for index, stop in enumerate(universe) if mask & (1 << index))
        for mask, _, _ in compact_states
    ]
    raw_walk = pd.read_csv(args.walk_matrix, dtype={"population_weight_2025": str})
    weight_map = (raw_walk[["population_unit_id", "population_weight_2025"]]
                  .drop_duplicates().set_index("population_unit_id")
                  ["population_weight_2025"].to_dict())
    substrate = validate_walk_matrix(raw_walk)
    exact_weights = [weight_map[value]
                     for value in substrate.population_meta["population_unit_id"]]
    access_vectors = threshold_vectors(stop_sets, substrate, exact_weights)
    retention_counts = [len(current_stop_set.intersection(stops)) for stops in stop_sets]
    vectors = np.empty((len(compact_states), 7), dtype=object)
    vectors[:, :6] = access_vectors
    vectors[:, 6] = [Fraction(value, len(current_stops)) for value in retention_counts]
    costs = [state[1] for state in compact_states]
    print(json.dumps({"stage": "exact_access_metrics_complete"}, sort_keys=True), flush=True)

    frontier_indices = pareto_indices(vectors, costs)
    frontier = []
    for index in frontier_indices:
        mask, cost, identities = compact_states[index]
        exact_access = tuple(access_vectors[index])
        row = {
            "portfolio_id": "NC3_" + hashlib.sha256(
                (";".join(identities) + "|" + str(cost)).encode()).hexdigest()[:20],
            "available_stop_ids": list(stop_sets[index]),
            "total_distance_m": str(cost),
            "movement_count": len(identities),
            "source_walk_ids": list(identities),
            **{field: float(value) for field, value in zip(FIELDS, exact_access)},
            "exact_access_ratios": [str(value) for value in exact_access],
            "retained_current_exact_stop_count": retention_counts[index],
            "retained_current_exact_stop_share": str(vectors[index, 6]),
            "retained_current_exact_stop_ids": sorted(
                current_stop_set.intersection(stop_sets[index])),
        }
        row["service_surface"] = [{
            **service,
            "within_approved_reference_cap": Decimal(service["annual_bus_km"]) <= cap,
        } for service in service_surface(
            row["total_distance_m"], row["movement_count"], headways=HEADWAYS,
            spans=SPANS, annual_days=ANNUAL_DAYS)]
        frontier.append(row)
    frontier.sort(key=lambda row: row["portfolio_id"])
    print(json.dumps({"stage": "exact_pareto_complete", "frontier": len(frontier)},
                     sort_keys=True), flush=True)

    max2_frontier = json.loads(args.max2_frontier.read_text(encoding="utf-8"))
    max2_vectors = [exact_row_vector(row, len(current_stops)) for row in max2_frontier]
    max2_costs = [Decimal(row["total_distance_m"]) for row in max2_frontier]
    max3_vectors = [exact_row_vector(row, len(current_stops)) for row in frontier]
    max3_costs = [Decimal(row["total_distance_m"]) for row in frontier]
    max3_three = [index for index, row in enumerate(frontier)
                  if row["movement_count"] == 3]

    max2_dominated_by_three = []
    three_dominates_max2 = set()
    for j, (vector2, cost2) in enumerate(zip(max2_vectors, max2_costs)):
        dominators = [
            i for i in max3_three
            if dominates(max3_vectors[i], max3_costs[i], vector2, cost2)
        ]
        if dominators:
            max2_dominated_by_three.append(j)
            three_dominates_max2.update(dominators)

    max2_stop_unions = {tuple(row["available_stop_ids"]) for row in max2_frontier}
    new_stop_union_count = sum(
        tuple(row["available_stop_ids"]) not in max2_stop_unions for row in frontier)
    current_result = current["all_movements_serve_olgiate_fs_portfolio"]["results"][1]
    current_vector = tuple(Fraction(value) for value in
                           current_result["same_substrate_access_comparison"]
                           ["current_exact_ratios"])
    no_worse_current = sum(
        all(vector[axis] >= current_vector[axis] for axis in range(6))
        and any(vector[axis] > current_vector[axis] for axis in range(6))
        for vector in max3_vectors
    )

    movement_distribution = {
        str(count): sum(row["movement_count"] == count for row in frontier)
        for count in sorted(set(row["movement_count"] for row in frontier))
    }
    retention_distribution = {
        str(count): sum(row["retained_current_exact_stop_count"] == count
                        for row in frontier)
        for count in sorted(set(row["retained_current_exact_stop_count"]
                                for row in frontier))
    }
    best_retention_by_movements = {
        str(count): max(row["retained_current_exact_stop_count"] for row in frontier
                        if row["movement_count"] == count)
        for count in sorted(set(row["movement_count"] for row in frontier))
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    frontier_path = args.output_dir / "rt031_network_connected_max3_frontier_v3.json"
    frontier_path.write_bytes(canonical(frontier))
    audit = {
        "contract": "RT031_NETWORK_CONNECTED_MAX3_STOP_RETENTION_PREFERENCE_FRONTIER_V3",
        "status": "PASS_POOL_SCOPED_NON_DECISIONAL_MAX3_FRONTIER",
        **enumeration,
        "evaluated_final_preprune_state_count": len(compact_states),
        "frontier_count": len(frontier),
        "frontier_movement_count_distribution": movement_distribution,
        "frontier_retention_count_distribution": retention_distribution,
        "best_retained_current_exact_stop_count": max(retention_counts[index]
                                                       for index in frontier_indices),
        "best_retained_current_exact_stop_count_by_movement_count": (
            best_retention_by_movements),
        "frontier_retention_at_least_7_count": sum(
            row["retained_current_exact_stop_count"] >= 7 for row in frontier),
        "frontier_retention_at_least_8_count": sum(
            row["retained_current_exact_stop_count"] >= 8 for row in frontier),
        "frontier_retention_at_least_9_count": sum(
            row["retained_current_exact_stop_count"] >= 9 for row in frontier),
        "frontier_retention_at_least_10_count": sum(
            row["retained_current_exact_stop_count"] >= 10 for row in frontier),
        "frontier_retention_all_11_count": sum(
            row["retained_current_exact_stop_count"] == 11 for row in frontier),
        "pareto_dimensions": [
            *({"field": field, "direction": "max"} for field in FIELDS),
            {"field": "retained_current_exact_stop_share", "direction": "max"},
            {"field": "total_distance_m", "direction": "min"},
        ],
        "current_stop_retention_required": False,
        "current_stop_retention_preference": True,
        "preference_has_weight": False,
        "preference_used_as_candidate_filter": False,
        "current_exact_stop_identity_count": len(current_stops),
        "current_exact_stop_ids": list(current_stops),
        "current_exact_access_ratios": [str(value) for value in current_vector],
        "frontier_no_worse_than_current_all_six_and_strict_any_count": no_worse_current,
        "max2_comparison": {
            "reference_frontier_sha256": sha256(args.max2_frontier),
            "reference_frontier_count": len(max2_frontier),
            "new_nondominated_stop_union_count": new_stop_union_count,
            "max2_frontier_points_strictly_dominated_by_a_three_movement_frontier_point": (
                len(max2_dominated_by_three)),
            "three_movement_frontier_points_strictly_dominating_a_max2_frontier_point": (
                len(three_dominates_max2)),
            "max3_strict_improvement_over_max2_exists": bool(max2_dominated_by_three),
        },
        "dominance_arithmetic": (
            "EXACT_SOURCE_DECIMAL_POPULATION_RATIOS_RETENTION_FRACTIONS_AND_DECIMAL_DISTANCE_FLOATS_DISPLAY_ONLY"),
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
            "reason": "EXACT_EXPANDED_NETWORK_LEVEL_BOUND",
        },
        "candidate_domain_complete": False,
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
            "max2_frontier": sha256(args.max2_frontier),
        },
        "output_sha256": {"frontier_json": sha256(frontier_path)},
    }
    audit_path = args.output_dir / "rt031_network_connected_max3_frontier_v3_audit.json"
    audit_path.write_bytes(canonical(audit))
    print(json.dumps(audit, sort_keys=True), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--hub-pool", type=Path, required=True)
    parser.add_argument("--generic-pool", type=Path, required=True)
    parser.add_argument("--walk-matrix", type=Path, required=True)
    parser.add_argument("--current-audit", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--max2-frontier", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-movements", type=int, default=3)
    main(parser.parse_args())
