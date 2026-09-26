"""Potential walking coverage of the fixed-waypoint kilometre-shortest path.

This assumes every encountered inventory identity and both unapproved new
points become useful stops; it is not passenger-service evidence.
"""

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
    audit = json.loads(paths["distance_audit"].read_text(encoding="utf-8"))
    road = json.loads(paths["road_screen"].read_text(encoding="utf-8"))
    prior = json.loads(paths["prior_access"].read_text(encoding="utf-8"))
    if (audit["contract"] != "RT031_LINE8_FIXED_WAYPOINT_DISTANCE_OBJECTIVE_AUDIT_V3"
            or road["contract"] != "RT031_UNIQUE_LINE_ROAD_SCREEN_V3"
            or prior["contract"] != "RT031_UNIQUE_LINE_CONDITIONAL_WALK_ACCESS_V3"
            or prior["input_sha256"]["matrix"] != EXPECTED["matrix"]
            or audit["network_selected"] is not False):
        raise ValueError("road or pedestrian source contract drift")
    fastest = audit["variants"]["full_retention_west_order"]["minutes"]
    shorter = audit["variants"]["full_retention_west_order"]["meters"]
    if (len(fastest["both_direction_encountered_stop_ids_not_boarding_guaranteed"]) != 25
            or len(shorter["both_direction_encountered_stop_ids_not_boarding_guaranteed"]) != 22
            or not shorter["represented_road_feasible"]):
        raise ValueError("road option drift")
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
    snaps = raw[["population_unit_id", "population_weight_2025",
                 "population_snap_node_id", "population_connector_distance_m"]].drop_duplicates()
    if snaps["population_unit_id"].duplicated().any():
        raise ValueError("population connector or weight drift")
    snap_map = snaps.set_index("population_unit_id")[[
        "population_snap_node_id", "population_connector_distance_m"]].to_dict("index")
    weight_map = snaps.set_index("population_unit_id")["population_weight_2025"].to_dict()
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
            raise ValueError("road stop identity missing from walk matrix")
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

    baseline = access(fastest["both_direction_encountered_stop_ids_not_boarding_guaranteed"])
    if baseline != prior["access"]["repair_FIVE_QUATTRO_STRADE_THEN_CARIPLO_plus_both_hypothetical"]:
        raise ValueError("conditional walking baseline drift")
    candidate = access(shorter["both_direction_encountered_stop_ids_not_boarding_guaranteed"])
    delta = {code: {str(threshold): round(100 * float(
        Fraction(candidate[code]["potential_walking_access_fraction"][str(threshold)])
        - Fraction(baseline[code]["potential_walking_access_fraction"][str(threshold)])), 6)
        for threshold in (5, 8, 10)} for code in baseline}
    result = {
        "contract": "RT031_LINE8_DISTANCE_OBJECTIVE_CONDITIONAL_WALK_ACCESS_V3",
        "status": "NON_DECISIONAL_POTENTIAL_WALKING_ACCESS_ONLY",
        "source_sha256": {key: sha256(paths[key], key in (
            "candidates_normalized", "road_screen", "distance_audit", "prior_access",
            "brivio_probe", "bound", "siting_audit", "contextual_audit"))
                          for key in paths},
        "baseline_25_identity_potential_access": baseline,
        "shorter_22_identity_potential_access": candidate,
        "potential_access_percentage_point_change_vs_25_identity_baseline": delta,
        "lost_encountered_inventory_ids": sorted(set(
            fastest["both_direction_encountered_stop_ids_not_boarding_guaranteed"])
            - set(shorter["both_direction_encountered_stop_ids_not_boarding_guaranteed"])),
        "semantics": "Potential 5/8/10 minute walking access if all encountered inventory identities and both hypothetical new points become useful boarding events; not stop approval, observed demand, directional service, timetable or passenger journey.",
        "decision_budget_km": None,
        "uncertainty_band_min": None,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
    }
    if "brivio_probe" in paths:
        probe = json.loads(paths["brivio_probe"].read_text(encoding="utf-8"))
        if (probe["contract"] != "RT031_LINE8_BRIVIO_WAYPOINT_RELAXATION_ROAD_PROBE_V3"
                or probe["network_selected"] is not False
                or "bound" not in paths
                or probe["source_sha256"]["bound"] != sha256(paths["bound"], True)):
            raise ValueError("Brivio bypass probe contract drift")
        bypass = access(probe["both_direction_encountered_stop_ids_not_boarding_guaranteed"])
        result["brivio_waypoint_relaxation_potential_access"] = bypass
        result["brivio_waypoint_relaxation_potential_access_pp_change_vs_25_identity_baseline"] = {
            code: {str(threshold): round(100 * float(
                Fraction(bypass[code]["potential_walking_access_fraction"][str(threshold)])
                - Fraction(baseline[code]["potential_walking_access_fraction"][str(threshold)])), 6)
                for threshold in (5, 8, 10)} for code in baseline}
    if "siting_audit" in paths:
        sites = json.loads(paths["siting_audit"].read_text(encoding="utf-8"))
        if (sites["contract"] != "RT031_LINE8_BRIVIO_EXISTING_SITE_REPLACEMENT_PROBE_V3"
                or sites["network_selected"] is not False
                or sites["source_sha256"]["distance_audit"] != sha256(paths["distance_audit"], True)):
            raise ValueError("existing-site probe contract drift")
        rows = []
        for index, row in enumerate(sites["options"]):
            if not row.get("represented_road_feasible"):
                continue
            value = access(row["both_direction_encountered_stop_ids_not_boarding_guaranteed"])
            changes = {code: {str(threshold): round(100 * float(
                Fraction(value[code]["potential_walking_access_fraction"][str(threshold)])
                - Fraction(baseline[code]["potential_walking_access_fraction"][str(threshold)])), 6)
                for threshold in (5, 8, 10)} for code in baseline}
            rows.append({"road_option_index": index, "replacement_id": row["replacement_id"],
                         "replacement_name": row["replacement_name"], "mode": row["mode"],
                         "annual_10_pairs_260_days_km_before_extras": row["annual_10_pairs_260_days_km_before_extras"],
                         "forward_running_minutes_excluding_dwell": row["forward_running_minutes_excluding_dwell"],
                         "reverse_running_minutes_excluding_dwell": row["reverse_running_minutes_excluding_dwell"],
                         "lost_reference_inventory_ids": row["lost_reference_inventory_ids"],
                         "potential_access": value,
                         "potential_access_pp_change_vs_reference": changes})
        def dominates(a, b):
            # No weighted aggregation; retain each municipality/threshold separately.
            numeric_a = [-a["annual_10_pairs_260_days_km_before_extras"],
                         -a["forward_running_minutes_excluding_dwell"],
                         -a["reverse_running_minutes_excluding_dwell"]]
            numeric_b = [-b["annual_10_pairs_260_days_km_before_extras"],
                         -b["forward_running_minutes_excluding_dwell"],
                         -b["reverse_running_minutes_excluding_dwell"]]
            for code in MUNICIPALITY_NAMES:
                for threshold in ("5", "8", "10"):
                    numeric_a.append(Fraction(a["potential_access"][code]["potential_walking_access_fraction"][threshold]))
                    numeric_b.append(Fraction(b["potential_access"][code]["potential_walking_access_fraction"][threshold]))
            lost_a, lost_b = set(a["lost_reference_inventory_ids"]), set(b["lost_reference_inventory_ids"])
            return (lost_a <= lost_b and all(x >= y for x, y in zip(numeric_a, numeric_b))
                    and (lost_a < lost_b or any(x > y for x, y in zip(numeric_a, numeric_b))))
        result["existing_site_options"] = rows
        result["existing_site_pareto_road_option_indices"] = [row["road_option_index"] for row in rows
            if not any(dominates(other, row) for other in rows)]
        result["existing_site_pareto_semantics"] = "Bounded witness set only: minimize annual model km and both directional running times; maximize each municipality's 5/8/10-minute potential access and retained reference-identity set inclusion. No weights, centre-equivalence guarantee or selected service."
    if "contextual_audit" in paths:
        contextual = json.loads(paths["contextual_audit"].read_text(encoding="utf-8"))
        if (contextual["contract"] != "RT031_LINE8_ALL_REFERENCE_CONTEXTUAL_ROAD_WITNESS_V3"
                or contextual["network_selected"] is not False
                or contextual["source_sha256"]["distance_audit"] != sha256(paths["distance_audit"], True)
                or contextual["known_successor_via_way_overlap"]):
            raise ValueError("contextual road witness not supported")
        value = access(contextual["both_direction_encountered_stop_ids_not_boarding_guaranteed"])
        result["all_reference_contextual_potential_access"] = value
        result["all_reference_contextual_access_pp_change_vs_reference"] = {
            code: {str(threshold): round(100 * float(
                Fraction(value[code]["potential_walking_access_fraction"][str(threshold)])
                - Fraction(baseline[code]["potential_walking_access_fraction"][str(threshold)])), 6)
                for threshold in (5, 8, 10)} for code in baseline}
    return result


def main(paths, output):
    result = build(paths)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":")) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for key in ("matrix", "pedestrian_osm", "candidates_normalized",
                "distance_audit", "road_screen", "prior_access"):
        parser.add_argument("--" + key, required=True, type=Path)
    parser.add_argument("--brivio_probe", type=Path)
    parser.add_argument("--bound", type=Path)
    parser.add_argument("--siting_audit", type=Path)
    parser.add_argument("--contextual_audit", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    paths = {key: getattr(args, key) for key in (
        "matrix", "pedestrian_osm", "candidates_normalized",
        "distance_audit", "road_screen", "prior_access")}
    if args.brivio_probe is not None:
        paths["brivio_probe"] = args.brivio_probe
        if args.bound is None:
            parser.error("--bound required with --brivio_probe")
        paths["bound"] = args.bound
    if args.siting_audit is not None:
        paths["siting_audit"] = args.siting_audit
    if args.contextual_audit is not None:
        paths["contextual_audit"] = args.contextual_audit
    main(paths, args.output)
