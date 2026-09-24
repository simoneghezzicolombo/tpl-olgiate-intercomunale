"""Conditional five-municipality walking access for the single Linea 8 brief."""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from phase2_final_stop_pedestrian_accessibility_substrate_v3 import (
    _dijkstra_to_stop, parse_osm_pedestrian_graph,
)
from phase2_rt029_v4_substrate import validate_walk_matrix
from scripts.phase2_audit_rt031_conditional_new_stop_access_v3 import (
    scaled_core_weights, weighted_ratio,
)
from scripts.phase2_bind_rt031_joint_target_witness_v3 import CURRENT_PATH, CURRENT_SHA256
from scripts.phase2_build_rt031_municipal_access_frontier_v4 import MUNICIPALITY_NAMES
from scripts.phase2_probe_rt031_unique_line_v3 import WEST, EAST


EXPECTED = {
    "matrix": "a47bbce413d056db185180173ab2f05dce0463cb626a2c81f4aff64de91b50c1",
    "pedestrian_osm": "896f192bbb481f0c07cdc5d695424bf29de85f89ac33ea72986a06e521b424cd",
    "candidates_normalized": "bf3f5c648803fb0ba03b2f9af2bd4fa02924cb387bb0a752fc3a7a8ee1f14bc0",
}


def sha256(path, normalized=False):
    data = path.read_bytes()
    return hashlib.sha256(data.replace(b"\r\n", b"\n") if normalized else data).hexdigest()


def pedestrian_time(graph, snap_map, unit_ids, lat, lon):
    snap = graph.snap(lat, lon)
    if snap.status != "REACHABLE" or not snap.node_id:
        raise ValueError("hypothetical stop cannot attach to pedestrian graph")
    distances = _dijkstra_to_stop(graph.reverse_adjacency, snap.node_id)
    times = np.array([
        (float(snap_map[unit]["population_connector_distance_m"])
         + distances.get(str(snap_map[unit]["population_snap_node_id"]), math.inf)
         + float(snap.connector_distance_m)) / 80
        for unit in unit_ids], dtype=float)
    return times, {"status": snap.status, "graph_node_id": snap.node_id,
                   "connector_distance_m": round(float(snap.connector_distance_m), 3)}


