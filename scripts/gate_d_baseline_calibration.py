#!/usr/bin/env python3
"""Gate D baseline road-routing and running-time calibration audit.

D184 and D185 are reconstructed from official Arriva GTFS stop sequences and routed
through the same structural OSM graph used for candidate loops. Only full endpoint-
to-endpoint patterns are admitted. Scheduled GTFS terminal-to-terminal time is
compared with the road model's pure-running time; the comparison is diagnostic and
is NOT used to silently calibrate candidate runtimes.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_d_route_integrity as routing
import gate_d_structural_candidates as structural

OUT = Path("data/audit_gate_d")
DEFAULT_ROADS = OUT / "osm_gate_d_structural.geojson"
DEFAULT_RESTRICTIONS = OUT / "osm_turn_restrictions_routable.csv"
DEFAULT_GTFS = OUT / "raw/arriva_addabus_2025_2026.zip"

ROUTE_ENDPOINT_TOKENS = {
    "D184": ("olgiate", "ravellino"),
    "D185": ("olgiate", "celana"),
}


def normal(value: str) -> str:
    return structural._normal(value)


def full_route_patterns(feed: dict, route_name: str) -> list[dict]:
    routes = feed["routes"]
    trips = feed["trips"]
    stop_times = feed["stop_times"]
    stops = feed["stops"]
    short_map = structural.route_short_map(feed)
    route_ids = {route_id for route_id, short in short_map.items() if short == route_name}
    target_trips = trips[trips["route_id"].isin(route_ids)].copy()
    if target_trips.empty:
        raise ValueError(f"{route_name}: no trips in official GTFS")

    stop_name_map = dict(zip(stops["stop_id"].astype(str), stops["stop_name"].astype(str)))
    endpoint_a, endpoint_b = ROUTE_ENDPOINT_TOKENS[route_name]
    by_direction: dict[str, Counter] = {}
    exemplar: dict[tuple[str, tuple[str, ...]], str] = {}

    for _, trip in target_trips.iterrows():
        trip_id = str(trip["trip_id"])
        group = stop_times[stop_times["trip_id"] == trip_id].copy()
        if group.empty:
            continue
        group["stop_sequence"] = pd.to_numeric(group["stop_sequence"], errors="raise")
        group = group.sort_values("stop_sequence")
        pattern = tuple(group["stop_id"].astype(str))
        names = [normal(stop_name_map.get(stop_id, "")) for stop_id in pattern]
        has_a = any(endpoint_a in name for name in names)
        has_b = any(endpoint_b in name for name in names)
        if not (has_a and has_b):
            continue
        direction = str(trip.get("direction_id", "NA"))
        by_direction.setdefault(direction, Counter())[pattern] += 1
        exemplar.setdefault((direction, pattern), trip_id)

    rows = []
    for direction, counter in sorted(by_direction.items()):
        # Prefer the most frequently operated full pattern. Ties favour the pattern
        # with more stops, then lexical stop-id order for deterministic output.
        ranked = sorted(counter.items(), key=lambda item: (-item[1], -len(item[0]), item[0]))
        pattern, pattern_count = ranked[0]
        rows.append({
            "route_short_name": route_name,
            "direction_id": direction,
            "pattern": pattern,
            "pattern_trip_count": int(pattern_count),
            "representative_trip_id": exemplar[(direction, pattern)],
        })
    if not rows:
        raise ValueError(f"{route_name}: no full endpoint-to-endpoint pattern found")
    return rows


def hhmmss_minutes(value: str) -> float:
    return structural.hhmmss_minutes(value)


def route_pattern(
    feed: dict,
    graph,
    turn_rules: dict,
    nodes: list,
    node_array,
    pattern_row: dict,
    max_snap_m: float = 250.0,
) -> tuple[dict, LineString]:
    stops = feed["stops"].copy()
    stop_times = feed["stop_times"].copy()
    stop_lookup = stops.set_index("stop_id")
    pattern = list(pattern_row["pattern"])

    point_rows = []
    for sequence, stop_id in enumerate(pattern, start=1):
        if stop_id not in stop_lookup.index:
            raise ValueError(f"GTFS stop {stop_id} missing from stops.txt")
        row = stop_lookup.loc[stop_id]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        point_rows.append({
            "sequence": sequence,
            "stop_id": stop_id,
            "stop_name": str(row["stop_name"]),
            "lon": float(row["stop_lon"]),
            "lat": float(row["stop_lat"]),
        })
    points = gpd.GeoDataFrame(
        point_rows,
        geometry=gpd.points_from_xy(
            [row["lon"] for row in point_rows],
            [row["lat"] for row in point_rows],
        ),
        crs=4326,
    ).to_crs(32632)
    snapped = [structural.snap_point(nodes, node_array, geom) for geom in points.geometry]
    max_snap = max(distance for _, distance in snapped)
    if max_snap > max_snap_m:
        offending = max(range(len(snapped)), key=lambda idx: snapped[idx][1])
        raise ValueError(
            f"{pattern_row['route_short_name']} direction {pattern_row['direction_id']}: "
            f"stop {point_rows[offending]['stop_id']} snap {max_snap:.1f} m exceeds {max_snap_m:.1f} m"
        )

    traversed = []
    snapped_nodes = [node for node, _ in snapped]
    for start, end in zip(snapped_nodes[:-1], snapped_nodes[1:]):
        if start == end:
            continue
        edge_path = routing.shortest_bus_edges(graph, start, end, turn_rules)
        for u, v, edge_key in edge_path:
            traversed.append((u, v, edge_key, graph.get_edge_data(u, v, edge_key)))
    if not traversed:
        raise ValueError(f"{pattern_row['route_short_name']}: no baseline road edges produced")

    total_m = sum(float(item[3]["length_m"]) for item in traversed)
    model_min = sum(float(item[3]["running_minutes"]) for item in traversed)
    uncertain_m = sum(
        float(item[3]["length_m"])
        for item in traversed
        if item[3].get("uncertainty_flags")
    )

    coords = []
    for _, _, _, data in traversed:
        part = list(data["geometry"].coords)
        coords.extend(part[1:] if coords and coords[-1] == part[0] else part)
    geometry = LineString(coords)

    trip_id = pattern_row["representative_trip_id"]
    trip_times = stop_times[stop_times["trip_id"] == trip_id].copy()
    trip_times["stop_sequence"] = pd.to_numeric(trip_times["stop_sequence"], errors="raise")
    trip_times = trip_times.sort_values("stop_sequence")
    scheduled_min = hhmmss_minutes(trip_times.iloc[-1]["arrival_time"]) - hhmmss_minutes(
        trip_times.iloc[0]["departure_time"]
    )
    if scheduled_min <= 0:
        raise ValueError(f"{trip_id}: non-positive scheduled runtime")

    trip_row = feed["trips"][feed["trips"]["trip_id"] == trip_id].iloc[0]
    shape_id = trip_row.get("shape_id")
    shape_km = None
    shape_coverage_pct = None
    if pd.notna(shape_id):
        shapes = feed["shapes"]
        shape_points = shapes[shapes["shape_id"] == shape_id].copy()
        if len(shape_points) >= 2:
            shape_points["shape_pt_sequence"] = pd.to_numeric(
                shape_points["shape_pt_sequence"], errors="raise"
            )
            shape_points = shape_points.sort_values("shape_pt_sequence")
            shape_geom = gpd.GeoSeries(
                [LineString(list(zip(
                    shape_points["shape_pt_lon"].astype(float),
                    shape_points["shape_pt_lat"].astype(float),
                )))],
                crs=4326,
            ).to_crs(32632).iloc[0]
            shape_km = float(shape_geom.length) / 1000.0
            coverage_m = float(geometry.intersection(shape_geom.buffer(35)).length)
            shape_coverage_pct = 100.0 * coverage_m / total_m if total_m else None

    return {
        "route_short_name": pattern_row["route_short_name"],
        "direction_id": pattern_row["direction_id"],
        "representative_trip_id": trip_id,
        "pattern_trip_count": pattern_row["pattern_trip_count"],
        "stop_count": len(pattern),
        "road_route_km": total_m / 1000.0,
        "gtfs_shape_km": shape_km,
        "road_vs_gtfs_shape_pct": (
            100.0 * ((total_m / 1000.0) - shape_km) / shape_km
            if shape_km and shape_km > 0 else None
        ),
        "road_route_inside_gtfs_shape_35m_pct": shape_coverage_pct,
        "scheduled_terminal_to_terminal_min": scheduled_min,
        "model_pure_running_min": model_min,
        "scheduled_minus_model_min": scheduled_min - model_min,
        "scheduled_to_model_ratio": scheduled_min / model_min if model_min > 0 else None,
        "uncertain_road_km": uncertain_m / 1000.0,
        "max_stop_snap_m": max_snap,
        "distance_status": "DERIVED_OSM_STRUCTURAL",
        "schedule_status": "FACT_OFFICIAL_GTFS_REFERENCE_PERIOD",
        "model_status": "MODEL_OUTPUT_NOT_OBSERVED",
        "calibration_status": "DIAGNOSTIC_ONLY_NOT_APPLIED_TO_CANDIDATES",
    }, geometry


def audit(roads_path: Path, restrictions_path: Path, gtfs_path: Path):
    roads = gpd.read_file(roads_path)
    feed = structural.read_gtfs(gtfs_path, "ARRIVA_ADDABUS_OFFICIAL_2025_2026")
    graph = routing.build_bus_graph(roads)
    turn_rules = routing.load_turn_restrictions(restrictions_path)
    nodes, node_array = structural.node_index(graph)

    metrics = []
    geoms = []
    for route_name in ("D184", "D185"):
        for pattern in full_route_patterns(feed, route_name):
            row, geometry = route_pattern(feed, graph, turn_rules, nodes, node_array, pattern)
            metrics.append(row)
            geoms.append({
                "route_short_name": row["route_short_name"],
                "direction_id": row["direction_id"],
                "representative_trip_id": row["representative_trip_id"],
                "geometry": geometry,
            })
    return pd.DataFrame(metrics), gpd.GeoDataFrame(geoms, geometry="geometry", crs=32632).to_crs(4326)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--roads", default=str(DEFAULT_ROADS))
    parser.add_argument("--restrictions", default=str(DEFAULT_RESTRICTIONS))
    parser.add_argument("--gtfs", default=str(DEFAULT_GTFS))
    parser.add_argument("--out-dir", default=str(OUT))
    args = parser.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    metrics, geometries = audit(Path(args.roads), Path(args.restrictions), Path(args.gtfs))
    metrics.to_csv(out / "structural_baseline_calibration.csv", index=False)
    geometries.to_file(out / "structural_baseline_geometry.geojson", driver="GeoJSON")

    summary = {
        "routes": sorted(metrics["route_short_name"].unique().tolist()),
        "baseline_patterns_routed": int(len(metrics)),
        "median_scheduled_to_model_ratio": float(metrics["scheduled_to_model_ratio"].median()),
        "median_abs_scheduled_minus_model_min": float(metrics["scheduled_minus_model_min"].abs().median()),
        "minimum_gtfs_shape_coverage_35m_pct": float(
            metrics["road_route_inside_gtfs_shape_35m_pct"].dropna().min()
        ),
        "epistemic_status": "MIXED_FACT_SCHEDULE_DERIVED_DISTANCE_MODEL_OUTPUT_TIME",
        "candidate_runtime_calibration_applied": False,
        "reason_not_applied": (
            "Baseline scheduled time includes stopping, dwell and traffic effects whereas candidate metric is pure-running time; the comparison is a model-bias diagnostic, not a transferable scalar."
        ),
    }
    (out / "structural_baseline_calibration_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    print(metrics.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
