#!/usr/bin/env python3
"""Screen the pinned one-million-state RT031 pool against Current-Service V4."""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import pandas as pd

from phase2_rt029_v4_substrate import validate_walk_matrix
from scripts.phase2_compare_rt031_movement_portfolios_v3 import threshold_vectors
from scripts.phase2_compare_rt031_with_current_baseline_v4 import (
    FINAL_STOPS_SHA256, V4_CLUSTERS_LOGICAL_SHA256, V4_VALIDATION_LOGICAL_SHA256,
    WALK_SHA256, logical_sha256, read_csv, sha256,
)
from src.phase2_rt031_current_baseline_comparison_v3 import (
    DIMENSIONS, compare_with_structural_subset, exact_current_stop_subset,
)
from src.phase2_rt031_movement_portfolios_v3 import enumerate_availability_envelope

EXPANDED_POOL_SHA256 = "273109c45f899cb3c3170bd272a2d8e6aa00d4cb4e3a747caf3205e786cd5703"


def main(args) -> dict:
    for path, digest in ((args.pool, EXPANDED_POOL_SHA256),
                         (args.walk_matrix, WALK_SHA256),
                         (args.final_stops, FINAL_STOPS_SHA256)):
        if sha256(path) != digest:
            raise ValueError(f"pinned input drift: {path}")
    if logical_sha256(args.v4_clusters) != V4_CLUSTERS_LOGICAL_SHA256:
        raise ValueError("Current-Service V4 cluster lineage drift")
    if logical_sha256(args.v4_validation) != V4_VALIDATION_LOGICAL_SHA256:
        raise ValueError("Current-Service V4 validation lineage drift")
    validation = json.loads(args.v4_validation.read_text(encoding="utf-8"))
    if (validation.get("status") != "PASS_PHASE2_CURRENT_SERVICE_ACCESS_BASELINE_V4"
            or validation.get("current_service_baseline_complete") is not False
            or validation.get("fuzzy_matching_used") is not False
            or validation.get("nearest_neighbour_matching_used") is not False):
        raise ValueError("Current-Service V4 semantics are not admissible")

    pool = json.loads(args.pool.read_text(encoding="utf-8"))
    if (pool.get("status") != "RESOURCE_LIMIT_INCOMPLETE"
            or pool.get("expanded_states") != 1_000_000
            or pool.get("execution_expansion_limit") != 1_000_000
            or pool.get("found_stop_set_count") != len(pool.get("candidates", []))):
        raise ValueError("expanded-pool execution contract drift")
    budget = Decimal(pool["distance_budget_m"])
    envelope = enumerate_availability_envelope(pool["candidates"], distance_budget_m=budget)
    summaries = envelope.pop("availability_summaries")

    raw = pd.read_csv(args.walk_matrix, dtype={"population_weight_2025": str})
    weights = (raw[["population_unit_id", "population_weight_2025"]]
               .drop_duplicates().set_index("population_unit_id")["population_weight_2025"].to_dict())
    substrate = validate_walk_matrix(raw)
    exact_weights = [weights[x] for x in substrate.population_meta["population_unit_id"]]
    bridge = exact_current_stop_subset(read_csv(args.v4_clusters), read_csv(args.final_stops))
    stop_sets = [tuple(x["available_stop_ids"]) for x in summaries]
    vectors = threshold_vectors(stop_sets, substrate, exact_weights)
    baseline = tuple(threshold_vectors(
        [tuple(bridge["mapped_stop_place_ids"])], substrate, exact_weights,
    )[0])
    rows = []
    for summary, vector in zip(summaries, vectors):
        rows.append({**summary,
                     "exact_threshold_ratios": json.dumps([str(x) for x in vector])})
    comparison = compare_with_structural_subset(rows, baseline)
    broad = []
    for row, vector in zip(rows, vectors):
        if all(x >= y for x, y in zip(vector, baseline)) and any(x > y for x, y in zip(vector, baseline)):
            broad.append({
                "available_stop_ids": row["available_stop_ids"],
                "distance_m": row["distance_m"],
                "conditional_annual_carrier_km": str(Decimal(row["distance_m"]) * 32 * 260 / 1000),
                "minimum_distance_witnesses": row["minimum_distance_witnesses"],
                "exact_threshold_ratios": [str(x) for x in vector],
                "display_threshold_shares": [float(x) for x in vector],
                "public_service_assigned": False,
            })
    broad.sort(key=lambda x: (Decimal(x["distance_m"]), x["available_stop_ids"]))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    cases_path = args.output_dir / "conditional_broad_access_cases.json"
    cases_path.write_text(json.dumps(broad, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    dimension_path = args.output_dir / "expanded_pool_componentwise_comparison.csv"
    with dimension_path.open("w", encoding="utf-8", newline="") as handle:
        fields = ["dimension", "current_exact_ratio", "current_share",
                  "expanded_pool_maximum_ratio", "expanded_pool_maximum_share",
                  "expanded_minus_current_percentage_points"]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for field, current, maximum in zip(DIMENSIONS, baseline, comparison["candidate_componentwise_maxima"]):
            writer.writerow({"dimension": field, "current_exact_ratio": str(current),
                             "current_share": format(float(current), ".15f"),
                             "expanded_pool_maximum_ratio": str(maximum),
                             "expanded_pool_maximum_share": format(float(maximum), ".15f"),
                             "expanded_minus_current_percentage_points": format(float((maximum-current)*100), ".9f")})

    status = ("CONDITIONAL_BROAD_ACCESS_CASES_FOUND_IN_INCOMPLETE_POOL" if broad else
              "NO_BROAD_ACCESS_REPLACEMENT_CASE_IN_EXPANDED_INCOMPLETE_POOL")
    payload = {
        "contract": "RT031_EXPANDED_POOL_CURRENT_V4_SAME_SUBSTRATE_FEASIBILITY_V3",
        "status": status,
        "source_search_status": pool["status"],
        "source_search_exhaustive": pool["exhaustive"],
        "source_expanded_states": pool["expanded_states"],
        "source_pending_heap_entries": pool["pending_heap_entries"],
        "source_walk_count": len(pool["candidates"]),
        "portfolio_envelope": envelope,
        "unique_availability_set_count": len(summaries),
        "comparison": {k: (dict(zip(DIMENSIONS, map(str, v)))
                          if k == "candidate_componentwise_maxima" else v)
                       for k, v in comparison.items()},
        "current_exact_identity_subset": bridge,
        "current_exact_threshold_ratios": dict(zip(DIMENSIONS, map(str, baseline))),
        "conditional_broad_access_case_count": len(broad),
        "conclusion": ("EXPANDED_POOL_CONTAINS_CONDITIONAL_CASES_REQUIRING_TYPED_SERVICE_BINDING"
                       if broad else "EXPANDED_POOL_STILL_DOES_NOT_ESTABLISH_BROAD_ACCESS_REPLACEMENT"),
        "candidate_coverage_semantics": "POTENTIAL_IF_STOPS_BECOME_PUBLICLY_SERVED",
        "weighted_score": False,
        "uncertainty_band_applied": False,
        "public_service_assigned": False,
        "network_selected": False,
        "scope": "SUPPLIED_ONE_MILLION_STATE_POOL_SINGLETONS_AND_DISTINCT_PAIRS_ONLY",
        "input_sha256": {"expanded_pool": EXPANDED_POOL_SHA256, "walk_matrix": WALK_SHA256,
                         "final_stops": FINAL_STOPS_SHA256,
                         "v4_clusters_logical": V4_CLUSTERS_LOGICAL_SHA256,
                         "v4_validation_logical": V4_VALIDATION_LOGICAL_SHA256},
        "output_sha256": {cases_path.name: sha256(cases_path), dimension_path.name: sha256(dimension_path)},
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
    }
    audit_path = args.output_dir / "expanded_pool_current_v4_audit.json"
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(payload, sort_keys=True))
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", type=Path, required=True)
    parser.add_argument("--walk-matrix", type=Path, required=True)
    parser.add_argument("--final-stops", type=Path, required=True)
    parser.add_argument("--v4-clusters", type=Path, required=True)
    parser.add_argument("--v4-validation", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    main(parser.parse_args())