def main(paths, output):
    for key in EXPECTED:
        if sha256(paths[key], key.endswith("normalized")) != EXPECTED[key]:
            raise ValueError(f"pinned source drift: {key}")
    road = json.loads(paths["road_screen"].read_text(encoding="utf-8"))
    if (road.get("contract") != "RT031_UNIQUE_LINE_ROAD_SCREEN_V3"
            or road.get("network_selected") is not False
            or road["south_proxy"]["boarding_stop_certified"] is not False
            or road["north_proxy"]["boarding_stop_certified"] is not False):
        raise ValueError("road-screen semantics drift")
    repair = json.loads(paths["repair_screen"].read_text(encoding="utf-8"))
    if (repair.get("contract") != "RT031_CURRENT_STOP_REPAIR_ROAD_SCREEN_V3"
            or repair.get("network_selected") is not False):
        raise ValueError("current-stop repair semantics drift")
    if sha256(CURRENT_PATH) != CURRENT_SHA256:
        raise ValueError("current exact-stop reference drift")
    current_ids = set(json.loads(CURRENT_PATH.read_text(encoding="utf-8"))
                      ["current_exact_identity_subset"]["mapped_stop_place_ids"])
    with paths["candidates_normalized"].open(encoding="utf-8", newline="") as stream:
        south = next(r for r in csv.DictReader(stream)
                     if r["candidate_id"] == "P2V2S_0031")
    if south["physical_status"] != "FIELD_CHECK_PENDING":
        raise ValueError("south candidate status drift")
    raw = pd.read_csv(paths["matrix"], dtype={
        "population_unit_id": str, "population_weight_2025": str,
        "population_snap_node_id": str, "population_municipality_code": str,
        "stop_place_id": str}, usecols=[
            "population_unit_id", "population_weight_2025", "population_scope",
            "population_municipality_code", "population_municipality_name",
            "stop_place_id", "stop_service_class", "walk_time_min",
            "reachability_status", "population_snap_node_id",
            "population_connector_distance_m"])
    raw["population_municipality_code"] = raw["population_municipality_code"].map(
        lambda value: str(int(value)))
    snap_rows = raw[["population_unit_id", "population_weight_2025",
                     "population_snap_node_id", "population_connector_distance_m"]].drop_duplicates()
    if snap_rows["population_unit_id"].duplicated().any():
        raise ValueError("population unit snap or weight drift")
    snap_map = snap_rows.set_index("population_unit_id")[
        ["population_snap_node_id", "population_connector_distance_m"]].to_dict("index")
    weight_map = snap_rows.set_index("population_unit_id")["population_weight_2025"].to_dict()
    substrate = validate_walk_matrix(raw)
    meta = substrate.population_meta
    unit_ids = meta["population_unit_id"].astype(str).tolist()
    if set(unit_ids) != set(snap_map):
        raise ValueError("population universe drift")
    core, weights = scaled_core_weights(substrate, weight_map)
    codes = meta["population_municipality_code"].astype(str).to_numpy()
    if tuple(sorted(set(codes[core]))) != tuple(MUNICIPALITY_NAMES):
        raise ValueError("five-municipality universe drift")
    stop_ids = sorted({value for _, value in WEST + EAST
                       if value.startswith(("ASF::", "FROZEN::"))})
    if any(stop not in substrate.stop_index for stop in stop_ids):
        raise ValueError("representative stop not in walking matrix")
    if any(stop not in substrate.stop_index for stop in current_ids):
        raise ValueError("current exact stop not in walking matrix")
    baseline = np.min(substrate.walk_time_matrix[:,
                      [substrate.stop_index[stop] for stop in stop_ids]], axis=1)
    current_time = np.min(substrate.walk_time_matrix[:,
                          [substrate.stop_index[stop] for stop in sorted(current_ids)]], axis=1)
    encountered_ids = road["existing_stop_attachment_nodes_encountered_in_both_full_directions"]
    if any(stop not in substrate.stop_index for stop in encountered_ids):
        raise ValueError("encountered existing stop not in walking matrix")
    encountered_time = np.min(substrate.walk_time_matrix[:,
                              [substrate.stop_index[stop] for stop in encountered_ids]], axis=1)
    graph = parse_osm_pedestrian_graph(paths["pedestrian_osm"])
    if graph.graph_digest != "aaad8a16e4c3715161cce6f686acccbf29e4e9def57424e8ad02594c9a69f1f4":
        raise ValueError("pedestrian graph drift")
    south_time, south_snap = pedestrian_time(
        graph, snap_map, unit_ids, float(south["lat"]), float(south["lon"]))
    north_time, north_snap = pedestrian_time(
        graph, snap_map, unit_ids, float(road["north_proxy"]["lat"]),
        float(road["north_proxy"]["lon"]))
    scenarios = {
        "current_exact_identity_subset": current_time,
        "representative_existing_stops_only": baseline,
        "hypothetical_plus_south": np.minimum(baseline, south_time),
        "hypothetical_plus_north": np.minimum(baseline, north_time),
        "hypothetical_plus_both": np.minimum(np.minimum(baseline, south_time), north_time),
        "all_existing_attachment_nodes_encountered_in_both_directions": encountered_time,
        "all_encountered_plus_both_hypothetical": np.minimum(
            np.minimum(encountered_time, south_time), north_time),
    }
    for order, option in repair["combined_repair_order_options"].items():
        expected_count = {"THREE": 9, "FOUR": 10, "FIVE": 11}[order.split("_", 1)[0]]
        if (option["reachable_both_directions"] is not True
                or option["represented_via_node_bad_turn_count"] != 0
                or option["represented_via_node_joins_at_fs_allowed"] is not True
                or option["known_successor_via_way_overlap"]
                or option["previously_encountered_stop_ids_lost"]
                or option["current_exact_stop_ids_encountered_count"] != expected_count):
            raise ValueError("repair option road-screen drift")
        ids = option["both_direction_encountered_stop_ids"]
        if any(stop not in substrate.stop_index for stop in ids):
            raise ValueError("repair stop not in walking matrix")
        repaired_time = np.min(substrate.walk_time_matrix[:,
                               [substrate.stop_index[stop] for stop in ids]], axis=1)
        scenarios["repair_" + order + "_plus_both_hypothetical"] = np.minimum(
            np.minimum(repaired_time, south_time), north_time)
    access = {}
    for name, times in scenarios.items():
        access[name] = {}
        for code, municipality in (("TOTAL", "Five municipalities"), *MUNICIPALITY_NAMES.items()):
            eligible = core if code == "TOTAL" else core & (codes == code)
            access[name][code] = {
                "municipality": municipality,
                "potential_walking_access_fraction": {
                    str(threshold): str(weighted_ratio(times <= threshold, weights, eligible))
                    for threshold in (5, 8, 10)},
            }
    comparison_time = scenarios["all_encountered_plus_both_hypothetical"]
    current_change = {}
    for code, municipality in (("TOTAL", "Five municipalities"), *MUNICIPALITY_NAMES.items()):
        eligible = core if code == "TOTAL" else core & (codes == code)
        current_change[code] = {
            "municipality": municipality,
            "newly_covered_fraction": {str(t): str(weighted_ratio(
                (comparison_time <= t) & (current_time > t), weights, eligible))
                for t in (5, 8, 10)},
            "no_longer_covered_fraction": {str(t): str(weighted_ratio(
                (comparison_time > t) & (current_time <= t), weights, eligible))
                for t in (5, 8, 10)},
        }
    repair_change = {}
    for name, times in scenarios.items():
        if not name.startswith("repair_"):
            continue
        repair_change[name] = {}
        for code, municipality in (("TOTAL", "Five municipalities"), *MUNICIPALITY_NAMES.items()):
            eligible = core if code == "TOTAL" else core & (codes == code)
            repair_change[name][code] = {
                "municipality": municipality,
                "newly_covered_fraction": {str(t): str(weighted_ratio(
                    (times <= t) & (current_time > t), weights, eligible))
                    for t in (5, 8, 10)},
                "no_longer_covered_fraction": {str(t): str(weighted_ratio(
                    (times > t) & (current_time <= t), weights, eligible))
                    for t in (5, 8, 10)},
            }
    payload = {
        "contract": "RT031_UNIQUE_LINE_CONDITIONAL_WALK_ACCESS_V3",
        "status": "NON_DECISIONAL_POTENTIAL_WALKING_ACCESS",
        "input_sha256": {key: sha256(value, key.endswith("normalized")
                                      or key in ("road_screen", "repair_screen"))
                         for key, value in paths.items()},
        "representative_existing_stop_ids": stop_ids,
        "existing_attachment_node_stop_ids_encountered_both_directions": encountered_ids,
        "encountered_node_is_ordered_boarding_event": False,
        "current_exact_stop_identity_retention_if_all_encountered_are_served": {
            "retained_ids": sorted(set(encountered_ids) & current_ids),
            "retained_count": len(set(encountered_ids) & current_ids),
            "current_subset_count": len(current_ids),
            "current_subset_sha256": CURRENT_SHA256,
            "semantics": "identity intersection only; directional occurrence and passenger service not certified",
        },
        "south": {"candidate_id": "P2V2S_0031", "physical_status": "FIELD_CHECK_PENDING",
                  "pedestrian_snap": south_snap, "boarding_event_certified": False},
        "north": {"road_node_proxy_id": road["north_proxy"]["graph_node_id"],
                  "stop_exists": False, "pedestrian_snap": north_snap,
                  "boarding_event_certified": False},
        "access": access,
        "conditional_change_vs_current_exact_identity_subset": current_change,
        "repair_change_vs_current_exact_identity_subset": repair_change,
        "scope": "core RT028 population; potential walk to a representative or hypothetical stop only",
        "directional_service_or_fs_journey_certified": False,
        "access_is_observed_demand": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "decision_budget_km": None,
        "uncertainty_band_min": None,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                 separators=(",", ":")) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for key in (*EXPECTED, "road_screen", "repair_screen"):
        parser.add_argument("--" + key, required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    main({key: getattr(args, key) for key in (*EXPECTED, "road_screen", "repair_screen")}, args.output)
