#!/usr/bin/env python3
"""Gate D road/route integrity pipeline.

Build a directed bus-routing graph from the real OSM highway extract and calculate
candidate-route geometry, distance and modelled running time without accepting
pre-computed metrics from candidate definitions.

Candidate waypoint coordinates are design inputs and therefore ASSUMPTION unless
an upstream Gate C process marks them as FACT/RECONSTRUCTED from official GTFS.
Distances are DERIVED from OSM geometry. Running times are MODEL OUTPUT because
OSM does not provide observed bus running times for every road segment.
"""
from __future__ import annotations

import argparse
import ast
import math
import re
from pathlib import Path

import geopandas as gpd
import networkx as nx
import pandas as pd
from shapely.geometry import LineString

OSM_HIGHWAYS = Path("data/raw/osm/osm_highways_core.geojson")
OUT_METRICS = Path("outputs/gate_d_route_metrics.csv")
OUT_GEOMETRY = Path("outputs/gate_d_route_geometry.geojson")

# These are explicit modelling assumptions, never observations.
DEFAULT_SPEED_KMH = {
    "motorway": 60.0,
    "trunk": 50.0,
    "primary": 40.0,
    "secondary": 35.0,
    "tertiary": 30.0,
    "unclassified": 25.0,
    "residential": 22.0,
    "living_street": 12.0,
    "service": 15.0,
}
BUS_HIGHWAYS = set(DEFAULT_SPEED_KMH)
ACCESS_DENY = {"no", "private", "agricultural", "forestry"}


