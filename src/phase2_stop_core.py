#!/usr/bin/env python3
"""Build an auditable Phase-2 candidate-stop universe from frozen Gate B/D evidence.

No final topology, headway, timetable, budget or network ranking is produced.
New stop points are discovery hypotheses only and are always labelled
PROPOSED_STOP/FIELD_CHECK_PENDING.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import zipfile
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point

GATE_B_COMMIT = "55d726564e13acca55ce563cc911263ac513acb0"
GATE_D_COMPUTATIONAL_COMMIT = "7c220f7586d0f6e5cccd14a2d518be52eb1c4a55"
GATE_B_ARTIFACT_ZIP_SHA256 = "aca8889c8f1a4148c252c3530a56e8c68fa3f33c8e6ddf81a9ed743c51c1cfd1"
GATE_D_ARTIFACT_ZIP_SHA256 = "6fbc06d74d5ba970bc980e4cde6234245e0753c22386f703ea313c6a4de9206a"
UTM = 32632
THRESHOLDS = (5, 8, 10, 12)
MAX_STOP_SNAP_M = 250.0
WALK_CONNECTOR_KMH = 4.8
DISCOVERY_SAMPLE_M = 150.0
DISCOVERY_SEED_RADIUS_M = 800.0
PRUNE_EXISTING_STOP_M = 150.0
PRUNE_CANDIDATE_RADIUS_M = 220.0
PRUNE_CATCHMENT_JACCARD = 0.90
PRUNE_CATCHMENT_RADIUS_M = 500.0
CORE_BUFFER_M = 150.0

DEFAULT_SPEED_KMH = {
    "motorway": 60.0, "trunk": 50.0, "primary": 40.0, "secondary": 35.0,
    "tertiary": 30.0, "unclassified": 25.0, "residential": 22.0,
    "living_street": 12.0, "service": 15.0,
}
BUS_HIGHWAYS = set(DEFAULT_SPEED_KMH)
ACCESS_DENY = {"no", "private", "agricultural", "forestry"}
EXPLICIT_ALLOW = {"yes", "designated", "permissive"}
CONDITIONAL_ACCESS = {"destination", "customers", "delivery"}
STOP_SITING_UNSUPPORTED_HIGHWAYS = {"motorway", "trunk"}
TAG_COLUMNS = {
    "maxspeed", "oneway", "junction", "access", "bus", "psv", "lanes", "width",
    "maxwidth", "maxheight", "maxweight", "vehicle", "motor_vehicle", "oneway:bus", "oneway:psv",
}
MAJOR_AMENITIES = {
    "school", "kindergarten", "college", "university", "hospital", "clinic", "doctors",
    "pharmacy", "nursing_home", "social_facility", "townhall", "community_centre",
    "library", "post_office", "marketplace", "courthouse", "police",
}
MAJOR_SHOPS = {"supermarket", "mall", "department_store"}
MAJOR_LEISURE = {"sports_centre", "stadium", "swimming_pool", "fitness_centre"}
MAJOR_TOURISM = {"museum", "attraction"}
SETTLEMENT_PLACE_TYPES = {"village", "hamlet", "suburb", "neighbourhood", "locality", "isolated_dwelling"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normal(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().casefold())


def parse_other_tags(value: object) -> dict[str, str]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return {}
    return dict(re.findall(r'"([^\"]+)"=>"([^\"]*)"', str(value)))


def row_tags(row: pd.Series) -> dict[str, str]:
    tags = parse_other_tags(row.get("other_tags"))
    for key in TAG_COLUMNS:
        value = row.get(key)
        if value is not None and not (isinstance(value, float) and math.isnan(value)):
            text = str(value).strip()
            if text and text.lower() != "nan":
                tags[key] = text
    return tags


def modal_access(tags: dict[str, str], key: str):
    raw = str(tags.get(key, "")).strip().lower()
    if not raw:
        return None, []
    if raw in ACCESS_DENY:
        return False, []
    if raw in EXPLICIT_ALLOW:
        return True, []
    if raw in CONDITIONAL_ACCESS:
        return True, [f"conditional_{key}={raw}"]
    return False, [f"unparsed_{key}={raw}"]


def bus_eligibility(row: pd.Series) -> tuple[bool, list[str]]:
    """Exact Gate-D-v4 modal access precedence for structural eligibility."""
    highway = str(row.get("highway") or "")
    if highway not in BUS_HIGHWAYS:
        return False, [f"highway={highway or 'missing'}"]
    tags = row_tags(row)
    uncertainty: list[str] = []
    bus_decision, bus_notes = modal_access(tags, "bus")
    uncertainty.extend(bus_notes)
    if "bus" in tags and bus_decision is False:
        return False, bus_notes or ["explicit_bus_restriction"]
    if bus_decision is True:
        specific_allow = True
    else:
        psv_decision, psv_notes = modal_access(tags, "psv")
        uncertainty.extend(psv_notes)
        if "psv" in tags and psv_decision is False:
            return False, psv_notes or ["explicit_psv_restriction"]
        specific_allow = psv_decision is True
    if not specific_allow:
        for key in ("access", "vehicle", "motor_vehicle"):
            value = str(tags.get(key, "")).strip().lower()
            if value in ACCESS_DENY:
                return False, [f"explicit_{key}_restriction"]
            if value in CONDITIONAL_ACCESS:
                uncertainty.append(f"conditional_{key}={value}")
    for key in ("maxheight", "maxweight", "maxwidth", "width", "lanes"):
        if key not in tags:
            uncertainty.append(f"missing_{key}")
    return True, sorted(set(uncertainty))


def load_walk_graph(bdir: Path):
    nodes = pd.read_csv(bdir / "walk_graph_nodes.csv")
    edges = pd.read_csv(bdir / "walk_graph_edges.csv")
    nodes = nodes[nodes["in_giant_component"].astype(str).str.lower().isin({"true", "1"})].copy()
    edges = edges[edges["in_giant_component"].astype(str).str.lower().isin({"true", "1"})].copy()
    directed = nx.DiGraph()
    undirected = nx.Graph()
    for r in nodes.itertuples(index=False):
        directed.add_node(int(r.node_id), x=float(r.x_utm32), y=float(r.y_utm32))
        undirected.add_node(int(r.node_id), x=float(r.x_utm32), y=float(r.y_utm32))
    for r in edges.itertuples(index=False):
        u, v = int(r.u), int(r.v)
        if u not in directed or v not in directed:
            continue
        uv, vu, length = float(r.walk_min_uv), float(r.walk_min_vu), float(r.length_m)
        directed.add_edge(u, v, walk_min=uv, length_m=length)
        directed.add_edge(v, u, walk_min=vu, length_m=length)
        if undirected.has_edge(u, v):
            if length < undirected[u][v]["length_m"]:
                undirected[u][v]["length_m"] = length
        else:
            undirected.add_edge(u, v, length_m=length)
    ids = nodes["node_id"].astype(int).to_numpy()
    xy = nodes[["x_utm32", "y_utm32"]].to_numpy(float)
    return directed, undirected, nodes, ids, cKDTree(xy)


def read_gtfs_zip(path: Path, feed: str) -> dict[str, pd.DataFrame]:
    with zipfile.ZipFile(path) as z:
        out = {name[:-4]: pd.read_csv(z.open(name), dtype=str) for name in ("stops.txt", "routes.txt", "trips.txt", "stop_times.txt")}
    out["feed"] = feed
    return out


def route_map(feed: dict) -> dict[str, str]:
    r = feed["routes"]
    return dict(zip(r["route_id"].astype(str), r["route_short_name"].astype(str)))


def stop_route_lookup(feeds: list[dict]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for feed in feeds:
        sm = route_map(feed)
        trips = feed["trips"][["trip_id", "route_id"]].copy()
        st = feed["stop_times"][["trip_id", "stop_id"]].merge(trips, on="trip_id", how="inner")
        st["route_short_name"] = st["route_id"].map(sm)
        for sid, group in st.dropna(subset=["route_short_name"]).groupby("stop_id"):
            result[str(sid)].update(group["route_short_name"].astype(str))
    return result


def cluster_existing_stops(stops: pd.DataFrame) -> pd.DataFrame:
    g = gpd.GeoDataFrame(stops.copy(), geometry=gpd.points_from_xy(stops.stop_lon, stops.stop_lat), crs=4326).to_crs(UTM)
    xy = np.column_stack([g.geometry.x, g.geometry.y])
    tree = cKDTree(xy)
    parent = list(range(len(g)))
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    def union(a,b):
        ra,rb=find(a),find(b)
        if ra!=rb: parent[max(ra,rb)]=min(ra,rb)
    for a,b in tree.query_pairs(40.0):
        union(a,b)
    roots=[find(i) for i in range(len(g))]
    unique={root:i+1 for i,root in enumerate(sorted(set(roots)))}
    stops=stops.copy()
    stops["physical_cluster_id"]=[f"EX_{unique[r]:03d}" for r in roots]
    return stops


def multi_source_nearest_stop_distance(undirected: nx.Graph, stops: pd.DataFrame):
    import heapq
    dist: dict[int,float] = {}
    source: dict[int,str] = {}
    heap=[]
    for r in stops.loc[stops.snap_ok.astype(bool)].itertuples(index=False):
        node=int(r.graph_node_id); d=float(r.snap_distance_m); sid=str(r.physical_cluster_id)
        if d < dist.get(node, float("inf")):
            dist[node]=d; source[node]=sid; heapq.heappush(heap,(d,sid,node))
    while heap:
        d,sid,u=heapq.heappop(heap)
        if d != dist.get(u) or sid != source.get(u): continue
        for v,data in undirected[u].items():
            nd=d+float(data["length_m"])
            if nd < dist.get(v,float("inf")):
                dist[v]=nd; source[v]=sid; heapq.heappush(heap,(nd,sid,v))
    return dist, source


def walk_distances_to_stop_node(directed: nx.DiGraph, stop_node: int, stop_connector_min: float, cutoff=12.0):
    rg = directed.reverse(copy=False)
    raw = nx.single_source_dijkstra_path_length(rg, stop_node, cutoff=max(0.0, cutoff-stop_connector_min), weight="walk_min")
    return {int(n): float(v)+stop_connector_min for n,v in raw.items()}


def cell_membership(cells: pd.DataFrame, distances: dict[int,float], threshold: float):
    nodes=cells["nearest_graph_node_id"].astype(int)
    net=nodes.map(distances).astype(float)
    total=net + pd.to_numeric(cells["connector_walk_min"], errors="coerce")
    ok=cells["connector_within_limit"].astype(str).str.lower().isin({"true","1"}) & total.notna() & total.le(threshold)
    return ok, total
