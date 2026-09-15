#!/usr/bin/env python3
"""Build an exact municipal-axis frontier from the certified one-line pool."""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from phase2_rt029_v4_substrate import validate_walk_matrix
from src.phase2_rt031_municipal_access_frontier_v4 import (
    exact_pareto_indices,
    objective_dimensions,
)


CANDIDATE_SHA256 = "69b847a22b60aeb50f65d7f56c7950e33a98a83a5275ce1a672a187a5a6b965b"
WALK_SHA256 = "a47bbce413d056db185180173ab2f05dce0463cb626a2c81f4aff64de91b50c1"
CURRENT_STOP_COUNT = 11
ANNUAL_SERVICE_DAYS = 260
REFERENCE_DAILY_CYCLES = 20
MUNICIPALITY_NAMES = {
    "97010": "Brivio",
    "97012": "Calco",
    "97058": "Olgiate Molgora",
    "97074": "Santa Maria Hoe",
    "97092": "La Valletta Brianza",
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def logical_sha256(path):
    return hashlib.sha256(
        Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def canonical(payload):
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def detailed_threshold_vectors(stop_sets, substrate, exact_weights):
    meta = substrate.population_meta
    core = meta["population_scope"].astype(str).to_numpy() == "core"
    codes = meta["population_municipality_code"].astype(str).to_numpy()[core]
    municipality_codes = tuple(sorted(set(codes)))
    if tuple(MUNICIPALITY_NAMES) != municipality_codes:
        raise ValueError("core municipality universe changed")
    decimals = [Decimal(str(value)) for value, use in zip(exact_weights, core) if use]
    scale = max(0, max(-value.as_tuple().exponent for value in decimals))
    integers = [int(value * (10 ** scale)) for value in decimals]
    if any(value < 0 for value in integers) or sum(integers) <= 0:
        raise ValueError("invalid exact population weights")
    matrix = substrate.walk_time_matrix[core]
    if not 0 < len(substrate.stop_index) <= 63:
        raise ValueError("stop mask domain exceeds exact uint64 representation")
    bits = np.left_shift(
        np.uint64(1), np.arange(len(substrate.stop_index), dtype=np.uint64))
    masks = np.array([
        sum(int(bits[substrate.stop_index[stop]]) for stop in stops)
        for stops in stop_sets
    ], dtype=np.uint64)
    base = 10 ** 9
    limb_count = max(1, (max(integers).bit_length() + 28) // 29)
    limbs = [np.array([
        (value // (base ** limb)) % base for value in integers
    ], dtype=np.int64) for limb in range(limb_count)]
    if len(integers) * (base - 1) > np.iinfo(np.int64).max:
        raise ValueError("unsafe exact population accumulation")

    groups = [codes == code for code in municipality_codes]
    totals = [sum(value for value, use in zip(integers, group) if use)
              for group in groups]
    total_population = sum(integers)
    all_group = np.ones(len(integers), dtype=bool)

    def mass(inside, group):
        result = np.zeros(inside.shape[1], dtype=object)
        for limb, values in enumerate(limbs):
            result += (np.sum(inside[group] * values[group, None], axis=0,
                              dtype=np.int64).astype(object) * (base ** limb))
        return result

    totals_out = np.empty((len(stop_sets), 3), dtype=object)
    municipal_out = np.empty(
        (len(stop_sets), len(municipality_codes), 3), dtype=object)
    for threshold_index, threshold in enumerate((5, 8, 10)):
        population_masks = np.sum(
            np.where(matrix <= threshold, bits, np.uint64(0)),
            axis=1, dtype=np.uint64)
        for start in range(0, len(masks), 256):
            end = min(start + 256, len(masks))
            inside = ((population_masks[:, None] & masks[None, start:end]) != 0)
            totals_out[start:end, threshold_index] = [
                Fraction(value, total_population)
                for value in mass(inside, all_group)
            ]
            for group_index, (group, total) in enumerate(zip(groups, totals)):
                municipal_out[start:end, group_index, threshold_index] = [
                    Fraction(value, total) for value in mass(inside, group)
                ]
    return municipality_codes, totals_out, municipal_out


def main(args):
    if sha256(args.candidates) != CANDIDATE_SHA256:
        raise ValueError("pinned one-line candidate pool drift")
    if sha256(args.walk_matrix) != WALK_SHA256:
        raise ValueError("pinned walking substrate drift")
    with gzip.open(args.candidates, "rt", encoding="utf-8", newline="") as handle:
        candidates = list(csv.DictReader(handle))
    if len(candidates) != 3663:
        raise ValueError("one-line candidate universe changed")
    stop_sets = [tuple(json.loads(row["available_stop_ids"])) for row in candidates]
    if any("FROZEN::L00407" not in stops for stops in stop_sets):
        raise ValueError("candidate without required Olgiate FS stop")

    raw_walk = pd.read_csv(args.walk_matrix,
                           dtype={"population_weight_2025": str})
    weight_map = (raw_walk[["population_unit_id", "population_weight_2025"]]
                  .drop_duplicates().set_index("population_unit_id")
                  ["population_weight_2025"].to_dict())
    substrate = validate_walk_matrix(raw_walk)
    exact_weights = [weight_map[value] for value in
                     substrate.population_meta["population_unit_id"]]
    codes, totals, municipal = detailed_threshold_vectors(
        stop_sets, substrate, exact_weights)

    current = json.loads(args.current_audit.read_text(encoding="utf-8"))
    current_stops = tuple(current["current_exact_identity_subset"]
                          ["mapped_stop_place_ids"])
    if len(current_stops) != CURRENT_STOP_COUNT:
        raise ValueError("current exact stop universe changed")
    _, current_totals, current_municipal = detailed_threshold_vectors(
        (current_stops,), substrate, exact_weights)

    retention = [len(set(stops).intersection(current_stops)) for stops in stop_sets]
    benefits = [
        tuple(totals[index])
        + tuple(municipal[index].reshape(-1))
        + (Fraction(retention[index], CURRENT_STOP_COUNT),)
        for index in range(len(candidates))
    ]
    costs = [Decimal(row["total_distance_m"]) for row in candidates]
    frontier_indices = exact_pareto_indices(benefits, costs)

    frontier = []
    for index in frontier_indices:
        row = candidates[index]
        municipal_values = {
            code: {
                str(threshold): str(municipal[index, code_index, threshold_index])
                for threshold_index, threshold in enumerate((5, 8, 10))
            }
            for code_index, code in enumerate(codes)
        }
        frontier.append({
            "candidate_line_id": row["candidate_line_id"],
            "total_distance_m": row["total_distance_m"],
            "conditional_annual_bus_km_at_20_daily_cycles": str(
                costs[index] * REFERENCE_DAILY_CYCLES
                * ANNUAL_SERVICE_DAYS / Decimal(1000)),
            "available_stop_ids": list(stop_sets[index]),
            "realization_ids": json.loads(row["realization_ids"]),
            "discovery_lanes": json.loads(row["discovery_lanes"]),
            "retained_current_exact_stop_count": retention[index],
            "retained_current_exact_stop_ids": json.loads(
                row["retained_current_exact_stop_ids"]),
            "exact_total_coverage": {
                str(threshold): str(totals[index, threshold_index])
                for threshold_index, threshold in enumerate((5, 8, 10))
            },
            "exact_municipality_coverage": municipal_values,
        })
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    cap = Decimal(str(policy["human_policy_decisions"]["annual_bus_km_cap"]))
    within_reference = [
        row for row in frontier
        if Decimal(row["conditional_annual_bus_km_at_20_daily_cycles"]) <= cap
    ]
    current_baseline = {
        "exact_total_coverage": {
            str(threshold): str(current_totals[0, threshold_index])
            for threshold_index, threshold in enumerate((5, 8, 10))
        },
        "exact_municipality_coverage": {
            code: {
                str(threshold): str(current_municipal[0, code_index, threshold_index])
                for threshold_index, threshold in enumerate((5, 8, 10))
            }
            for code_index, code in enumerate(codes)
        },
    }
    non_regression_count = sum(
        all(Fraction(row["exact_total_coverage"][str(threshold)])
            >= current_totals[0, threshold_index]
            for threshold_index, threshold in enumerate((5, 8, 10)))
        and all(
            Fraction(row["exact_municipality_coverage"][code][str(threshold)])
            >= current_municipal[0, code_index, threshold_index]
            for code_index, code in enumerate(codes)
            for threshold_index, threshold in enumerate((5, 8, 10))
        )
        for row in within_reference
    )
    retention_distribution = {
        str(value): sum(
            row["retained_current_exact_stop_count"] == value
            for row in within_reference)
        for value in sorted({
            row["retained_current_exact_stop_count"] for row in within_reference})
    }
    output = {
        "contract": "RT031_SINGLE_LINE_MUNICIPAL_ACCESS_FRONTIER_V4",
        "status": "PASS_POOL_SCOPED_NON_DECISIONAL_MUNICIPAL_FRONTIER",
        "candidate_count": len(candidates),
        "frontier_count": len(frontier),
        "frontier": frontier,
        "municipality_codes": list(codes),
        "municipality_names": MUNICIPALITY_NAMES,
        "current_exact_identity_baseline": current_baseline,
        "pareto_dimensions": list(objective_dimensions(codes)),
        "current_stop_retention_is_pareto_preference": True,
        "municipality_coverage_axes_are_separate_pareto_preferences": True,
        "municipality_non_regression_is_hard_filter": False,
        "weighted_score": False,
        "reference_resource_context": {
            "annual_bus_km_cap": str(cap),
            "daily_cycles": REFERENCE_DAILY_CYCLES,
            "annual_service_days_design_assumption": ANNUAL_SERVICE_DAYS,
            "frontier_within_cap_count": len(within_reference),
            "frontier_within_cap_retention_distribution": retention_distribution,
            "componentwise_non_regression_all_total_and_municipal_axes_count":
                non_regression_count,
            "componentwise_non_regression_used_as_filter": False,
            "maximum_retained_current_exact_stop_count_within_cap": max(
                (row["retained_current_exact_stop_count"]
                 for row in within_reference), default=None),
            "service_pattern_selected": False,
        },
        "popular_times_used_as_weight": False,
        "popular_times_used_as_demand": False,
        "upstream_candidate_domain_complete": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "input_sha256": {
            "candidates": CANDIDATE_SHA256,
            "walk_matrix": WALK_SHA256,
            "current_audit": logical_sha256(args.current_audit),
            "policy": logical_sha256(args.policy),
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result = args.output_dir / "rt031_municipal_access_frontier_v4.json"
    result.write_bytes(canonical(output))
    audit = {key: value for key, value in output.items() if key != "frontier"}
    audit["result_sha256"] = sha256(result)
    (args.output_dir / "rt031_municipal_access_frontier_v4_audit.json").write_bytes(
        canonical(audit))
    print(json.dumps(audit, sort_keys=True))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--walk-matrix", type=Path, required=True)
    parser.add_argument("--current-audit", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    main(parser.parse_args())
