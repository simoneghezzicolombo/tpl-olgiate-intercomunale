#!/usr/bin/env python3
"""Gate D road/route integrity pipeline.

Build a directed bus-routing graph from a real OSM highway extract and calculate
candidate-route geometry, distance and modelled running time without accepting
pre-computed route metrics.

Candidate waypoint coordinates are design inputs and therefore ASSUMPTION unless
an upstream process marks them FACT/RECONSTRUCTED from a traceable source.
Distances are DERIVED from OSM geometry. Running times are MODEL OUTPUT because
OSM maxspeed is a legal limit, not an observed bus operating speed.
"""
from __future__ import annotations

import argparse
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
ACCESS_ALLOW = {"yes", "designated", "permissive", "destination"}
TAG_COLUMNS = {
    "maxspeed", "oneway", "junction", "access", "bus", "psv", "lanes",
    "width", "maxwidth", "maxheight", "maxweight",
}


def parse_other_tags(value) -> dict[str, str]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return {}
    return dict(re.findall(r'"([^\"]+)"=>"([^\"]*)"', str(value)))


def row_tags(row) -> dict[str, str]:
    tags = parse_other_tags(row.get("other_tags"))
    for key in TAG_COLUMNS:
        value = row.get(key)
        if value is not None and not (isinstance(value, float) and math.isnan(value)):
            text = str(value).strip()
            if text and text.lower() != "nan":
                tags[key] = text
    return tags


def oneway_direction(tags: dict[str, str]) -> tuple[int, str | None]:
    """Return 1 forward, -1 reverse, 0 bidirectional and optional uncertainty."""
    raw = str(tags.get("oneway", "")).strip().lower()
    if raw in {"yes", "1", "true"}:
        return 1, None
    if raw == "-1":
        return -1, None
    if raw in {"no", "0", "false", ""}:
        if not raw and str(tags.get("junction", "")).lower() == "roundabout":
            return 1, None
        return 0, None
    return 0, f"unparsed_oneway={raw}"


def parse_speed_kmh(tags: dict[str, str], highway: str) -> tuple[float, str]:
    raw = tags.get("maxspeed")
    if raw:
        match = re.search(r"(\d+(?:\.\d+)?)", raw)
        if match:
            speed = float(match.group(1))
            if "mph" in raw.lower():
                speed *= 1.609344
            return max(8.0, speed * 0.70), "MODEL_OUTPUT_FROM_OSM_MAXSPEED"
    return DEFAULT_SPEED_KMH[highway], "ASSUMPTION_BY_HIGHWAY_CLASS"


def bus_eligibility(row) -> tuple[bool, list[str]]:
    highway = str(row.get("highway") or "")
    if highway not in BUS_HIGHWAYS:
        return False, [f"highway={highway or 'missing'}"]
    tags = row_tags(row)
    if tags.get("bus") == "no" or tags.get("psv") == "no":
        return False, ["explicit_bus_restriction"]
    specific_allow = tags.get("bus") in ACCESS_ALLOW or tags.get("psv") in ACCESS_ALLOW
    if tags.get("access") in ACCESS_DENY and not specific_allow:
        return False, ["explicit_access_restriction"]
    uncertain = []
    for key in ("maxheight", "maxweight", "maxwidth", "width", "lanes"):
        if key not in tags:
            uncertain.append(f"missing_{key}")
    _, oneway_uncertainty = oneway_direction(tags)
    if oneway_uncertainty:
        uncertain.append(oneway_uncertainty)
    return True, uncertain


def endpoint_key(x: float, y: float, ndigits: int = 2) -> tuple[float, float]:
    return round(float(x), ndigits), round(float(y), ndigits)


def _add_segment(
    graph: nx.MultiDiGraph,
    start_xy,
    end_xy,
    attrs: dict,
    direction: int,
) -> None:
    segment = LineString([start_xy, end_xy])
    length_m = float(segment.length)
    if length_m <= 0:
        return
    minutes = length_m / (attrs["speed_kmh"] * 1000.0 / 60.0)
    start = endpoint_key(*start_xy)
    end = endpoint_key(*end_xy)
    edge_attrs = {**attrs, "length_m": length_m, "running_minutes": minutes, "geometry": segment}
    if direction >= 0:
        graph.add_edge(start, end, **edge_attrs)
    if direction <= 0:
        reverse = LineString([end_xy, start_xy])
        graph.add_edge(end, start, **{**edge_attrs, "geometry": reverse})


