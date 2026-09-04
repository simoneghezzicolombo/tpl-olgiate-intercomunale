#!/usr/bin/env python3
"""Certify the walking-access bridge for the Olgiate-Calco-Brivio hub.

Structural scenarios use the frozen rail anchor `rail:S01514` as their public
service hub. Walking catchments, however, are materialised for official bus-stop
physical clusters. This builder finds the unique official Olgiate station bus
stop within 100 m of the frozen rail anchor and records its physical cluster as
the passenger-access proxy for the hub. It does not assert current service or
move either source coordinate.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

STATUS = "PASS_HUB_ACCESS_BRIDGE_V2_BUILD"
CONTRACT = "PHASE2_HUB_ACCESS_BRIDGE_V2"
HUB_ID = "rail:S01514"
MAX_BRIDGE_DISTANCE_M = 100.0


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return 2.0 * r * math.asin(math.sqrt(a))


def is_station_stop(name: str, municipality: str) -> bool:
    text = " ".join(name.lower().replace(".", " ").replace("'", " ").split())
    municipality_text = " ".join(municipality.lower().split())
    return municipality_text == "olgiate molgora" and "olgiate" in text and "stazione" in text


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--routing-membership", type=Path, required=True)
    p.add_argument("--existing-stops", type=Path, required=True)
    p.add_argument("--existing-catchments", type=Path, required=True)
    p.add_argument("--matrix-validation", type=Path, required=True)
    p.add_argument("--stop-validation", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()

    matrix = json.loads(args.matrix_validation.read_text(encoding="utf-8"))
    stop_validation = json.loads(args.stop_validation.read_text(encoding="utf-8"))
    if matrix.get("status") != "PASS_REDUCED_PATH_MATRIX_V2_BUILD":
        raise ValueError("Reduced Path Matrix V2 is not certified")
    if stop_validation.get("status") != "PASS_STOP_UNIVERSE_V2_BUILD":
        raise ValueError("Stop Universe V2 is not certified")
    if matrix.get("lineage", {}).get("routing_anchor_membership_sha256") != sha256_path(args.routing_membership):
        raise ValueError("Routing membership hash mismatch")
    if matrix.get("lineage", {}).get("existing_stops_sha256") != sha256_path(args.existing_stops):
        raise ValueError("Existing stops hash mismatch")

    membership = rows(args.routing_membership)
    hubs = [r for r in membership if r.get("source_anchor_id") == HUB_ID and r.get("source_kind") == "HUB_RAIL"]
    if len(hubs) != 1:
        raise ValueError(f"Expected one frozen hub membership row, got {len(hubs)}")
    hub = hubs[0]
    if hub.get("evidence_status") != "FACT_FROZEN_GATE_D_RAIL_ANCHOR":
        raise ValueError("Hub lost frozen Gate-D FACT evidence")
    hub_lat = float(hub["lat"])
    hub_lon = float(hub["lon"])

    candidates = []
    for stop in rows(args.existing_stops):
        if not is_station_stop(stop.get("stop_name", ""), stop.get("COMUNE", "")):
            continue
        if not stop.get("epistemic_status", "").startswith("FACT_OFFICIAL_GTFS_"):
            continue
        distance = haversine_m(hub_lat, hub_lon, float(stop["stop_lat"]), float(stop["stop_lon"]))
        if distance <= MAX_BRIDGE_DISTANCE_M + 1e-9:
            candidates.append((distance, stop))
    if len(candidates) != 1:
        raise ValueError(
            f"Hub access bridge requires exactly one official Olgiate station stop within {MAX_BRIDGE_DISTANCE_M} m; got {[(d, r.get('stop_id')) for d, r in candidates]}"
        )
    distance, stop = candidates[0]
    cluster = stop["physical_cluster_id"].strip()
    if not cluster:
        raise ValueError("Selected station stop lacks physical cluster")

    catchment_clusters = set()
    with args.existing_catchments.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            catchment_clusters.add(row["physical_cluster_id"].strip())
    if cluster not in catchment_clusters:
        raise ValueError(f"Hub bridge cluster {cluster} lacks certified walking catchment")

    report = {
        "status": STATUS,
        "contract": CONTRACT,
        "hub_anchor_id": HUB_ID,
        "hub_lat": hub_lat,
        "hub_lon": hub_lon,
        "hub_evidence_status": hub["evidence_status"],
        "boarding_access_proxy_stop_id": stop["stop_id"],
        "boarding_access_proxy_stop_name": stop["stop_name"],
        "boarding_access_proxy_physical_cluster_id": cluster,
        "boarding_access_proxy_stop_lat": float(stop["stop_lat"]),
        "boarding_access_proxy_stop_lon": float(stop["stop_lon"]),
        "boarding_access_proxy_evidence_status": stop["epistemic_status"],
        "straight_line_bridge_distance_m": distance,
        "maximum_allowed_bridge_distance_m": MAX_BRIDGE_DISTANCE_M,
        "selection_rule": "UNIQUE_OFFICIAL_GTFS_OLGIATE_STATION_STOP_WITHIN_100M_OF_FROZEN_RAIL_ANCHOR",
        "current_service_activation_asserted": False,
        "coordinates_modified": False,
        "walking_catchment_recomputed": False,
        "semantics": "PASSENGER_BOARDING_ACCESS_PROXY_FOR_STRUCTURAL_HUB_ONLY",
        "lineage": {
            "routing_membership_sha256": sha256_path(args.routing_membership),
            "existing_stops_sha256": sha256_path(args.existing_stops),
            "existing_catchments_sha256": sha256_path(args.existing_catchments),
            "matrix_validation_sha256": sha256_path(args.matrix_validation),
            "stop_validation_sha256": sha256_path(args.stop_validation),
            "epoch_id": matrix["epoch_id"],
        },
        "epistemic_note": (
            "The structural hub and the official bus stop remain distinct source records. The official station bus-stop cluster is used only to supply an already-certified walking catchment to the hub boarding event because every Phase 2 structural public route starts at rail:S01514. This does not assert that historical GTFS service is currently active."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
