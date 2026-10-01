"""Conditional walking-access comparison for bounded Linea 8 local edits."""

import argparse
import csv
from fractions import Fraction
import json
from pathlib import Path

import numpy as np
import pandas as pd

from phase2_final_stop_pedestrian_accessibility_substrate_v3 import parse_osm_pedestrian_graph
from phase2_rt029_v4_substrate import validate_walk_matrix
from scripts.phase2_audit_rt031_conditional_new_stop_access_v3 import (
    scaled_core_weights, weighted_ratio,
)
from scripts.phase2_audit_rt031_unique_line_walk_access_v3 import (
    EXPECTED, pedestrian_time, sha256,
)
from scripts.phase2_build_rt031_municipal_access_frontier_v4 import MUNICIPALITY_NAMES


def build(paths):
    for key in ("matrix", "pedestrian_osm", "candidates_normalized"):
        if sha256(paths[key], key == "candidates_normalized") != EXPECTED[key]:
            raise ValueError(f"pinned pedestrian source drift: {key}")
    audit = json.loads(paths["shortcuts"].read_text(encoding="utf-8"))
    road = json.loads(paths["road_screen"].read_text(encoding="utf-8"))
    prior = json.loads(paths["prior_access"].read_text(encoding="utf-8"))
    if (audit["contract"] != "RT031_LINE8_LOCAL_SHORTCUT_SINGLE_EDIT_AUDIT_V3"
            or audit["network_selected"] is not False
            or audit["source_sha256"]["road_screen"] != sha256(paths["road_screen"], True)
            or prior["contract"] != "RT031_UNIQUE_LINE_CONDITIONAL_WALK_ACCESS_V3"
            or prior["input_sha256"]["matrix"] != EXPECTED["matrix"]):
        raise ValueError("local audit or prior access contract drift")
    with paths["candidates_normalized"].open(encoding="utf-8", newline="") as stream:
        south = next(r for r in csv.DictReader(stream) if r["candidate_id"] == "P2V2S_0031")
    if (south["physical_status"] != "FIELD_CHECK_PENDING"
            or road["north_proxy"]["boarding_stop_certified"] is not False):
        raise ValueError("hypothetical stop status drift")
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
        raise ValueError("population connector or weight drift")
    snap_map = snap_rows.set_index("population_unit_id")[[
        "population_snap_node_id", "population_connector_distance_m"]].to_dict("index")
    weight_map = snap_rows.set_index("population_unit_id")["population_weight_2025"].to_dict()
    substrate = validate_walk_matrix(raw)
    unit_ids = substrate.population_meta["population_unit_id"].astype(str).tolist()
    if set(unit_ids) != set(snap_map):
        raise ValueError("population universe drift")
    core, weights = scaled_core_weights(substrate, weight_map)
    codes = substrate.population_meta["population_municipality_code"].astype(str).to_numpy()
    graph = parse_osm_pedestrian_graph(paths["pedestrian_osm"])
    if graph.graph_digest != "aaad8a16e4c3715161cce6f686acccbf29e4e9def57424e8ad02594c9a69f1f4":
        raise ValueError("pinned pedestrian graph drift")
    south_time, _ = pedestrian_time(graph, snap_map, unit_ids,
                                    float(south["lat"]), float(south["lon"]))
    north_time, _ = pedestrian_time(graph, snap_map, unit_ids,
                                    float(road["north_proxy"]["lat"]),
                                    float(road["north_proxy"]["lon"]))
    hypothetical = np.minimum(south_time, north_time)

    def access(stop_ids):
        if not stop_ids or any(sid not in substrate.stop_index for sid in stop_ids):
            raise ValueError("shortcut stop identity missing from walk matrix")
        indices = [substrate.stop_index[sid] for sid in stop_ids]
        times = np.minimum(np.min(substrate.walk_time_matrix[:, indices], axis=1),
                           hypothetical)
        result = {}
        for code, municipality in (("TOTAL", "Five municipalities"),
                                   *MUNICIPALITY_NAMES.items()):
            eligible = core if code == "TOTAL" else core & (codes == code)
            result[code] = {
                "municipality": municipality,
                "potential_walking_access_fraction": {
                    str(threshold): str(weighted_ratio(times <= threshold, weights, eligible))
                    for threshold in (5, 8, 10)},
            }
        return result

    baseline = access(audit["baseline"][
        "both_direction_encountered_stop_ids_not_boarding_guaranteed"])
    reference = prior["access"]["repair_FIVE_QUATTRO_STRADE_THEN_CARIPLO_plus_both_hypothetical"]
    if baseline != reference:
        raise ValueError("local-edit walking baseline differs from certified conditional access")
    options = []
    for index, option in enumerate(audit["options"]):
        if not option["represented_road_feasible"]:
            continue
        candidate = access(option["both_direction_encountered_stop_ids_not_boarding_guaranteed"])
        delta_pp = {}
        for code in baseline:
            delta_pp[code] = {
                str(threshold): round(100 * float(
                    Fraction(candidate[code]["potential_walking_access_fraction"][str(threshold)])
                    - Fraction(baseline[code]["potential_walking_access_fraction"][str(threshold)])), 6)
                for threshold in (5, 8, 10)
            }
        options.append({
            "option_index_in_road_audit": index,
            "edit": option["edit"],
            "wing": option["wing"],
            "affected_waypoint_ids": option["affected_waypoint_ids"],
            "pair_km_saved_vs_baseline": option["pair_km_saved_vs_baseline"],
            "existing_stop_ids_lost_both_directions": option[
                "existing_stop_ids_lost_both_directions"],
            "potential_access_percentage_point_change_vs_baseline": delta_pp,
            "potential_access_fraction": candidate,
        })
    return {
        "contract": "RT031_LINE8_LOCAL_SHORTCUT_CONDITIONAL_WALK_AUDIT_V3",
        "status": "NON_DECISIONAL_POTENTIAL_WALKING_ACCESS_ONLY",
        "source_sha256": {key: sha256(paths[key], key in (
            "candidates_normalized", "road_screen", "shortcuts", "prior_access"))
                          for key in paths},
        "baseline_potential_access": baseline,
        "options": options,
        "new_stop_assumptions": ["Olgiate south field check pending",
                                 "San Zeno road-node proxy is not a stop"],
        "semantics": "Potential walk to encountered existing attachment nodes and both hypothetical new points, assuming all are served in the useful direction; not stop approval, timetable, passenger journey or observed demand.",
        "decision_budget_km": None,
        "uncertainty_band_min": None,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
    }


def main(paths, output):
    result = build(paths)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":")) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for key in ("matrix", "pedestrian_osm", "candidates_normalized", "shortcuts",
                "road_screen", "prior_access"):
        parser.add_argument("--" + key, required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    main({key: getattr(args, key) for key in ("matrix", "pedestrian_osm",
         "candidates_normalized", "shortcuts", "road_screen", "prior_access")},
         args.output)
