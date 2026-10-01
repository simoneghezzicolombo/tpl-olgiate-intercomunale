#!/usr/bin/env python3
"""Exact same-substrate access audit: RT031 pool versus Current-Service V4 subset."""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path

import pandas as pd

from phase2_rt029_v4_substrate import validate_walk_matrix
from scripts.phase2_compare_rt031_movement_portfolios_v3 import threshold_vectors
from src.phase2_rt031_current_baseline_comparison_v3 import (
    DIMENSIONS, compare_with_structural_subset, exact_current_stop_subset,
)

WALK_SHA256 = "a47bbce413d056db185180173ab2f05dce0463cb626a2c81f4aff64de91b50c1"
FINAL_STOPS_SHA256 = "53af82ccfc398719781faf526d482431d2258bd637a74349222e0c4967642076"
CANDIDATES_SHA256 = "de59464e060d8cac32bebeaa86d120ac8c7081b8f4651b4027a010dc729a541d"
V4_CLUSTERS_LOGICAL_SHA256 = "b9690e2814d93c62f26b104cd5713cb097ac64898b8d0c53bfbf64afff0404c9"
V4_VALIDATION_LOGICAL_SHA256 = "4308b5c5dcce7f58d598c891442f877b60aee09f9eac62fcf56b29ede1208306"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def logical_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    if path.suffix == ".gz":
        handle = gzip.open(path, "rt", encoding="utf-8-sig", newline="")
    else:
        handle = path.open(encoding="utf-8-sig", newline="")
    with handle:
        return list(csv.DictReader(handle))


