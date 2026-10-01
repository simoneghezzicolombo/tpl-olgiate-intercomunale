"""Exact walking-access descriptors for two typed hub-split directions."""

import argparse
from fractions import Fraction
import json
from pathlib import Path

import pandas as pd

from phase2_rt029_v4_substrate import validate_walk_matrix
from scripts.phase2_audit_rt031_real_pairwise_compatible_domain_v3 import (
    canonical, sha256_file,
)
from scripts.phase2_bind_rt031_joint_target_witness_v3 import (
    CURRENT_PATH, CURRENT_SHA256,
)
from scripts.phase2_build_rt031_municipal_access_frontier_v4 import (
    detailed_threshold_vectors, MUNICIPALITY_NAMES, WALK_SHA256,
)


TYPED_SHA256 = "c0169f3e39e1132853c2e8324d00bbb3030dbf5219c65889eee6ae4acf31b32e"
THRESHOLDS = (5, 8, 10)


def main(typed_path: Path, walk_matrix: Path, output: Path):
    if (sha256_file(typed_path) != TYPED_SHA256
            or sha256_file(walk_matrix) != WALK_SHA256
            or sha256_file(CURRENT_PATH) != CURRENT_SHA256):
        raise ValueError("typed, walking or current reference digest drift")
    typed = json.loads(typed_path.read_text(encoding="utf-8"))
    if (typed.get("contract") != "RT031_HUB_SPLIT_TYPED_ONE_LINE_V3"
            or typed.get("network_selected") is not False
            or typed.get("timetable_assigned") is not False):
        raise ValueError("typed hub-split contract drift")
    names = list(typed["directional_patterns"])
    stop_sets = [typed["directional_patterns"][name]["available_stop_ids"]
                 for name in names]
    current = json.loads(CURRENT_PATH.read_text(encoding="utf-8"))
    current_stops = current["current_exact_identity_subset"]["mapped_stop_place_ids"]
    raw = pd.read_csv(walk_matrix, dtype={"population_weight_2025": str})
    weight_map = (raw[["population_unit_id", "population_weight_2025"]]
                  .drop_duplicates().set_index("population_unit_id")
                  ["population_weight_2025"].to_dict())
    substrate = validate_walk_matrix(raw)
    weights = [weight_map[value] for value in
               substrate.population_meta["population_unit_id"]]
    codes, totals, municipal = detailed_threshold_vectors(
        stop_sets + [current_stops], substrate, weights)
    rows = {}
    for i, name in enumerate(names):
        retained = sorted(set(stop_sets[i]) & set(current_stops))
        rows[name] = {
            "candidate_line_id": typed["directional_patterns"][name]["candidate_line_id"],
            "distance_m": typed["directional_patterns"][name]["distance_m"],
            "retained_current_exact_stop_ids": retained,
            "retained_current_exact_stop_count": len(retained),
            "total_potential_walking_access": {
                str(t): str(totals[i, j]) for j, t in enumerate(THRESHOLDS)},
            "municipal_potential_walking_access": {
                code: {"municipality": MUNICIPALITY_NAMES[code],
                       "threshold_ratios": {str(t): str(municipal[i, k, j])
                                            for j, t in enumerate(THRESHOLDS)}}
                for k, code in enumerate(codes)},
        }
    baseline_index = len(names)
    payload = {
        "contract": "RT031_HUB_SPLIT_EXACT_WALK_ACCESS_V3",
        "status": "PASS_TYPED_SUBSTRATE_SCOPED_NON_DECISIONAL_ACCESS",
        "input_sha256": {
            "typed_hub_split": TYPED_SHA256,
            "walking_substrate": WALK_SHA256,
            "current_exact_identity_subset": CURRENT_SHA256,
        },
        "directional_patterns": rows,
        "current_exact_identity_subset": {
            "stop_count": len(current_stops),
            "total_potential_walking_access": {
                str(t): str(totals[baseline_index, j])
                for j, t in enumerate(THRESHOLDS)},
        },
        "coverage_is_potential_walking_not_observed_demand": True,
        "directional_timetable_or_travel_time_included": False,
        "candidate_domain_complete": False,
        "decision_budget_km": None,
        "uncertainty_band_min": None,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical(payload))
    print(json.dumps({name: {
        "total_10min_percent": round(float(Fraction(row["total_potential_walking_access"]["10"])) * 100, 2),
        "retained_exact": row["retained_current_exact_stop_count"],
    } for name, row in rows.items()}, sort_keys=True))
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--typed", type=Path, required=True)
    parser.add_argument("--walk-matrix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.typed, args.walk_matrix, args.output)