def build_bus_graph(highways: gpd.GeoDataFrame) -> nx.MultiDiGraph:
    """Split every OSM way at every vertex so junction nodes remain routable."""
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
        tags = row_tags(row)
        speed_kmh, speed_status = parse_speed_kmh(tags, highway)
        direction, _ = oneway_direction(tags)
        attrs = {
            "source_index": int(idx),
            "highway": highway,
            "speed_kmh": speed_kmh,
            "speed_status": speed_status,
            "uncertainty_flags": "|".join(uncertainty),
        }
        coords = list(geom.coords)
        for start_xy, end_xy in zip(coords[:-1], coords[1:]):
            if direction == -1:
                _add_segment(graph, start_xy, end_xy, attrs, -1)
            elif direction == 1:
                _add_segment(graph, start_xy, end_xy, attrs, 1)
            else:
                _add_segment(graph, start_xy, end_xy, attrs, 0)
    if graph.number_of_edges() == 0:
        raise ValueError("No bus-eligible OSM road edges were built")
    return graph


def nearest_node_with_distance(graph: nx.MultiDiGraph, x: float, y: float) -> tuple[tuple[float, float], float]:
    node = min(graph.nodes, key=lambda n: (n[0] - x) ** 2 + (n[1] - y) ** 2)
    distance_m = math.hypot(node[0] - x, node[1] - y)
    return node, distance_m


def route_candidate(
    graph: nx.MultiDiGraph,
    waypoints: gpd.GeoDataFrame,
    candidate_id: str,
    max_snap_m: float = 250.0,
) -> tuple[dict, LineString]:
    candidate = waypoints[waypoints["candidate_id"] == candidate_id].sort_values("sequence")
    if len(candidate) < 2:
        raise ValueError(f"{candidate_id}: at least two ordered waypoints required")
    projected = candidate.to_crs(32632)
    snapped = [nearest_node_with_distance(graph, p.x, p.y) for p in projected.geometry]
    max_observed_snap = max(distance for _, distance in snapped)
    if max_observed_snap > max_snap_m:
        raise ValueError(
            f"{candidate_id}: waypoint snap distance {max_observed_snap:.1f} m exceeds {max_snap_m:.1f} m"
        )
    nodes = [node for node, _ in snapped]
    edge_geoms = []
    route_m = route_min = uncertain_m = assumed_speed_m = 0.0
    for a, b in zip(nodes[:-1], nodes[1:]):
        try:
            path = nx.shortest_path(graph, a, b, weight="running_minutes")
        except nx.NetworkXNoPath as exc:
            raise ValueError(f"{candidate_id}: no directed bus path between snapped waypoints {a} and {b}") from exc
        for u, v in zip(path[:-1], path[1:]):
            edges = graph.get_edge_data(u, v)
            edge = min(edges.values(), key=lambda item: item["running_minutes"])
            route_m += edge["length_m"]
            route_min += edge["running_minutes"]
            edge_geoms.append(edge["geometry"])
            if edge["uncertainty_flags"]:
                uncertain_m += edge["length_m"]
            if edge["speed_status"] == "ASSUMPTION_BY_HIGHWAY_CLASS":
                assumed_speed_m += edge["length_m"]
    if not edge_geoms:
        raise ValueError(f"{candidate_id}: routing produced no road geometry")
    coords = []
    for geom in edge_geoms:
        part = list(geom.coords)
        coords.extend(part[1:] if coords and coords[-1] == part[0] else part)
    geometry = LineString(coords)
    return {
        "candidate_id": candidate_id,
        "route_km": route_m / 1000.0,
        "pure_running_minutes": route_min,
        "uncertain_road_km": uncertain_m / 1000.0,
        "assumed_speed_share": assumed_speed_m / route_m if route_m else 0.0,
        "max_waypoint_snap_m": max_observed_snap,
        "route_geometry_status": "DERIVED_OSM",
        "distance_status": "DERIVED_OSM",
        "running_time_status": "MODEL_OUTPUT",
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
    if df.duplicated(["candidate_id", "sequence"]).any():
        raise ValueError("Duplicate sequence values inside candidate definitions")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("waypoints_csv")
    parser.add_argument("--osm", default=str(OSM_HIGHWAYS))
    parser.add_argument("--out-metrics", default=str(OUT_METRICS))
    parser.add_argument("--out-geometry", default=str(OUT_GEOMETRY))
    parser.add_argument("--max-snap-m", type=float, default=250.0)
    args = parser.parse_args()
    highways = gpd.read_file(args.osm)
    graph = build_bus_graph(highways)
    raw = pd.read_csv(args.waypoints_csv)
    validate_waypoints(raw)
    points = gpd.GeoDataFrame(raw, geometry=gpd.points_from_xy(raw.lon, raw.lat), crs=4326)
    metrics, geoms = [], []
    for candidate_id in points["candidate_id"].drop_duplicates():
        row, geometry = route_candidate(graph, points, candidate_id, args.max_snap_m)
        metrics.append(row)
        geoms.append({"candidate_id": candidate_id, "geometry": geometry})
    out_metrics, out_geometry = Path(args.out_metrics), Path(args.out_geometry)
    out_metrics.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(metrics).to_csv(out_metrics, index=False)
    gpd.GeoDataFrame(geoms, crs=32632).to_crs(4326).to_file(out_geometry, driver="GeoJSON")
    print(pd.DataFrame(metrics).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
