#!/usr/bin/env python3
"""Gate D structural candidate-route audit.

This script deliberately evaluates the long-run structural road network rather than
the temporary 2026 Brivio bridge closure. It acquires real OSM data in small tiles,
reconstructs the bridge only when official D185 GTFS geometry proves that the
crossing is part of the ordinary bus network, resolves real GTFS/OSM anchors without
hard-coded coordinates, enforces OSM turn restrictions, and computes candidate
geometry/distance from the road graph.

No candidate is recommended here. Mondonico, Arlate, Ravellino, Caprino/Celana and
San Zeno are hypotheses to test. Running time is MODEL_OUTPUT, not observed runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely.geometry import LineString, Point

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_d_route_integrity as routing
import gate_d_turn_restrictions as turn_restrictions

OUT = Path("data/audit_gate_d")
RAW = OUT / "raw"
BBOX = (45.68, 9.31, 45.82, 9.56)  # south, west, north, east
OVERPASS_ENDPOINTS = [
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]
HEADERS = {
    "User-Agent": "tpl-olgiate-gate-d-structural/1.0 (+github.com/simoneghezzicolombo/tpl-olgiate-intercomunale)"
}
EVIDENCE_ROUTES = {"D148", "D150", "D170", "D184", "D185"}
TARGET_ROUTES = {"D184", "D185"}

ANCHOR_SPECS = {
    "FS": {
        "type": "gtfs_stop",
        "aliases": ["Olgiate Molgora - stazione f.s.", "Olgiate Molgora (stazione f.s.)"],
        "preferred_routes": ["D184", "D185"],
    },
    "SCARPONE": {
        "type": "gtfs_stop",
        "aliases": ["Olgiate Molgora - monticello scarpone"],
        "preferred_routes": ["D184"],
    },
    "ROVAGNATE": {
        "type": "gtfs_stop",
        "aliases": ["Rovagnate - la pesa"],
        "preferred_routes": ["D184"],
    },
    "PEREGO": {
        "type": "gtfs_stop",
        "aliases": ["Perego - s.s. 342/via s.caterina"],
        "preferred_routes": ["D184"],
    },
    "SMARIA": {
        "type": "gtfs_stop",
        "aliases": ["S.Maria Hoe'"],
        "preferred_routes": ["D184"],
    },
    "RAVELLINO": {
        "type": "gtfs_stop",
        "aliases": ["Ravellino", "Ravellino - via san rocco"],
        "preferred_routes": ["D184"],
    },
    "CALCO": {
        "type": "gtfs_stop",
        "aliases": ["Calco - via virgilio (pensilina asf)", "Calco - via virgilio"],
        "preferred_routes": ["D185"],
    },
    "BEVERATE": {
        "type": "gtfs_stop",
        "aliases": ["Brivio - beverate (cariplo)"],
        "preferred_routes": ["D185", "D150"],
    },
    "BRIVIO": {
        "type": "gtfs_stop",
        "aliases": ["Brivio - capolinea"],
        "preferred_routes": ["D185", "D150"],
    },
    "ARLATE": {
        "type": "gtfs_stop",
        "aliases": ["Calco - arlate - (provinciale)", "Calco- arlate - (provinciale)"],
        "preferred_routes": ["D150", "D170"],
    },
    "CISANO": {
        "type": "gtfs_stop",
        "aliases": ["Cisano - sosta"],
        "preferred_routes": ["D185"],
    },
    "CAPRINO": {
        "type": "gtfs_stop",
        "aliases": ["Caprino - piazza marconi"],
        "preferred_routes": ["D185"],
    },
    "CELANA": {
        "type": "gtfs_stop",
        "aliases": ["Celana"],
        "preferred_routes": ["D185"],
    },
    "MONDONICO": {
        "type": "osm_named_road",
        "name": "Via Mondonico",
    },
    "SAN_ZENO": {
        "type": "osm_named_road",
        "name": "Piazza San Zeno",
    },
}

CANDIDATES = [
    {
        "candidate_id": "WEST_COMPACT_MONDONICO_CW",
        "family": "WEST_COMPACT_MONDONICO",
        "direction": "CW",
        "anchors": ["FS", "SCARPONE", "ROVAGNATE", "PEREGO", "SMARIA", "MONDONICO", "FS"],
    },
    {
        "candidate_id": "WEST_COMPACT_MONDONICO_CCW",
        "family": "WEST_COMPACT_MONDONICO",
        "direction": "CCW",
        "anchors": ["FS", "MONDONICO", "SMARIA", "PEREGO", "ROVAGNATE", "SCARPONE", "FS"],
    },
    {
        "candidate_id": "EAST_COMPACT_ARLATE_CW",
        "family": "EAST_COMPACT_ARLATE",
        "direction": "CW",
        "anchors": ["FS", "CALCO", "BEVERATE", "BRIVIO", "ARLATE", "FS"],
    },
    {
        "candidate_id": "EAST_COMPACT_ARLATE_CCW",
        "family": "EAST_COMPACT_ARLATE",
        "direction": "CCW",
        "anchors": ["FS", "ARLATE", "BRIVIO", "BEVERATE", "CALCO", "FS"],
    },
    {
        "candidate_id": "WEST_RAVELLINO_EXTENSION",
        "family": "WEST_RAVELLINO_EXTENSION",
        "direction": "SENSITIVITY",
        "anchors": ["FS", "SCARPONE", "ROVAGNATE", "PEREGO", "SMARIA", "RAVELLINO", "MONDONICO", "FS"],
    },
    {
        "candidate_id": "EAST_CAPRINO_CELANA_EXTENSION",
        "family": "EAST_CAPRINO_CELANA_EXTENSION",
        "direction": "SENSITIVITY",
        "anchors": ["FS", "CALCO", "BEVERATE", "BRIVIO", "CISANO", "CAPRINO", "CELANA", "ARLATE", "FS"],
    },
    {
        "candidate_id": "WEST_SAN_ZENO_SENSITIVITY",
        "family": "WEST_SAN_ZENO_SENSITIVITY",
        "direction": "SENSITIVITY",
        "anchors": ["FS", "SAN_ZENO", "SCARPONE", "ROVAGNATE", "PEREGO", "SMARIA", "MONDONICO", "FS"],
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tiles(bbox) -> list[tuple[float, float, float, float]]:
    south, west, north, east = bbox
    mid_lat = (south + north) / 2.0
    mid_lon = (west + east) / 2.0
    return [
        (south, west, mid_lat, mid_lon),
        (south, mid_lon, mid_lat, east),
        (mid_lat, west, north, mid_lon),
        (mid_lat, mid_lon, north, east),
    ]


def _query_tile(tile) -> tuple[dict, str]:
    south, west, north, east = tile
    query = f"""[out:json][timeout:120];
