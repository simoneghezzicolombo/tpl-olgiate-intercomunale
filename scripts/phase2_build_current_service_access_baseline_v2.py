#!/usr/bin/env python3
"""Build an apples-to-apples, explicitly incomplete current-service access baseline.

Only D184/D185 PDF stop rows whose historical official GTFS identity was already
resolved conservatively may be localized. They are re-joined by exact stop_id to
Stop Universe V2 and evaluated against the same V2 building-piece population and
walking catchments used by candidate Access Equity V2.

The result is a certified lower bound, never an estimate of complete current
coverage. Unresolved stop rows cannot promote or reject a candidate.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from scripts.phase2_run_access_equity_v2 import load_population_units, sha256_path
from src.phase2_access_equity_v2 import summarise_walk_coverage_thresholds

ROUTE_SCOPE = ("D184", "D185")
THRESHOLDS = (5, 8, 10)
STATUS = "PASS_CURRENT_SERVICE_ACCESS_LOWER_BOUND_V2"
CONTRACT = "PHASE2_CURRENT_SERVICE_CERTIFIED_LOCALIZABLE_ACCESS_LOWER_BOUND_V2"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_v2_stop_clusters(path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for line_no, row in enumerate(read_csv(path), start=2):
        stop_id = str(row.get("stop_id", "")).strip()
        cluster = str(row.get("physical_cluster_id", "")).strip()
        if not stop_id or not cluster:
            raise ValueError(f"Missing V2 stop identity at line {line_no}")
        previous = mapping.get(stop_id)
        if previous is not None and previous != cluster:
            raise ValueError(f"V2 stop {stop_id!r} maps to multiple physical clusters")
        mapping[stop_id] = cluster
    if not mapping:
        raise ValueError("V2 official-stop table is empty")
    return mapping


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


def localize_current_rows(identity_rows: list[dict[str, str]], *, v2_stop_clusters: dict[str, str]) -> list[dict[str, str]]:
    localized: list[dict[str, str]] = []
    for row in identity_rows:
        route_id = str(row.get("route_id", "")).strip()
        if route_id not in ROUTE_SCOPE:
            continue
        identity_status = str(row.get("identity_status", "")).strip()
        resolved_stop_id = str(row.get("historical_gtfs_stop_id", "")).strip()
        if identity_status.startswith("RESOLVED_") and resolved_stop_id:
            cluster = v2_stop_clusters.get(resolved_stop_id, "")
            localization_status = "LOCALIZED_EXACT_RESOLVED_GTFS_ID_TO_V2_CLUSTER" if cluster else "RESOLVED_GTFS_ID_NOT_IN_V2_STOP_UNIVERSE"
        else:
            cluster = ""
            localization_status = "UNRESOLVED_IDENTITY_NOT_SPATIALLY_USED"
        localized.append({
            "route_id": route_id,
            "source_page": str(row.get("source_page", "")),
            "stop_sequence_on_page": str(row.get("stop_sequence_on_page", "")),
            "stop_label_pdf": str(row.get("stop_label_pdf", "")),
            "identity_status": identity_status,
            "historical_gtfs_stop_id": resolved_stop_id,
            "v2_physical_cluster_id": cluster,
            "localization_status": localization_status,
        })
    return localized


def _summary_payload(summary, *, municipality_codes: dict[str, str]) -> dict:
    by_code = {
        municipality_codes[name]: {
            "municipality": name,
            "coverage_share": summary.municipality_coverage_share[name],
        }
        for name in sorted(summary.municipality_coverage_share)
    }
    return {
        "covered_population": summary.covered_population,
        "coverage_share": summary.coverage_share,
        "worst_municipality": summary.worst_municipality,
        "worst_municipality_coverage_share": summary.worst_municipality_coverage_share,
        "municipality_coverage": by_code,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--identity-validation", type=Path, required=True)
    parser.add_argument("--v2-official-stops", type=Path, required=True)
    parser.add_argument("--existing-catchments", type=Path, required=True)
    parser.add_argument("--population-units", type=Path, required=True)
    parser.add_argument("--localized-output", type=Path, required=True)
    parser.add_argument("--validation-output", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.identity, args.identity_validation, args.v2_official_stops, args.existing_catchments, args.population_units):
        if not path.is_file():
            raise FileNotFoundError(path)

    identity_validation = read_json(args.identity_validation)
    if identity_validation.get("status") != "PASS":
        raise ValueError("Current-service stop-identity crosscheck is not PASS")
    matching_contract = identity_validation.get("matching_contract", {})
    if matching_contract.get("ambiguous_identity_policy") != "UNRESOLVED_FAIL_OPEN_FOR_DATA_PRESERVATION_BUT_FORBIDDEN_FOR_WALKING_GJT_JOIN":
        raise ValueError("Current-service identity contract no longer forbids ambiguous walking joins")
    gjt_contract = identity_validation.get("gjt_contract", {})
    if gjt_contract.get("ambiguous_or_unresolved_rows_may_not_be_used_as_spatial_stop_identity") is not True:
        raise ValueError("Current-service identity GJT contract no longer fail-closes unresolved rows")

    identity_rows = read_csv(args.identity)
    v2_stop_clusters = load_v2_stop_clusters(args.v2_official_stops)
    localized = localize_current_rows(identity_rows, v2_stop_clusters=v2_stop_clusters)
    if not localized:
        raise ValueError("No D184/D185 PDF stop rows found")

    unit_weights, unit_municipality, municipality_totals, municipality_codes = load_population_units(args.population_units)
    walks = load_existing_walks(args.existing_catchments, unit_weights=unit_weights)
    localized_clusters = sorted({row["v2_physical_cluster_id"] for row in localized if row["v2_physical_cluster_id"]})
    if not localized_clusters:
        raise ValueError("No D184/D185 current stop could be localized to Stop Universe V2")
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
        "route_id", "source_page", "stop_sequence_on_page", "stop_label_pdf", "identity_status",
        "historical_gtfs_stop_id", "v2_physical_cluster_id", "localization_status",
    ]
    with args.localized_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(localized)

    route_stats = {}
    for route_id in ROUTE_SCOPE:
        route_rows = [row for row in localized if row["route_id"] == route_id]
        route_stats[route_id] = {
            "pdf_stop_rows": len(route_rows),
            "resolved_historical_identity_rows": sum(row["identity_status"].startswith("RESOLVED_") and bool(row["historical_gtfs_stop_id"]) for row in route_rows),
            "localized_rows": sum(bool(row["v2_physical_cluster_id"]) for row in route_rows),
            "localized_unique_clusters": sorted({row["v2_physical_cluster_id"] for row in route_rows if row["v2_physical_cluster_id"]}),
        }

    payload = {
        "status": STATUS,
        "contract": CONTRACT,
        "route_scope": list(ROUTE_SCOPE),
        "baseline_role": "CERTIFIED_LOCALIZABLE_LOWER_BOUND_ONLY",
        "baseline_complete": False,
        "may_infer_true_current_total_coverage": False,
        "may_use_unresolved_rows_for_spatial_access": False,
        "non_regression_safeguard_semantics": "CANDIDATE_MAY_BE_REJECTED_ONLY_FOR_REGRESSION_BELOW_PROVEN_LOCALIZABLE_CURRENT_LOWER_BOUND; UNRESOLVED_CURRENT_STOPS_CANNOT_PROMOTE_OR_REJECT",
        "target_pdf_stop_rows": len(localized),
        "resolved_historical_identity_rows": sum(row["identity_status"].startswith("RESOLVED_") and bool(row["historical_gtfs_stop_id"]) for row in localized),
        "localized_rows": sum(bool(row["v2_physical_cluster_id"]) for row in localized),
        "localized_unique_physical_cluster_count": len(localized_clusters),
        "localized_unique_physical_clusters": localized_clusters,
        "unresolved_or_unlocalized_rows": sum(not bool(row["v2_physical_cluster_id"]) for row in localized),
        "route_stats": route_stats,
        "located_population_denominator": sum(unit_weights.values()),
        "population_unit_count": len(unit_weights),
        "coverage_lower_bound": {str(threshold): _summary_payload(summaries[threshold], municipality_codes=municipality_codes) for threshold in THRESHOLDS},
        "historical_station_identity_kept_separate_from_project_hub_bridge": True,
        "historical_station_stop_id": "300407",
        "project_station_access_stop_id": "L00407",
        "project_station_access_cluster": "EX_039",
        "lineage": {
            "identity_sha256": sha256_path(args.identity),
            "identity_validation_sha256": sha256_path(args.identity_validation),
            "v2_official_stops_sha256": sha256_path(args.v2_official_stops),
            "existing_catchments_sha256": sha256_path(args.existing_catchments),
            "population_units_sha256": sha256_path(args.population_units),
            "localized_output_sha256": sha256_path(args.localized_output),
        },
        "limitations": [
            "The official current PDF establishes current stop rows and timetable service, but not complete spatial stop identities.",
            "Historical GTFS is used only as a validity-bounded official identity crosscheck; it is not promoted to current-service activation evidence.",
            "Any D184/D185 row without a unique resolved historical GTFS stop_id that exactly reappears in Stop Universe V2 remains spatially unresolved.",
            "Coverage therefore represents a proven lower bound of current D184+D185 pedestrian access, not the true complete current-service coverage.",
        ],
    }
    args.validation_output.parent.mkdir(parents=True, exist_ok=True)
    args.validation_output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
