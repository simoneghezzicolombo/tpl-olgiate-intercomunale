#!/usr/bin/env python3
"""Build a stronger but still incomplete current-service access lower bound V3."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from scripts.phase2_run_access_equity_v2 import load_population_units, sha256_path
from src.phase2_access_equity_v2 import summarise_walk_coverage_thresholds
from src.phase2_current_service_baseline_v3 import make_v2_stops, localize_identity_rows_v3

ROUTE_SCOPE = ("D184", "D185")
THRESHOLDS = (5, 8, 10)
STATUS = "PASS_CURRENT_SERVICE_ACCESS_LOWER_BOUND_V3"
CONTRACT = "PHASE2_CURRENT_SERVICE_CERTIFIED_LOCALIZABLE_ACCESS_LOWER_BOUND_V3"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_existing_walks(path: Path, *, unit_weights: dict[str, float]) -> dict[str, dict[str, float]]:
    walks: dict[str, dict[str, float]] = {}
    for line_no, row in enumerate(read_csv(path), start=2):
        cluster = str(row.get("physical_cluster_id", "")).strip()
        unit_id = str(row.get("population_unit_id", "")).strip()
        if not cluster or not unit_id:
            raise ValueError(f"Missing catchment identity at line {line_no}")
        if unit_id not in unit_weights:
            raise ValueError(f"Unknown population unit {unit_id!r} at line {line_no}")
        walk_min = float(row["walk_min_to_stop"])
        if walk_min < 0 or walk_min > 12.0 + 1e-9:
            raise ValueError(f"Invalid certified existing-stop walk time at line {line_no}")
        row_weight = float(row["building_piece_population_model"])
        if abs(row_weight - unit_weights[unit_id]) > 1e-9:
            raise ValueError(f"Population mismatch for {unit_id!r} at line {line_no}")
        previous = walks.setdefault(cluster, {}).get(unit_id)
        if previous is None or walk_min < previous:
            walks[cluster][unit_id] = walk_min
    return walks


def summary_payload(summary, *, municipality_codes: dict[str, str]) -> dict:
    return {
        "covered_population": summary.covered_population,
        "coverage_share": summary.coverage_share,
        "worst_municipality": summary.worst_municipality,
        "worst_municipality_coverage_share": summary.worst_municipality_coverage_share,
        "municipality_coverage": {
            municipality_codes[name]: {
                "municipality": name,
                "coverage_share": summary.municipality_coverage_share[name],
            }
            for name in sorted(summary.municipality_coverage_share)
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--identity-validation", type=Path, required=True)
    parser.add_argument("--v2-official-stops", type=Path, required=True)
    parser.add_argument("--existing-catchments", type=Path, required=True)
    parser.add_argument("--population-units", type=Path, required=True)
    parser.add_argument("--baseline-v2-validation", type=Path, required=True)
    parser.add_argument("--localized-output", type=Path, required=True)
    parser.add_argument("--validation-output", type=Path, required=True)
    args = parser.parse_args()

    for path in (
        args.identity,
        args.identity_validation,
        args.v2_official_stops,
        args.existing_catchments,
        args.population_units,
        args.baseline_v2_validation,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    identity_validation = read_json(args.identity_validation)
    if identity_validation.get("status") != "PASS":
        raise ValueError("Current-service identity crosscheck is not PASS")
    matching_contract = identity_validation.get("matching_contract", {})
    if matching_contract.get("ambiguous_identity_policy") != "UNRESOLVED_FAIL_OPEN_FOR_DATA_PRESERVATION_BUT_FORBIDDEN_FOR_WALKING_GJT_JOIN":
        raise ValueError("Upstream current-service identity no longer fail-closes ambiguity")

    baseline_v2 = read_json(args.baseline_v2_validation)
    if baseline_v2.get("status") != "PASS_CURRENT_SERVICE_ACCESS_LOWER_BOUND_V2":
        raise ValueError("Expected certified V2 current-service lower bound")
    if baseline_v2.get("baseline_complete") is not False:
        raise ValueError("V2 baseline completeness semantics changed unexpectedly")

    identity_rows = read_csv(args.identity)
    v2_stop_rows = read_csv(args.v2_official_stops)
    localized = localize_identity_rows_v3(identity_rows, v2_stops=make_v2_stops(v2_stop_rows))
    if len(localized) != 51:
        raise ValueError(f"Expected exactly 51 D184/D185 PDF rows, got {len(localized)}")

    unit_weights, unit_municipality, municipality_totals, municipality_codes = load_population_units(args.population_units)
    walks = load_existing_walks(args.existing_catchments, unit_weights=unit_weights)
    localized_clusters = sorted({row["v2_physical_cluster_id"] for row in localized if row["v2_physical_cluster_id"]})
    if not localized_clusters:
        raise ValueError("No D184/D185 stop localized")
    missing_catchments = [cluster for cluster in localized_clusters if cluster not in walks]
    if missing_catchments:
        raise ValueError(f"Localized current clusters lack certified catchments: {missing_catchments}")

    summaries = summarise_walk_coverage_thresholds(
        frozenset(localized_clusters),
        walk_by_anchor=walks,
        unit_weights=unit_weights,
        unit_municipality=unit_municipality,
        municipality_totals=municipality_totals,
        thresholds=THRESHOLDS,
    )

    args.localized_output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "route_id",
        "source_page",
        "stop_sequence_on_page",
        "stop_label_pdf",
        "identity_status",
        "historical_gtfs_stop_id",
        "v2_physical_cluster_id",
        "localization_status",
        "v2_bridge_stop_ids",
        "v2_bridge_stop_names",
    ]
    with args.localized_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(localized)

    route_stats: dict[str, dict[str, object]] = {}
    for route_id in ROUTE_SCOPE:
        rows = [row for row in localized if row["route_id"] == route_id]
        route_stats[route_id] = {
            "pdf_stop_rows": len(rows),
            "localized_rows": sum(bool(row["v2_physical_cluster_id"]) for row in rows),
            "localized_unique_clusters": sorted({row["v2_physical_cluster_id"] for row in rows if row["v2_physical_cluster_id"]}),
            "v3_bridge_rows": sum(row["localization_status"] == "LOCALIZED_V2_ROUTE_NAME_SUBSET_UNIQUE_PHYSICAL_CLUSTER" for row in rows),
        }

    localized_rows = sum(bool(row["v2_physical_cluster_id"]) for row in localized)
    bridge_rows = [row for row in localized if row["localization_status"] == "LOCALIZED_V2_ROUTE_NAME_SUBSET_UNIQUE_PHYSICAL_CLUSTER"]
    unresolved_rows = len(localized) - localized_rows

    # V3 must be monotonic relative to the certified lower-bound baseline. It may
    # strengthen the lower bound, never weaken it or claim completeness.
    if localized_rows < int(baseline_v2["localized_rows"]):
        raise ValueError("V3 localized fewer rows than certified V2 lower bound")
    for threshold in THRESHOLDS:
        if summaries[threshold].coverage_share + 1e-12 < float(baseline_v2["coverage_lower_bound"][str(threshold)]["coverage_share"]):
            raise ValueError(f"V3 coverage regressed below V2 at {threshold} minutes")

    payload = {
        "status": STATUS,
        "contract": CONTRACT,
        "route_scope": list(ROUTE_SCOPE),
        "baseline_role": "CERTIFIED_LOCALIZABLE_LOWER_BOUND_ONLY",
        "baseline_complete": False,
        "may_infer_true_current_total_coverage": False,
        "may_use_ambiguous_rows_for_spatial_access": False,
        "target_pdf_stop_rows": len(localized),
        "localized_rows": localized_rows,
        "localized_unique_physical_cluster_count": len(localized_clusters),
        "localized_unique_physical_clusters": localized_clusters,
        "v3_new_bridge_rows": len(bridge_rows),
        "v3_new_bridge_pdf_rows": [
            {
                "route_id": row["route_id"],
                "source_page": row["source_page"],
                "stop_sequence_on_page": row["stop_sequence_on_page"],
                "stop_label_pdf": row["stop_label_pdf"],
                "cluster": row["v2_physical_cluster_id"],
                "evidence_stop_ids": row["v2_bridge_stop_ids"],
                "evidence_stop_names": row["v2_bridge_stop_names"],
            }
            for row in bridge_rows
        ],
        "unresolved_or_unlocalized_rows": unresolved_rows,
        "route_stats": route_stats,
        "located_population_denominator": sum(unit_weights.values()),
        "population_unit_count": len(unit_weights),
        "coverage_lower_bound": {
            str(threshold): summary_payload(summaries[threshold], municipality_codes=municipality_codes)
            for threshold in THRESHOLDS
        },
        "v2_comparison": {
            "localized_rows_v2": baseline_v2["localized_rows"],
            "unresolved_or_unlocalized_rows_v2": baseline_v2["unresolved_or_unlocalized_rows"],
            "coverage_share_v2": {
                str(threshold): baseline_v2["coverage_lower_bound"][str(threshold)]["coverage_share"]
                for threshold in THRESHOLDS
            },
            "coverage_share_v3": {
                str(threshold): summaries[threshold].coverage_share
                for threshold in THRESHOLDS
            },
        },
        "matching_contract": {
            "current_service_activation_source": "OFFICIAL_OPERATOR_PDF_ONLY",
            "v2_gtfs_role": "VALIDITY_BOUNDED_OFFICIAL_IDENTITY_COORDINATE_CROSSCHECK_ONLY",
            "historically_ambiguous_rows_overridden": False,
            "historical_no_name_match_rows_may_use_v2_bridge": True,
            "same_route_required": True,
            "minimum_official_name_token_count": 3,
            "official_name_tokens_must_be_contained_in_pdf_label": True,
            "all_compatible_v2_records_must_share_one_physical_cluster": True,
            "edit_distance_fuzzy_matching_used": False,
            "coordinate_nearest_matching_used": False,
            "coordinate_distance_tolerance_used": False,
            "manual_alias_map_used": False,
            "route_specific_stop_whitelist_used": False,
        },
        "non_regression_safeguard_semantics": "CANDIDATE_MAY_BE_REJECTED_ONLY_FOR_REGRESSION_BELOW_PROVEN_LOCALIZABLE_CURRENT_LOWER_BOUND; UNRESOLVED_CURRENT_STOPS_CANNOT_PROMOTE_OR_REJECT",
        "lineage": {
            "identity_sha256": sha256_path(args.identity),
            "identity_validation_sha256": sha256_path(args.identity_validation),
            "v2_official_stops_sha256": sha256_path(args.v2_official_stops),
            "existing_catchments_sha256": sha256_path(args.existing_catchments),
            "population_units_sha256": sha256_path(args.population_units),
            "baseline_v2_validation_sha256": sha256_path(args.baseline_v2_validation),
            "localized_output_sha256": sha256_path(args.localized_output),
        },
        "limitations": [
            "The official current PDF establishes current D184/D185 service rows but not complete spatial identities.",
            "Stop Universe V2 is used only as a validity-bounded official identity/coordinate cross-check and never as proof of 2026 service activation.",
            "Rows already demonstrated ambiguous by historical official GTFS remain unresolved even if a tempting V2 name match exists.",
            "V2 bridging is permitted only for historical NO_HISTORICAL_GTFS_NAME_MATCH rows under the declared same-route, >=3-token, single-cluster rule.",
            "Coverage remains a proven lower bound, not the complete current-service pedestrian-access baseline.",
        ],
    }
    args.validation_output.parent.mkdir(parents=True, exist_ok=True)
    args.validation_output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