(
  way[\"highway\"]({south},{west},{north},{east});
  relation[\"type\"=\"restriction\"]({south},{west},{north},{east});
);
(._;>;);
out body;"""
    errors = []
    for endpoint in OVERPASS_ENDPOINTS:
        for attempt in range(2):
            try:
                response = requests.post(
                    endpoint,
                    data={"data": query},
                    headers=HEADERS,
                    timeout=180,
                )
                response.raise_for_status()
                payload = response.json()
                if not payload.get("elements"):
                    raise ValueError("empty Overpass tile")
                return payload, endpoint
            except Exception as exc:  # deterministic endpoint fallback; surfaced in summary
                errors.append(f"{endpoint} attempt {attempt + 1}: {exc}")
    raise RuntimeError("Overpass tile failed: " + " | ".join(errors))


def acquire_osm_tiled(raw_path: Path) -> tuple[dict, list[str]]:
    if raw_path.exists() and raw_path.stat().st_size > 0:
        return json.loads(raw_path.read_text(encoding="utf-8")), ["REUSED_EXISTING_RAW_SNAPSHOT"]
    merged = {}
    endpoints_used = []
    for tile in _tiles(BBOX):
        payload, endpoint = _query_tile(tile)
        endpoints_used.append(endpoint)
        for element in payload.get("elements", []):
            key = (str(element.get("type")), int(element.get("id")))
            merged[key] = element
    type_order = {"node": 0, "way": 1, "relation": 2}
    elements = sorted(
        merged.values(),
        key=lambda e: (type_order.get(str(e.get("type")), 9), int(e.get("id"))),
    )
    combined = {
        "version": 0.6,
        "generator": "Gate D tiled Overpass merge",
        "elements": elements,
    }
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(combined, ensure_ascii=False), encoding="utf-8")
    return combined, endpoints_used


def roads_from_payload(payload: dict) -> gpd.GeoDataFrame:
    elements = payload.get("elements", [])
    nodes = {
        int(element["id"]): (float(element["lon"]), float(element["lat"]))
        for element in elements
        if element.get("type") == "node" and "lon" in element and "lat" in element
    }
    rows = []
    for element in elements:
        tags = element.get("tags", {})
        if element.get("type") != "way" or "highway" not in tags:
            continue
        node_ids = element.get("nodes", [])
        coords = [nodes[node_id] for node_id in node_ids if node_id in nodes]
        if len(coords) < 2:
            continue
        row = {
            "osm_way_id": int(element["id"]),
            "highway": tags.get("highway"),
            "geometry": LineString(coords),
        }
        for key in routing.TAG_COLUMNS:
            row[key] = tags.get(key)
        row["other_tags"] = ",".join(
            f'"{key}"=>"{value}"'
            for key, value in tags.items()
            if key not in {"highway", *routing.TAG_COLUMNS}
        )
        rows.append(row)
    roads = gpd.GeoDataFrame(rows, geometry="geometry", crs=4326)
    if roads.empty:
        raise AssertionError("No OSM highways reconstructed from tiled snapshot")
    return roads


def read_gtfs(path: Path, feed_label: str) -> dict[str, pd.DataFrame | str]:
    if not path.exists() or path.stat().st_size == 0:
        raise FileNotFoundError(path)
    with zipfile.ZipFile(path) as zf:
        required = {"routes.txt", "trips.txt", "stops.txt", "stop_times.txt", "shapes.txt"}
        missing = required - set(zf.namelist())
        if missing:
            raise ValueError(f"{feed_label}: GTFS missing {sorted(missing)}")
        data = {
            name[:-4]: pd.read_csv(zf.open(name), dtype=str)
            for name in required
        }
    data["feed_label"] = feed_label
    return data


def route_short_map(feed: dict) -> dict[str, str]:
    routes = feed["routes"]
    short_col = "route_short_name" if "route_short_name" in routes.columns else "route_long_name"
    return dict(zip(routes["route_id"], routes[short_col]))


def shape_lines(feed: dict, route_names: set[str]) -> gpd.GeoDataFrame:
    routes = feed["routes"]
    trips = feed["trips"]
    shapes = feed["shapes"]
    short_map = route_short_map(feed)
    route_ids = {route_id for route_id, short in short_map.items() if short in route_names}
    selected = trips[trips["route_id"].isin(route_ids)].dropna(subset=["shape_id"]).copy()
    rows = []
    for shape_id, group in selected.groupby("shape_id"):
        points = shapes[shapes["shape_id"] == shape_id].copy()
        if len(points) < 2:
            continue
        points["shape_pt_sequence"] = pd.to_numeric(points["shape_pt_sequence"], errors="raise")
        points = points.sort_values("shape_pt_sequence")
        geom = LineString(
            list(zip(points["shape_pt_lon"].astype(float), points["shape_pt_lat"].astype(float)))
        )
        route_id = group["route_id"].mode().iat[0]
        rows.append({
            "feed": feed["feed_label"],
            "route_short_name": short_map[route_id],
            "shape_id": shape_id,
            "trip_count": int(len(group)),
            "geometry": geom,
        })
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=4326)


def _normal(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip().casefold())


def stop_routes(feed: dict, stop_ids: set[str]) -> set[str]:
    stop_times = feed["stop_times"]
    trips = feed["trips"]
    short_map = route_short_map(feed)
    trip_ids = set(stop_times.loc[stop_times["stop_id"].isin(stop_ids), "trip_id"])
    route_ids = set(trips.loc[trips["trip_id"].isin(trip_ids), "route_id"])
    return {short_map[route_id] for route_id in route_ids if route_id in short_map}


def resolve_gtfs_anchor(key: str, spec: dict, feeds: list[dict]) -> dict:
    aliases = {_normal(alias) for alias in spec["aliases"]}
    preferred = set(spec.get("preferred_routes", []))
    candidates = []
    for feed in feeds:
        stops = feed["stops"].copy()
        matches = stops[stops["stop_name"].map(_normal).isin(aliases)].copy()
        if matches.empty:
            continue
        all_ids = set(matches["stop_id"].astype(str))
        served = stop_routes(feed, all_ids)
        if preferred and served & preferred:
            candidates.append((feed, matches, served))
        elif not preferred:
            candidates.append((feed, matches, served))
    if not candidates:
        raise ValueError(f"{key}: no official GTFS stop matches {spec['aliases']}")
    rows = pd.concat([entry[1] for entry in candidates], ignore_index=True)
    lon = float(pd.to_numeric(rows["stop_lon"], errors="raise").mean())
    lat = float(pd.to_numeric(rows["stop_lat"], errors="raise").mean())
    routes = sorted(set().union(*(entry[2] for entry in candidates)))
    return {
        "anchor_id": key,
        "lon": lon,
        "lat": lat,
        "epistemic_status": "FACT",
        "source_type": "OFFICIAL_GTFS_STOP_CLUSTER_CENTROID",
        "source_detail": ";".join(sorted(set(rows["stop_name"].astype(str)))),
        "official_routes_serving": ";".join(routes),
        "source_ids": ";".join(sorted(set(rows["stop_id"].astype(str)))),
    }


def osm_name(row) -> str | None:
    return routing.parse_other_tags(row.get("other_tags")).get("name")


def resolve_osm_road_anchor(key: str, spec: dict, roads: gpd.GeoDataFrame) -> dict:
    named = roads.copy()
    named["_name"] = named.apply(osm_name, axis=1)
    matches = named[named["_name"] == spec["name"]].copy()
    if matches.empty:
        raise ValueError(f"{key}: OSM named road not found: {spec['name']}")
    eligible_mask = matches.apply(lambda row: routing.bus_eligibility(row)[0], axis=1)
    eligible = matches[eligible_mask].copy()
    if eligible.empty:
        raise ValueError(f"{key}: OSM named road exists but has no bus-eligible segment")
    projected = eligible.to_crs(32632)
    lengths = projected.geometry.length
    chosen = projected.loc[lengths.idxmax()]
    point = chosen.geometry.interpolate(0.5, normalized=True)
    point_wgs = gpd.GeoSeries([point], crs=32632).to_crs(4326).iloc[0]
    width_values = sorted({str(v) for v in eligible["width"].dropna().astype(str) if str(v).strip()})
    lanes_values = sorted({str(v) for v in eligible["lanes"].dropna().astype(str) if str(v).strip()})
    return {
        "anchor_id": key,
        "lon": float(point_wgs.x),
        "lat": float(point_wgs.y),
        "epistemic_status": "ASSUMPTION",
        "source_type": "OSM_NAMED_ROAD_DESIGN_ANCHOR",
        "source_detail": spec["name"],
        "official_routes_serving": "",
        "source_ids": ";".join(sorted(set(eligible["osm_way_id"].astype(str)))),
        "osm_highways": ";".join(sorted(set(eligible["highway"].astype(str)))),
        "osm_width_values": ";".join(width_values),
        "osm_lanes_values": ";".join(lanes_values),
    }


def resolve_anchors(feeds: list[dict], roads: gpd.GeoDataFrame) -> pd.DataFrame:
    rows = []
    for key, spec in ANCHOR_SPECS.items():
        if spec["type"] == "gtfs_stop":
            rows.append(resolve_gtfs_anchor(key, spec, feeds))
        elif spec["type"] == "osm_named_road":
            rows.append(resolve_osm_road_anchor(key, spec, roads))
        else:
            raise ValueError(f"Unknown anchor type: {spec['type']}")
    return pd.DataFrame(rows)


def d185_bridge_evidence(
    roads: gpd.GeoDataFrame,
    d185_shapes: gpd.GeoDataFrame,
) -> tuple[pd.Series, dict]:
    bridge_name = roads.apply(
        lambda row: routing.parse_other_tags(row.get("other_tags")).get("bridge:name"), axis=1
    )
    mask = bridge_name == "Ponte di Brivio"
    bridge = roads[mask].copy()
    if bridge.empty:
        raise AssertionError("OSM Ponte di Brivio way not found")
    if d185_shapes.empty:
        raise AssertionError("Official D185 GTFS shape evidence missing")
    bridge_m = bridge.to_crs(32632)
    d185_buffer = d185_shapes.to_crs(32632).geometry.buffer(35).union_all()
    total = float(bridge_m.geometry.length.sum())
    overlap = float(bridge_m.geometry.apply(lambda geom: geom.intersection(d185_buffer).length).sum())
    coverage = 100.0 * overlap / total if total else 0.0
    if coverage < 80.0:
        raise AssertionError(
            f"D185 official GTFS does not sufficiently support Brivio bridge structural reconstruction: {coverage:.1f}%"
        )
    detail = {
        "bridge_way_ids": sorted(bridge["osm_way_id"].astype(int).tolist()),
        "current_osm_highway_values": sorted(set(bridge["highway"].astype(str))),
        "current_osm_maxweight_values": sorted(set(bridge["maxweight"].dropna().astype(str))),
        "d185_gtfs_bridge_coverage_35m_pct": coverage,
    }
    return mask, detail


def structuralize_brivio_bridge(
    roads: gpd.GeoDataFrame,
    d185_shapes: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, dict]:
    mask, detail = d185_bridge_evidence(roads, d185_shapes)
    structural = roads.copy()
    construction_mask = mask & (structural["highway"].astype(str) == "construction")
    restored_ids = structural.loc[construction_mask, "osm_way_id"].astype(int).tolist()
    if restored_ids:
        structural.loc[construction_mask, "highway"] = "primary"
    detail.update({
        "restored_structural_way_ids": sorted(restored_ids),
        "structural_override_status": (
            "RECONSTRUCTED_FROM_FACT_GTFS_D185_AND_OSM_BRIDGE_GEOMETRY"
            if restored_ids else "NO_TEMPORARY_CONSTRUCTION_OVERRIDE_NEEDED"
        ),
        "temporary_2026_closure_used_in_routing": False,
        "weight_interpretation": (
            "UNRESOLVED: OSM maxweight is retained as evidence but not enforced because official D185 GTFS proves ordinary bus use; post-works vehicle eligibility needs authoritative confirmation."
        ),
    })
    return structural, detail


def make_waypoints(anchor_df: pd.DataFrame) -> pd.DataFrame:
    lookup = anchor_df.set_index("anchor_id").to_dict("index")
    rows = []
    for candidate in CANDIDATES:
        for sequence, anchor_id in enumerate(candidate["anchors"], start=1):
            anchor = lookup[anchor_id]
            rows.append({
                "candidate_id": candidate["candidate_id"],
                "family": candidate["family"],
                "direction": candidate["direction"],
                "sequence": sequence,
                "anchor_id": anchor_id,
                "lat": anchor["lat"],
                "lon": anchor["lon"],
                "epistemic_status": anchor["epistemic_status"],
                "source_type": anchor["source_type"],
                "source_detail": anchor["source_detail"],
            })
    return pd.DataFrame(rows)


def node_index(graph) -> tuple[list, np.ndarray]:
    nodes = list(graph.nodes)
    array = np.asarray(nodes, dtype=float)
    return nodes, array


def snap_point(nodes: list, array: np.ndarray, point: Point) -> tuple[tuple[float, float], float]:
    delta = array - np.asarray([point.x, point.y])
    squared = np.einsum("ij,ij->i", delta, delta)
    position = int(np.argmin(squared))
    return nodes[position], float(math.sqrt(squared[position]))


def route_one_candidate(
    graph,
    nodes: list,
    node_array: np.ndarray,
    waypoints: gpd.GeoDataFrame,
    candidate: dict,
    turn_rules: dict,
    evidence_buffer,
    bridge_way_ids: set[int],
    max_snap_m: float = 75.0,
) -> tuple[dict, LineString]:
    points = waypoints[waypoints["candidate_id"] == candidate["candidate_id"]].sort_values("sequence")
    projected = points.to_crs(32632)
    snapped = [snap_point(nodes, node_array, geom) for geom in projected.geometry]
    max_snap = max(distance for _, distance in snapped)
    if max_snap > max_snap_m:
        raise ValueError(
            f"{candidate['candidate_id']}: max waypoint snap {max_snap:.1f} m exceeds {max_snap_m:.1f} m"
        )
    snapped_nodes = [node for node, _ in snapped]
    traversed = []
    for start, end in zip(snapped_nodes[:-1], snapped_nodes[1:]):
        edge_path = routing.shortest_bus_edges(graph, start, end, turn_rules)
        for u, v, edge_key in edge_path:
            traversed.append((u, v, edge_key, graph.get_edge_data(u, v, edge_key)))
    if not traversed:
        raise ValueError(f"{candidate['candidate_id']}: no road edges produced")

    total_m = sum(float(item[3]["length_m"]) for item in traversed)
    total_min = sum(float(item[3]["running_minutes"]) for item in traversed)
    uncertain_m = sum(
        float(item[3]["length_m"]) for item in traversed if item[3].get("uncertainty_flags")
    )
    assumed_m = sum(
        float(item[3]["length_m"])
        for item in traversed
        if item[3].get("speed_status") == "ASSUMPTION_BY_HIGHWAY_CLASS"
    )

    seen = set()
    unique_undirected_m = 0.0
    for u, v, _, data in traversed:
        segment_key = tuple(sorted((u, v)))
        if segment_key not in seen:
            unique_undirected_m += float(data["length_m"])
            seen.add(segment_key)
    repeated_excess_m = max(0.0, total_m - unique_undirected_m)

    coords = []
    for _, _, _, data in traversed:
        part = list(data["geometry"].coords)
        coords.extend(part[1:] if coords and coords[-1] == part[0] else part)
    geometry = LineString(coords)
    coverage_m = float(geometry.intersection(evidence_buffer).length) if evidence_buffer is not None else 0.0

    turn_contexts = 0
    previous_way = None
    for u, _, _, data in traversed:
        if previous_way is not None and (u, previous_way) in turn_rules:
            turn_contexts += 1
        previous_way = data.get("osm_way_id")

    bridge_entries = 0
    previous_bridge = False
    bridge_m = 0.0
    for _, _, _, data in traversed:
        on_bridge = routing.normalize_way_id(data.get("osm_way_id")) in bridge_way_ids
        if on_bridge:
            bridge_m += float(data["length_m"])
        if on_bridge and not previous_bridge:
            bridge_entries += 1
        previous_bridge = on_bridge

    return {
        "candidate_id": candidate["candidate_id"],
        "family": candidate["family"],
        "direction": candidate["direction"],
        "route_km": total_m / 1000.0,
        "pure_running_minutes": total_min,
        "repeated_edge_excess_km": repeated_excess_m / 1000.0,
        "repeated_edge_excess_pct": 100.0 * repeated_excess_m / total_m if total_m else 0.0,
        "official_bus_shape_coverage_30m_pct": 100.0 * coverage_m / total_m if total_m else 0.0,
        "uncertain_road_km": uncertain_m / 1000.0,
        "assumed_speed_share": assumed_m / total_m if total_m else 0.0,
        "max_waypoint_snap_m": max_snap,
        "turn_restriction_contexts_on_route": turn_contexts,
        "bridge_entries": bridge_entries,
        "bridge_km": bridge_m / 1000.0,
        "temporary_brivio_closure_used": False,
        "distance_status": "DERIVED_OSM_STRUCTURAL",
        "running_time_status": "MODEL_OUTPUT",
        "turn_restrictions_status": "ENFORCED_OSM",
        "candidate_status": "HYPOTHESIS_NOT_RECOMMENDATION",
        "epistemic_status": "PROVISIONAL_UNTIL_GATE_C_FOR_GTFS_ANCHOR_INTERPRETATION",
    }, geometry


def hhmmss_minutes(value: str) -> float:
    hour, minute, second = [int(piece) for piece in str(value).split(":")]
    return hour * 60 + minute + second / 60.0


def representative_gtfs_patterns(feed: dict, route_name: str) -> list[dict]:
    routes = feed["routes"]
    trips = feed["trips"]
    stop_times = feed["stop_times"]
    shapes = feed["shapes"]
    short_map = route_short_map(feed)
    route_ids = {route_id for route_id, short in short_map.items() if short == route_name}
    target_trips = trips[trips["route_id"].isin(route_ids)].copy()
    rows = []
    for direction_value, direction_trips in target_trips.groupby(target_trips.get("direction_id", pd.Series(index=target_trips.index, dtype=str)).fillna("NA")):
        patterns = Counter()
        pattern_trip = {}
        for trip_id in direction_trips["trip_id"]:
            group = stop_times[stop_times["trip_id"] == trip_id].copy()
            if group.empty:
                continue
            group["stop_sequence"] = pd.to_numeric(group["stop_sequence"], errors="raise")
            group = group.sort_values("stop_sequence")
            pattern = tuple(group["stop_id"].astype(str))
            patterns[pattern] += 1
            pattern_trip.setdefault(pattern, trip_id)
        if not patterns:
            continue
        pattern, count = patterns.most_common(1)[0]
        trip_id = pattern_trip[pattern]
        group = stop_times[stop_times["trip_id"] == trip_id].copy()
        group["stop_sequence"] = pd.to_numeric(group["stop_sequence"], errors="raise")
        group = group.sort_values("stop_sequence")
        runtime = hhmmss_minutes(group.iloc[-1]["arrival_time"]) - hhmmss_minutes(group.iloc[0]["departure_time"])
        trip = target_trips[target_trips["trip_id"] == trip_id].iloc[0]
        shape_id = trip.get("shape_id")
        shape_km = None
        if pd.notna(shape_id):
            points = shapes[shapes["shape_id"] == shape_id].copy()
            if len(points) >= 2:
                points["shape_pt_sequence"] = pd.to_numeric(points["shape_pt_sequence"], errors="raise")
                points = points.sort_values("shape_pt_sequence")
                geom = gpd.GeoSeries(
                    [LineString(list(zip(points["shape_pt_lon"].astype(float), points["shape_pt_lat"].astype(float))))],
                    crs=4326,
                ).to_crs(32632).iloc[0]
                shape_km = float(geom.length) / 1000.0
        rows.append({
            "route_short_name": route_name,
            "direction_id": direction_value,
            "representative_trip_id": trip_id,
            "pattern_trip_count": int(count),
            "stop_count": int(len(group)),
            "scheduled_terminal_to_terminal_min": runtime,
            "gtfs_shape_km": shape_km,
            "epistemic_status": "FACT_GTFS_PROVISIONAL_UNTIL_GATE_C",
        })
    return rows


def build_summary(metrics: pd.DataFrame, bridge_detail: dict, turn_summary: dict, acquisition: dict) -> dict:
    lookup = metrics.set_index("candidate_id")
    west_cw = lookup.loc["WEST_COMPACT_MONDONICO_CW"]
    west_ccw = lookup.loc["WEST_COMPACT_MONDONICO_CCW"]
    east_cw = lookup.loc["EAST_COMPACT_ARLATE_CW"]
    east_ccw = lookup.loc["EAST_COMPACT_ARLATE_CCW"]
    compact_mean_km = (
        (float(west_cw["route_km"]) + float(west_ccw["route_km"])) / 2.0
        + (float(east_cw["route_km"]) + float(east_ccw["route_km"])) / 2.0
    )
    compact_mean_minutes = (
        (float(west_cw["pure_running_minutes"]) + float(west_ccw["pure_running_minutes"])) / 2.0
        + (float(east_cw["pure_running_minutes"]) + float(east_ccw["pure_running_minutes"])) / 2.0
    )
    return {
        "verdict": "PROVISIONAL",
        "gate_b_status": "PASS",
        "gate_c_dependency": "PROVISIONAL_ONLY_FOR_GTFS_SERVICE_AND_ANCHOR_INTERPRETATION",
        "analysis_network": "STRUCTURAL_NETWORK",
        "temporary_brivio_closure_used_in_candidate_routing": False,
        "compact_double_loop_mean_km": compact_mean_km,
        "compact_double_loop_mean_pure_running_minutes_model": compact_mean_minutes,
        "west_directional_km_difference": abs(float(west_cw["route_km"]) - float(west_ccw["route_km"])),
        "east_directional_km_difference": abs(float(east_cw["route_km"]) - float(east_ccw["route_km"])),
        "ravellino_extension_km": float(lookup.loc["WEST_RAVELLINO_EXTENSION", "route_km"]),
        "caprino_celana_extension_km": float(lookup.loc["EAST_CAPRINO_CELANA_EXTENSION", "route_km"]),
        "san_zeno_sensitivity_km": float(lookup.loc["WEST_SAN_ZENO_SENSITIVITY", "route_km"]),
        "bridge_structural_evidence": bridge_detail,
        "turn_restrictions": turn_summary,
        "osm_acquisition": acquisition,
        "calco_superiore_status": "NOT_TESTED_NO_UNIQUE_TRACEABLE_ANCHOR_YET",
        "remaining_physical_checks": [
            "Mondonico bus width / swept-path / meeting clearance because OSM has motor access but lacks decisive bus geometry dimensions",
            "San Zeno operational turning and one-way feasibility; sensitivity only",
            "Brivio bridge post-works authoritative vehicle/mass eligibility because OSM maxweight evidence conflicts with ordinary D185 GTFS use",
        ],
        "note": "No Pareto or recommendation conclusion is produced by Gate D.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--osm-json", default=str(RAW / "osm_gate_d_context.json"))
    parser.add_argument("--arriva-gtfs", default=str(RAW / "arriva_addabus_2025_2026.zip"))
    parser.add_argument("--lineelecco-gtfs", default=str(RAW / "lineelecco_2025_2026.zip"))
    parser.add_argument("--out-dir", default=str(OUT))
    args = parser.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    raw_path = Path(args.osm_json)
    payload, endpoints = acquire_osm_tiled(raw_path)
    roads = roads_from_payload(payload)
    roads.to_file(out / "osm_gate_d_context.geojson", driver="GeoJSON")

    feeds = [
        read_gtfs(Path(args.arriva_gtfs), "ARRIVA_ADDABUS"),
        read_gtfs(Path(args.lineelecco_gtfs), "LINEE_LECCO"),
    ]
    all_shapes = []
    for feed in feeds:
        shapes = shape_lines(feed, EVIDENCE_ROUTES)
        if not shapes.empty:
            all_shapes.append(shapes)
    evidence_shapes = pd.concat(all_shapes, ignore_index=True) if all_shapes else pd.DataFrame()
    evidence_shapes = gpd.GeoDataFrame(evidence_shapes, geometry="geometry", crs=4326)
    d185_shapes = evidence_shapes[evidence_shapes["route_short_name"] == "D185"].copy()

    structural_roads, bridge_detail = structuralize_brivio_bridge(roads, d185_shapes)
    structural_roads.to_file(out / "osm_gate_d_structural.geojson", driver="GeoJSON")

    restriction_df, restriction_summary = turn_restrictions.resolve_restrictions(payload)
    restriction_path = out / "osm_turn_restrictions_routable.csv"
    restriction_df.to_csv(restriction_path, index=False)
    (out / "osm_turn_restrictions_summary.json").write_text(
        json.dumps(restriction_summary, indent=2), encoding="utf-8"
    )

    graph = routing.build_bus_graph(structural_roads)
    turn_rules = routing.load_turn_restrictions(restriction_path)
    active_turn_rule_keys = sum(1 for via, _ in turn_rules if via in graph)

    anchor_df = resolve_anchors(feeds, structural_roads)
    anchor_df.to_csv(out / "structural_anchor_evidence.csv", index=False)
    waypoint_df = make_waypoints(anchor_df)
    waypoint_df.to_csv(out / "structural_candidate_waypoints.csv", index=False)
    waypoints = gpd.GeoDataFrame(
        waypoint_df,
        geometry=gpd.points_from_xy(waypoint_df["lon"], waypoint_df["lat"]),
        crs=4326,
    )

    if evidence_shapes.empty:
        evidence_buffer = None
    else:
        evidence_buffer = evidence_shapes.to_crs(32632).geometry.buffer(30).union_all()

    nodes, array = node_index(graph)
    bridge_way_ids = {int(value) for value in bridge_detail["bridge_way_ids"]}
    metric_rows = []
    geometry_rows = []
    for candidate in CANDIDATES:
        row, geometry = route_one_candidate(
            graph,
            nodes,
            array,
            waypoints,
            candidate,
            turn_rules,
            evidence_buffer,
            bridge_way_ids,
        )
        metric_rows.append(row)
        geometry_rows.append({
            "candidate_id": candidate["candidate_id"],
            "family": candidate["family"],
            "direction": candidate["direction"],
            "geometry": geometry,
        })

    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(out / "structural_candidate_metrics.csv", index=False)
    gpd.GeoDataFrame(geometry_rows, geometry="geometry", crs=32632).to_crs(4326).to_file(
        out / "structural_candidate_geometry.geojson", driver="GeoJSON"
    )

    baseline_rows = []
    for feed in feeds:
        for route in TARGET_ROUTES:
            baseline_rows.extend(representative_gtfs_patterns(feed, route))
    baselines = pd.DataFrame(baseline_rows)
    baselines.to_csv(out / "structural_gtfs_baseline_patterns.csv", index=False)

    acquisition = {
        "bbox": {"south": BBOX[0], "west": BBOX[1], "north": BBOX[2], "east": BBOX[3]},
        "overpass_endpoints_used": endpoints,
        "raw_osm_sha256": sha256(raw_path),
        "raw_osm_elements": int(len(payload.get("elements", []))),
        "osm_highway_ways": int(len(roads)),
        "structural_graph_nodes": int(graph.number_of_nodes()),
        "structural_graph_directed_edges": int(graph.number_of_edges()),
        "turn_rule_keys_loaded": int(len(turn_rules)),
        "turn_rule_keys_matching_graph_nodes": int(active_turn_rule_keys),
    }
    summary = build_summary(metrics, bridge_detail, restriction_summary, acquisition)
    (out / "structural_candidate_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    print(json.dumps(summary, indent=2))
    print("\n--- STRUCTURAL CANDIDATES ---")
    print(metrics.to_string(index=False))
    print("\n--- ANCHOR EVIDENCE ---")
    print(anchor_df.to_string(index=False))
    if not baselines.empty:
        print("\n--- GTFS BASELINE PATTERNS ---")
        print(baselines.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
