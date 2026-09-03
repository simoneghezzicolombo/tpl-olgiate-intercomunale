"""Building-section piece geometry and accessibility helpers for Phase 2.

The dasymetric accounting unit is a building-section intersection.  For buildings
crossing census or municipal boundaries, accessibility and boundary diagnostics
must use a representative point of that intersection rather than a single point
for the whole building.

All points and weights are DERIVED from official DBGT / ISTAT geometries.  No
resident count is observed at this level; population remains MODEL_OUTPUT.
"""
from __future__ import annotations

import math

import geopandas as gpd
import networkx as nx
import pandas as pd
from scipy.spatial import cKDTree
from shapely import make_valid as shapely_make_valid
from shapely.geometry import Point, box

PIECE_POINT_STATUS = "DERIVED_REPRESENTATIVE_POINT_OF_DBGT_BUILDING_SECTION_INTERSECTION"
PIECE_WEIGHT_STATUS = "DERIVED_FROM_DBGT_GEOMETRY_AND_AVAILABLE_VOLUME"
ACCESS_STATUS = "MODEL_OUTPUT_GATE_B_WALK_GRAPH_BUILDING_SECTION_PIECE_REPRESENTATIVE_POINT"
BOUNDARY_STATUS = "MODEL_OUTPUT_SPATIAL_COMPARISON_BUILDING_SECTION_PIECE_POINT"
SPATIAL_STATUS = "DERIVED_SPATIAL_DISTRIBUTION_COMPARISON_BUILDING_SECTION_PIECE_POINT"


def build_section_pieces(buildings: gpd.GeoDataFrame, section_geometry: gpd.GeoDataFrame) -> pd.DataFrame:
    required_buildings = {
        "CLASSREF", "footprint_area_m2", "dbgt_volume_complete", "dbgt_volume_proxy_m3",
        "eligible_primary", "eligible_fallback", "geometry",
    }
    required_sections = {"section_id", "municipality_code", "geometry"}
    if not required_buildings.issubset(buildings.columns):
        raise ValueError(f"building columns missing: {required_buildings - set(buildings.columns)}")
    if not required_sections.issubset(section_geometry.columns):
        raise ValueError(f"section columns missing: {required_sections - set(section_geometry.columns)}")
    if buildings.crs is None or section_geometry.crs is None:
        raise ValueError("building/section CRS missing")

    b = buildings.to_crs(32632)
    sec = section_geometry.to_crs(32632)[["section_id", "municipality_code", "geometry"]].copy()
    eligible = b.loc[b["eligible_primary"] | b["eligible_fallback"], [
        "CLASSREF", "footprint_area_m2", "dbgt_volume_complete", "dbgt_volume_proxy_m3",
        "eligible_primary", "eligible_fallback", "geometry",
    ]].copy()
    joined = gpd.sjoin(eligible, sec, how="inner", predicate="intersects")
    sec_geom = sec.geometry.to_dict()
    rows: list[dict] = []
    for row in joined.itertuples():
        inter = shapely_make_valid(row.geometry.intersection(sec_geom[row.index_right]))
        if inter.is_empty:
            continue
        area = float(inter.area)
        if not math.isfinite(area) or area <= 0:
            continue
        footprint_area = float(row.footprint_area_m2)
        if bool(row.dbgt_volume_complete) and pd.notna(row.dbgt_volume_proxy_m3) and footprint_area > 0:
            weight = float(row.dbgt_volume_proxy_m3) * area / footprint_area
            basis = "DBGT_VOLUME_PROXY_COMPLETE_PRORATED_BY_SECTION_INTERSECTION"
        else:
            weight = area
            basis = "DBGT_FOOTPRINT_SECTION_INTERSECTION_AREA"
        if not math.isfinite(weight) or weight <= 0:
            continue
        rep = inter.representative_point()
        rows.append({
            "building_id": str(row.CLASSREF),
            "section_id": str(row.section_id),
            "municipality_code": str(row.municipality_code),
            "eligible_primary": bool(row.eligible_primary),
            "eligible_fallback": bool(row.eligible_fallback),
            "intersection_area_m2": area,
            "allocation_weight": weight,
            "allocation_weight_basis_piece": basis,
            "weight_epistemic_status": PIECE_WEIGHT_STATUS,
            "piece_x_utm32": float(rep.x),
            "piece_y_utm32": float(rep.y),
            "piece_point_epistemic_status": PIECE_POINT_STATUS,
        })
    out = pd.DataFrame(rows)
    if len(out) and out.duplicated(["building_id", "section_id"]).any():
        raise RuntimeError("duplicate building-section piece after geometric intersection")
    return out


