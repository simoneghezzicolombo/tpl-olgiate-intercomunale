#!/usr/bin/env python3
"""Build Phase 2 Current-Service Baseline V4 from official public transit geodata."""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import math
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.phase2_run_access_equity_v2 import load_population_units, sha256_path
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
    haversine_m,
    normalise_official_name,
    validate_official_coordinate,
)

THRESHOLDS = (5, 8, 10, 12)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def deterministic_gzip_writer(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    return raw, gz, text


def read_gtfs_csv(zf: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    try:
        payload = zf.read(name)
    except KeyError as exc:
        raise ValueError(f"Official GTFS missing required {name}") from exc
    text = payload.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def parse_official_gtfs(gtfs_zip: Path):
    with zipfile.ZipFile(gtfs_zip) as zf:
        routes = read_gtfs_csv(zf, "routes.txt")
        trips = read_gtfs_csv(zf, "trips.txt")
        stop_times = read_gtfs_csv(zf, "stop_times.txt")
        stops = read_gtfs_csv(zf, "stops.txt")

    route_ids = {
        row["route_id"]
        for row in routes
        if str(row.get("route_short_name", "")).strip() in ROUTE_SCOPE
        or str(row.get("route_id", "")).strip() in ROUTE_SCOPE
    }
    if not route_ids:
        raise ValueError("Official GTFS has no D184/D185 routes")

    trip_meta: dict[str, tuple[str, str]] = {}
    route_short_by_id = {
        row["route_id"]: str(row.get("route_short_name", "")).strip() or row["route_id"]
        for row in routes
        if row["route_id"] in route_ids
    }
    for row in trips:
        route_id = str(row.get("route_id", "")).strip()
        if route_id not in route_ids:
            continue
        short = route_short_by_id[route_id]
        if short not in ROUTE_SCOPE:
            continue
        trip_id = str(row.get("trip_id", "")).strip()
        direction = str(row.get("direction_id", "")).strip()
        if not trip_id:
            raise ValueError("GTFS trip without trip_id")
        trip_meta[trip_id] = (short, direction)

    stop_meta: dict[str, dict[str, str]] = {}
    for row in stops:
        stop_id = str(row.get("stop_id", "")).strip()
        if stop_id:
            stop_meta[stop_id] = row

    per_trip: dict[str, list[tuple[int, str]]] = {}
    for row in stop_times:
        trip_id = str(row.get("trip_id", "")).strip()
        if trip_id not in trip_meta:
            continue
        stop_id = str(row.get("stop_id", "")).strip()
        if stop_id not in stop_meta:
            raise ValueError(f"GTFS stop_time references unknown stop {stop_id!r}")
        try:
            seq = int(float(str(row.get("stop_sequence", "")).strip()))
        except Exception as exc:
            raise ValueError(f"Invalid stop_sequence for trip {trip_id}") from exc
        per_trip.setdefault(trip_id, []).append((seq, stop_id))

    if not per_trip:
        raise ValueError("No D184/D185 stop_times in official GTFS")

    pattern_by_trip: dict[str, str] = {}
    pattern_members: dict[str, tuple[str, ...]] = {}
    for trip_id in sorted(per_trip):
        route, direction = trip_meta[trip_id]
        ordered = tuple(stop_id for _, stop_id in sorted(per_trip[trip_id]))
        pid = deterministic_pattern_id(route, direction, ordered)
        pattern_by_trip[trip_id] = pid
        if pid in pattern_members and pattern_members[pid] != ordered:
            raise ValueError("Pattern hash collision")
        pattern_members[pid] = ordered

    agg: dict[tuple[str, str, str], dict] = {}
    for trip_id in sorted(per_trip):
        route, direction = trip_meta[trip_id]
        pid = pattern_by_trip[trip_id]
        for seq, stop_id in sorted(per_trip[trip_id]):
            key = (route, direction, stop_id)
            a = agg.setdefault(key, {
                "route_id": route,
                "direction_id": direction,
                "stop_id": stop_id,
                "trip_ids": set(),
                "pattern_ids": set(),
                "sequences": [],
            })
            a["trip_ids"].add(trip_id)
            a["pattern_ids"].add(pid)
            a["sequences"].append(seq)

    directional: list[dict[str, object]] = []
    unique_stops: dict[str, StopForClustering] = {}
    for (route, direction, stop_id), a in sorted(agg.items()):
        sm = stop_meta[stop_id]
        name = str(sm.get("stop_name", "")).strip()
        if not name:
            raise ValueError(f"Official GTFS stop {stop_id} lacks stop_name")
        try:
            lat = float(sm["stop_lat"])
            lon = float(sm["stop_lon"])
        except Exception as exc:
            raise ValueError(f"Official GTFS stop {stop_id} lacks valid coordinates") from exc
        validate_official_coordinate(lat, lon)
        current = StopForClustering(stop_id, name, lat, lon)
        if stop_id in unique_stops and unique_stops[stop_id] != current:
            raise ValueError(f"Conflicting GTFS metadata for stop {stop_id}")
        unique_stops[stop_id] = current
        directional.append({
            "route_id": route,
            "direction_id": direction,
            "stop_id": stop_id,
            "stop_name": name,
            "stop_lat": lat,
            "stop_lon": lon,
            "trip_count": len(a["trip_ids"]),
            "trip_ids": ";".join(sorted(a["trip_ids"])),
            "pattern_count": len(a["pattern_ids"]),
            "pattern_ids": ";".join(sorted(a["pattern_ids"])),
            "min_stop_sequence": min(a["sequences"]),
            "max_stop_sequence": max(a["sequences"]),
        })

    return directional, unique_stops, pattern_members


def load_frozen_stop_clusters(path: Path):
    frozen_by_stop_id: dict[str, str] = {}
    rows_by_id: dict[str, dict[str, str]] = {}
    for row in read_csv(path):
        stop_id = str(row["stop_id"]).strip()
        cluster = str(row["physical_cluster_id"]).strip()
        if not stop_id or not cluster:
            raise ValueError("Frozen official stop missing identity")
        if stop_id in frozen_by_stop_id:
            raise ValueError(f"Duplicate frozen stop_id {stop_id}")
        frozen_by_stop_id[stop_id] = cluster
        rows_by_id[stop_id] = row
    return frozen_by_stop_id, rows_by_id


def crosscheck_exact_frozen_identity(unique_stops, frozen_rows):
    for stop_id, stop in sorted(unique_stops.items()):
        frozen = frozen_rows.get(stop_id)
        if not frozen:
            continue
        flat = float(frozen["stop_lat"])
        flon = float(frozen["stop_lon"])
        distance = haversine_m(stop.stop_lat, stop.stop_lon, flat, flon)
        if distance > 250.0:
            raise ValueError(
                f"Lineage contradiction: exact stop_id {stop_id} moved {distance:.1f} m "
                "between official GTFS evidence and frozen certified stop universe"
            )


def load_existing_walks(path: Path, *, unit_weights: dict[str, float]):
    walks: dict[str, dict[str, float]] = {}
    for line_no, row in enumerate(read_csv(path), start=2):
        cluster = str(row["physical_cluster_id"]).strip()
        unit_id = str(row["population_unit_id"]).strip()
        if unit_id not in unit_weights:
            raise ValueError(f"Unknown population unit at line {line_no}")
        walk_min = float(row["walk_min_to_stop"])
        row_weight = float(row["building_piece_population_model"])
        if not math.isfinite(walk_min) or walk_min < 0 or walk_min > 12.0 + 1e-9:
            raise ValueError(f"Invalid certified walk time at line {line_no}")
        if abs(row_weight - unit_weights[unit_id]) > 1e-9:
            raise ValueError(f"Population weight changed at line {line_no}")
        previous = walks.setdefault(cluster, {}).get(unit_id)
        if previous is None or walk_min < previous:
            walks[cluster][unit_id] = walk_min
    return walks


def cluster_rows(unique_stops, cluster_by_stop, reason_by_stop, directional):
    route_by_stop: dict[str, set[str]] = {}
    pattern_by_stop: dict[str, set[str]] = {}
    for row in directional:
        route_by_stop.setdefault(str(row["stop_id"]), set()).add(str(row["route_id"]))
        pattern_by_stop.setdefault(str(row["stop_id"]), set()).update(
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
            "directional_stop_member_count": len(ms),
            "member_stop_ids": ";".join(s.stop_id for s in ms),
            "member_stop_names": ";".join(s.stop_name for s in ms),
            "member_coordinates": ";".join(f"{s.stop_lat:.6f},{s.stop_lon:.6f}" for s in ms),
            "routes": ";".join(sorted({r for s in ms for r in route_by_stop.get(s.stop_id, set())})),
            "pattern_ids": ";".join(sorted({p for s in ms for p in pattern_by_stop.get(s.stop_id, set())})),
            "clustering_reasons": ";".join(sorted({reason_by_stop[s.stop_id] for s in ms})),
        })
    return out


def write_csv(path: Path, rows: list[dict], fields: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def coverage_by_unit(*, selected_clusters, walks, unit_weights, unit_municipality, municipality_codes):
    best: dict[str, tuple[float, str]] = {}
    for cid in sorted(selected_clusters):
        for uid, minutes in walks.get(cid, {}).items():
            previous = best.get(uid)
            if previous is None or (minutes, cid) < previous:
                best[uid] = (minutes, cid)

    rows = []
    for uid in sorted(unit_weights):
        pair = best.get(uid)
        minutes = pair[0] if pair else None
        cid = pair[1] if pair else ""
        municipality = unit_municipality[uid]
        row = {
            "population_unit_id": uid,
            "PRO_COM_T": municipality_codes[municipality],
            "COMUNE": municipality,
            "building_piece_population_model": f"{unit_weights[uid]:.12f}",
            "min_walk_min_to_v4_structural_stop": "" if minutes is None else f"{minutes:.12f}",
            "nearest_physical_stop_cluster_id": cid,
        }
        for t in THRESHOLDS:
            row[f"covered_{t}m"] = str(minutes is not None and minutes <= t).lower()
        rows.append(row)
    return rows


def write_population_access_gzip(path: Path, rows: list[dict]):
    fields = [
        "population_unit_id", "PRO_COM_T", "COMUNE", "building_piece_population_model",
        "min_walk_min_to_v4_structural_stop", "nearest_physical_stop_cluster_id",
        "covered_5m", "covered_8m", "covered_10m", "covered_12m",
    ]
    raw, gz, text = deterministic_gzip_writer(path)
    try:
        writer = csv.DictWriter(text, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    finally:
        text.close()


def municipality_rows(summaries, *, municipality_totals, municipality_codes):
    out = []
    for municipality in sorted(municipality_totals):
        row = {
            "PRO_COM_T": municipality_codes[municipality],
            "COMUNE": municipality,
            "located_population_model": f"{municipality_totals[municipality]:.12f}",
        }
        for t in THRESHOLDS:
            share = summaries[t].municipality_coverage_share[municipality]
            row[f"coverage_{t}m_share"] = f"{share:.15f}"
            row[f"covered_population_{t}m"] = f"{share * municipality_totals[municipality]:.12f}"
        out.append(row)
    return out


def exact_settlement_anchor(rows, name: str):
    target = normalise_official_name(name)
    matches = [
        row for row in rows
        if str(row.get("anchor_type", "")).strip() == "SETTLEMENT"
        and normalise_official_name(row.get("name", "")) == target
    ]
    if len(matches) > 1:
        raise ValueError(f"Ambiguous exact settlement anchor for {name!r}")
    return matches[0] if matches else None


def named_support_clusters(cluster_records, diagnostic_name: str):
    target = normalise_official_name(diagnostic_name)
    wanted = []
    for row in cluster_records:
        names = [normalise_official_name(v) for v in str(row["member_stop_names"]).split(";")]
        if diagnostic_name == "Centro/Stazione":
            if any("olgiate molgora" in n and "stazione" in n for n in names):
                wanted.append(row["physical_stop_cluster_id"])
        elif diagnostic_name == "Monticello":
            if any("monticello" in n for n in names):
                wanted.append(row["physical_stop_cluster_id"])
        elif target and any(target in n for n in names):
            wanted.append(row["physical_stop_cluster_id"])
    return sorted(set(wanted))


def build_olgiate_diagnostic(anchor_rows, cluster_records, municipality_output):
    olgiate = next((r for r in municipality_output if r["COMUNE"] == "Olgiate Molgora"), None)
    if not olgiate:
        raise ValueError("Olgiate Molgora absent from certified population universe")

    specs = [
        ("Centro/Stazione", "Olgiate Molgora"),
        ("Mondonico", "Mondonico"),
        ("San Zeno", "San Zeno"),
        ("Monticello", "Monticello"),
    ]
    out = []
    for area, anchor_name in specs:
        anchor = exact_settlement_anchor(anchor_rows, anchor_name)
        clusters = named_support_clusters(cluster_records, area)
        contextual_walk = ""
        anchor_id = ""
        anchor_status = "NO_CERTIFIED_SETTLEMENT_ANCHOR"
        if anchor:
            anchor_id = str(anchor["anchor_id"])
            anchor_status = "CERTIFIED_OSM_SETTLEMENT_ANCHOR_AVAILABLE"
            contextual_walk = str(anchor.get("current_walk_min", "")).strip()
        access_status = (
            "NAMED_D184_D185_PHYSICAL_STOP_CLUSTER_SUPPORT"
            if clusters else
            "NO_NAMED_D184_D185_PHYSICAL_STOP_CLUSTER_AT_SETTLEMENT_ANCHOR"
        )
        out.append({
            "area": area,
            "settlement_anchor_id": anchor_id,
            "anchor_status": anchor_status,
            "current_service_accessibility": access_status,
            "useful_physical_stop_clusters": ";".join(clusters),
            "v4_d184_d185_anchor_walk_min": "",
            "all_existing_service_anchor_walk_min_context_only": contextual_walk,
            "walking_coverage_semantics": (
                "D184_D185_SPECIFIC_ANCHOR_WALK_TIME_NOT_MATERIALISED; "
                "CONTEXT_COLUMN_IF_PRESENT_IS_ALL_EXISTING_SERVICE_ONLY"
            ),
            "olgiate_coverage_5m_share": olgiate["coverage_5m_share"],
            "olgiate_coverage_8m_share": olgiate["coverage_8m_share"],
            "olgiate_coverage_10m_share": olgiate["coverage_10m_share"],
            "field_uncertainty": (
                "NO_NEW_ROUTING_OR_COORDINATE_ASSUMPTION; NAMED_STOP_SUPPORT_ONLY. "
                "SAN_ZENO_REMAINS_UNRESOLVED_IF NO CERTIFIED ANCHOR."
            ),
            "used_in_candidate_optimisation": "false",
        })
    return out


def source_manifest_index(path: Path):
    rows = read_csv(path)
    index = {str(r["dataset_id"]): r for r in rows}
    required = {
        "official_gtfs_arriva_addabus_2025_2026",
        "arriva_current_timetable_page_2026_09_04",
        "atp_brivio_temporary_disruption_notice_2026",
    }
    missing = [key for key in required if key not in index or index[key].get("available") != "true"]
    if missing:
        raise ValueError(f"Required official sources unavailable: {missing}")
    for row in rows:
        if row.get("available") == "true" and not row.get("sha256"):
            raise ValueError(f"Available source lacks SHA256: {row.get('dataset_id')}")
    return rows, index


def text_contains_all(path: Path, tokens: tuple[str, ...]) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace").lower()
    return all(token.lower() in text for token in tokens)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gtfs-zip", type=Path, required=True)
    ap.add_argument("--source-provenance", type=Path, required=True)
    ap.add_argument("--current-arriva-page", type=Path, required=True)
    ap.add_argument("--bridge-notice", type=Path, required=True)
    ap.add_argument("--future-arriva-page", type=Path)
    ap.add_argument("--frozen-official-stops", type=Path, required=True)
    ap.add_argument("--existing-catchments", type=Path, required=True)
    ap.add_argument("--population-units", type=Path, required=True)
    ap.add_argument("--settlement-anchors", type=Path, required=True)
    ap.add_argument("--v3-validation", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    args = ap.parse_args()

    for path in [
        args.gtfs_zip, args.source_provenance, args.current_arriva_page, args.bridge_notice,
        args.frozen_official_stops, args.existing_catchments, args.population_units,
        args.settlement_anchors, args.v3_validation,
    ]:
        if not path.is_file():
            raise FileNotFoundError(path)

    _, source_index = source_manifest_index(args.source_provenance)

    if not text_contains_all(args.current_arriva_page, ("d184", "d185", "13 settembre 2026")):
        raise ValueError("Current Arriva timetable page does not certify both routes in the 2026-09-04 validity window")
    if not text_contains_all(args.bridge_notice, ("d185", "4 maggio")):
        raise ValueError("Official bridge notice does not identify D185 in the 2026 temporary disruption")
    future_ok = bool(
        args.future_arriva_page
        and text_contains_all(args.future_arriva_page, ("d184", "d185", "14 settembre 2026"))
    )

    v3 = read_json(args.v3_validation)
    if v3.get("status") != "PASS_CURRENT_SERVICE_ACCESS_LOWER_BOUND_V3":
        raise ValueError("Expected certified V3 baseline input")

    directional, unique_stops, pattern_members = parse_official_gtfs(args.gtfs_zip)
    frozen_by_id, frozen_rows = load_frozen_stop_clusters(args.frozen_official_stops)
    crosscheck_exact_frozen_identity(unique_stops, frozen_rows)
    cluster_by_stop, cluster_reason = cluster_stop_records(
        list(unique_stops.values()), frozen_cluster_by_stop_id=frozen_by_id
    )

    for row in directional:
        sid = str(row["stop_id"])
        row["physical_stop_cluster_id"] = cluster_by_stop[sid]
        row["clustering_reason"] = cluster_reason[sid]
        row["activation_evidence_status"] = activation_status(str(row["route_id"]))
        row["current_reference_date"] = REFERENCE_DATE
        row["temporary_disruption_excluded"] = str(row["route_id"] == "D185").lower()
        row["future_2026_09_14_corroboration"] = (
            "FUTURE_2026_09_14_ROUTE_PUBLISHED_CONTINUITY_ONLY" if future_ok else ""
        )
        row["ridership_evidence"] = "false"

    clusters = cluster_rows(unique_stops, cluster_by_stop, cluster_reason, directional)

    unit_weights, unit_municipality, municipality_totals, municipality_codes = load_population_units(args.population_units)
    walks = load_existing_walks(args.existing_catchments, unit_weights=unit_weights)
    all_route_clusters = {str(r["physical_stop_cluster_id"]) for r in clusters}
    certified_catchment_clusters = {cid for cid in all_route_clusters if cid in walks}
    if not certified_catchment_clusters:
        raise ValueError("No D184/D185 physical cluster has frozen certified catchment evidence")

    v3_clusters = set(v3.get("localized_unique_physical_clusters", []))
    if not v3_clusters.issubset(certified_catchment_clusters):
        raise ValueError(
            "V4 lost one or more V3 certified physical clusters: "
            + ",".join(sorted(v3_clusters - certified_catchment_clusters))
        )

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

    directional_fields = [
        "route_id", "direction_id", "stop_id", "stop_name", "stop_lat", "stop_lon",
        "physical_stop_cluster_id", "clustering_reason", "trip_count", "trip_ids",
        "pattern_count", "pattern_ids", "min_stop_sequence", "max_stop_sequence",
        "activation_evidence_status", "current_reference_date", "temporary_disruption_excluded",
        "future_2026_09_14_corroboration", "ridership_evidence",
    ]
    directional_path = args.outdir / "current_service_directional_stops_v4.csv"
    write_csv(directional_path, directional, directional_fields)

    cluster_fields = [
        "physical_stop_cluster_id", "representative_stop_id", "representative_stop_name",
        "representative_stop_lat", "representative_stop_lon", "directional_stop_member_count",
        "member_stop_ids", "member_stop_names", "member_coordinates", "routes", "pattern_ids",
        "clustering_reasons", "certified_phase2_catchment_available",
    ]
    for row in clusters:
        row["certified_phase2_catchment_available"] = str(
            row["physical_stop_cluster_id"] in certified_catchment_clusters
        ).lower()
    cluster_path = args.outdir / "current_service_physical_stop_clusters_v4.csv"
    write_csv(cluster_path, clusters, cluster_fields)

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
        municipality_path, municipality_output,
        ["PRO_COM_T", "COMUNE", "located_population_model",
         "coverage_5m_share", "covered_population_5m",
         "coverage_8m_share", "covered_population_8m",
         "coverage_10m_share", "covered_population_10m",
         "coverage_12m_share", "covered_population_12m"]
    )

    anchor_rows = read_csv(args.settlement_anchors)
    olgiate_rows = build_olgiate_diagnostic(anchor_rows, clusters, municipality_output)
    olgiate_path = args.outdir / "current_service_olgiate_diagnostic_v4.csv"
    write_csv(
        olgiate_path, olgiate_rows,
        ["area", "settlement_anchor_id", "anchor_status", "current_service_accessibility",
         "useful_physical_stop_clusters", "v4_d184_d185_anchor_walk_min",
         "all_existing_service_anchor_walk_min_context_only", "walking_coverage_semantics",
         "olgiate_coverage_5m_share", "olgiate_coverage_8m_share",
         "olgiate_coverage_10m_share", "field_uncertainty", "used_in_candidate_optimisation"]
    )

    comparison = [
        {"scope": "GLOBAL", "metric": "pdf_timing_rows", "v3": str(v3["target_pdf_stop_rows"]), "v4": "NOT_STOP_UNIVERSE", "notes": "V4 does not treat PDF timing rows as physical-stop universe"},
        {"scope": "GLOBAL", "metric": "localized_pdf_rows", "v3": str(v3["localized_rows"]), "v4": "NOT_APPLICABLE", "notes": "forced PDF matching retired"},
        {"scope": "GLOBAL", "metric": "unresolved_pdf_rows", "v3": str(v3["unresolved_or_unlocalized_rows"]), "v4": "NOT_APPLICABLE", "notes": "V4 unit is official physical stops"},
        {"scope": "GLOBAL", "metric": "directional_route_stop_records", "v3": "", "v4": str(len(directional)), "notes": "aggregated by route+direction+stop_id"},
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
            "notes": "same frozen population units and catchment semantics",
        })
    for mrow in municipality_output:
        code = mrow["PRO_COM_T"]
        name = mrow["COMUNE"]
        for t in (5, 8, 10):
            old = v3["coverage_lower_bound"][str(t)]["municipality_coverage"][code]["coverage_share"]
            comparison.append({
                "scope": name, "metric": f"coverage_{t}m_share",
                "v3": f"{float(old):.15f}", "v4": mrow[f"coverage_{t}m_share"],
                "notes": "municipality comparison on frozen located-building population",
            })
    comparison_path = args.outdir / "current_service_v3_v4_comparison.csv"
    write_csv(comparison_path, comparison, ["scope", "metric", "v3", "v4", "notes"])

    interface = []
    for t in (5, 8, 10):
        interface.append({
            "scope": "GLOBAL", "metric": f"coverage_{t}m_share",
            "CURRENT_D184_D185_V4": f"{summaries[t].coverage_share:.15f}",
            "PRIMARY": "", "RUNNER_UP": "", "selection_status": "NOT_SELECTED",
        })
    for row in municipality_output:
        for t in (5, 8, 10):
            interface.append({
                "scope": row["COMUNE"], "metric": f"coverage_{t}m_share",
                "CURRENT_D184_D185_V4": row[f"coverage_{t}m_share"],
                "PRIMARY": "", "RUNNER_UP": "", "selection_status": "NOT_SELECTED",
            })
    for t in (5, 8, 10):
        interface.append({
            "scope": "GLOBAL", "metric": f"worst_municipality_{t}m_share",
            "CURRENT_D184_D185_V4": f"{summaries[t].worst_municipality_coverage_share:.15f}",
            "PRIMARY": "", "RUNNER_UP": "", "selection_status": "NOT_SELECTED",
        })
    interface_path = args.outdir / "current_service_candidate_comparison_interface_v4.csv"
    write_csv(
        interface_path, interface,
        ["scope", "metric", "CURRENT_D184_D185_V4", "PRIMARY", "RUNNER_UP", "selection_status"]
    )

    provenance_path = args.outdir / "current_service_v4_source_provenance.csv"
    shutil.copyfile(args.source_provenance, provenance_path)

    kml_available = any(
        source_index.get(key, {}).get("available") == "true"
        for key in ("atp_d184_kml_2025", "atp_d185_kml_2025")
    )
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
        "kml_source_official": kml_available,
        "future_2026_09_14_used_as_current": FUTURE_2026_09_14_USED_AS_CURRENT,
        "future_2026_09_14_continuity_corroboration_available": future_ok,
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
        "d185_structural_baseline_role": "HISTORICAL_ORDINARY_NETWORK_STRUCTURE_NOT_2026_09_04_STOP_LEVEL_OPERATIONAL_SNAPSHOT",
        "historical_gtfs_identity_implies_current_trip_activation": False,
        "current_service_evidence_relabelled_as_ridership": CURRENT_SERVICE_EVIDENCE_IS_RIDERSHIP,
        "directional_stop_record_count": len(directional),
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
        "decision_impact_reason": (
            "V4 strengthens current-service reporting evidence without modifying Stage C/D/E/F or selecting a candidate. "
            "PRIMARY/RUNNER_UP do not yet exist, so no certified hard-safeguard contradiction is materialised."
        ),
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
            "gtfs_sha256": sha256_path(args.gtfs_zip),
            "source_provenance_sha256": sha256_path(args.source_provenance),
            "frozen_official_stops_sha256": sha256_path(args.frozen_official_stops),
            "existing_catchments_sha256": sha256_path(args.existing_catchments),
            "population_units_sha256": sha256_path(args.population_units),
            "settlement_anchors_sha256": sha256_path(args.settlement_anchors),
            "v3_validation_sha256": sha256_path(args.v3_validation),
            "directional_stops_sha256": sha256_path(directional_path),
            "physical_clusters_sha256": sha256_path(cluster_path),
            "population_access_sha256": sha256_path(population_path),
            "municipality_access_sha256": sha256_path(municipality_path),
            "olgiate_diagnostic_sha256": sha256_path(olgiate_path),
            "v3_v4_comparison_sha256": sha256_path(comparison_path),
            "candidate_comparison_interface_sha256": sha256_path(interface_path),
            "persisted_source_provenance_sha256": sha256_path(provenance_path),
        },
        "limitations": [
            "The 2025/26 official GTFS certifies stop identity, coordinates, route membership and historical ordinary patterns, not 2026-09-04 trip-level activation.",
            "D184 and D185 current route-level operation is established from the Arriva timetable validity window covering 2026-09-04.",
            "By explicit project policy, the temporary 2026 Brivio bridge diversion is documented but excluded from the D185 structural comparison baseline.",
            "D185 historical ordinary stop identities are therefore not relabelled as CURRENT_2026_09_04 stop-level operations.",
            "Physical clusters lacking frozen Phase 2 catchment evidence remain in the official stop universe but do not receive invented walking catchments.",
            "Olgiate settlement diagnostics do not create new route-specific walking times; contextual all-existing-service anchor values, when present, remain explicitly separate.",
            "Current-service baseline is not certified absolutely complete because route-level current activation does not prove every historical ordinary stop was served on the reference date.",
        ],
    }

    validation_path = args.outdir / "current_service_access_baseline_v4_validation.json"
    validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