def main(args) -> dict:
    expected = {
        args.walk_matrix: WALK_SHA256,
        args.final_stops: FINAL_STOPS_SHA256,
        args.candidates: CANDIDATES_SHA256,
    }
    for path, digest in expected.items():
        if sha256(path) != digest:
            raise ValueError(f"pinned input drift: {path}")
    if logical_sha256(args.v4_clusters) != V4_CLUSTERS_LOGICAL_SHA256:
        raise ValueError("Current-Service V4 cluster lineage drift")
    if logical_sha256(args.v4_validation) != V4_VALIDATION_LOGICAL_SHA256:
        raise ValueError("Current-Service V4 validation lineage drift")

    validation = json.loads(args.v4_validation.read_text(encoding="utf-8"))
    required = {
        "status": "PASS_PHASE2_CURRENT_SERVICE_ACCESS_BASELINE_V4",
        "current_route_level_activation_certified_for_reference_date": True,
        "fuzzy_matching_used": False,
        "nearest_neighbour_matching_used": False,
        "invented_stop_coordinates": False,
        "primary_selected": False,
        "runner_up_selected": False,
    }
    if any(validation.get(k) != v for k, v in required.items()):
        raise ValueError("Current-Service V4 is not admissible for structural comparison")
    if validation.get("current_service_baseline_complete") is not False:
        raise ValueError("V4 incompleteness semantics drift")

    bridge = exact_current_stop_subset(read_csv(args.v4_clusters), read_csv(args.final_stops))
    raw = pd.read_csv(args.walk_matrix, dtype={"population_weight_2025": str})
    weight_map = (raw[["population_unit_id", "population_weight_2025"]]
                  .drop_duplicates().set_index("population_unit_id")["population_weight_2025"].to_dict())
    substrate = validate_walk_matrix(raw)
    exact_weights = [weight_map[x] for x in substrate.population_meta["population_unit_id"]]
    baseline = tuple(threshold_vectors(
        [tuple(bridge["mapped_stop_place_ids"])], substrate, exact_weights,
    )[0])
    candidate_rows = read_csv(args.candidates)
    result = compare_with_structural_subset(candidate_rows, baseline)

    comparison = []
    for field, current, maximum in zip(DIMENSIONS, baseline, result["candidate_componentwise_maxima"]):
        comparison.append({
            "dimension": field,
            "current_structural_exact_id_subset_ratio": str(current),
            "current_structural_exact_id_subset_share": format(float(current), ".15f"),
            "rt031_supplied_pool_maximum_ratio": str(maximum),
            "rt031_supplied_pool_maximum_share": format(float(maximum), ".15f"),
            "rt031_minus_current_percentage_points": format(float((maximum - current) * 100), ".9f"),
            "componentwise_maximum_relation": ("RT031_MAX_HIGHER" if maximum > current else
                                                "EQUAL" if maximum == current else "CURRENT_SUBSET_HIGHER"),
        })

    args.output_dir.mkdir(parents=True, exist_ok=True)
    comparison_path = args.output_dir / "rt031_vs_current_v4_same_substrate_dimensions.csv"
    with comparison_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparison[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(comparison)

    payload = {
        "contract": "RT031_CURRENT_V4_SAME_SUBSTRATE_STRUCTURAL_ACCESS_AUDIT_V3",
        "status": result["status"],
        "conclusion": ("THE_SUPPLIED_ONE_TWO_MOVEMENT_POOL_DOES_NOT_ESTABLISH_A_BROAD_"
                       "ACCESS_REPLACEMENT_CASE_AGAINST_THE_EXACT_ID_CURRENT_STRUCTURAL_SUBSET"),
        "candidate_universe": "ALL_173663_UNIQUE_AVAILABILITY_SETS_IN_PINNED_RT031_ONE_TWO_MOVEMENT_POOL",
        "candidate_coverage_semantics": "POTENTIAL_IF_STOPS_BECOME_PUBLICLY_SERVED",
        "current_comparator_semantics": (
            "D184_D185_V4_STRUCTURAL_PHYSICAL_STOP_SUBSET_MAPPED_BY_EXACT_OFFICIAL_ID;_"
            "ROUTE_LEVEL_CURRENT_ACTIVATION_NOT_STOP_LEVEL_OPERATION_SNAPSHOT"
        ),
        "same_rt028_population_and_walk_matrix_used": True,
        "population_or_walking_substrate_cross_version_comparison_used": False,
        "mapping": bridge,
        "exact_baseline_threshold_ratios": dict(zip(DIMENSIONS, map(str, baseline))),
        "display_baseline_threshold_shares": dict(zip(DIMENSIONS, map(float, baseline))),
        "candidate_componentwise_maxima": dict(zip(
            DIMENSIONS, map(str, result["candidate_componentwise_maxima"]))),
        "candidate_count": result["candidate_count"],
        "candidate_no_worse_than_baseline_all_six_count": result["candidate_no_worse_than_baseline_all_six_count"],
        "candidate_strictly_broadly_superior_count": result["candidate_strictly_broadly_superior_count"],
        "baseline_no_worse_than_candidate_all_six_count": result["baseline_no_worse_than_candidate_all_six_count"],
        "broad_replacement_case_established": result["broad_replacement_case_established"],
        "weighted_score": False,
        "tolerance_or_uncertainty_band_applied": False,
        "candidate_public_service_inferred": False,
        "current_stop_level_activation_inferred": False,
        "general_rt031_search_complete": False,
        "current_service_baseline_complete": False,
        "scope_rejection": "SUPPLIED_POOL_ONLY_NOT_ALL_POSSIBLE_NETWORKS",
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "network_selected": False,
        "input_sha256": {
            "walk_matrix": WALK_SHA256,
            "final_stops": FINAL_STOPS_SHA256,
            "candidate_availability_comparison": CANDIDATES_SHA256,
            "v4_clusters_logical": V4_CLUSTERS_LOGICAL_SHA256,
            "v4_validation_logical": V4_VALIDATION_LOGICAL_SHA256,
        },
        "output_sha256": {comparison_path.name: sha256(comparison_path)},
    }
    audit_path = args.output_dir / "rt031_current_v4_same_substrate_audit.json"
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(payload, sort_keys=True))
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--walk-matrix", type=Path, required=True)
    parser.add_argument("--final-stops", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--v4-clusters", type=Path, required=True)
    parser.add_argument("--v4-validation", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    main(parser.parse_args())
