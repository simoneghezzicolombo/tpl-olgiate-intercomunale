#!/usr/bin/env python3
"""Deterministic frozen GTFS↔OSM existing-stop conflation audit.

RT-006 epistemic contract:
- reuse existing physical stop infrastructure first;
- OSM is corroborating physical evidence, not official GTFS truth;
- an identifier/name match cannot override a geographically implausible position;
- distance-only evidence never confirms identity;
- no proposed stop, corridor, passenger pattern or winner is produced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path

import pandas as pd
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GTFS = ROOT / "outputs/phase2/stop_universe_v2/existing_official_stops.csv"
DEFAULT_OSM = ROOT / "data/raw/osm/osm_bus_stops_core.json"
DEFAULT_OUT = ROOT / "outputs/phase2/network_design_method_audit_v3"
UTM = Transformer.from_crs(4326, 32632, always_xy=True)

# A strong textual/ID identity signal still needs spatial plausibility.
REF_CONFIRM_MAX_M = 75.0
EXACT_NAME_CONFIRM_MAX_M = 75.0
EXACT_NAME_REVIEW_MAX_M = 300.0
TOKEN_NAME_MAX_M = 100.0
TOKEN_JACCARD_MIN = 0.60
DISTANCE_REVIEW_MAX_M = 45.0
DISTANCE_UNIQUE_MARGIN_M = 15.0


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def norm_text(value: object) -> str:
    text = "" if value is None or pd.isna(value) else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("hoe'", "hoe").replace("molgora-", "molgora ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def tokens(value: object) -> set[str]:
    low_information = {"bus", "fermata", "stop", "platform", "via", "piazza"}
    return {t for t in norm_text(value).split() if len(t) > 1 and t not in low_information}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def parse_osm(path: Path) -> pd.DataFrame:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for el in payload.get("elements", []):
        tags = el.get("tags") or {}
        if "lat" not in el or "lon" not in el:
            continue
        highway = str(tags.get("highway") or "")
        pt = str(tags.get("public_transport") or "")
        bus = str(tags.get("bus") or "")
        if highway != "bus_stop" and pt not in {"platform", "stop_position"} and bus != "yes":
            continue
        lon, lat = float(el["lon"]), float(el["lat"])
        x, y = UTM.transform(lon, lat)
        rows.append({
            "osm_type": str(el.get("type") or ""),
            "osm_id": str(el.get("id")),
            "osm_lon": lon,
            "osm_lat": lat,
            "osm_x": x,
            "osm_y": y,
            "osm_name": str(tags.get("name") or ""),
            "osm_name_norm": norm_text(tags.get("name")),
            "osm_ref": str(tags.get("ref") or "").strip(),
            "osm_network": str(tags.get("network") or ""),
            "osm_operator": str(tags.get("operator") or ""),
            "osm_public_transport": pt,
            "osm_highway": highway,
            "osm_bus": bus,
            "osm_shelter": str(tags.get("shelter") or ""),
            "osm_bench": str(tags.get("bench") or ""),
            "osm_departures_board": str(tags.get("departures_board") or ""),
            "osm_tactile_paving": str(tags.get("tactile_paving") or ""),
        })
    out = pd.DataFrame(rows)
    if out.empty:
        raise ValueError("Frozen OSM bus-stop extract contains no usable point elements")
    if out["osm_id"].duplicated().any():
        raise ValueError("OSM element IDs are not unique in frozen bus-stop extract")
    return out.sort_values("osm_id").reset_index(drop=True)


def load_gtfs(path: Path) -> tuple[pd.DataFrame, dict[str, dict]]:
    gtfs = pd.read_csv(path, dtype=str).fillna("")
    required = {
        "stop_id", "stop_name", "stop_lon", "stop_lat",
        "official_routes_reference_gtfs", "physical_cluster_id", "stop_code", "COMUNE",
    }
    missing = required - set(gtfs.columns)
    if missing:
        raise ValueError(f"Existing official stop file missing columns: {sorted(missing)}")
    gtfs["stop_lon"] = pd.to_numeric(gtfs["stop_lon"], errors="raise")
    gtfs["stop_lat"] = pd.to_numeric(gtfs["stop_lat"], errors="raise")
    xy = [UTM.transform(float(lon), float(lat)) for lon, lat in zip(gtfs.stop_lon, gtfs.stop_lat)]
    gtfs["gtfs_x"] = [p[0] for p in xy]
    gtfs["gtfs_y"] = [p[1] for p in xy]

    clusters: dict[str, dict] = {}
    for cid, group in gtfs.groupby("physical_cluster_id", sort=True):
        aliases = sorted({str(v) for v in group.stop_name if str(v).strip()})
        refs = sorted({
            str(v).strip()
            for col in ("stop_id", "stop_code")
            for v in group[col]
            if str(v).strip()
        })
        routes: set[str] = set()
        for value in group.official_routes_reference_gtfs:
            routes.update(r for r in str(value).split("|") if r)
        clusters[str(cid)] = {
            "aliases": aliases,
            "norms": sorted({norm_text(v) for v in aliases if norm_text(v)}),
            "refs": refs,
            "routes": sorted(routes),
            "municipalities": sorted({str(v) for v in group.COMUNE if str(v).strip()}),
            "records": group.copy(),
        }
    return gtfs, clusters


def cluster_distance_m(osm_row: pd.Series, cluster: dict) -> float:
    r = cluster["records"]
    dx = r["gtfs_x"].astype(float) - float(osm_row.osm_x)
    dy = r["gtfs_y"].astype(float) - float(osm_row.osm_y)
    return float((dx.pow(2) + dy.pow(2)).pow(0.5).min())


def name_similarity(osm_name: str, cluster: dict) -> tuple[bool, float]:
    n = norm_text(osm_name)
    if not n:
        return False, 0.0
    exact = n in set(cluster["norms"])
    score = max((jaccard(tokens(n), tokens(alias)) for alias in cluster["norms"]), default=0.0)
    return exact, float(score)


def classify_one(osm_row: pd.Series, clusters: dict[str, dict]) -> dict:
    ranked = []
    for cid, cluster in clusters.items():
        exact_name, token_score = name_similarity(osm_row.osm_name, cluster)
        ranked.append({
            "cluster_id": cid,
            "distance_m": cluster_distance_m(osm_row, cluster),
            "exact_ref": bool(osm_row.osm_ref and osm_row.osm_ref in set(cluster["refs"])),
            "exact_name": exact_name,
            "token_jaccard": token_score,
        })
    ranked.sort(key=lambda r: (r["distance_m"], r["cluster_id"]))
    nearest = ranked[0]
    second_dist = ranked[1]["distance_m"] if len(ranked) > 1 else math.inf

    exact_refs = sorted(
        (r for r in ranked if r["exact_ref"]),
        key=lambda r: (r["distance_m"], r["cluster_id"]),
    )
    if exact_refs:
        chosen = exact_refs[0]
        status = (
            "CONFIRMED_EXACT_REF_DISTANCE"
            if chosen["distance_m"] <= REF_CONFIRM_MAX_M
            else "CONFLICT_EXACT_REF_DISTANCE_REVIEW"
        )
    else:
        exact_names = sorted(
            (r for r in ranked if r["exact_name"]),
            key=lambda r: (r["distance_m"], r["cluster_id"]),
        )
        if exact_names and exact_names[0]["distance_m"] <= EXACT_NAME_CONFIRM_MAX_M:
            chosen = exact_names[0]
            status = "CONFIRMED_EXACT_NAME_DISTANCE"
        elif exact_names and exact_names[0]["distance_m"] <= EXACT_NAME_REVIEW_MAX_M:
            chosen = exact_names[0]
            status = "PROBABLE_EXACT_NAME_DISTANCE_REVIEW"
        else:
            token_matches = sorted(
                (
                    r for r in ranked
                    if r["token_jaccard"] >= TOKEN_JACCARD_MIN
                    and r["distance_m"] <= TOKEN_NAME_MAX_M
                ),
                key=lambda r: (-r["token_jaccard"], r["distance_m"], r["cluster_id"]),
            )
            if token_matches:
                chosen = token_matches[0]
                status = "PROBABLE_TOKEN_NAME_DISTANCE_REVIEW"
            elif (
                nearest["distance_m"] <= DISTANCE_REVIEW_MAX_M
                and second_dist - nearest["distance_m"] >= DISTANCE_UNIQUE_MARGIN_M
            ):
                chosen = nearest
                status = "PROBABLE_DISTANCE_ONLY_REVIEW"
            else:
                chosen = nearest
                status = "OSM_ONLY_UNMATCHED_REFERENCE_GTFS"

    matched = not status.startswith("OSM_ONLY")
    cluster = clusters[chosen["cluster_id"]]
    return {
        **{k: osm_row[k] for k in osm_row.index if k not in {"osm_x", "osm_y"}},
        "matched_physical_cluster_id": chosen["cluster_id"] if matched else "",
        "match_status": status,
        "match_distance_m": round(float(chosen["distance_m"]), 3),
        "match_exact_ref": bool(chosen["exact_ref"]),
        "match_exact_name": bool(chosen["exact_name"]),
        "match_token_jaccard": round(float(chosen["token_jaccard"]), 4),
        "nearest_gtfs_cluster_id_even_if_unmatched": nearest["cluster_id"],
        "nearest_gtfs_distance_m": round(float(nearest["distance_m"]), 3),
        "second_nearest_gtfs_distance_m": round(float(second_dist), 3) if math.isfinite(second_dist) else "",
        "gtfs_cluster_names": "|".join(cluster["aliases"]) if matched else "",
        "gtfs_cluster_routes": "|".join(cluster["routes"]) if matched else "",
        "gtfs_cluster_municipalities": "|".join(cluster["municipalities"]) if matched else "",
        "epistemic_status": (
            "CROSS_SOURCE_EXISTING_STOP_EVIDENCE"
            if status.startswith("CONFIRMED")
            else "CROSS_SOURCE_MATCH_REQUIRES_REVIEW"
            if "REVIEW" in status
            else "FACT_OSM_OBSERVATION_UNCONFIRMED_BY_REFERENCE_GTFS"
        ),
    }


def build_cluster_summary(gtfs: pd.DataFrame, clusters: dict[str, dict], matches: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cid, cluster in sorted(clusters.items()):
        mm = matches[matches["matched_physical_cluster_id"].eq(cid)]
        confirmed = mm[mm["match_status"].str.startswith("CONFIRMED")]
        review = mm[mm["match_status"].str.contains("REVIEW", regex=False)]
        records = cluster["records"]
        rows.append({
            "physical_cluster_id": cid,
            "gtfs_stop_ids": "|".join(sorted(set(records.stop_id.astype(str)))),
            "gtfs_stop_names": "|".join(cluster["aliases"]),
            "gtfs_routes_reference": "|".join(cluster["routes"]),
            "gtfs_municipalities": "|".join(cluster["municipalities"]),
            "gtfs_record_count": int(len(records)),
            "osm_confirmed_element_count": int(len(confirmed)),
            "osm_review_element_count": int(len(review)),
            "osm_confirmed_ids": "|".join(sorted(confirmed.osm_id.astype(str))) if not confirmed.empty else "",
            "osm_review_ids": "|".join(sorted(review.osm_id.astype(str))) if not review.empty else "",
            "cross_source_status": (
                "GTFS_PLUS_OSM_CONFIRMED" if len(confirmed)
                else "GTFS_PLUS_OSM_REVIEW" if len(review)
                else "GTFS_ONLY_IN_FROZEN_OSM_EXTRACT"
            ),
        })
    return pd.DataFrame(rows).sort_values("physical_cluster_id").reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gtfs", type=Path, default=DEFAULT_GTFS)
    ap.add_argument("--osm", type=Path, default=DEFAULT_OSM)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    for path in (args.gtfs, args.osm):
        if not path.exists():
            raise FileNotFoundError(path)
    args.out.mkdir(parents=True, exist_ok=True)

    gtfs, clusters = load_gtfs(args.gtfs)
    osm = parse_osm(args.osm)
    matches = pd.DataFrame([classify_one(row, clusters) for _, row in osm.iterrows()])
    matches = matches.sort_values(["match_status", "osm_id"]).reset_index(drop=True)
    cluster_summary = build_cluster_summary(gtfs, clusters, matches)

    match_csv = args.out / "existing_stop_gtfs_osm_matches_v3.csv"
    cluster_csv = args.out / "existing_stop_master_clusters_audit_v3.csv"
    validation_path = args.out / "existing_stop_conflation_v3_validation.json"
    matches.to_csv(match_csv, index=False)
    cluster_summary.to_csv(cluster_csv, index=False)

    counts = matches["match_status"].value_counts().sort_index().to_dict()
    confirmed_osm = int(matches["match_status"].str.startswith("CONFIRMED").sum())
    review_osm = int(matches["match_status"].str.contains("REVIEW", regex=False).sum())
    unmatched_osm = int(matches["match_status"].eq("OSM_ONLY_UNMATCHED_REFERENCE_GTFS").sum())
    conflict_osm = int(matches["match_status"].str.startswith("CONFLICT").sum())
    gtfs_confirmed_clusters = int(cluster_summary["cross_source_status"].eq("GTFS_PLUS_OSM_CONFIRMED").sum())

    status = "PASS_EXISTING_STOP_CONFLATION_AUDIT_V3"
    if confirmed_osm == 0 or gtfs_confirmed_clusters == 0:
        status = "FAIL_EXISTING_STOP_CONFLATION_AUDIT_V3"

    validation = {
        "status": status,
        "contract": "EXISTING_STOP_FIRST_CROSS_SOURCE_AUDIT_NOT_ROUTE_SELECTION",
        "inputs": {
            "gtfs_existing_stops": str(args.gtfs.relative_to(ROOT)),
            "gtfs_sha256": sha256(args.gtfs),
            "osm_bus_stops": str(args.osm.relative_to(ROOT)),
            "osm_sha256": sha256(args.osm),
        },
        "counts": {
            "reference_gtfs_records": int(len(gtfs)),
            "reference_gtfs_physical_clusters": int(len(clusters)),
            "frozen_osm_bus_stop_elements": int(len(osm)),
            "osm_confirmed_elements": confirmed_osm,
            "osm_review_elements": review_osm,
            "osm_conflict_elements": conflict_osm,
            "osm_unmatched_elements": unmatched_osm,
            "gtfs_clusters_with_confirmed_osm_evidence": gtfs_confirmed_clusters,
            "gtfs_clusters_without_confirmed_osm_evidence": int(len(clusters) - gtfs_confirmed_clusters),
            "match_status_counts": {str(k): int(v) for k, v in counts.items()},
        },
        "matching_contract": {
            "ref_confirm_max_m": REF_CONFIRM_MAX_M,
            "exact_name_confirm_max_m": EXACT_NAME_CONFIRM_MAX_M,
            "exact_name_review_max_m": EXACT_NAME_REVIEW_MAX_M,
            "token_name_max_m": TOKEN_NAME_MAX_M,
            "token_jaccard_min": TOKEN_JACCARD_MIN,
            "distance_review_max_m": DISTANCE_REVIEW_MAX_M,
            "distance_unique_margin_m": DISTANCE_UNIQUE_MARGIN_M,
            "identity_without_spatial_plausibility_can_confirm": False,
            "distance_only_can_confirm": False,
            "osm_only_promoted_to_official": False,
        },
        "outputs": {
            "matches": str(match_csv.relative_to(ROOT)),
            "matches_sha256": sha256(match_csv),
            "cluster_audit": str(cluster_csv.relative_to(ROOT)),
            "cluster_audit_sha256": sha256(cluster_csv),
        },
        "guards": {
            "proposed_stops_generated": False,
            "passenger_stop_pattern_selected": False,
            "corridor_selected": False,
            "winner_selected": False,
            "osm_is_treated_as_official_gtfs_truth": False,
        },
    }
    validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if status.startswith("FAIL"):
        raise SystemExit(status)
    print(json.dumps(validation, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
