"""Sensitivity screen for the caller's south-of-SS342 area, not a mapped boundary.

The two envelopes are explicit design assumptions. Walking access uses the
same pinned RT016 population units and RT028 graph/matrix as RT031.
"""

import argparse
import csv
from decimal import Decimal
from fractions import Fraction
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.phase2_audit_rt031_conditional_new_stop_access_v3 import (
    EXPECTED as ACCESS_EXPECTED, scaled_core_weights, weighted_ratio,
)
from scripts.phase2_audit_rt031_local_stop_siting_v3 import sha256


EXPECTED = {
    "typed": ACCESS_EXPECTED["typed"],
    "siting": "61c18718037efe5b38bd31f621175055028b8ecad916093ce04ebb88ec630815",
    "matrix": ACCESS_EXPECTED["walk_matrix"],
    "pedestrian_osm": ACCESS_EXPECTED["osm_pedestrian"],
    "population_units": "edba328d0214bec3a17357d2f21aba316b7ce4596b8ef47dad0c0ac92e45cd54",
    "roads_normalized_newlines": "2a1082b10f5a6560bdf69e8dc344541d3a892f751054316ea582fef32fe6b4c4",
    "candidates_normalized_newlines": ACCESS_EXPECTED["candidates_normalized_newlines"],
}
ROAD_WAYS_WEST_TO_EAST = ("48540240", "48540239", "220035446", "26499969")
INNER_BOUNDS = (9.394, 45.720, 9.404, 45.7315)
OUTER_SOUTH_LAT = 45.7175
TARGET_CANDIDATE = "P2V2S_0031"
FS_STOP = "FROZEN::L00407"
THRESHOLDS = (5, 8, 10)


def south_of_road_envelopes(roads):
    from shapely.geometry import Polygon, box
    features = {str(item["properties"]["osm_id"]): item
                for item in roads["features"]}
    road_points = []
    for way_id in ROAD_WAYS_WEST_TO_EAST:
        feature = features[way_id]
        properties = feature["properties"]
        if (properties.get("name") != "Via Como"
                or '"ref"=>"SS342"' not in properties.get("other_tags", "")):
            raise ValueError(f"SS342 road identity drift: {way_id}")
        points = list(reversed(feature["geometry"]["coordinates"]))
        if road_points and road_points[-1] != points[0]:
            raise ValueError("SS342 screen boundary is discontinuous")
        road_points.extend(points if not road_points else points[1:])
    west_lon, east_lon = road_points[0][0], road_points[-1][0]
    outer = Polygon(road_points + [(east_lon, OUTER_SOUTH_LAT),
                                   (west_lon, OUTER_SOUTH_LAT)])
    inner = outer.intersection(box(*INNER_BOUNDS))
    if not outer.is_valid or not inner.is_valid or inner.is_empty:
        raise ValueError("invalid provisional area geometry")
    return {"inner": inner, "outer": outer}


def exact_weight(unit_ids, weight_map, mask):
    return str(sum((Decimal(weight_map[unit_ids[i]])
                    for i in np.flatnonzero(mask)), Decimal(0)))