def _stop_seed_walk_minutes(stops: pd.DataFrame, connector_m_per_min: float) -> dict[int, float]:
    """Return one deterministic minimum stop-connector seed per graph node.

    Gate B may contain multiple official GTFS stops snapped to the same walking
    graph node.  A DiGraph stores only one parallel edge for a given
    ``super_source -> graph_node`` pair, so adding stops row by row would make
    the result depend on row order.  The mathematically correct multi-source
    seed is the minimum valid stop snap time for each graph node.
    """
    required = {"graph_node_id", "snap_distance_m", "snap_ok"}
    if not required.issubset(stops.columns):
        raise ValueError(f"GTFS stop seed columns missing: {required - set(stops.columns)}")
    if not math.isfinite(connector_m_per_min) or connector_m_per_min <= 0:
        raise ValueError("connector_m_per_min must be finite and positive")

    valid = stops.loc[stops["snap_ok"].astype(bool), ["graph_node_id", "snap_distance_m"]].copy()
    if valid.empty:
        raise RuntimeError("no valid official GTFS stops snapped in Gate B")
    valid["graph_node_id"] = pd.to_numeric(valid["graph_node_id"], errors="raise").astype(int)
    valid["snap_distance_m"] = pd.to_numeric(valid["snap_distance_m"], errors="raise").astype(float)
    if (~valid["snap_distance_m"].map(math.isfinite)).any() or (valid["snap_distance_m"] < 0).any():
        raise RuntimeError("invalid GTFS stop snap distance in Gate B")

    seed = (
        valid.groupby("graph_node_id", sort=True)["snap_distance_m"]
        .min()
        .div(connector_m_per_min)
    )
    return {int(node): float(minutes) for node, minutes in seed.items()}


def compute_accessibility(
    building_allocations: pd.DataFrame,
    _building_points: pd.DataFrame,
    gate_b_dir,
    *,
    core_codes: set[str],
    connector_max_m: float,
    connector_m_per_min: float,
) -> pd.DataFrame:
    required = {"building_id", "section_id", "municipality_code", "piece_x_utm32", "piece_y_utm32"}
    if not required.issubset(building_allocations.columns):
        raise ValueError(f"piece accessibility columns missing: {required - set(building_allocations.columns)}")

    nodes = pd.read_csv(gate_b_dir / "walk_graph_nodes.csv")
    edges = pd.read_csv(gate_b_dir / "walk_graph_edges.csv")
    stops = pd.read_csv(gate_b_dir / "gtfs_core_stops.csv")
    nodes = nodes.loc[nodes["in_giant_component"].astype(bool)].copy()
    edges = edges.loc[edges["in_giant_component"].astype(bool)].copy()
    if nodes.empty or edges.empty:
        raise RuntimeError("Gate B giant walking component is empty")

    graph = nx.DiGraph()
    for row in edges.itertuples(index=False):
        graph.add_edge(int(row.u), int(row.v), weight=float(row.walk_min_uv))
        graph.add_edge(int(row.v), int(row.u), weight=float(row.walk_min_vu))
    reverse = graph.reverse(copy=True)
    super_source = -1
    reverse.add_node(super_source)
    stop_seed_minutes = _stop_seed_walk_minutes(stops, connector_m_per_min)
    for graph_node_id, snap_walk_min in stop_seed_minutes.items():
        reverse.add_edge(super_source, graph_node_id, weight=snap_walk_min)
    network_minutes = nx.single_source_dijkstra_path_length(reverse, super_source, weight="weight")

    node_ids = nodes["node_id"].astype(int).tolist()
    xy = list(zip(nodes["x_utm32"].astype(float), nodes["y_utm32"].astype(float)))
    tree = cKDTree(xy)

    out = building_allocations.loc[building_allocations["municipality_code"].isin(core_codes)].copy()
    if out[["piece_x_utm32", "piece_y_utm32"]].isna().any().any():
        raise RuntimeError("allocated core building-section piece lacks representative point")
    distances, indexes = tree.query(out[["piece_x_utm32", "piece_y_utm32"]].to_numpy(), k=1)
    out["nearest_graph_node_id"] = [node_ids[int(i)] for i in indexes]
    out["connector_distance_m"] = [float(v) for v in distances]
    out["connector_walk_min"] = out["connector_distance_m"] / connector_m_per_min
    out["connector_within_limit"] = out["connector_distance_m"] <= connector_max_m
    out["network_walk_min_to_gtfs_stop"] = out["nearest_graph_node_id"].map(network_minutes)
    out["walk_min_to_nearest_gtfs_stop"] = out["network_walk_min_to_gtfs_stop"] + out["connector_walk_min"]
    out.loc[~out["connector_within_limit"], "walk_min_to_nearest_gtfs_stop"] = math.nan
    for threshold in (5, 8, 10, 12):
        out[f"covered_{threshold}min"] = out["walk_min_to_nearest_gtfs_stop"].le(threshold).fillna(False)
    out["accessibility_epistemic_status"] = ACCESS_STATUS
    return out


