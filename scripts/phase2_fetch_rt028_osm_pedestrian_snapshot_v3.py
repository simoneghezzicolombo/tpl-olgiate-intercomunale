#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re

import pandas as pd
import requests

SNAPSHOT_TIMESTAMP = "2026-09-06T12:00:00Z"
OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
BUFFER_M = 500.0
_OSM_BASE_META_RE = re.compile(rb'<meta\s+osm_base="[^"]+"\s*/>')


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonicalize_overpass_osm_bytes(raw: bytes) -> bytes:
    """Remove Overpass response-time metadata from an otherwise pinned snapshot.

    Historical Overpass queries can return identical OSM entities while changing
    only the root-level ``<meta osm_base=.../>`` value to the server replication
    time at which the response was produced. That field is not part of the
    requested historical OSM state and must not perturb RT-028 input, graph or
    matrix digests.
    """
    matches = list(_OSM_BASE_META_RE.finditer(raw))
    if len(matches) != 1:
        raise RuntimeError(
            "RT-028 expected exactly one volatile Overpass <meta osm_base=.../> element, "
            f"found {len(matches)}"
        )
    match = matches[0]
    return raw[: match.start()] + raw[match.end() :]


def derive_bbox(pop: pd.DataFrame, stops: pd.DataFrame) -> tuple[float, float, float, float]:
    lat = pd.concat([pd.to_numeric(pop["lat"]), pd.to_numeric(stops["lat"])], ignore_index=True)
    lon = pd.concat([pd.to_numeric(pop["lon"]), pd.to_numeric(stops["lon"])], ignore_index=True)
    if lat.isna().any() or lon.isna().any():
        raise ValueError("population/stops contain invalid coordinates")
    mean_lat = math.radians(float(lat.mean()))
    dlat = BUFFER_M / 111_320.0
    dlon = BUFFER_M / (111_320.0 * max(0.2, math.cos(mean_lat)))
    return (
        float(lat.min() - dlat),
        float(lon.min() - dlon),
        float(lat.max() + dlat),
        float(lon.max() + dlon),
    )


def build_query(bbox: tuple[float, float, float, float]) -> str:
    s, w, n, e = bbox
    lines = [
        f'[out:xml][date:"{SNAPSHOT_TIMESTAMP}"][timeout:240];',
        "(",
        f'  way["highway"]({s:.8f},{w:.8f},{n:.8f},{e:.8f});',
        f'  node["barrier"]({s:.8f},{w:.8f},{n:.8f},{e:.8f});',
        f'  way["barrier"]({s:.8f},{w:.8f},{n:.8f},{e:.8f});',
        f'  way["railway"]({s:.8f},{w:.8f},{n:.8f},{e:.8f});',
        f'  way["waterway"]({s:.8f},{w:.8f},{n:.8f},{e:.8f});',
        f'  way["natural"="water"]({s:.8f},{w:.8f},{n:.8f},{e:.8f});',
        f'  way["water"]({s:.8f},{w:.8f},{n:.8f},{e:.8f});',
        ");",
        "(._;>;);",
        "out meta;",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--population", required=True)
    ap.add_argument("--stops", required=True)
    ap.add_argument("--output-osm", required=True)
    ap.add_argument("--output-meta", required=True)
    args = ap.parse_args()

    pop = pd.read_csv(args.population)
    stops = pd.read_csv(args.stops)
    if len(stops) != 36:
        raise ValueError(f"RT-028 requires exactly 36 final stops, got {len(stops)}")

    bbox = derive_bbox(pop, stops)
    query = build_query(bbox)
    query_sha = hashlib.sha256(query.encode("utf-8")).hexdigest()

    response = None
    failures = []
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            r = requests.post(
                endpoint,
                data={"data": query},
                headers={"User-Agent": "tpl-olgiate-research/RT-028"},
                timeout=(15, 300),
            )
            r.raise_for_status()
            if len(r.content) < 1000 or b"<osm" not in r.content[:1000]:
                raise RuntimeError(f"unexpected OSM response size/content: {len(r.content)}")
            response = (endpoint, r.content)
            break
        except Exception as exc:
            failures.append(f"{endpoint}: {type(exc).__name__}: {exc}")
    if response is None:
        raise RuntimeError("all pinned Overpass snapshot endpoints failed: " + " | ".join(failures))

    endpoint, response_bytes = response
    canonical_osm = canonicalize_overpass_osm_bytes(response_bytes)
    out = Path(args.output_osm)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(canonical_osm)
    osm_sha = sha256_bytes(canonical_osm)
    meta = {
        "contract": "RT028_OSM_PEDESTRIAN_SNAPSHOT_V3",
        "snapshot_timestamp": SNAPSHOT_TIMESTAMP,
        "overpass_endpoint_used": endpoint,
        "fallback_failures_before_success": failures,
        "bbox_south_west_north_east": [round(x, 8) for x in bbox],
        "bbox_rule": "union of RT-016 population-unit coordinates and frozen 36 stop coordinates + 500 m metric-equivalent buffer",
        "query": query,
        "query_sha256": query_sha,
        "osm_snapshot_sha256": osm_sha,
        "osm_snapshot_bytes": len(canonical_osm),
        "overpass_response_bytes_before_canonicalization": len(response_bytes),
        "overpass_volatile_osm_base_removed": True,
        "canonicalization_rule": "REMOVE_ROOT_META_OSM_BASE_RESPONSE_TIME_ONLY",
        "selectors": [
            "highway",
            "barrier nodes/ways",
            "railway ways",
            "waterway ways",
            "natural=water ways",
            "water=* ways",
        ],
        "municipal_boundaries_used_as_routing_barriers": False,
    }
    Path(args.output_meta).write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(meta, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