def parse_other_tags(value) -> dict[str, str]:
    """Parse GDAL OSM ``other_tags`` strings into a small dict."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return {}
    text = str(value)
    pairs = re.findall(r'"([^\"]+)"=>"([^\"]*)"', text)
    return dict(pairs)


def normalize_bool(value: str | None) -> bool:
    return str(value or "").lower() in {"yes", "1", "true", "-1"}


def parse_speed_kmh(tags: dict[str, str], highway: str) -> tuple[float, str]:
    raw = tags.get("maxspeed")
    if raw:
        m = re.search(r"(\d+(?:\.\d+)?)", raw)
        if m:
            speed = float(m.group(1))
            if "mph" in raw.lower():
                speed *= 1.609344
            # Route running speed cannot be assumed equal to legal maximum.
            return max(8.0, speed * 0.70), "MODEL OUTPUT_FROM_OSM_MAXSPEED"
    return DEFAULT_SPEED_KMH[highway], "ASSUMPTION_BY_HIGHWAY_CLASS"


def bus_eligibility(row) -> tuple[bool, list[str]]:
    highway = str(row.get("highway") or "")
    if highway not in BUS_HIGHWAYS:
        return False, [f"highway={highway or 'missing'}"]
    tags = parse_other_tags(row.get("other_tags"))
    if tags.get("access") in ACCESS_DENY or tags.get("bus") == "no" or tags.get("psv") == "no":
        return False, ["explicit_access_restriction"]
    uncertain = []
    for key in ("maxheight", "maxweight", "maxwidth", "width", "lanes"):
        if key not in tags:
            uncertain.append(f"missing_{key}")
    return True, uncertain


def endpoint_key(x: float, y: float, ndigits: int = 2) -> tuple[float, float]:
    return round(float(x), ndigits), round(float(y), ndigits)


def build_bus_graph(highways: gpd.GeoDataFrame) -> nx.MultiDiGraph:
    if highways.crs is None:
        raise ValueError("OSM highway extract has no CRS")
    roads = highways.to_crs(32632).explode(index_parts=False, ignore_index=True)
    graph = nx.MultiDiGraph()
    for idx, row in roads.iterrows():
        geom = row.geometry
        if not isinstance(geom, LineString) or geom.is_empty or len(geom.coords) < 2:
            continue
        eligible, uncertainty = bus_eligibility(row)
        if not eligible:
            continue
        highway = str(row.get("highway"))
        tags = parse_other_tags(row.get("other_tags"))
        speed_kmh, speed_status = parse_speed_kmh(tags, highway)
        length_m = float(geom.length)
        if length_m <= 0:
            continue
        minutes = length_m / (speed_kmh * 1000.0 / 60.0)
        start = endpoint_key(*geom.coords[0])
        end = endpoint_key(*geom.coords[-1])
        attrs = {
            "source_index": int(idx),
            "highway": highway,
            "length_m": length_m,
            "running_minutes": minutes,
            "speed_kmh": speed_kmh,
            "speed_status": speed_status,
            "uncertainty_flags": "|".join(uncertainty),
            "geometry": geom,
        }
        oneway = normalize_bool(tags.get("oneway"))
        graph.add_edge(start, end, **attrs)
        if not oneway:
            reverse = LineString(list(geom.coords)[::-1])
            graph.add_edge(end, start, **{**attrs, "geometry": reverse})
    if graph.number_of_edges() == 0:
        raise ValueError("No bus-eligible OSM road edges were built")
    return graph


def nearest_node(graph: nx.MultiDiGraph, x: float, y: float) -> tuple[float, float]:
    return min(graph.nodes, key=lambda n: (n[0] - x) ** 2 + (n[1] - y) ** 2)


def route_candidate(graph: nx.MultiDiGraph, waypoints: gpd.GeoDataFrame, candidate_id: str) -> tuple[dict, LineString]:
    candidate = waypoints[waypoints["candidate_id"] == candidate_id].sort_values("sequence")
    if len(candidate) < 2:
        raise ValueError(f"{candidate_id}: at least two ordered waypoints required")
    projected = candidate.to_crs(32632)
    nodes = [nearest_node(graph, p.x, p.y) for p in projected.geometry]
    edge_geoms = []
    route_m = 0.0
    route_min = 0.0
    uncertain_m = 0.0
    assumed_speed_m = 0.0
    for a, b in zip(nodes[:-1], nodes[1:]):
        path = nx.shortest_path(graph, a, b, weight="running_minutes")
        for u, v in zip(path[:-1], path[1:]):
            candidates = graph.get_edge_data(u, v)
            edge = min(candidates.values(), key=lambda e: e["running_minutes"])
            route_m += edge["length_m"]
            route_min += edge["running_minutes"]
            edge_geoms.append(edge["geometry"])
            if edge["uncertainty_flags"]:
                uncertain_m += edge["length_m"]
            if edge["speed_status"] == "ASSUMPTION_BY_HIGHWAY_CLASS":
                assumed_speed_m += edge["length_m"]
    coords = []
    for geom in edge_geoms:
        part = list(geom.coords)
        if coords and coords[-1] == part[0]:
            coords.extend(part[1:])
        else:
            coords.extend(part)
    geometry = LineString(coords)
    return {
        "candidate_id": candidate_id,
        "route_km": route_m / 1000.0,
        "pure_running_minutes": route_min,
        "uncertain_road_km": uncertain_m / 1000.0,
        "assumed_speed_share": assumed_speed_m / route_m if route_m else 0.0,
        "route_geometry_status": "DERIVED_OSM",
        "distance_status": "DERIVED_OSM",
        "running_time_status": "MODEL OUTPUT",
        "candidate_input_status": ";".join(sorted(set(candidate["epistemic_status"].astype(str)))),
    }, geometry


def validate_waypoints(df: pd.DataFrame) -> None:
    required = {"candidate_id", "sequence", "lat", "lon", "epistemic_status"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Candidate waypoint CSV missing columns: {sorted(missing)}")
    allowed = {"FACT", "RECONSTRUCTED", "ASSUMPTION"}
    bad = set(df["epistemic_status"].astype(str)) - allowed
    if bad:
        raise ValueError(f"Unsupported candidate waypoint epistemic status: {sorted(bad)}")
    if df[["lat", "lon"]].isna().any().any():
        raise ValueError("Candidate waypoint coordinates contain nulls")
    duplicated = df.duplicated(["candidate_id", "sequence"])
    if duplicated.any():
        raise ValueError("Duplicate sequence values inside candidate definitions")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("waypoints_csv", help="Ordered candidate waypoints; coordinates must carry epistemic_status")
    parser.add_argument("--osm", default=str(OSM_HIGHWAYS))
    parser.add_argument("--out-metrics", default=str(OUT_METRICS))
    parser.add_argument("--out-geometry", default=str(OUT_GEOMETRY))
    args = parser.parse_args()

    highways = gpd.read_file(args.osm)
    graph = build_bus_graph(highways)
    raw = pd.read_csv(args.waypoints_csv)
    validate_waypoints(raw)
    points = gpd.GeoDataFrame(raw, geometry=gpd.points_from_xy(raw.lon, raw.lat), crs=4326)

    metrics = []
    geoms = []
    for candidate_id in points["candidate_id"].drop_duplicates():
        row, geometry = route_candidate(graph, points, candidate_id)
        metrics.append(row)
        geoms.append({"candidate_id": candidate_id, "geometry": geometry})

    out_metrics = Path(args.out_metrics)
    out_geometry = Path(args.out_geometry)
    out_metrics.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(metrics).to_csv(out_metrics, index=False)
    gpd.GeoDataFrame(geoms, crs=32632).to_crs(4326).to_file(out_geometry, driver="GeoJSON")
    print(pd.DataFrame(metrics).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
