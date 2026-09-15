#!/usr/bin/env python3
"""Build the exact supplied-pool frontier for one public-line candidate walk."""
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
from src.phase2_rt031_single_line_frontier_v3 import (
    combine_single_walk_candidates,
)


HUB = "FROZEN::L00407"
HEADWAYS = (20, 30, 40, 60)
SPANS = (600, 720, 960)
ANNUAL_DAYS = 260
ACCESS_FIELDS = (
    "potential_core_share_5min", "potential_core_share_8min",
    "potential_core_share_10min", "potential_worst_municipality_share_5min",
    "potential_worst_municipality_share_8min",
    "potential_worst_municipality_share_10min",
)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def parse_named_paths(values):
    parsed = []
    names = set()
    for raw in values:
        name, separator, path = raw.partition("=")
        if not separator or not name or name in names:
            raise ValueError("pools require unique NAME=PATH declarations")
        names.add(name)
        parsed.append((name, Path(path)))
    return parsed


def main(args):
    named_paths = parse_named_paths(args.pool)
    named_pools = [(name, json.loads(path.read_text(encoding="utf-8")))
                   for name, path in named_paths]
    combined = combine_single_walk_candidates(named_pools, hub_stop_id=HUB)
    candidates = combined.pop("candidates")
    current = json.loads(args.current_audit.read_text(encoding="utf-8"))
    if current.get("contract") != "RT031_CURRENT_EXACT_TARGET_COVER_RESOURCE_SYMMETRY_V3":
        raise ValueError("current benchmark contract drift")
    current_stops = frozenset(
        current["current_exact_identity_subset"]["mapped_stop_place_ids"])
    if len(current_stops) != 11 or HUB not in current_stops:
        raise ValueError("current exact stop identity drift")
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    cap = Decimal(str(policy["human_policy_decisions"]["annual_bus_km_cap"]))

    raw_walk = pd.read_csv(args.walk_matrix, dtype={"population_weight_2025": str})
    weight_map = (raw_walk[["population_unit_id", "population_weight_2025"]]
                  .drop_duplicates().set_index("population_unit_id")
                  ["population_weight_2025"].to_dict())
    substrate = validate_walk_matrix(raw_walk)
    exact_weights = [weight_map[value]
                     for value in substrate.population_meta["population_unit_id"]]
    access = threshold_vectors(
        [row["available_stop_ids"] for row in candidates], substrate, exact_weights)
    vectors = np.empty((len(candidates), 7), dtype=object)
    vectors[:, :6] = access
    retention = [len(current_stops.intersection(row["available_stop_ids"]))
                 for row in candidates]
    vectors[:, 6] = [Fraction(value, len(current_stops)) for value in retention]
    costs = [Decimal(row["minimum_found_distance_m"]) for row in candidates]
    frontier_indices = pareto_indices(vectors, costs)
    for index, row in enumerate(candidates):
        row["total_distance_m"] = row.pop("minimum_found_distance_m")
        row["exact_access_ratios"] = [str(value) for value in access[index]]
        row.update({field: float(value)
                    for field, value in zip(ACCESS_FIELDS, access[index])})
        row["retained_current_exact_stop_count"] = retention[index]
        row["retained_current_exact_stop_share"] = str(vectors[index, 6])
        row["retained_current_exact_stop_ids"] = sorted(
            current_stops.intersection(row["available_stop_ids"]))

    current_result = current["all_movements_serve_olgiate_fs_portfolio"]["results"][1]
    current_vector = tuple(Fraction(value) for value in
                           current_result["same_substrate_access_comparison"]
                           ["current_exact_ratios"])
    benchmark_better = [
        index for index in frontier_indices
        if all(access[index, axis] >= current_vector[axis] for axis in range(6))
        and any(access[index, axis] > current_vector[axis] for axis in range(6))
    ]
    frontier = []
    for index in frontier_indices:
        row = dict(candidates[index])
        row["service_surface"] = [{
            **service,
            "within_approved_reference_cap": Decimal(service["annual_bus_km"]) <= cap,
        } for service in service_surface(
            row["total_distance_m"], 1, headways=HEADWAYS, spans=SPANS,
            annual_days=ANNUAL_DAYS)]
        frontier.append(row)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "rt031_single_line_candidates_v3.csv.gz"
    fields = [
        "candidate_line_id", "total_distance_m", *ACCESS_FIELDS,
        "retained_current_exact_stop_count", "retained_current_exact_stop_share",
        "exact_access_ratios", "retained_current_exact_stop_ids",
        "available_stop_ids", "realization_ids", "discovery_lanes",
        "physical_closed_walk_count", "intended_public_route_identity_count",
    ]
    zipped_csv(csv_path, fields, ({
        **row,
        "exact_access_ratios": json.dumps(row["exact_access_ratios"], separators=(",", ":")),
        "retained_current_exact_stop_ids": json.dumps(row["retained_current_exact_stop_ids"], separators=(",", ":")),
        "available_stop_ids": json.dumps(row["available_stop_ids"], separators=(",", ":")),
        "realization_ids": json.dumps(row["realization_ids"], separators=(",", ":")),
        "discovery_lanes": json.dumps(row["discovery_lanes"], separators=(",", ":")),
    } for row in candidates))
    frontier_path = args.output_dir / "rt031_single_line_frontier_v3.json"
    frontier_path.write_bytes(canonical(frontier))
    audit = {
        "contract": "RT031_SINGLE_RECOGNIZABLE_LINE_DISCOVERY_FRONTIER_V3",
        "status": "PASS_POOL_SCOPED_NON_DECISIONAL_SINGLE_LINE_FRONTIER",
        **combined,
        "candidate_count": len(candidates),
        "frontier_count": len(frontier),
        "frontier_no_worse_than_current_all_six_and_strict_any_count": len(
            benchmark_better),
        "maximum_available_stop_count": max(
            len(row["available_stop_ids"]) for row in candidates),
        "maximum_retained_current_exact_stop_count": max(retention),
        "pareto_dimensions": [
            *({"field": field, "direction": "max"} for field in ACCESS_FIELDS),
            {"field": "retained_current_exact_stop_share", "direction": "max"},
            {"field": "total_distance_m", "direction": "min"},
        ],
        "single_line_semantics": (
            "ONE_PUBLIC_ROUTE_IDENTITY; DIRECTIONAL_VARIANTS_ALLOWED_ONLY_AFTER_"
            "ORDERED_EVENT_AND_PASSENGER_CONTINUITY_BINDING"),
        "single_public_line_required": True,
        "current_stop_retention_required": False,
        "current_stop_retention_preference": True,
        "retention_semantics": (
            "EXACT_STOP_IDENTITY_SHARE_ONLY_NOT_DIRECTIONAL_OCCURRENCE_OR_ORDERED_SERVICE_EVENT"),
        "service_surface": {
            "uniform_headway_min": list(HEADWAYS),
            "span_minutes": list(SPANS),
            "annual_service_days": ANNUAL_DAYS,
            "annual_bus_km_cap_reference": str(cap),
            "frequency_used_as_candidate_filter": False,
            "annual_bus_km_used_as_candidate_filter": False,
        },
        "municipal_od_spatially_downscaled": False,
        "demand_weighted_gjt_computed": False,
        "empirical_missed_connection_probability_computed": False,
        "weighted_score": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "input_sha256": {
            **{"pool::" + name: sha256(path) for name, path in named_paths},
            "walk_matrix": sha256(args.walk_matrix),
            "current_audit": sha256(args.current_audit),
            "policy": sha256(args.policy),
        },
        "output_sha256": {
            "candidate_csv_gz": sha256(csv_path),
            "frontier_json": sha256(frontier_path),
        },
    }
    (args.output_dir / "rt031_single_line_frontier_v3_audit.json").write_bytes(
        canonical(audit))
    print(json.dumps(audit, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", action="append", required=True,
                        help="repeat NAME=PATH")
    parser.add_argument("--walk-matrix", type=Path, required=True)
    parser.add_argument("--current-audit", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    main(parser.parse_args())
