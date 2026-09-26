#!/usr/bin/env python3
"""Describe, without filtering, current-service tradeoffs on the RT031 frontier."""
from __future__ import annotations

import argparse
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
from pathlib import Path


FRONTIER_SHA256 = "0757d9513e21e1e68a7fc43c1732b45c4ccd83242e84d20ea8a324d0866bca26"
BRIVIO = "97010"
THRESHOLDS = ("5", "8", "10")


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def percentage(value):
    return str(Decimal(value.numerator) * 100 / Decimal(value.denominator))


def classify(row, baseline):
    total = [Fraction(row["exact_total_coverage"][key]) for key in THRESHOLDS]
    current_total = [Fraction(baseline["exact_total_coverage"][key])
                     for key in THRESHOLDS]
    brivio = [Fraction(row["exact_municipality_coverage"][BRIVIO][key])
              for key in THRESHOLDS]
    current_brivio = [Fraction(baseline["exact_municipality_coverage"][BRIVIO][key])
                      for key in THRESHOLDS]
    total_all_nonregressing = all(left >= right for left, right in zip(
        total, current_total))
    return {
        "total_all_three_nonregressing": total_all_nonregressing,
        "total_all_three_nonregressing_with_some_strict_gain":
            total_all_nonregressing and any(left > right for left, right in zip(
                total, current_total)),
        "brivio_all_three_nonregressing": all(left >= right for left, right in zip(
            brivio, current_brivio)),
        "total_10min_strict_gain": total[-1] > current_total[-1],
        "brivio_10min_nonregressing": brivio[-1] >= current_brivio[-1],
    }


def build_audit(source):
    if (source.get("contract") != "RT031_SINGLE_LINE_MUNICIPAL_ACCESS_FRONTIER_V4"
            or source.get("status")
            != "PASS_POOL_SCOPED_NON_DECISIONAL_MUNICIPAL_FRONTIER"
            or source.get("frontier_count") != 778
            or source.get("municipality_non_regression_is_hard_filter") is not False
            or source.get("network_selected") is not False):
        raise ValueError("municipal frontier contract drift")
    cap = Decimal(source["reference_resource_context"]["annual_bus_km_cap"])
    rows = sorted((row for row in source["frontier"] if Decimal(
        row["conditional_annual_bus_km_at_20_daily_cycles"]) <= cap),
        key=lambda row: row["candidate_line_id"])
    if len(rows) != 736 or len({row["candidate_line_id"] for row in rows}) != 736:
        raise ValueError("within-cap candidate domain drift")
    baseline = source["current_exact_identity_baseline"]
    classified = [(row, classify(row, baseline)) for row in rows]
    by_retention = []
    for retained in sorted({row["retained_current_exact_stop_count"]
                            for row in rows}):
        group = [(row, flags) for row, flags in classified
                 if row["retained_current_exact_stop_count"] == retained]
        both_all = [row["candidate_line_id"] for row, flags in group
                    if flags["total_all_three_nonregressing_with_some_strict_gain"]
                    and flags["brivio_all_three_nonregressing"]]
        both_ten = [row["candidate_line_id"] for row, flags in group
                    if flags["total_10min_strict_gain"]
                    and flags["brivio_10min_nonregressing"]]
        by_retention.append({
            "retained_current_exact_stop_count": retained,
            "candidate_count": len(group),
            "total_all_three_nonregressing_with_some_strict_gain_count": sum(
                flags["total_all_three_nonregressing_with_some_strict_gain"]
                for _, flags in group),
            "brivio_all_three_nonregressing_count": sum(
                flags["brivio_all_three_nonregressing"] for _, flags in group),
            "both_all_three_count": len(both_all),
            "both_all_three_candidate_line_ids": both_all,
            "total_10min_strict_gain_count": sum(
                flags["total_10min_strict_gain"] for _, flags in group),
            "brivio_10min_nonregressing_count": sum(
                flags["brivio_10min_nonregressing"] for _, flags in group),
            "both_10min_count": len(both_ten),
            "both_10min_candidate_line_ids": both_ten,
            "separate_max_total_10min_percent": percentage(max(Fraction(
                row["exact_total_coverage"]["10"]) for row, _ in group)),
            "separate_max_brivio_10min_percent": percentage(max(Fraction(
                row["exact_municipality_coverage"][BRIVIO]["10"])
                for row, _ in group)),
        })
    both_rows = [row for row, flags in classified
                 if flags["total_all_three_nonregressing_with_some_strict_gain"]
                 and flags["brivio_all_three_nonregressing"]]
    per_municipality_within_both = {}
    for code in source["municipality_codes"]:
        current = [Fraction(baseline["exact_municipality_coverage"][code][key])
                   for key in THRESHOLDS]
        per_municipality_within_both[code] = {
            "municipality_name": source["municipality_names"][code],
            "all_three_nonregressing_count": sum(
                all(Fraction(row["exact_municipality_coverage"][code][key])
                    >= current[index]
                    for index, key in enumerate(THRESHOLDS))
                for row in both_rows),
            "10min_candidate_share_range_percent": [
                percentage(min(Fraction(row["exact_municipality_coverage"]
                                        [code]["10"]) for row in both_rows)),
                percentage(max(Fraction(row["exact_municipality_coverage"]
                                        [code]["10"]) for row in both_rows)),
            ] if both_rows else None,
            "10min_current_share_percent": percentage(current[-1]),
        }
    return {
        "contract": "RT031_MUNICIPAL_TRADEOFF_ANATOMY_V4",
        "status": "PASS_DESCRIPTIVE_NO_CANDIDATE_FILTER",
        "candidate_count": len(rows),
        "comparison_baseline": "CURRENT_EXACT_IDENTITY_STRUCTURAL_SUBSET_SAME_WALKING_SUBSTRATE",
        "brivio_municipality_code": BRIVIO,
        "threshold_minutes": [5, 8, 10],
        "strict_total_gain_requires_all_three_nonregressing": True,
        "brivio_nonregression_is_hard_filter": False,
        "total_nonregression_is_hard_filter": False,
        "retention_is_hard_filter": False,
        "separate_maxima_are_same_candidate_guarantee": False,
        "municipal_od_spatially_downscaled": False,
        "demand_weighted_gjt_computed": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "input_sha256": {"municipal_frontier": FRONTIER_SHA256},
        "by_retained_current_exact_stop_count": by_retention,
        "total_and_brivio_all_three_joint_count": len(both_rows),
        "total_and_brivio_all_three_joint_candidate_line_ids": [
            row["candidate_line_id"] for row in both_rows],
        "per_municipality_within_total_and_brivio_joint":
            per_municipality_within_both,
    }


def main(args):
    if hashlib.sha256(args.frontier.read_bytes()).hexdigest() != FRONTIER_SHA256:
        raise ValueError("pinned municipal frontier drift")
    result = build_audit(json.loads(args.frontier.read_text(encoding="utf-8")))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "municipal_tradeoff_anatomy_v4.json").write_bytes(
        canonical(result))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontier", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    main(parser.parse_args())