def main(typed_path, siting_path, matrix_path, pedestrian_osm_path,
         population_path, output):
    from shapely.geometry import Point, mapping
    from phase2_final_stop_pedestrian_accessibility_substrate_v3 import (
        _dijkstra_to_stop, parse_osm_pedestrian_graph,
    )
    from phase2_rt029_v4_substrate import validate_walk_matrix

    roads_path = Path("data/raw/osm/osm_highways_core.geojson")
    candidates_path = Path("outputs/phase2/stop_universe_v2/proposed_stop_candidates.csv")
    paths = {"typed": typed_path, "siting": siting_path, "matrix": matrix_path,
             "pedestrian_osm": pedestrian_osm_path,
             "population_units": population_path,
             "roads_normalized_newlines": roads_path,
             "candidates_normalized_newlines": candidates_path}
    for label, path in paths.items():
        if sha256(path, label.endswith("_normalized_newlines")) != EXPECTED[label]:
            raise ValueError(f"pinned source drift: {label}")
    typed = json.loads(typed_path.read_text(encoding="utf-8"))
    siting = json.loads(siting_path.read_text(encoding="utf-8"))
    if (typed.get("contract") != "RT031_HUB_SPLIT_TYPED_ONE_LINE_V3"
            or typed.get("network_selected") is not False
            or typed.get("timetable_assigned") is not False):
        raise ValueError("typed non-decisional contract drift")
    candidate_site = next(option for option in siting["candidate_options"]
                          if option["candidate_id"] == TARGET_CANDIDATE)
    if (candidate_site["physical_status"] != "FIELD_CHECK_PENDING"
            or any(candidate_site["osm_way_traversed_by_variant"].values())):
        raise ValueError("candidate route/siting evidence drift")
    areas = south_of_road_envelopes(json.loads(roads_path.read_text(encoding="utf-8")))
    with population_path.open("r", encoding="utf-8", newline="") as stream:
        population = {row["unit_id"]: row for row in csv.DictReader(stream)}
    with candidates_path.open("r", encoding="utf-8", newline="") as stream:
        candidate = next(row for row in csv.DictReader(stream)
                         if row["candidate_id"] == TARGET_CANDIDATE)
    if (candidate["physical_status"] != "FIELD_CHECK_PENDING"
            or candidate["osm_way_id"] != "40627763"):
        raise ValueError("southern candidate source drift")
    raw = pd.read_csv(matrix_path, dtype={"population_weight_2025": str,
                                          "population_snap_node_id": str},
                      usecols=["population_unit_id", "population_weight_2025",
                               "population_scope", "population_municipality_code",
                               "population_municipality_name", "stop_place_id",
                               "stop_service_class", "walk_time_min",
                               "reachability_status", "population_snap_node_id",
                               "population_connector_distance_m"])
    unit_snap = raw[["population_unit_id", "population_snap_node_id",
                     "population_connector_distance_m"]].drop_duplicates()
    if unit_snap["population_unit_id"].duplicated().any():
        raise ValueError("population snap drift")
    snap_map = unit_snap.set_index("population_unit_id").to_dict("index")
    weight_rows = raw[["population_unit_id", "population_weight_2025"]].drop_duplicates()
    if weight_rows["population_unit_id"].duplicated().any():
        raise ValueError("population weight drift across stops")
    matrix_weights = weight_rows.set_index("population_unit_id")[
        "population_weight_2025"].to_dict()
    substrate = validate_walk_matrix(raw)
    meta = substrate.population_meta
    unit_ids = meta["population_unit_id"].tolist()
    if set(unit_ids) != set(population):
        raise ValueError("RT016/RT028 population unit mismatch")
    for unit_id in unit_ids:
        if abs(Decimal(matrix_weights[unit_id]) - Decimal(
                population[unit_id]["population_weight_2025"])) > Decimal("0.000000000001"):
            raise ValueError("RT016/RT028 population weight drift")
    core, weights = scaled_core_weights(substrate, matrix_weights)
    olgiate = meta["population_municipality_code"].astype(str).to_numpy() == "97058"
    points = [Point(float(population[unit_id]["lon"]),
                    float(population[unit_id]["lat"])) for unit_id in unit_ids]
    graph = parse_osm_pedestrian_graph(pedestrian_osm_path)
    if graph.graph_digest != "aaad8a16e4c3715161cce6f686acccbf29e4e9def57424e8ad02594c9a69f1f4":
        raise ValueError("pedestrian graph drift")
    snap = graph.snap(float(candidate["lat"]), float(candidate["lon"]))
    if snap.status != "REACHABLE" or not snap.node_id:
        raise ValueError("candidate graph snap drift")
    distances = _dijkstra_to_stop(graph.reverse_adjacency, snap.node_id)
    candidate_time = np.array([
        (float(snap_map[unit]["population_connector_distance_m"])
         + distances.get(str(snap_map[unit]["population_snap_node_id"]), math.inf)
         + float(snap.connector_distance_m)) / 80
        for unit in unit_ids], dtype=float)
    station_time = substrate.walk_time_matrix[:, substrate.stop_index[FS_STOP]]
    area_rows = {}
    for area_name, polygon in areas.items():
        eligible = np.array([polygon.covers(point) for point in points]) & core & olgiate
        if not eligible.any():
            raise ValueError("empty provisional area")
        patterns = {}
        for name, pattern in sorted(typed["directional_patterns"].items()):
            stops = [substrate.stop_index[stop]
                     for stop in pattern["available_stop_ids"]]
            base_time = np.min(substrate.walk_time_matrix[:, stops], axis=1)
            patterns[name] = {
                str(t): {
                    "baseline_walk_access": str(weighted_ratio(base_time <= t, weights, eligible)),
                    "hypothetical_with_P2V2S_0031_walk_access": str(weighted_ratio(
                        np.minimum(base_time, candidate_time) <= t, weights, eligible)),
                    "conditional_marginal": str(weighted_ratio(
                        (candidate_time <= t) & (base_time > t), weights, eligible)),
                } for t in THRESHOLDS}
            for row in patterns[name].values():
                if (Fraction(row["baseline_walk_access"])
                        + Fraction(row["conditional_marginal"])
                        != Fraction(row["hypothetical_with_P2V2S_0031_walk_access"])):
                    raise ValueError("conditional walking access decomposition drift")
        area_rows[area_name] = {
            "geometry": mapping(polygon),
            "unit_count": int(eligible.sum()),
            "modelled_population_weight": exact_weight(unit_ids, matrix_weights, eligible),
            "direct_walk_to_FS": {
                str(t): str(weighted_ratio(station_time <= t, weights, eligible))
                for t in THRESHOLDS},
            "patterns": patterns,
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "contract": "RT031_SOUTH_OLGIATE_PROVISIONAL_AREA_SENSITIVITY_V3",
        "status": "NON_DECISIONAL_UNVERIFIED_AREA_AND_HYPOTHETICAL_STOP",
        "input_sha256": EXPECTED,
        "north_boundary_osm_ss342_way_ids_west_to_east": ROAD_WAYS_WEST_TO_EAST,
        "inner_clip_bounds_lon_lat": INNER_BOUNDS,
        "outer_south_lat_assumption": OUTER_SOUTH_LAT,
        "area_shapes_are_assumptions_not_digitised_caller_outline": True,
        "municipal_population_units_only": True,
        "source_population_is_modelled_not_observed_od": True,
        "candidate_id": TARGET_CANDIDATE,
        "candidate_physical_status": candidate["physical_status"],
        "candidate_connector_m": snap.connector_distance_m,
        "candidate_road_traversed_by_current_four_paths": False,
        "bus_route_to_candidate_certified": False,
        "directional_service_event_at_candidate_certified": False,
        "results_are_potential_walking_access_not_fs_passenger_journeys": True,
        "areas": area_rows,
        "decision_budget_km": None,
        "uncertainty_band_min": None,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
    }
    output.write_bytes((json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":")) + "\n").encode("utf-8"))
    print(json.dumps({name: {"units": row["unit_count"]}
                      for name, row in area_rows.items()}, sort_keys=True))
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--typed", type=Path, required=True)
    parser.add_argument("--siting", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--pedestrian-osm", type=Path, required=True)
    parser.add_argument("--population", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.typed, args.siting, args.matrix, args.pedestrian_osm,
         args.population, args.output)
