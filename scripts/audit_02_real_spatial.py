#!/usr/bin/env python3
"""
audit_02_real_spatial.py

Gate B spatial-integrity pipeline for the Olgiate intermunicipal TPL study.

This checkpoint deliberately replaces the legacy synthetic spatial model. It uses:
- official ISTAT 2026 municipal geometries;
- the real WorldPop 2020 100 m raster acquired in Gate A;
- official ISTAT POSAS 2025 municipal totals for deterministic calibration;
- the real OpenStreetMap highway snapshot acquired in Gate A;
- the Copernicus GLO-30 DSM acquired in Gate A;
- official Agenzia TPL GTFS stop coordinates.

No manual settlement nuclei, random population, Euclidean road multiplier, manual stop
coordinates or hand-entered elevations are allowed in this checkpoint.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from scipy.spatial import cKDTree
from shapely.geometry import LineString, MultiLineString

BOUNDARIES = Path("data/raw/boundaries/comuni_core_istat_2026.geojson")
WORLDPOP = Path("data/raw/worldpop/worldpop_core_unadj_raw.tif")
POSAS = Path("data/raw/istat/POSAS_2025_it_097_Lecco.csv")
OSM_LINES = Path("data/raw/osm/osm_highways_core.geojson")
OSM_BBOX_META = Path("data/raw/osm/osm_core_bbox.meta.json")
DEM_RAW = Path("data/raw/dem/Copernicus_DSM_COG_10_N45_00_E009_00_DEM.tif")
GTFS_STOPS = Path("data/raw/gtfs/agency_arriva/stops.txt")

OUT_DIR = Path("data/audit_gate_b")
POP_CELLS = OUT_DIR / "population_cells_real.csv"
GRAPH_NODES = OUT_DIR / "walk_graph_nodes.csv"
GRAPH_EDGES = OUT_DIR / "walk_graph_edges.csv"
CORE_STOPS = OUT_DIR / "gtfs_core_stops.csv"
ACCESS_CELLS = OUT_DIR / "population_accessibility.csv"
COVERAGE = OUT_DIR / "coverage_summary.csv"
SPOT_CHECKS = OUT_DIR / "spot_checks.csv"
SUMMARY = OUT_DIR / "gate_b_summary.json"

CORE_CODES = {"097010", "097012", "097058", "097074", "097092"}
UTM_EPSG = 32632
WALK_CONNECTOR_KMH = 4.8
MAX_CELL_CONNECTOR_M = 300.0
MAX_STOP_SNAP_M = 250.0
ROAD_BUFFER_M = 350.0
THRESHOLDS_MIN = (5, 8, 10, 12)

BLOCKED_HIGHWAYS = {
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "construction",
    "proposed",
    "raceway",
}

SPOT_EXPECTED = {
    "300407": ("Olgiate Molgora - stazione f.s.", 45.733710, 9.405760),
    "300063": ("Brivio - capolinea", 45.741333, 9.445700),
    "300089": ("Calco - via statale (edicola)", 45.723933, 9.415100),
    "300782": ("S.Maria Hoe'", 45.744283, 9.373817),
    "300804": ("Rovagnate - la pesa", 45.737250, 9.374517),
}


def require_inputs() -> None:
    required = [BOUNDARIES, WORLDPOP, POSAS, OSM_LINES, OSM_BBOX_META, DEM_RAW, GTFS_STOPS]
    missing = [str(p) for p in required if not p.exists() or p.stat().st_size == 0]
    if missing:
        raise FileNotFoundError(
            "Gate B requires Gate A acquisition first; missing/empty inputs: " + ", ".join(missing)
        )


def load_boundaries() -> gpd.GeoDataFrame:
    gdf = gpd.read_file(BOUNDARIES).to_crs(4326)
    gdf["PRO_COM_T"] = gdf["PRO_COM_T"].astype(str).str.zfill(6)
    gdf = gdf[gdf["PRO_COM_T"].isin(CORE_CODES)].copy()
    if len(gdf) != 5:
        raise ValueError(f"Expected five official core municipalities, found {len(gdf)}")
    if set(gdf["PRO_COM_T"]) != CORE_CODES:
        raise ValueError("Core municipality codes do not match the audited set")
    return gdf


def verify_osm_extent(boundaries: gpd.GeoDataFrame) -> dict:
    payload = json.loads(OSM_BBOX_META.read_text(encoding="utf-8"))
    south, west, north, east = payload["bbox_south_west_north_east"]
    minx, miny, maxx, maxy = boundaries.total_bounds
    covers = west <= minx and south <= miny and east >= maxx and north >= maxy
    if not covers:
        raise AssertionError(
            "OSM acquisition does not cover the full official municipal extent: "
            f"osm={(south, west, north, east)}, municipalities={(miny, minx, maxy, maxx)}"
        )
    return {
        "osm_bbox": [south, west, north, east],
        "municipal_bounds": [float(miny), float(minx), float(maxy), float(maxx)],
        "covers_full_core": True,
    }


def load_posas_totals() -> pd.DataFrame:
    df = pd.read_csv(
        POSAS,
        sep=";",
        skiprows=1,
        dtype={"Codice comune": str},
        encoding="utf-8-sig",
        low_memory=False,
    )
    required = {"Codice comune", "Comune", "Totale"}
    if not required.issubset(df.columns):
        raise ValueError(f"POSAS schema changed; missing={required - set(df.columns)}")
    df["Codice comune"] = (
        df["Codice comune"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
    )
    df["Totale"] = pd.to_numeric(df["Totale"], errors="coerce")
    core = df[df["Codice comune"].isin(CORE_CODES)].copy()
    totals = (
        core.groupby(["Codice comune", "Comune"], as_index=False)["Totale"]
        .sum()
        .rename(columns={"Totale": "istat_2025"})
    )
    if len(totals) != 5 or totals["istat_2025"].isna().any():
        raise ValueError(f"Could not derive all five POSAS totals: {totals}")
    return totals


def extract_worldpop_cells(
    boundaries: gpd.GeoDataFrame, posas_totals: pd.DataFrame
) -> gpd.GeoDataFrame:
    with rasterio.open(WORLDPOP) as src:
        if src.crs is None or src.crs.to_epsg() != 4326:
            raise ValueError(f"Unexpected WorldPop CRS: {src.crs}")
        arr = src.read(1, masked=True)
        valid = (~np.ma.getmaskarray(arr)) & np.isfinite(arr.filled(np.nan)) & (arr.filled(0) > 0)
        rows, cols = np.where(valid)
        values = np.asarray(arr.filled(np.nan)[rows, cols], dtype=float)
        xs, ys = rasterio.transform.xy(src.transform, rows, cols, offset="center")
        res_x, res_y = map(abs, src.res)

    cells = gpd.GeoDataFrame(
        {
            "raster_row": rows.astype(int),
            "raster_col": cols.astype(int),
            "lon": np.asarray(xs, dtype=float),
            "lat": np.asarray(ys, dtype=float),
            "worldpop_2020_raw": values,
            "cell_width_deg": res_x,
            "cell_height_deg": res_y,
        },
        geometry=gpd.points_from_xy(xs, ys),
        crs=4326,
    )
    joined = gpd.sjoin(
        cells,
        boundaries[["PRO_COM_T", "COMUNE", "geometry"]],
        how="inner",
        predicate="within",
    ).drop(columns=["index_right"])
    if len(joined) < 1000:
        raise ValueError(f"Unexpectedly few populated WorldPop cells in core: {len(joined)}")

    raw_sums = (
        joined.groupby("PRO_COM_T", as_index=False)["worldpop_2020_raw"]
        .sum()
        .rename(columns={"worldpop_2020_raw": "worldpop_2020_sum"})
    )
    factors = posas_totals.merge(raw_sums, left_on="Codice comune", right_on="PRO_COM_T")
    factors["calibration_factor_2025"] = factors["istat_2025"] / factors["worldpop_2020_sum"]
    if not np.isfinite(factors["calibration_factor_2025"]).all():
        raise ValueError("Non-finite WorldPop calibration factor")

    factor_map = dict(zip(factors["PRO_COM_T"], factors["calibration_factor_2025"]))
    joined["calibration_factor_2025"] = joined["PRO_COM_T"].map(factor_map)
    joined["pop_calibrated_2025"] = (
        joined["worldpop_2020_raw"] * joined["calibration_factor_2025"]
    )

    check = joined.groupby("PRO_COM_T")["pop_calibrated_2025"].sum()
    targets = posas_totals.set_index("Codice comune")["istat_2025"]
    for code in CORE_CODES:
        if abs(float(check.loc[code]) - float(targets.loc[code])) > 1e-6:
            raise AssertionError(f"Population calibration failed for {code}")

    joined = joined.reset_index(drop=True)
    joined["cell_id"] = [f"WP_{i:05d}" for i in range(1, len(joined) + 1)]
    cols_out = [
        "cell_id",
        "raster_row",
        "raster_col",
        "lat",
        "lon",
        "PRO_COM_T",
        "COMUNE",
        "worldpop_2020_raw",
        "calibration_factor_2025",
        "pop_calibrated_2025",
        "cell_width_deg",
        "cell_height_deg",
        "geometry",
    ]
    return joined[cols_out]


def _tag_value(row: pd.Series, key: str) -> str | None:
    if key in row.index and pd.notna(row[key]):
        value = str(row[key]).strip()
        if value and value.lower() != "nan":
            return value
    other = str(row.get("other_tags", ""))
    m = re.search(rf'"{re.escape(key)}"=>"([^"]*)"', other)
    return m.group(1) if m else None


def _walkable(row: pd.Series) -> bool:
    highway = _tag_value(row, "highway")
    if not highway or highway in BLOCKED_HIGHWAYS:
        return False
    foot = (_tag_value(row, "foot") or "").lower()
    access = (_tag_value(row, "access") or "").lower()
    if foot == "no":
        return False
    if access in {"no", "private"} and foot not in {"yes", "designated", "permissive"}:
        return False
    return True


def _iter_lines(geom):
    if isinstance(geom, LineString):
        yield geom
    elif isinstance(geom, MultiLineString):
        yield from geom.geoms


def _node_key(lon: float, lat: float) -> tuple[float, float]:
    return (round(float(lon), 7), round(float(lat), 7))


def _load_dem_array():
    src = rasterio.open(DEM_RAW)
    arr = src.read(1, masked=True)
    return src, arr


def _dem_median(src, arr, lon: float, lat: float) -> float:
    try:
        row, col = src.index(lon, lat)
    except Exception:
        return float("nan")
    r0, r1 = max(0, row - 1), min(arr.shape[0], row + 2)
    c0, c1 = max(0, col - 1), min(arr.shape[1], col + 2)
    window = arr[r0:r1, c0:c1]
    values = np.asarray(window.compressed(), dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    return float(np.median(values))


def tobler_walk_minutes(length_m: float, dz_m: float) -> float:
    if length_m <= 0:
        return 0.0
    slope = float(np.clip(dz_m / length_m, -0.6, 0.6))
    speed_kmh = 6.0 * math.exp(-3.5 * abs(slope + 0.05))
    speed_kmh = float(np.clip(speed_kmh, 0.5, 7.0))
    return length_m / (speed_kmh * 1000.0 / 60.0)


def build_walk_graph(boundaries: gpd.GeoDataFrame):
    lines = gpd.read_file(OSM_LINES).to_crs(4326)
    lines = lines[lines.geometry.notna()].copy()
    if "highway" not in lines.columns:
        raise ValueError(f"OSM line layer lacks highway column: {list(lines.columns)}")
    lines = lines[lines.apply(_walkable, axis=1)].copy()

    core_metric = boundaries.to_crs(UTM_EPSG).geometry.union_all().buffer(ROAD_BUFFER_M)
    lines_metric = lines.to_crs(UTM_EPSG)
    lines = lines.loc[lines_metric.intersects(core_metric).values].copy()
    if len(lines) < 1000:
        raise ValueError(f"Unexpectedly few walkable OSM ways around core: {len(lines)}")

    transformer = Transformer.from_crs(4326, UTM_EPSG, always_xy=True)
    undirected_segments: dict[tuple[tuple[float, float], tuple[float, float]], dict] = {}
    node_xy: dict[tuple[float, float], tuple[float, float]] = {}

    for _, row in lines.iterrows():
        highway = _tag_value(row, "highway") or "unknown"
        for geom in _iter_lines(row.geometry):
            coords = list(geom.coords)
            for a, b in zip(coords[:-1], coords[1:]):
                u = _node_key(a[0], a[1])
                v = _node_key(b[0], b[1])
                if u == v:
                    continue
                ux, uy = transformer.transform(*u)
                vx, vy = transformer.transform(*v)
                length = math.hypot(vx - ux, vy - uy)
                if length < 0.2:
                    continue
                node_xy[u] = (ux, uy)
                node_xy[v] = (vx, vy)
                key = tuple(sorted((u, v)))
                prev = undirected_segments.get(key)
                if prev is None or length < prev["length_m"]:
                    undirected_segments[key] = {
                        "u": u,
                        "v": v,
                        "length_m": length,
                        "highway": highway,
                    }

    if len(node_xy) < 1500 or len(undirected_segments) < 1500:
        raise ValueError(
            f"Walk graph too small: nodes={len(node_xy)}, segments={len(undirected_segments)}"
        )

    dem_src, dem_arr = _load_dem_array()
    elevations = {node: _dem_median(dem_src, dem_arr, node[0], node[1]) for node in node_xy}
    dem_src.close()
    finite = np.array([v for v in elevations.values() if np.isfinite(v)], dtype=float)
    if len(finite) / len(elevations) < 0.95:
        raise ValueError(
            f"Too many graph nodes lack DEM elevation: {len(finite)}/{len(elevations)}"
        )

    fill_elev = float(np.median(finite))
    for k, v in list(elevations.items()):
        if not np.isfinite(v):
            elevations[k] = fill_elev

    G = nx.DiGraph()
    node_id = {node: i for i, node in enumerate(sorted(node_xy), start=1)}
    node_rows = []
    for node, i in node_id.items():
        x, y = node_xy[node]
        G.add_node(i, lon=node[0], lat=node[1], x=x, y=y, elevation_m=elevations[node])
        node_rows.append(
            {
                "node_id": i,
                "lon": node[0],
                "lat": node[1],
                "x_utm32": x,
                "y_utm32": y,
                "elevation_m": elevations[node],
            }
        )

    edge_rows = []
    edge_id = 1
    for seg in undirected_segments.values():
        u_key, v_key = seg["u"], seg["v"]
        u, v = node_id[u_key], node_id[v_key]
        length = float(seg["length_m"])
        zu, zv = elevations[u_key], elevations[v_key]
        uv = tobler_walk_minutes(length, zv - zu)
        vu = tobler_walk_minutes(length, zu - zv)
        G.add_edge(u, v, length_m=length, walk_min=uv, highway=seg["highway"])
        G.add_edge(v, u, length_m=length, walk_min=vu, highway=seg["highway"])
        edge_rows.append(
            {
                "edge_id": edge_id,
                "u": u,
                "v": v,
                "length_m": length,
                "highway": seg["highway"],
                "elev_u_m": zu,
                "elev_v_m": zv,
                "slope_uv": (zv - zu) / length,
                "walk_min_uv": uv,
                "walk_min_vu": vu,
            }
        )
        edge_id += 1

    UG = G.to_undirected()
    components = sorted(nx.connected_components(UG), key=len, reverse=True)
    giant = components[0]
    giant_ratio = len(giant) / G.number_of_nodes()
    G = G.subgraph(giant).copy()
    node_df = pd.DataFrame(node_rows)
    node_df["in_giant_component"] = node_df["node_id"].isin(giant)
    edge_df = pd.DataFrame(edge_rows)
    edge_df["in_giant_component"] = edge_df["u"].isin(giant) & edge_df["v"].isin(giant)

    info = {
        "walkable_source_features": int(len(lines)),
        "graph_nodes_all": int(len(node_rows)),
        "graph_edges_undirected_all": int(len(edge_rows)),
        "giant_component_nodes": int(G.number_of_nodes()),
        "giant_component_directed_edges": int(G.number_of_edges()),
        "giant_component_ratio": float(giant_ratio),
        "dem_missing_nodes_filled": int(len(elevations) - len(finite)),
    }
    return G, node_df, edge_df, info


def _graph_kdtree(G: nx.DiGraph):
    ids = np.array(list(G.nodes), dtype=int)
    xy = np.array([(G.nodes[i]["x"], G.nodes[i]["y"]) for i in ids], dtype=float)
    return ids, xy, cKDTree(xy)


def load_core_gtfs_stops(boundaries: gpd.GeoDataFrame, G: nx.DiGraph) -> pd.DataFrame:
    stops = pd.read_csv(GTFS_STOPS, dtype={"stop_id": str, "stop_code": str})
    required = {"stop_id", "stop_name", "stop_lat", "stop_lon"}
    if not required.issubset(stops.columns):
        raise ValueError(f"GTFS stops schema changed; missing={required - set(stops.columns)}")
    stops = stops.dropna(subset=["stop_lat", "stop_lon"]).copy()
    sgdf = gpd.GeoDataFrame(
        stops,
        geometry=gpd.points_from_xy(stops["stop_lon"], stops["stop_lat"]),
        crs=4326,
    )
    metric = sgdf.to_crs(UTM_EPSG)
    bmetric = boundaries.to_crs(UTM_EPSG)
    core_union = bmetric.geometry.union_all().buffer(150.0)
    sgdf = sgdf.loc[metric.within(core_union).values].copy()
    metric = sgdf.to_crs(UTM_EPSG)
    if len(sgdf) < 10:
        raise ValueError(f"Unexpectedly few official GTFS stops in core: {len(sgdf)}")

    ids, _, tree = _graph_kdtree(G)
    xy = np.column_stack([metric.geometry.x.to_numpy(), metric.geometry.y.to_numpy()])
    dist, idx = tree.query(xy, k=1)
    sgdf["graph_node_id"] = ids[idx]
    sgdf["snap_distance_m"] = dist
    sgdf["snap_ok"] = sgdf["snap_distance_m"] <= MAX_STOP_SNAP_M

    munis = bmetric[["PRO_COM_T", "COMUNE", "geometry"]].reset_index(drop=True)
    assigned_codes = []
    assigned_names = []
    for geom in metric.geometry:
        distances = munis.geometry.distance(geom)
        j = int(distances.to_numpy().argmin())
        assigned_codes.append(munis.loc[j, "PRO_COM_T"])
        assigned_names.append(munis.loc[j, "COMUNE"])
    sgdf["PRO_COM_T"] = assigned_codes
    sgdf["COMUNE"] = assigned_names

    cols = [
        "stop_id",
        "stop_code",
        "stop_name",
        "stop_lat",
        "stop_lon",
        "PRO_COM_T",
        "COMUNE",
        "graph_node_id",
        "snap_distance_m",
        "snap_ok",
    ]
    return pd.DataFrame(sgdf[cols])


def calculate_accessibility(
    cells: gpd.GeoDataFrame, stops: pd.DataFrame, G: nx.DiGraph
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    usable_stops = stops[stops["snap_ok"]].copy()
    source_nodes = sorted(set(usable_stops["graph_node_id"].astype(int)))
    if len(source_nodes) < 5:
        raise ValueError(f"Too few GTFS stops snapped to walk graph: {len(source_nodes)}")

    # Stop snapping is not free: use a synthetic super-source on the reversed
    # graph and connect each official GTFS stop node with its metric snap time.
    reversed_graph = G.reverse(copy=True)
    super_source = 0
    while super_source in reversed_graph:
        super_source -= 1
    reversed_graph.add_node(super_source)
    stop_connector_min = {}
    for _, stop in usable_stops.iterrows():
        node = int(stop["graph_node_id"])
        connector = float(stop["snap_distance_m"]) / (WALK_CONNECTOR_KMH * 1000.0 / 60.0)
        stop_connector_min[node] = min(stop_connector_min.get(node, float("inf")), connector)
    for node, connector in stop_connector_min.items():
        reversed_graph.add_edge(super_source, node, walk_min=connector)
    distances = nx.single_source_dijkstra_path_length(
        reversed_graph, super_source, weight="walk_min"
    )
    network_to_stop = {node: dist for node, dist in distances.items() if node != super_source}

    ids, _, tree = _graph_kdtree(G)
    cmetric = cells.to_crs(UTM_EPSG)
    xy = np.column_stack([cmetric.geometry.x.to_numpy(), cmetric.geometry.y.to_numpy()])
    connector_dist, idx = tree.query(xy, k=1)
    nearest_node = ids[idx]
    network_min = np.array([network_to_stop.get(int(n), np.nan) for n in nearest_node], dtype=float)
    connector_min = connector_dist / (WALK_CONNECTOR_KMH * 1000.0 / 60.0)
    connector_ok = connector_dist <= MAX_CELL_CONNECTOR_M
    access_min = network_min + connector_min
    access_min[~connector_ok | ~np.isfinite(network_min)] = np.nan

    out = pd.DataFrame(cells.drop(columns="geometry"))
    out["nearest_graph_node_id"] = nearest_node
    out["connector_distance_m"] = connector_dist
    out["connector_walk_min"] = connector_min
    out["network_walk_min_to_gtfs_stop"] = network_min
    out["walk_min_to_nearest_gtfs_stop"] = access_min
    out["connector_within_limit"] = connector_ok
    for t in THRESHOLDS_MIN:
        out[f"covered_{t}min"] = out["walk_min_to_nearest_gtfs_stop"] <= t

    total_pop = float(out["pop_calibrated_2025"].sum())
    reachable_pop = float(out.loc[out["walk_min_to_nearest_gtfs_stop"].notna(), "pop_calibrated_2025"].sum())
    rows = []
    for code, group in out.groupby("PRO_COM_T"):
        muni_total = float(group["pop_calibrated_2025"].sum())
        for t in THRESHOLDS_MIN:
            pop = float(group.loc[group[f"covered_{t}min"], "pop_calibrated_2025"].sum())
            rows.append(
                {
                    "scope": "municipality",
                    "PRO_COM_T": code,
                    "COMUNE": str(group["COMUNE"].iloc[0]),
                    "threshold_min": t,
                    "population_total_2025": muni_total,
                    "population_covered_2025": pop,
                    "coverage_pct": 100.0 * pop / muni_total if muni_total else np.nan,
                }
            )
    for t in THRESHOLDS_MIN:
        pop = float(out.loc[out[f"covered_{t}min"], "pop_calibrated_2025"].sum())
        rows.append(
            {
                "scope": "core_total",
                "PRO_COM_T": "ALL",
                "COMUNE": "CORE 5 COMUNI",
                "threshold_min": t,
                "population_total_2025": total_pop,
                "population_covered_2025": pop,
                "coverage_pct": 100.0 * pop / total_pop if total_pop else np.nan,
            }
        )
    coverage = pd.DataFrame(rows)
    info = {
        "gtfs_stops_total_core": int(len(stops)),
        "gtfs_stops_snap_ok": int(stops["snap_ok"].sum()),
        "unique_stop_graph_nodes": int(len(source_nodes)),
        "population_total_2025": total_pop,
        "population_with_graph_access": reachable_pop,
        "population_with_graph_access_pct": 100.0 * reachable_pop / total_pop,
        "max_cell_connector_m": MAX_CELL_CONNECTOR_M,
        "max_stop_snap_m": MAX_STOP_SNAP_M,
    }
    return out, coverage, info


def run_spot_checks(stops: pd.DataFrame) -> pd.DataFrame:
    to_metric = Transformer.from_crs(4326, UTM_EPSG, always_xy=True)
    rows = []
    indexed = stops.set_index("stop_id", drop=False)
    for stop_id, (expected_name, expected_lat, expected_lon) in SPOT_EXPECTED.items():
        present = stop_id in indexed.index
        if present:
            row = indexed.loc[stop_id]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            x1, y1 = to_metric.transform(expected_lon, expected_lat)
            x2, y2 = to_metric.transform(float(row["stop_lon"]), float(row["stop_lat"]))
            coordinate_error_m = math.hypot(x2 - x1, y2 - y1)
            name_match = str(row["stop_name"]).strip().casefold() == expected_name.casefold()
            snap_m = float(row["snap_distance_m"])
        else:
            coordinate_error_m = float("nan")
            name_match = False
            snap_m = float("nan")
        passed = bool(
            present
            and name_match
            and coordinate_error_m <= 5.0
            and np.isfinite(snap_m)
            and snap_m <= MAX_STOP_SNAP_M
        )
        rows.append(
            {
                "stop_id": stop_id,
                "expected_name": expected_name,
                "present_in_official_gtfs": present,
                "name_match": name_match,
                "coordinate_error_m": coordinate_error_m,
                "graph_snap_distance_m": snap_m,
                "pass": passed,
            }
        )
    return pd.DataFrame(rows)


def write_outputs(
    cells: gpd.GeoDataFrame,
    G: nx.DiGraph,
    node_df: pd.DataFrame,
    edge_df: pd.DataFrame,
    stops: pd.DataFrame,
    access: pd.DataFrame,
    coverage: pd.DataFrame,
    spots: pd.DataFrame,
    extent_info: dict,
    graph_info: dict,
    access_info: dict,
) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(cells.drop(columns="geometry")).to_csv(POP_CELLS, index=False)
    node_df.to_csv(GRAPH_NODES, index=False)
    edge_df.to_csv(GRAPH_EDGES, index=False)
    stops.to_csv(CORE_STOPS, index=False)
    access.to_csv(ACCESS_CELLS, index=False)
    coverage.to_csv(COVERAGE, index=False)
    spots.to_csv(SPOT_CHECKS, index=False)

    core_cov = coverage[coverage["scope"] == "core_total"].set_index("threshold_min")
    summary = {
        "gate": "B",
        "status": "PENDING_EXTERNAL_REVIEW",
        "epistemic_status": {
            "worldpop_2020_raw": "FACT",
            "population_calibrated_2025": "ESTIMATE",
            "osm_walk_graph": "DERIVED",
            "dem_node_elevation": "DERIVED",
            "gtfs_stop_coordinates": "FACT",
            "accessibility": "MODEL_OUTPUT",
        },
        "population_cells": int(len(cells)),
        "population_raw_worldpop_2020": float(cells["worldpop_2020_raw"].sum()),
        "population_calibrated_2025": float(cells["pop_calibrated_2025"].sum()),
        "coverage_pct": {
            str(t): float(core_cov.loc[t, "coverage_pct"]) for t in THRESHOLDS_MIN
        },
        "spot_checks_passed": int(spots["pass"].sum()),
        "spot_checks_total": int(len(spots)),
        "extent": extent_info,
        "graph": graph_info,
        "access": access_info,
        "method_notes": [
            "WorldPop 2020 values are preserved separately from the municipality-calibrated 2025 derivative.",
            "Population calibration is multiplicative within each official municipality and exactly quadrates to POSAS 2025 totals.",
            "OSM walk edges exclude motorway/trunk/construction/proposed/raceway and explicit no-foot/private access unless foot access overrides it.",
            "Copernicus GLO-30 is a DSM; node elevations use a 3x3 median to reduce local building/tree artifacts but are not treated as bare-earth truth.",
            "Walking times use directional Tobler slope adjustment on the OSM graph. Cell-to-network connectors are limited to 300 m and use 4.8 km/h.",
            "GTFS stops.txt is the institutional primary stop source. OSM stop tags are not used to define stops.",
            "Raster-cell population coverage uses each cell centre as the representative routing point; the original 2020 raster value remains attached to that cell.",
        ],
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    print("=" * 80)
    print("AUDIT CHECKPOINT 2: REAL SPATIAL INTEGRITY (GATE B)")
    print("=" * 80)
    require_inputs()
    boundaries = load_boundaries()
    extent_info = verify_osm_extent(boundaries)
    posas_totals = load_posas_totals()
    cells = extract_worldpop_cells(boundaries, posas_totals)
    G, node_df, edge_df, graph_info = build_walk_graph(boundaries)
    stops = load_core_gtfs_stops(boundaries, G)
    access, coverage, access_info = calculate_accessibility(cells, stops, G)
    spots = run_spot_checks(stops)
    summary = write_outputs(
        cells,
        G,
        node_df,
        edge_df,
        stops,
        access,
        coverage,
        spots,
        extent_info,
        graph_info,
        access_info,
    )

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if not spots["pass"].all():
        raise AssertionError("One or more independent GTFS spatial spot checks failed")
    if graph_info["giant_component_ratio"] < 0.75:
        raise AssertionError(
            f"OSM walk graph giant component too small: {graph_info['giant_component_ratio']:.3f}"
        )
    if access_info["population_with_graph_access_pct"] < 85.0:
        raise AssertionError(
            "Too much calibrated population cannot reach the graph within the audited connector limit: "
            f"{access_info['population_with_graph_access_pct']:.1f}%"
        )
    print("[OK] Gate B computational pipeline completed; external review still required.")


if __name__ == "__main__":
    main()