def boundary_comparison(
    building_allocations: pd.DataFrame,
    _building_points: pd.DataFrame,
    gate_b_dir,
    core_boundaries_path,
    *,
    core_codes: set[str],
    boundary_band_m: float,
    normalise_municipality,
) -> pd.DataFrame:
    boundaries = gpd.read_file(core_boundaries_path).to_crs(32632)
    boundaries["municipality_code"] = boundaries["PRO_COM_T"].map(normalise_municipality)
    boundary_map = boundaries.set_index("municipality_code").geometry.to_dict()

    cells = pd.read_csv(gate_b_dir / "population_cells_real.csv")
    cells["municipality_code"] = cells["PRO_COM_T"].map(normalise_municipality)
    cell_pts = gpd.GeoDataFrame(cells, geometry=gpd.points_from_xy(cells.lon, cells.lat), crs=4326).to_crs(32632)
    cell_pts["distance_to_municipal_boundary_m"] = [
        row.geometry.distance(boundary_map[row.municipality_code].boundary)
        for row in cell_pts.itertuples()
    ]
    v1 = (
        cell_pts.loc[cell_pts["distance_to_municipal_boundary_m"] <= boundary_band_m]
        .groupby("municipality_code")["pop_calibrated_2025"].sum().to_dict()
    )

    alloc = building_allocations.loc[building_allocations["municipality_code"].isin(core_codes)].copy()
    if alloc[["piece_x_utm32", "piece_y_utm32"]].isna().any().any():
        raise RuntimeError("piece point missing in boundary comparison")
    alloc["distance_to_municipal_boundary_m"] = [
        Point(float(r.piece_x_utm32), float(r.piece_y_utm32)).distance(boundary_map[r.municipality_code].boundary)
        for r in alloc.itertuples()
    ]
    v2 = (
        alloc.loc[alloc["distance_to_municipal_boundary_m"] <= boundary_band_m]
        .groupby("municipality_code")["building_piece_population_model"].sum().to_dict()
    )
    return pd.DataFrame([
        {
            "municipality_code": code,
            "boundary_band_m_assumption": boundary_band_m,
            "v1_worldpop_population_near_boundary": float(v1.get(code, 0.0)),
            "v2_building_population_near_boundary": float(v2.get(code, 0.0)),
            "v2_minus_v1_population_near_boundary": float(v2.get(code, 0.0) - v1.get(code, 0.0)),
            "epistemic_status": BOUNDARY_STATUS,
        }
        for code in sorted(core_codes)
    ])


def spatial_distribution_comparison(
    building_allocations: pd.DataFrame,
    _building_points: pd.DataFrame,
    gate_b_dir,
    *,
    core_codes: set[str],
    normalise_municipality,
) -> pd.DataFrame:
    cells = pd.read_csv(gate_b_dir / "population_cells_real.csv")
    cells["municipality_code"] = cells["PRO_COM_T"].map(normalise_municipality)
    cells_gdf = gpd.GeoDataFrame(cells, geometry=gpd.points_from_xy(cells.lon, cells.lat), crs=4326).to_crs(32632)
    cells_gdf["x"] = cells_gdf.geometry.x
    cells_gdf["y"] = cells_gdf.geometry.y
    alloc = building_allocations.loc[building_allocations["municipality_code"].isin(core_codes)].copy()
    if alloc[["piece_x_utm32", "piece_y_utm32"]].isna().any().any():
        raise RuntimeError("piece point missing in spatial distribution comparison")

    rows = []
    for code in sorted(core_codes) + ["CORE_TOTAL"]:
        v1 = cells_gdf if code == "CORE_TOTAL" else cells_gdf.loc[cells_gdf["municipality_code"] == code]
        v2 = alloc if code == "CORE_TOTAL" else alloc.loc[alloc["municipality_code"] == code]
        w1 = v1["pop_calibrated_2025"].astype(float)
        w2 = v2["building_piece_population_model"].astype(float)
        if float(w1.sum()) <= 0:
            raise RuntimeError(f"V1 population denominator non-positive for {code}")
        x1 = float((v1["x"] * w1).sum() / w1.sum())
        y1 = float((v1["y"] * w1).sum() / w1.sum())
        x2 = float((v2["piece_x_utm32"] * w2).sum() / w2.sum()) if w2.sum() else math.nan
        y2 = float((v2["piece_y_utm32"] * w2).sum() / w2.sum()) if w2.sum() else math.nan
        shift = math.hypot(x2 - x1, y2 - y1) if math.isfinite(x2) else math.nan
        rows.append({
            "municipality_code": code,
            "v1_worldpop_weighted_centroid_x_utm32": x1,
            "v1_worldpop_weighted_centroid_y_utm32": y1,
            "v2_building_weighted_centroid_x_utm32": x2,
            "v2_building_weighted_centroid_y_utm32": y2,
            "weighted_centroid_shift_m": shift,
            "epistemic_status": SPATIAL_STATUS,
        })
    return pd.DataFrame(rows)
