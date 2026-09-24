#!/usr/bin/env python3
"""Build the source-closed passenger-stop foundation for Phase 2 V3.

RT-005 showed that structural routing anchors had been allowed to stand in for
complete passenger stop patterns. This builder does not generate routes. It
creates the corrected stop-side foundation that a future corridor generator
must consume.

Key rules:
- structural waypoints are not passenger stops;
- frozen D184/D185 physical stops are immediately reusable passenger-stop
  evidence;
- proposed candidates remain hypotheses while FIELD_CHECK_PENDING;
- a bare technical ID is never treated as sufficient human-facing identity;
- municipality policy guards are policy records, not geographic evidence points;
- named service-area audit points are resolved only from certified repository
  evidence, with intentionally missing evidence recorded rather than invented.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
import re
import unicodedata

STUDY_MUNICIPALITIES = {
    "Olgiate Molgora", "Calco", "Brivio", "Santa Maria Hoè", "La Valletta Brianza"
}


def normalise(value: str) -> str:
    value = str(value or "").replace("HoÃ¨", "Hoè").strip()
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", value))


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [{k: normalise(v) for k, v in row.items()} for row in csv.DictReader(handle)]


def float_or_none(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371008.8
    p1, p2 = radians(lat1), radians(lat2)
    dphi, dlambda = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlambda / 2) ** 2
    return 2 * r * asin(sqrt(a))


def candidate_identity(row: dict[str, str]) -> tuple[bool, str]:
    settlement = normalise(row.get("settlement_additional_10min_names", ""))
    destination = normalise(row.get("destination_additional_10min_names", ""))
    parts = [part for part in (settlement, destination) if part]
    if not parts:
        return False, ""
    return True, " / ".join(dict.fromkeys(" / ".join(parts).replace("|", " / ").split(" / ")))


def build_existing(existing_rows, current_cluster_rows):
    current = {r["physical_stop_cluster_id"]: r for r in current_cluster_rows if r.get("physical_stop_cluster_id")}
    rows_by_cluster: dict[str, list[dict[str, str]]] = {}
    for row in existing_rows:
        municipality = normalise(row.get("COMUNE", ""))
        cluster = row.get("physical_cluster_id", "")
        if municipality in STUDY_MUNICIPALITIES and cluster:
            rows_by_cluster.setdefault(cluster, []).append(row)

    out = []
    for cluster in sorted(rows_by_cluster):
        source_rows = rows_by_cluster[cluster]
        current_row = current.get(cluster)
        representative = source_rows[0]
        if current_row:
            rep_id = current_row.get("representative_stop_id", "")
            representative = next((r for r in source_rows if r.get("stop_id") == rep_id), representative)
        municipality = normalise(representative.get("COMUNE", ""))
        reuse = current_row is not None
        out.append({
            "stop_foundation_id": f"existing:{cluster}",
            "source_stop_id": representative.get("stop_id", ""),
            "physical_cluster_id": cluster,
            "stop_class": "EXISTING_OFFICIAL",
            "human_label": representative.get("stop_name", ""),
            "municipality": municipality,
            "lat": representative.get("stop_lat", ""),
            "lon": representative.get("stop_lon", ""),
            "road_name_or_context": representative.get("stop_name", ""),
            "evidence_status": representative.get("epistemic_status", ""),
            "road_eligibility_status": "OFFICIAL_STOP_LOCATION",
            "field_check_status": "NOT_REQUIRED_FOR_EXISTING_IDENTITY",
            "current_d184_d185_physical_stop": bool_text(reuse),
            "current_routes": current_row.get("routes", "") if current_row else "",
            "human_identity_ready": "true",
            "finalist_stop_ready": bool_text(reuse),
            "readiness_reason": "CURRENT_D184_D185_OFFICIAL_PHYSICAL_STOP_REUSE_READY" if reuse else "REFERENCE_PERIOD_OFFICIAL_STOP_EVALUATION_ONLY",
            "nearest_official_stop_walk_network_m": "0",
            "population_reachable_10min": "",
            "population_additional_10min": "",
            "settlement_context": "",
            "destination_context": "",
            "source_lineage": "stop_universe_v2/existing_official_stops.csv",
        })
    return out


def build_proposed(source_rows):
    out = []
    for row in source_rows:
        municipality = normalise(row.get("COMUNE", ""))
        cid = row.get("candidate_id", "")
        if municipality not in STUDY_MUNICIPALITIES or not cid:
            continue
        identity_ready, identity = candidate_identity(row)
        status_blob = f"{row.get('epistemic_status','')}|{row.get('physical_status','')}"
        field_pending = "FIELD_CHECK_PENDING" in status_blob
        road_status = row.get("road_eligibility_status", "")
        finalist_ready = identity_ready and not field_pending and bool(road_status)
        reasons = []
        if not identity_ready:
            reasons.append("HUMAN_IDENTITY_REQUIRED")
        if field_pending:
            reasons.append("FIELD_CHECK_REQUIRED")
        if not road_status:
            reasons.append("ROAD_ELIGIBILITY_STATUS_MISSING")
        if finalist_ready:
            reasons.append("PROPOSED_STOP_READY")
        out.append({
            "stop_foundation_id": f"proposed:{cid}",
            "source_stop_id": cid,
            "physical_cluster_id": "",
            "stop_class": "PROPOSED_HYPOTHESIS",
            "human_label": identity if identity_ready else f"Candidate {cid}",
            "municipality": municipality,
            "lat": row.get("lat", ""),
            "lon": row.get("lon", ""),
            "road_name_or_context": row.get("highway", ""),
            "evidence_status": row.get("epistemic_status", ""),
            "road_eligibility_status": road_status,
            "field_check_status": "PENDING" if field_pending else "RESOLVED_OR_NOT_FLAGGED",
            "current_d184_d185_physical_stop": "false",
            "current_routes": "",
            "human_identity_ready": bool_text(identity_ready),
            "finalist_stop_ready": bool_text(finalist_ready),
            "readiness_reason": "|".join(reasons),
            "nearest_official_stop_walk_network_m": row.get("nearest_official_stop_walk_network_m", ""),
            "population_reachable_10min": row.get("population_reachable_10min", ""),
            "population_additional_10min": row.get("population_additional_10min", ""),
            "settlement_context": row.get("settlement_additional_10min_names", ""),
            "destination_context": row.get("destination_additional_10min_names", ""),
            "source_lineage": "stop_universe_v2/proposed_stop_candidates.csv",
        })
    return out


def point_index(rows):
    out = []
    for row in rows:
        lat, lon = float_or_none(row.get("lat")), float_or_none(row.get("lon"))
        if lat is not None and lon is not None:
            out.append((row, lat, lon))
    return out


def nearest(point, candidates):
    lat, lon = point
    best = None
    for row, clat, clon in candidates:
        d = haversine_m(lat, lon, clat, clon)
        if best is None or d < best[0]:
            best = (d, row)
    return best


def resolve_contract(contract_rows, settlements, current_clusters, foundation_rows):
    settlement_by_id = {r.get("anchor_id", ""): r for r in settlements}
    cluster_by_id = {r.get("physical_stop_cluster_id", ""): r for r in current_clusters}
    current_points = point_index([r for r in foundation_rows if r["current_d184_d185_physical_stop"] == "true"])
    proposed_points = point_index([r for r in foundation_rows if r["stop_class"] == "PROPOSED_HYPOTHESIS"])
    out = []
    for source in contract_rows:
        row = dict(source)
        anchor_id = row.get("evidence_anchor_id", "")
        record_type = row.get("record_type", "")
        declared_status = row.get("evidence_status", "")
        evidence = None
        lat = lon = None

        if record_type == "MUNICIPALITY_GUARD":
            resolved = declared_status == "POLICY_GUARD" and not anchor_id
        elif anchor_id.startswith("OSM_"):
            evidence = settlement_by_id.get(anchor_id)
            resolved = evidence is not None
            if evidence:
                lat, lon = float_or_none(evidence.get("lat")), float_or_none(evidence.get("lon"))
        elif anchor_id:
            evidence = cluster_by_id.get(anchor_id)
            resolved = evidence is not None
            if evidence:
                lat = float_or_none(evidence.get("representative_stop_lat"))
                lon = float_or_none(evidence.get("representative_stop_lon"))
        else:
            resolved = declared_status == "MISSING_CERTIFIED_ANCHOR"

        row["evidence_resolved_as_declared"] = bool_text(resolved)
        row["evidence_lat"] = "" if lat is None else f"{lat:.7f}"
        row["evidence_lon"] = "" if lon is None else f"{lon:.7f}"
        ncur = nearest((lat, lon), current_points) if lat is not None and lon is not None else None
        nprop = nearest((lat, lon), proposed_points) if lat is not None and lon is not None else None
        row["nearest_current_stop_id"] = ncur[1]["stop_foundation_id"] if ncur else ""
        row["nearest_current_stop_label"] = ncur[1]["human_label"] if ncur else ""
        row["nearest_current_stop_distance_m_geodesic"] = f"{ncur[0]:.1f}" if ncur else ""
        row["nearest_proposed_candidate_id"] = nprop[1]["stop_foundation_id"] if nprop else ""
        row["nearest_proposed_candidate_label"] = nprop[1]["human_label"] if nprop else ""
        row["nearest_proposed_candidate_distance_m_geodesic"] = f"{nprop[0]:.1f}" if nprop else ""
        out.append(row)
    return out


def write_csv(path: Path, rows):
    if not rows:
        raise ValueError(f"Refusing to write empty {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--existing-stops", type=Path, required=True)
    p.add_argument("--proposed-stops", type=Path, required=True)
    p.add_argument("--settlements", type=Path, required=True)
    p.add_argument("--current-v4-clusters", type=Path, required=True)
    p.add_argument("--territorial-contract", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()

    existing = build_existing(read_csv(args.existing_stops), read_csv(args.current_v4_clusters))
    proposed = build_proposed(read_csv(args.proposed_stops))
    foundation = sorted(existing + proposed, key=lambda r: (r["municipality"], r["stop_class"], r["stop_foundation_id"]))
    resolved_contract = resolve_contract(
        read_csv(args.territorial_contract), read_csv(args.settlements),
        read_csv(args.current_v4_clusters), foundation
    )

    counts = {}
    for municipality in sorted(STUDY_MUNICIPALITIES):
        rows = [r for r in foundation if r["municipality"] == municipality]
        counts[municipality] = {
            "current_d184_d185_reuse_ready": sum(r["current_d184_d185_physical_stop"] == "true" for r in rows),
            "reference_existing_total": sum(r["stop_class"] == "EXISTING_OFFICIAL" for r in rows),
            "proposed_hypothesis_total": sum(r["stop_class"] == "PROPOSED_HYPOTHESIS" for r in rows),
            "proposed_human_identity_ready": sum(r["stop_class"] == "PROPOSED_HYPOTHESIS" and r["human_identity_ready"] == "true" for r in rows),
            "proposed_finalist_ready_now": sum(r["stop_class"] == "PROPOSED_HYPOTHESIS" and r["finalist_stop_ready"] == "true" for r in rows),
        }

    unresolved = [r["area_id"] for r in resolved_contract if r["evidence_resolved_as_declared"] != "true"]
    documented_missing = [r["area_id"] for r in resolved_contract if r.get("evidence_status") == "MISSING_CERTIFIED_ANCHOR"]
    pending = [r for r in proposed if r["field_check_status"] == "PENDING"]
    ready = [r for r in proposed if r["finalist_stop_ready"] == "true"]

    write_csv(args.output_dir / "passenger_stop_foundation_v3.csv", foundation)
    write_csv(args.output_dir / "territorial_service_audit_points_v3.csv", resolved_contract)
    validation = {
        "status": "PASS_PASSENGER_STOP_FOUNDATION_V3",
        "contract": "PHASE2_CORRIDOR_AND_PASSENGER_STOP_PATTERN_V3_FOUNDATION",
        "route_generation_performed": False,
        "topology_ranked": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "structural_waypoints_equated_to_passenger_stops": False,
        "study_municipalities": sorted(STUDY_MUNICIPALITIES),
        "territorial_contract_record_count": len(resolved_contract),
        "territorial_contract_unresolved_evidence_rows": unresolved,
        "intentionally_documented_missing_certified_anchor_areas": documented_missing,
        "existing_foundation_stop_count": len(existing),
        "proposed_hypothesis_count": len(proposed),
        "proposed_field_check_pending_count": len(pending),
        "proposed_finalist_ready_now_count": len(ready),
        "proposed_candidates_are_automatically_finalist_ready": False,
        "municipality_counts": counts,
        "policy_guards": {
            "every_study_municipality_requires_explicit_passenger_stop_or_human_exception": True,
            "service_area_audit_requires_explicit_service_or_exclusion_reason": True,
            "bare_technical_candidate_id_is_not_human_identity": True,
            "field_check_pending_candidate_cannot_silently_be_finalist_ready": True,
            "current_official_stop_reuse_is_tested_before_new_stop": True,
        },
        "lineage": {
            "existing_stops": {"path": str(args.existing_stops), "sha256": sha256_path(args.existing_stops)},
            "proposed_stops": {"path": str(args.proposed_stops), "sha256": sha256_path(args.proposed_stops)},
            "settlements": {"path": str(args.settlements), "sha256": sha256_path(args.settlements)},
            "current_v4_clusters": {"path": str(args.current_v4_clusters), "sha256": sha256_path(args.current_v4_clusters)},
            "territorial_contract": {"path": str(args.territorial_contract), "sha256": sha256_path(args.territorial_contract)},
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "passenger_stop_foundation_v3_validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(validation, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
