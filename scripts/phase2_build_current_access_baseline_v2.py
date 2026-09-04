#!/usr/bin/env python3
"""Materialise a source-closed current D184+D185 walking-access lower bound.

The current primary timetable PDFs identify which D184/D185 stop rows are active
on 2026-09-03, but the conservative PDF->historical-GTFS identity crosswalk does
not spatially resolve every row. This builder therefore uses only current rows
with a resolved official GTFS identity that can be joined exactly to a Stop
Universe V2 physical cluster. The resulting access metric is a certified lower
bound on current-service stop access, never a complete current baseline.

It is valid for one-sided non-regression screening only: if a candidate's worst
municipality access is below this lower bound, regression is demonstrated. A
candidate above the lower bound is not thereby proven non-regressing against the
unknown full current-service stop set.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.phase2_access_equity_v2 import summarise_walk_coverage_thresholds

STATUS = "PASS_CURRENT_ACCESS_LOWER_BOUND_V2_BUILD"
CONTRACT = "PHASE2_CURRENT_D184_D185_ACCESS_LOWER_BOUND_V2"
CURRENT_ROUTES = {"D184", "D185"}
THRESHOLDS = (5, 8, 10, 12)


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_population_units(path: Path):
    weights: dict[str, float] = {}
    municipalities: dict[str, str] = {}
    totals: dict[str, float] = {}
    codes: dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for line_no, row in enumerate(csv.DictReader(handle), start=2):
            unit_id = row["population_unit_id"].strip()
            municipality = row["COMUNE"].strip()
            code = row["PRO_COM_T"].strip()
            weight = float(row["building_piece_population_model"])
            if not unit_id or not municipality or not code or not math.isfinite(weight) or weight < 0:
                raise ValueError(f"Invalid population unit at line {line_no}")
            if unit_id in weights:
                raise ValueError(f"Duplicate population unit {unit_id}")
            weights[unit_id] = weight
            municipalities[unit_id] = municipality
            totals[municipality] = totals.get(municipality, 0.0) + weight
            if municipality in codes and codes[municipality] != code:
                raise ValueError(f"Conflicting municipality code for {municipality}")
            codes[municipality] = code
    if not weights:
        raise ValueError("Population universe is empty")
    return weights, municipalities, totals, codes


def load_existing_walks(path: Path, *, unit_weights: dict[str, float]):
    walks: dict[str, dict[str, float]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for line_no, row in enumerate(csv.DictReader(handle), start=2):
            cluster = row["physical_cluster_id"].strip()
            unit_id = row["population_unit_id"].strip()
            walk = float(row["walk_min_to_stop"])
            row_weight = float(row["building_piece_population_model"])
            if unit_id not in unit_weights:
                raise ValueError(f"Unknown catchment population unit {unit_id} at line {line_no}")
            if not math.isclose(row_weight, unit_weights[unit_id], rel_tol=0.0, abs_tol=1e-9):
                raise ValueError(f"Catchment population mismatch for {unit_id}")
            if not math.isfinite(walk) or walk < 0 or walk > 12.0 + 1e-9:
                raise ValueError(f"Invalid existing-stop walk time at line {line_no}")
            previous = walks.setdefault(cluster, {}).get(unit_id)
            if previous is None or walk < previous:
                walks[cluster][unit_id] = walk
    if not walks:
        raise ValueError("Existing-stop catchments are empty")
    return walks


def validate_upstream(args) -> tuple[dict, dict, dict]:
    identity = load_json(args.identity_validation)
    stop = load_json(args.stop_validation)
    access = load_json(args.access_validation)
    if identity.get("status") != "PASS" or identity.get("reference_date") != "2026-09-03":
        raise ValueError("Current-service identity crosswalk is not certified for 2026-09-03")
    if identity.get("scope") != "CURRENT_PDF_STOP_ROW_TO_OFFICIAL_STOP_IDENTITY_CROSSCHECK":
        raise ValueError("Unexpected current-service identity scope")
    if stop.get("status") != "PASS_STOP_UNIVERSE_V2_BUILD":
        raise ValueError("Stop Universe V2 is not certified")
    if access.get("status") != "PASS_ACCESS_EQUITY_V2_BUILD":
        raise ValueError("Access Equity V2 is not certified")
    lineage = access.get("lineage", {})
    checks = {
        "existing catchments": (lineage.get("existing_catchments_sha256"), sha256_path(args.existing_catchments)),
        "population units": (lineage.get("population_units_sha256"), sha256_path(args.population_units)),
        "stop validation": (lineage.get("stop_validation_sha256"), sha256_path(args.stop_validation)),
        "identity output": (identity.get("output_sha256", {}).get("identity"), sha256_path(args.identity)),
    }
    for label, (expected, actual) in checks.items():
        if expected != actual:
            raise ValueError(f"Upstream hash mismatch for {label}")
    return identity, stop, access


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--identity", type=Path, required=True)
    p.add_argument("--identity-validation", type=Path, required=True)
    p.add_argument("--v2-existing-stops", type=Path, required=True)
    p.add_argument("--stop-validation", type=Path, required=True)
    p.add_argument("--existing-catchments", type=Path, required=True)
    p.add_argument("--population-units", type=Path, required=True)
    p.add_argument("--access-validation", type=Path, required=True)
    p.add_argument("--mapping-output", type=Path, required=True)
    p.add_argument("--validation-output", type=Path, required=True)
    args = p.parse_args()

    identity_validation, stop_validation, access_validation = validate_upstream(args)
    identity_rows = load_csv(args.identity)
    v2_stops = load_csv(args.v2_existing_stops)
    unit_weights, unit_municipality, municipality_totals, municipality_codes = load_population_units(args.population_units)
    existing_walks = load_existing_walks(args.existing_catchments, unit_weights=unit_weights)

    stop_to_cluster: dict[str, str] = {}
    for row in v2_stops:
        stop_id = row["stop_id"].strip()
        cluster = row["physical_cluster_id"].strip()
        if not stop_id or not cluster:
            raise ValueError("V2 existing stop lacks stop/cluster identity")
        if stop_id in stop_to_cluster and stop_to_cluster[stop_id] != cluster:
            raise ValueError(f"V2 stop {stop_id} maps to multiple clusters")
        stop_to_cluster[stop_id] = cluster

    mapping_rows: list[dict[str, object]] = []
    current_row_count = 0
    resolved_identity_count = 0
    v2_mapped_row_count = 0
    unresolved_identity_count = 0
    resolved_not_in_v2_count = 0
    clusters: set[str] = set()

    for row in identity_rows:
        route = row["route_id"].strip()
        if route not in CURRENT_ROUTES:
            continue
        current_row_count += 1
        resolved_stop = row["historical_gtfs_stop_id"].strip()
        equivalent = [token.strip() for token in row["historical_gtfs_equivalent_stop_ids"].split("|") if token.strip()]
        candidate_ids = sorted(set(([resolved_stop] if resolved_stop else []) + equivalent))
        matched_clusters = sorted({stop_to_cluster[sid] for sid in candidate_ids if sid in stop_to_cluster})
        if resolved_stop:
            resolved_identity_count += 1
            if len(matched_clusters) > 1:
                raise ValueError(
                    f"Resolved current row {route}/{row['source_page']}/{row['stop_sequence_on_page']} maps to multiple V2 clusters: {matched_clusters}"
                )
            if matched_clusters:
                cluster = matched_clusters[0]
                clusters.add(cluster)
                v2_mapped_row_count += 1
                mapping_status = "RESOLVED_CURRENT_ROW_JOINED_EXACTLY_TO_V2_PHYSICAL_CLUSTER"
            else:
                cluster = ""
                resolved_not_in_v2_count += 1
                mapping_status = "RESOLVED_CURRENT_GTFS_IDENTITY_NOT_IN_V2_CORE_STOP_UNIVERSE"
        else:
            cluster = ""
            unresolved_identity_count += 1
            mapping_status = "CURRENT_PDF_ROW_SPATIALLY_UNRESOLVED"
        mapping_rows.append({
            "route_id": route,
            "source_page": row["source_page"],
            "stop_sequence_on_page": row["stop_sequence_on_page"],
            "stop_label_pdf": row["stop_label_pdf"],
            "identity_status": row["identity_status"],
            "historical_gtfs_stop_id": resolved_stop,
            "historical_gtfs_equivalent_stop_ids": row["historical_gtfs_equivalent_stop_ids"],
            "physical_cluster_id_v2": cluster,
            "mapping_status": mapping_status,
            "used_in_current_access_lower_bound": "true" if cluster else "false",
        })

    if current_row_count != 51:
        raise ValueError(f"Expected 51 current D184+D185 PDF stop rows, got {current_row_count}")
    if resolved_identity_count != 20:
        raise ValueError(f"Expected 20 resolved D184+D185 identity rows from certified crosswalk, got {resolved_identity_count}")
    if not clusters:
        raise ValueError("No current D184+D185 physical clusters could be localised")
    missing_catchments = sorted(clusters - set(existing_walks))
    if missing_catchments:
        raise ValueError(f"Mapped current clusters lack V2 catchment evidence: {missing_catchments}")

    summaries = summarise_walk_coverage_thresholds(
        clusters,
        walk_by_anchor=existing_walks,
        unit_weights=unit_weights,
        unit_municipality=unit_municipality,
        municipality_totals=municipality_totals,
        thresholds=THRESHOLDS,
    )

    args.mapping_output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(mapping_rows[0])
    with args.mapping_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(mapping_rows)

    by_threshold: dict[str, object] = {}
    for threshold in THRESHOLDS:
        summary = summaries[threshold]
        by_threshold[str(threshold)] = {
            "covered_population_lower_bound": summary.covered_population,
            "coverage_share_lower_bound": summary.coverage_share,
            "worst_municipality_lower_bound": summary.worst_municipality,
            "worst_municipality_coverage_share_lower_bound": summary.worst_municipality_coverage_share,
            "municipality_coverage_share_lower_bound": {
                municipality_codes[name]: {
                    "name": name,
                    "share": summary.municipality_coverage_share[name],
                }
                for name in sorted(municipality_totals)
            },
        }

    validation = {
        "status": STATUS,
        "contract": CONTRACT,
        "reference_date": "2026-09-03",
        "routes": sorted(CURRENT_ROUTES),
        "current_pdf_stop_row_count": current_row_count,
        "resolved_historical_gtfs_identity_row_count": resolved_identity_count,
        "spatially_unresolved_current_pdf_row_count": unresolved_identity_count,
        "resolved_identity_not_in_v2_core_stop_universe_row_count": resolved_not_in_v2_count,
        "v2_exactly_mapped_current_row_count": v2_mapped_row_count,
        "unique_v2_physical_cluster_lower_bound_count": len(clusters),
        "v2_physical_clusters_lower_bound": sorted(clusters),
        "located_population": sum(unit_weights.values()),
        "population_unit_count": len(unit_weights),
        "thresholds_min": list(THRESHOLDS),
        "access_lower_bound_by_threshold": by_threshold,
        "full_current_service_spatial_baseline_complete": False,
        "non_regression_use": "ONE_SIDED_FAIL_ONLY: CANDIDATE_BELOW_LOWER_BOUND_IS_DEMONSTRATED_REGRESSION; CANDIDATE_AT_OR_ABOVE_LOWER_BOUND_REMAINS_UNKNOWN_VS_FULL_CURRENT_SERVICE",
        "unresolved_rows_used_as_spatial_facts": False,
        "historical_gtfs_used_to_assert_current_activation": False,
        "passenger_demand_inferred": False,
        "topology_ranked": False,
        "service_policy_selected": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "lineage": {
            "identity_sha256": sha256_path(args.identity),
            "identity_validation_sha256": sha256_path(args.identity_validation),
            "v2_existing_stops_sha256": sha256_path(args.v2_existing_stops),
            "stop_validation_sha256": sha256_path(args.stop_validation),
            "existing_catchments_sha256": sha256_path(args.existing_catchments),
            "population_units_sha256": sha256_path(args.population_units),
            "access_validation_sha256": sha256_path(args.access_validation),
            "mapping_output_sha256": sha256_path(args.mapping_output),
            "access_scenario_output_sha256": access_validation["lineage"]["scenario_output_sha256"],
            "stop_universe_population_model_status": stop_validation["population_model_status"],
        },
        "epistemic_note": (
            "Current primary PDFs determine current D184/D185 row activation on 2026-09-03. Historical official GTFS is used only for the already-certified identity crosscheck. Only resolved identities that join exactly to Stop Universe V2 physical clusters contribute to this access result. Because unresolved current rows are omitted, every reported access value is a lower bound, not a complete current-service baseline."
        ),
    }
    args.validation_output.write_text(json.dumps(validation, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
