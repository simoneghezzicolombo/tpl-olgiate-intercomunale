#!/usr/bin/env python3
"""Gate D baseline calibration without hard-coded outer route endpoints.

For D184/D185, the representative baseline in each GTFS direction is the most
frequently operated exact stop pattern that includes an official Olgiate Molgora
station stop. This is DERIVED from the official reference-period GTFS; no external
terminus such as Ravellino, Caprino or Celana is hard-coded.

For spatial calibration only, ordered stop coordinates are projected onto the
representative trip's own official GTFS shape before road snapping. This resolves
internal GTFS stop/shape coordinate inconsistencies without inventing geometry and
records the displacement as a reconstruction diagnostic. Schedule times remain the
unaltered official stop_times FACT.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Apply the exact Gate D bus > psv > generic access hierarchy first.
import gate_d_structural_candidates_v4  # noqa: F401
import gate_d_baseline_calibration as calibration


SELECTION_STATUS = "DERIVED_MOST_FREQUENT_OLGIATE_STATION_ANCHORED_OFFICIAL_GTFS_PATTERN"
SPATIAL_STATUS = "RECONSTRUCTED_FROM_OFFICIAL_GTFS_STOP_SEQUENCE_CONSTRAINED_TO_OFFICIAL_GTFS_SHAPE"


def _is_olgiate_station(name: str) -> bool:
    text = calibration.normal(name)
    return "olgiate molgora" in text and "stazione f.s." in text


def dominant_olgiate_patterns(feed: dict, route_name: str) -> list[dict]:
    routes = feed["routes"]
    trips = feed["trips"]
    stop_times = feed["stop_times"]
    stops = feed["stops"]
    short_map = calibration.structural.route_short_map(feed)
    route_ids = {route_id for route_id, short in short_map.items() if short == route_name}
    target_trips = trips[trips["route_id"].isin(route_ids)].copy()
    if target_trips.empty:
        raise ValueError(f"{route_name}: no trips in official GTFS")

    stop_name_map = dict(zip(stops["stop_id"].astype(str), stops["stop_name"].astype(str)))
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
        names = [stop_name_map.get(stop_id, "") for stop_id in pattern]
        if not any(_is_olgiate_station(name) for name in names):
            continue
        direction = str(trip.get("direction_id", "NA"))
        by_direction.setdefault(direction, Counter())[pattern] += 1
        exemplar.setdefault((direction, pattern), trip_id)

    rows = []
    for direction, counter in sorted(by_direction.items()):
        # Frequency first; ties prefer more stops, then lexical ids. This selects
        # the dominant official service pattern without prescribing its far end.
        ranked = sorted(counter.items(), key=lambda item: (-item[1], -len(item[0]), item[0]))
        pattern, pattern_count = ranked[0]
        rows.append({
            "route_short_name": route_name,
            "direction_id": direction,
            "pattern": pattern,
            "pattern_trip_count": int(pattern_count),
            "representative_trip_id": exemplar[(direction, pattern)],
            "pattern_selection_status": SELECTION_STATUS,
        })
    if not rows:
        raise ValueError(f"{route_name}: no Olgiate-station-anchored official pattern found")
    return rows


def _official_shape_for_trip(feed: dict, trip_id: str) -> LineString:
    trip_rows = feed["trips"][feed["trips"]["trip_id"] == trip_id]
    if len(trip_rows) != 1:
        raise ValueError(f"{trip_id}: expected exactly one official GTFS trip row")
    shape_id = trip_rows.iloc[0].get("shape_id")
    if pd.isna(shape_id):
        raise ValueError(f"{trip_id}: missing official GTFS shape_id")
    points = feed["shapes"][feed["shapes"]["shape_id"] == shape_id].copy()
    if len(points) < 2:
        raise ValueError(f"{trip_id}: official GTFS shape has fewer than two points")
    points["shape_pt_sequence"] = pd.to_numeric(points["shape_pt_sequence"], errors="raise")
    points = points.sort_values("shape_pt_sequence")
    return LineString(list(zip(points["shape_pt_lon"].astype(float), points["shape_pt_lat"].astype(float))))


def shape_constrained_feed(feed: dict, pattern_row: dict) -> tuple[dict, dict]:
    """Return a copy whose pattern stop coordinates lie on the trip's official shape."""
    trip_id = pattern_row["representative_trip_id"]
    shape_wgs = _official_shape_for_trip(feed, trip_id)
    shape_metric = gpd.GeoSeries([shape_wgs], crs=4326).to_crs(32632).iloc[0]

    stops = feed["stops"].copy()
    stop_ids = list(pattern_row["pattern"])
    displacement = []
    projected_positions = []

    for stop_id in stop_ids:
        rows = stops[stops["stop_id"] == stop_id]
        if len(rows) != 1:
            raise ValueError(f"{trip_id}: stop {stop_id} is not unique in official stops.txt")
        row = rows.iloc[0]
        point_wgs = gpd.GeoSeries(
            gpd.points_from_xy([float(row["stop_lon"])], [float(row["stop_lat"])]), crs=4326
        ).iloc[0]
        point_metric = gpd.GeoSeries([point_wgs], crs=4326).to_crs(32632).iloc[0]
        position = float(shape_metric.project(point_metric))
        nearest_metric = shape_metric.interpolate(position)
        displacement.append(float(point_metric.distance(nearest_metric)))
        projected_positions.append(position)
        nearest_wgs = gpd.GeoSeries([nearest_metric], crs=32632).to_crs(4326).iloc[0]
        mask = stops["stop_id"] == stop_id
        stops.loc[mask, "stop_lon"] = str(float(nearest_wgs.x))
        stops.loc[mask, "stop_lat"] = str(float(nearest_wgs.y))

    # A simple route pattern should progress monotonically along its own official
    # shape. Fail closed rather than silently reorder stops if GTFS is inconsistent.
    tolerance_m = 5.0
    if any(b + tolerance_m < a for a, b in zip(projected_positions[:-1], projected_positions[1:])):
        raise ValueError(f"{trip_id}: stop sequence is not monotonic along official GTFS shape")

    corrected = dict(feed)
    corrected["stops"] = stops
    diagnostics = {
        "gtfs_stops_shape_constrained": len(stop_ids),
        "max_original_stop_to_shape_m": max(displacement) if displacement else 0.0,
        "median_original_stop_to_shape_m": float(pd.Series(displacement).median()) if displacement else 0.0,
        "baseline_spatial_status": SPATIAL_STATUS,
        "shape_monotonicity_tolerance_m": tolerance_m,
        "shape_monotonicity_tolerance_status": "ASSUMPTION_NUMERICAL_TOLERANCE_NOT_ROUTE_METRIC",
    }
    return corrected, diagnostics


_original_route_pattern = calibration.route_pattern


def route_pattern_v4(feed, graph, turn_rules, nodes, node_array, pattern_row, max_snap_m=250.0):
    corrected_feed, diagnostics = shape_constrained_feed(feed, pattern_row)
    row, geometry = _original_route_pattern(
        corrected_feed,
        graph,
        turn_rules,
        nodes,
        node_array,
        pattern_row,
        max_snap_m=max_snap_m,
    )
    row.update(diagnostics)
    row["pattern_selection_status"] = pattern_row["pattern_selection_status"]
    return row, geometry


calibration.full_route_patterns = dominant_olgiate_patterns
calibration.route_pattern = route_pattern_v4


if __name__ == "__main__":
    raise SystemExit(calibration.main())
