#!/usr/bin/env python3
"""Build Current-Service Baseline V4 from frozen certified public-source extracts.

This builder deliberately does not access the network. It consumes the exact
D184/D185 GTFS-derived extracts persisted by the public-geodata recovery
workstream, frozen current-service activation evidence and the already
certified Phase 2 walking/population universe.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
import json
import math
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.phase2_run_access_equity_v2 import load_population_units, sha256_path
from scripts.phase2_build_current_service_access_baseline_v4 import (
    THRESHOLDS,
    build_olgiate_diagnostic,
    coverage_by_unit,
    crosscheck_exact_frozen_identity,
    load_existing_walks,
    load_frozen_stop_clusters,
    municipality_rows,
    read_csv,
    read_json,
    write_csv,
    write_population_access_gzip,
)
from src.phase2_access_equity_v2 import summarise_walk_coverage_thresholds
from src.phase2_current_service_baseline_v4 import (
    BASELINE_SEMANTICS,
    CONTRACT,
    CURRENT_SERVICE_EVIDENCE_IS_RIDERSHIP,
    FUTURE_2026_09_14_USED_AS_CURRENT,
    OLGIATE_DIAGNOSTIC_IN_CANDIDATE_OPTIMISATION,
    PDF_TIMING_ROWS_TREATED_AS_COMPLETE_STOP_UNIVERSE,
    REFERENCE_DATE,
    ROUTE_SCOPE,
    STATUS,
    StopForClustering,
    activation_status,
    cluster_stop_records,
    deterministic_pattern_id,
    validate_official_coordinate,
)

RECOVERY_STATUS = "PASS_PUBLIC_SOURCE_DISCOVERY"
RECOVERY_COMMIT = "4ab527827456eb40572a72b4c7b87f8fe5f4dcac"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(str(value).strip())


def validate_current_route_activation(path: Path) -> dict[str, dict[str, str]]:
    reference = parse_iso_date(REFERENCE_DATE)
    found: dict[str, dict[str, str]] = {}
    for row in read_csv(path):
        route = str(row.get("route_id", "")).strip()
        if route not in ROUTE_SCOPE:
            continue
        valid_from = parse_iso_date(row["valid_from"])
        valid_to = parse_iso_date(row["valid_to"])
        if not (valid_from <= reference <= valid_to):
            continue
        if int(row["active_timetable_columns"]) <= 0:
            raise ValueError(f"Current-service reference has no active columns for {route}")
        if str(row.get("epistemic_status", "")).strip() != "RECONSTRUCTED_FROM_OFFICIAL_PRIMARY_TIMETABLE":
            raise ValueError(f"Unexpected activation epistemic status for {route}")
        found[route] = row
    missing = sorted(set(ROUTE_SCOPE) - set(found))
    if missing:
        raise ValueError(f"Frozen route-level activation evidence missing for {missing}")
    return found


def validate_temporary_conditions(path: Path) -> dict[str, str]:
    matches = []
    for row in read_csv(path):
        if str(row.get("route_id", "")).strip() != "D185":
            continue
        if "TEMPORARY" not in str(row.get("condition_type", "")).upper():
            continue
        matches.append(row)
    if len(matches) != 1:
        raise ValueError("Expected exactly one frozen D185 temporary bridge condition")
    row = matches[0]
    if str(row.get("ordinary_network_baseline_replaced", "")).strip().lower() != "false":
        raise ValueError("Frozen evidence says the temporary D185 condition replaces the ordinary baseline")
    if str(row.get("reference_date_active", "")).strip().lower() != "true":
        raise ValueError("Frozen D185 temporary condition was not active at source reference date")
    return row


def parse_source_hash(path: Path) -> str:
    text = path.read_text(encoding="utf-8").strip()
    digest = text.split()[0] if text else ""
    if not _SHA256_RE.fullmatch(digest):
        raise ValueError("Frozen GTFS source hash is not a SHA256")
    return digest


def parse_certified_gtfs_extract(route_stops_path: Path, patterns_path: Path, summary_path: Path):
    summary = read_json(summary_path)
    if summary.get("status") != RECOVERY_STATUS:
        raise ValueError("GTFS recovery summary is not PASS_PUBLIC_SOURCE_DISCOVERY")
    if sorted(summary.get("route_ids_gtfs", [])) != sorted(ROUTE_SCOPE):
        raise ValueError("GTFS recovery route scope differs from D184/D185")

    patterns = read_csv(patterns_path)
    pattern_members: dict[str, tuple[str, ...]] = {}
    pattern_ids_by_route_stop: dict[tuple[str, str], set[str]] = {}
    pattern_trip_count: dict[str, int] = {}
    for row_no, row in enumerate(patterns, start=2):
        route = str(row.get("route_short_name", "")).strip()
        if route not in ROUTE_SCOPE:
            raise ValueError(f"Out-of-scope route in frozen pattern extract at row {row_no}")
        stop_ids = tuple(v.strip() for v in str(row.get("stop_ids", "")).split("|") if v.strip())
        stop_names = tuple(v.strip() for v in str(row.get("stop_names", "")).split("|"))
        if not stop_ids or len(stop_ids) != int(row["stop_count"]):
            raise ValueError(f"Invalid frozen pattern stop count at row {row_no}")
        if len(stop_names) != len(stop_ids):
            raise ValueError(f"Frozen pattern stop names/ids length mismatch at row {row_no}")
        pid = deterministic_pattern_id(route, "SOURCE_CLOSED", stop_ids)
        if pid in pattern_members and pattern_members[pid] != stop_ids:
            raise ValueError("Deterministic pattern collision in frozen extract")
        pattern_members[pid] = stop_ids
        pattern_trip_count[pid] = int(row["trip_count"])
        for stop_id in set(stop_ids):
            pattern_ids_by_route_stop.setdefault((route, stop_id), set()).add(pid)

    if len(pattern_members) != int(summary["distinct_route_trip_patterns"]):
        raise ValueError("Frozen pattern count disagrees with recovery summary")

    records = []
    unique_stops: dict[str, StopForClustering] = {}
    keys = set()
    for row_no, row in enumerate(read_csv(route_stops_path), start=2):
        route = str(row.get("route_short_name", "")).strip()
        route_id = str(row.get("route_id_gtfs", "")).strip()
        stop_id = str(row.get("stop_id", "")).strip()
        stop_name = str(row.get("stop_name", "")).strip()
        if route not in ROUTE_SCOPE or route_id != route:
            raise ValueError(f"Unexpected route identity in frozen route-stop extract at row {row_no}")
        if not stop_id or not stop_name:
            raise ValueError(f"Missing stop identity in frozen route-stop extract at row {row_no}")
        key = (route, stop_id)
        if key in keys:
            raise ValueError(f"Duplicate route-stop record {key}")
        keys.add(key)
        lat = float(row["stop_lat"])
        lon = float(row["stop_lon"])
        validate_official_coordinate(lat, lon)
        stop = StopForClustering(stop_id, stop_name, lat, lon)
        if stop_id in unique_stops and unique_stops[stop_id] != stop:
            raise ValueError(f"Conflicting official metadata for stop_id {stop_id}")
        unique_stops[stop_id] = stop
        pids = sorted(pattern_ids_by_route_stop.get(key, set()))
        if not pids:
            raise ValueError(f"Frozen route-stop record {key} is absent from all frozen patterns")
        records.append({
            "route_id": route,
            "stop_id": stop_id,
            "stop_name": stop_name,
            "stop_lat": lat,
            "stop_lon": lon,
            "trip_stop_time_row_count": int(row["trip_stop_time_row_count"]),
            "pattern_count": len(pids),
            "pattern_ids": ";".join(pids),
            "pattern_trip_count_sum": sum(pattern_trip_count[pid] for pid in pids),
            "min_stop_sequence": int(row["min_stop_sequence"]),
            "max_stop_sequence": int(row["max_stop_sequence"]),
        })

    if len(records) != int(summary["official_route_specific_stop_record_count"]):
        raise ValueError("Frozen route-stop record count disagrees with recovery summary")
    return records, unique_stops, pattern_members, summary


def build_cluster_rows(unique_stops, cluster_by_stop, reason_by_stop, route_records):
    route_by_stop: dict[str, set[str]] = {}
    pattern_by_stop: dict[str, set[str]] = {}
    for row in route_records:
        sid = str(row["stop_id"])
        route_by_stop.setdefault(sid, set()).add(str(row["route_id"]))
        pattern_by_stop.setdefault(sid, set()).update(
            p for p in str(row["pattern_ids"]).split(";") if p
        )
    members: dict[str, list[StopForClustering]] = {}
    for stop_id, stop in unique_stops.items():
        members.setdefault(cluster_by_stop[stop_id], []).append(stop)
    out = []
    for cid in sorted(members):
        ms = sorted(members[cid], key=lambda s: s.stop_id)
        rep = ms[0]
        out.append({
            "physical_stop_cluster_id": cid,
            "representative_stop_id": rep.stop_id,
            "representative_stop_name": rep.stop_name,
            "representative_stop_lat": rep.stop_lat,
            "representative_stop_lon": rep.stop_lon,
            "stop_id_member_count": len(ms),
            "member_stop_ids": ";".join(s.stop_id for s in ms),
            "member_stop_names": ";".join(s.stop_name for s in ms),
            "member_coordinates": ";".join(f"{s.stop_lat:.6f},{s.stop_lon:.6f}" for s in ms),
            "routes": ";".join(sorted({r for s in ms for r in route_by_stop.get(s.stop_id, set())})),
            "pattern_ids": ";".join(sorted({p for s in ms for p in pattern_by_stop.get(s.stop_id, set())})),
            "clustering_reasons": ";".join(sorted({reason_by_stop[s.stop_id] for s in ms})),
        })
    return out


def write_provenance(path: Path, *, args, gtfs_binary_sha256: str, recovery_summary: dict, kml_rows):
    rows = [
        {
            "dataset_id": "official_gtfs_d184_d185_route_stops_frozen",
            "source_kind": "FROZEN_CERTIFIED_EXTRACT",
            "source_commit": RECOVERY_COMMIT,
            "source_reference": str(recovery_summary.get("source_url", "")),
            "sha256": sha256_path(args.gtfs_route_stops),
            "upstream_binary_sha256": gtfs_binary_sha256,
            "epistemic_role": "OFFICIAL_STOP_IDENTITY_COORDINATES_ROUTE_MEMBERSHIP",
            "used_in_numeric_coverage": "true",
        },
        {
            "dataset_id": "official_gtfs_d184_d185_patterns_frozen",
            "source_kind": "FROZEN_CERTIFIED_EXTRACT",
            "source_commit": RECOVERY_COMMIT,
            "source_reference": str(recovery_summary.get("source_url", "")),
            "sha256": sha256_path(args.gtfs_patterns),
            "upstream_binary_sha256": gtfs_binary_sha256,
            "epistemic_role": "HISTORICAL_ORDINARY_ROUTE_PATTERN_CORROBORATION",
            "used_in_numeric_coverage": "false",
        },
        {
            "dataset_id": "current_service_reference_frozen",
            "source_kind": "FROZEN_PRIMARY_TIMETABLE_EVIDENCE",
            "source_commit": RECOVERY_COMMIT,
            "source_reference": "outputs/phase2/current_service_reference_2026-09-03.csv",
            "sha256": sha256_path(args.current_service_reference),
            "upstream_binary_sha256": "",
            "epistemic_role": "CURRENT_ROUTE_LEVEL_ACTIVATION_VALID_THROUGH_2026_09_13",
            "used_in_numeric_coverage": "false",
        },
        {
            "dataset_id": "d185_temporary_condition_frozen",
            "source_kind": "FROZEN_PRIMARY_TIMETABLE_EVIDENCE",
            "source_commit": RECOVERY_COMMIT,
            "source_reference": "outputs/phase2/current_service_temporary_conditions_2026-09-03.csv",
            "sha256": sha256_path(args.temporary_conditions),
            "upstream_binary_sha256": "",
            "epistemic_role": "TEMPORARY_DISRUPTION_DOCUMENTED_AND_EXCLUDED_FROM_STRUCTURAL_BASELINE",
            "used_in_numeric_coverage": "false",
        },
    ]
    for kml in kml_rows:
        rows.append({
            "dataset_id": kml["archive_id"],
            "source_kind": "USER_ARCHIVED_PUBLIC_KML_PROVENANCE",
            "source_commit": "",
            "source_reference": kml["renumbering_source_url"],
            "sha256": kml["sha256"],
            "upstream_binary_sha256": "",
            "epistemic_role": kml["epistemic_role"],
            "used_in_numeric_coverage": "false",
        })
    write_csv(
        path,
        rows,
        ["dataset_id", "source_kind", "source_commit", "source_reference", "sha256",
         "upstream_binary_sha256", "epistemic_role", "used_in_numeric_coverage"],
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gtfs-route-stops", type=Path, required=True)
    ap.add_argument("--gtfs-patterns", type=Path, required=True)
    ap.add_argument("--gtfs-recovery-summary", type=Path, required=True)
    ap.add_argument("--gtfs-source-sha256", type=Path, required=True)
    ap.add_argument("--current-service-reference", type=Path, required=True)
    ap.add_argument("--temporary-conditions", type=Path, required=True)
    ap.add_argument("--archived-kml-provenance", type=Path, required=True)
    ap.add_argument("--frozen-official-stops", type=Path, required=True)
    ap.add_argument("--existing-catchments", type=Path, required=True)
    ap.add_argument("--population-units", type=Path, required=True)
    ap.add_argument("--settlement-anchors", type=Path, required=True)
    ap.add_argument("--v3-validation", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    args = ap.parse_args()

    for path in vars(args).values():
        if isinstance(path, Path) and path != args.outdir and not path.is_file():
            raise FileNotFoundError(path)

    activation = validate_current_route_activation(args.current_service_reference)
    temporary = validate_temporary_conditions(args.temporary_conditions)
    gtfs_binary_sha256 = parse_source_hash(args.gtfs_source_sha256)
    route_records, unique_stops, pattern_members, recovery_summary = parse_certified_gtfs_extract(
        args.gtfs_route_stops, args.gtfs_patterns, args.gtfs_recovery_summary
    )

    kml_rows = read_csv(args.archived_kml_provenance)
    mapping = {(r["legacy_line"], r["current_line"]) for r in kml_rows}
    if mapping != {("D84", "D184"), ("E03", "D185")}:
        raise ValueError("Archived KML renumbering provenance must be exactly D84->D184 and E03->D185")
    if any(not _SHA256_RE.fullmatch(str(r["sha256"]).strip()) for r in kml_rows):
        raise ValueError("Archived KML provenance contains invalid SHA256")
    if any(str(r["used_in_numeric_coverage"]).strip().lower() != "false" for r in kml_rows):
        raise ValueError("Archived KMLs must remain corroboration-only in V4 numeric coverage")

    v3 = read_json(args.v3_validation)
    if v3.get("status") != "PASS_CURRENT_SERVICE_ACCESS_LOWER_BOUND_V3":
        raise ValueError("Expected certified V3 baseline input")

    frozen_by_id, frozen_rows = load_frozen_stop_clusters(args.frozen_official_stops)
    crosscheck_exact_frozen_identity(unique_stops, frozen_rows)
    cluster_by_stop, cluster_reason = cluster_stop_records(
        list(unique_stops.values()), frozen_cluster_by_stop_id=frozen_by_id
    )

    for row in route_records:
        sid = str(row["stop_id"])
        route = str(row["route_id"])
        row["physical_stop_cluster_id"] = cluster_by_stop[sid]
        row["clustering_reason"] = cluster_reason[sid]
        row["activation_evidence_status"] = activation_status(route)
        row["current_reference_date"] = REFERENCE_DATE
        row["temporary_disruption_excluded"] = str(route == "D185").lower()
        row["ridership_evidence"] = "false"

    clusters = build_cluster_rows(unique_stops, cluster_by_stop, cluster_reason, route_records)

    unit_weights, unit_municipality, municipality_totals, municipality_codes = load_population_units(args.population_units)
    walks = load_existing_walks(args.existing_catchments, unit_weights=unit_weights)
    all_route_clusters = {str(r["physical_stop_cluster_id"]) for r in clusters}
    certified_catchment_clusters = {cid for cid in all_route_clusters if cid in walks}
    if not certified_catchment_clusters:
        raise ValueError("No D184/D185 physical cluster has frozen certified catchment evidence")

    v3_clusters = set(v3.get("localized_unique_physical_clusters", []))
    if not v3_clusters.issubset(certified_catchment_clusters):
        raise ValueError("V4 lost V3 certified physical clusters: " + ",".join(sorted(v3_clusters - certified_catchment_clusters)))

    summaries = summarise_walk_coverage_thresholds(
        frozenset(certified_catchment_clusters),
        walk_by_anchor=walks,
        unit_weights=unit_weights,
        unit_municipality=unit_municipality,
        municipality_totals=municipality_totals,
        thresholds=THRESHOLDS,
    )
    for t in (5, 8, 10):
        old = float(v3["coverage_lower_bound"][str(t)]["coverage_share"])
        if summaries[t].coverage_share + 1e-12 < old:
            raise ValueError(f"V4 coverage regressed below V3 at {t} minutes")

    args.outdir.mkdir(parents=True, exist_ok=True)

    route_records_path = args.outdir / "current_service_route_stop_records_v4.csv"
    write_csv(
        route_records_path,
        route_records,
        ["route_id", "stop_id", "stop_name", "stop_lat", "stop_lon",
         "physical_stop_cluster_id", "clustering_reason", "trip_stop_time_row_count",
         "pattern_count", "pattern_ids", "pattern_trip_count_sum", "min_stop_sequence",
         "max_stop_sequence", "activation_evidence_status", "current_reference_date",
         "temporary_disruption_excluded", "ridership_evidence"],
    )

    for row in clusters:
        row["certified_phase2_catchment_available"] = str(
            row["physical_stop_cluster_id"] in certified_catchment_clusters
        ).lower()
    cluster_path = args.outdir / "current_service_physical_stop_clusters_v4.csv"
    write_csv(
        cluster_path,
        clusters,
        ["physical_stop_cluster_id", "representative_stop_id", "representative_stop_name",
         "representative_stop_lat", "representative_stop_lon", "stop_id_member_count",
         "member_stop_ids", "member_stop_names", "member_coordinates", "routes", "pattern_ids",
         "clustering_reasons", "certified_phase2_catchment_available"],
    )

    unit_rows = coverage_by_unit(
        selected_clusters=certified_catchment_clusters,
        walks=walks,
        unit_weights=unit_weights,
        unit_municipality=unit_municipality,
        municipality_codes=municipality_codes,
    )
    population_path = args.outdir / "current_service_access_by_population_unit_v4.csv.gz"
    write_population_access_gzip(population_path, unit_rows)

    municipality_output = municipality_rows(
        summaries,
        municipality_totals=municipality_totals,
        municipality_codes=municipality_codes,
    )
    municipality_path = args.outdir / "current_service_access_by_municipality_v4.csv"
    write_csv(
        municipality_path,
        municipality_output,
        ["PRO_COM_T", "COMUNE", "located_population_model",
         "coverage_5m_share", "covered_population_5m",
         "coverage_8m_share", "covered_population_8m",
         "coverage_10m_share", "covered_population_10m",
         "coverage_12m_share", "covered_population_12m"],
    )

    anchor_rows = read_csv(args.settlement_anchors)
    olgiate_rows = build_olgiate_diagnostic(anchor_rows, clusters, municipality_output)
    olgiate_path = args.outdir / "current_service_olgiate_diagnostic_v4.csv"
    write_csv(
        olgiate_path,
        olgiate_rows,
        ["area", "settlement_anchor_id", "anchor_status", "current_service_accessibility",
         "useful_physical_stop_clusters", "v4_d184_d185_anchor_walk_min",
         "all_existing_service_anchor_walk_min_context_only", "walking_coverage_semantics",
         "olgiate_coverage_5m_share", "olgiate_coverage_8m_share",
         "olgiate_coverage_10m_share", "field_uncertainty", "used_in_candidate_optimisation"],
    )

    comparison = [
        {"scope": "GLOBAL", "metric": "pdf_timing_rows", "v3": str(v3["target_pdf_stop_rows"]), "v4": "NOT_STOP_UNIVERSE", "notes": "V4 retires PDF timing rows as the geographic stop universe"},
        {"scope": "GLOBAL", "metric": "localized_pdf_rows", "v3": str(v3["localized_rows"]), "v4": "NOT_APPLICABLE", "notes": "V4 uses official GTFS route-stop identities"},
        {"scope": "GLOBAL", "metric": "unresolved_pdf_rows", "v3": str(v3["unresolved_or_unlocalized_rows"]), "v4": "NOT_APPLICABLE", "notes": "V4 does not force timing-row geolocation"},
        {"scope": "GLOBAL", "metric": "route_specific_stop_records", "v3": "", "v4": str(len(route_records)), "notes": "frozen official GTFS extract"},
        {"scope": "GLOBAL", "metric": "unique_official_stop_ids", "v3": "", "v4": str(len(unique_stops)), "notes": "official GTFS D184/D185"},
        {"scope": "GLOBAL", "metric": "physical_stop_clusters", "v3": str(v3["localized_unique_physical_cluster_count"]), "v4": str(len(clusters)), "notes": "deterministic strong-evidence clustering"},
        {"scope": "GLOBAL", "metric": "physical_clusters_with_certified_phase2_catchment", "v3": str(v3["localized_unique_physical_cluster_count"]), "v4": str(len(certified_catchment_clusters)), "notes": "only these feed coverage"},
        {"scope": "GLOBAL", "metric": "official_stops_without_coordinates", "v3": "", "v4": "0", "notes": "no coordinates invented"},
    ]
    for t in (5, 8, 10):
        comparison.append({
            "scope": "GLOBAL", "metric": f"coverage_{t}m_share",
            "v3": f"{float(v3['coverage_lower_bound'][str(t)]['coverage_share']):.15f}",
            "v4": f"{summaries[t].coverage_share:.15f}",
            "notes": "same frozen population units and certified walking catchments",
        })
    for mrow in municipality_output:
        code = mrow["PRO_COM_T"]
        for t in (5, 8, 10):
            old = v3["coverage_lower_bound"][str(t)]["municipality_coverage"][code]["coverage_share"]
            comparison.append({
                "scope": mrow["COMUNE"], "metric": f"coverage_{t}m_share",
                "v3": f"{float(old):.15f}", "v4": mrow[f"coverage_{t}m_share"],
                "notes": "frozen located-building population denominator",
            })
    comparison_path = args.outdir / "current_service_v3_v4_comparison.csv"
    write_csv(comparison_path, comparison, ["scope", "metric", "v3", "v4", "notes"])

    interface = []
    for t in (5, 8, 10):
        interface.append({"scope": "GLOBAL", "metric": f"coverage_{t}m_share", "CURRENT_D184_D185_V4": f"{summaries[t].coverage_share:.15f}", "PRIMARY": "", "RUNNER_UP": "", "selection_status": "NOT_SELECTED"})
    for row in municipality_output:
        for t in (5, 8, 10):
            interface.append({"scope": row["COMUNE"], "metric": f"coverage_{t}m_share", "CURRENT_D184_D185_V4": row[f"coverage_{t}m_share"], "PRIMARY": "", "RUNNER_UP": "", "selection_status": "NOT_SELECTED"})
    for t in (5, 8, 10):
        interface.append({"scope": "GLOBAL", "metric": f"worst_municipality_{t}m_share", "CURRENT_D184_D185_V4": f"{summaries[t].worst_municipality_coverage_share:.15f}", "PRIMARY": "", "RUNNER_UP": "", "selection_status": "NOT_SELECTED"})
    interface_path = args.outdir / "current_service_candidate_comparison_interface_v4.csv"
    write_csv(interface_path, interface, ["scope", "metric", "CURRENT_D184_D185_V4", "PRIMARY", "RUNNER_UP", "selection_status"])

    provenance_path = args.outdir / "current_service_v4_source_provenance.csv"
    write_provenance(provenance_path, args=args, gtfs_binary_sha256=gtfs_binary_sha256, recovery_summary=recovery_summary, kml_rows=kml_rows)

    municipality_results = {
        row["PRO_COM_T"]: {
            "municipality": row["COMUNE"],
            "coverage_5m_share": float(row["coverage_5m_share"]),
            "coverage_8m_share": float(row["coverage_8m_share"]),
            "coverage_10m_share": float(row["coverage_10m_share"]),
            "coverage_12m_share": float(row["coverage_12m_share"]),
        }
        for row in municipality_output
    }

    validation = {
        "status": STATUS,
        "contract": CONTRACT,
        "reference_date": REFERENCE_DATE,
        "route_scope": list(ROUTE_SCOPE),
        "gtfs_source_official": True,
        "gtfs_source_closed_extract": True,
        "gtfs_live_download_required": False,
        "gtfs_recovery_frozen_commit": RECOVERY_COMMIT,
        "gtfs_upstream_binary_sha256": gtfs_binary_sha256,
        "archived_kml_corroboration_available": True,
        "archived_kml_used_in_numeric_coverage": False,
        "archived_kml_legacy_to_current_mapping": {"D84": "D184", "E03": "D185"},
        "future_2026_09_14_used_as_current": FUTURE_2026_09_14_USED_AS_CURRENT,
        "pdf_timing_rows_treated_as_complete_stop_universe": PDF_TIMING_ROWS_TREATED_AS_COMPLETE_STOP_UNIVERSE,
        "physical_stop_clustering_deterministic": True,
        "fuzzy_matching_used": False,
        "nearest_neighbour_matching_used": False,
        "invented_stop_coordinates": False,
        "walking_graph_epoch_changed": False,
        "population_units_changed": False,
        "current_service_baseline_complete": False,
        "current_service_baseline_semantics": BASELINE_SEMANTICS,
        "temporary_brivio_bridge_disruption_excluded_from_structural_baseline": True,
        "temporary_condition_ordinary_network_baseline_replaced": False,
        "d185_structural_baseline_role": "HISTORICAL_ORDINARY_NETWORK_STRUCTURE_NOT_2026_09_04_STOP_LEVEL_OPERATIONAL_SNAPSHOT",
        "historical_gtfs_identity_implies_current_trip_activation": False,
        "current_route_level_activation_certified_for_reference_date": True,
        "current_service_evidence_relabelled_as_ridership": CURRENT_SERVICE_EVIDENCE_IS_RIDERSHIP,
        "route_specific_stop_record_count": len(route_records),
        "official_gtfs_unique_stop_id_count": len(unique_stops),
        "official_physical_stop_cluster_count": len(clusters),
        "physical_clusters_with_certified_phase2_catchment_count": len(certified_catchment_clusters),
        "physical_clusters_without_certified_phase2_catchment_count": len(clusters) - len(certified_catchment_clusters),
        "unresolved_stop_coordinate_count": 0,
        "pattern_count": len(pattern_members),
        "population_unit_count": len(unit_weights),
        "located_population_denominator": sum(unit_weights.values()),
        "coverage_5m": summaries[5].coverage_share,
        "coverage_8m": summaries[8].coverage_share,
        "coverage_10m": summaries[10].coverage_share,
        "coverage_12m": summaries[12].coverage_share,
        "worst_municipality_5m": summaries[5].worst_municipality,
        "worst_municipality_5m_share": summaries[5].worst_municipality_coverage_share,
        "worst_municipality_8m": summaries[8].worst_municipality,
        "worst_municipality_8m_share": summaries[8].worst_municipality_coverage_share,
        "worst_municipality_10m": summaries[10].worst_municipality,
        "worst_municipality_10m_share": summaries[10].worst_municipality_coverage_share,
        "municipality_results": municipality_results,
        "olgiate_diagnostic_available": True,
        "olgiate_diagnostic_used_in_candidate_optimisation": OLGIATE_DIAGNOSTIC_IN_CANDIDATE_OPTIMISATION,
        "decision_gate_reopen_required": False,
        "decision_impact": "CASE_A_BASELINE_ENRICHMENT_ONLY_PRE_FINALIZER",
        "primary_selected": False,
        "runner_up_selected": False,
        "v3_comparison": {
            "v3_localized_pdf_rows": v3["localized_rows"],
            "v3_physical_clusters": v3["localized_unique_physical_cluster_count"],
            "v3_unresolved_pdf_rows": v3["unresolved_or_unlocalized_rows"],
            "v3_coverage_5m": v3["coverage_lower_bound"]["5"]["coverage_share"],
            "v3_coverage_8m": v3["coverage_lower_bound"]["8"]["coverage_share"],
            "v3_coverage_10m": v3["coverage_lower_bound"]["10"]["coverage_share"],
        },
        "lineage": {
            "gtfs_route_stops_extract_sha256": sha256_path(args.gtfs_route_stops),
            "gtfs_patterns_extract_sha256": sha256_path(args.gtfs_patterns),
            "gtfs_recovery_summary_sha256": sha256_path(args.gtfs_recovery_summary),
            "gtfs_source_hash_file_sha256": sha256_path(args.gtfs_source_sha256),
            "current_service_reference_sha256": sha256_path(args.current_service_reference),
            "temporary_conditions_sha256": sha256_path(args.temporary_conditions),
            "archived_kml_provenance_sha256": sha256_path(args.archived_kml_provenance),
            "frozen_official_stops_sha256": sha256_path(args.frozen_official_stops),
            "existing_catchments_sha256": sha256_path(args.existing_catchments),
            "population_units_sha256": sha256_path(args.population_units),
            "settlement_anchors_sha256": sha256_path(args.settlement_anchors),
            "v3_validation_sha256": sha256_path(args.v3_validation),
            "route_stop_records_sha256": sha256_path(route_records_path),
            "physical_clusters_sha256": sha256_path(cluster_path),
            "population_access_sha256": sha256_path(population_path),
            "municipality_access_sha256": sha256_path(municipality_path),
            "olgiate_diagnostic_sha256": sha256_path(olgiate_path),
            "v3_v4_comparison_sha256": sha256_path(comparison_path),
            "candidate_comparison_interface_sha256": sha256_path(interface_path),
            "persisted_source_provenance_sha256": sha256_path(provenance_path),
        },
        "limitations": [
            "The frozen 2025/26 official GTFS extract certifies stop identity, coordinates, route membership and historical ordinary patterns, not 2026-09-04 trip-level activation.",
            "D184 and D185 route-level operation on 2026-09-04 is established from frozen official primary-timetable evidence valid through 2026-09-13.",
            "By explicit project policy, the temporary 2026 Brivio bridge condition is documented but excluded from the D185 structural comparison baseline.",
            "D185 historical ordinary stop identities are not relabelled as CURRENT_2026_09_04 stop-level operations.",
            "Physical clusters lacking frozen Phase 2 catchment evidence remain in the official stop universe but do not receive invented walking catchments.",
            "Archived D84 and E03 KML provenance corroborates the legacy geometry lineage D84->D184 and E03->D185 but is not used numerically.",
            "Current-service baseline is not certified absolutely complete because route-level current activation does not prove every historical ordinary stop was served on the reference date.",
        ],
    }

    validation_path = args.outdir / "current_service_access_baseline_v4_validation.json"
    validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
