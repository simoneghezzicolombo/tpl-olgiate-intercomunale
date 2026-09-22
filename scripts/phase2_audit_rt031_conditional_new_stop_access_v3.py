"""Conditional, no-selection walking gains for all 40 Olgiate stop hypotheses.

Uses the same pinned RT028 pedestrian graph/population units as the existing
RT031 line comparison. A hypothetical point is never certified as a bus stop.
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

from phase2_final_stop_pedestrian_accessibility_substrate_v3 import (
    _dijkstra_to_stop, parse_osm_pedestrian_graph,
)
from phase2_rt029_v4_substrate import validate_walk_matrix
from scripts.phase2_audit_rt031_local_stop_siting_v3 import sha256
from scripts.phase2_build_rt031_municipal_access_frontier_v4 import (
    MUNICIPALITY_NAMES, detailed_threshold_vectors,
)


EXPECTED = {
    "typed": "c0169f3e39e1132853c2e8324d00bbb3030dbf5219c65889eee6ae4acf31b32e",
    "baseline_access": "a029684a5e788a0c2a23b5da389f4719ed787e5c31f6951a0f60fdd9b590a076",
    "walk_matrix": "a47bbce413d056db185180173ab2f05dce0463cb626a2c81f4aff64de91b50c1",
    "osm_pedestrian": "896f192bbb481f0c07cdc5d695424bf29de85f89ac33ea72986a06e521b424cd",
    "candidates_normalized_newlines": "bf3f5c648803fb0ba03b2f9af2bd4fa02924cb387bb0a752fc3a7a8ee1f14bc0",
    "poi_normalized_newlines": "5592e7ee0860f7acc71b42922b7e5f0986a5eb2357c52dc1025f5b51a303a672",
    "anchors_normalized_newlines": "c3ab598a43bfb83f31f086d6a14f29d92941969a349ef9087b5e6d87fe10b3d1",
}
THRESHOLDS = (5, 8, 10)


def scaled_core_weights(substrate, weight_map):
    meta = substrate.population_meta
    core = meta["population_scope"].astype(str).to_numpy() == "core"
    values = [Decimal(weight_map[unit]) for unit in meta["population_unit_id"]]
    scale = max(0, max(-value.as_tuple().exponent for value in values))
    integer = [int(value * (10 ** scale)) for value in values]
    if any(value < 0 for value in integer) or sum(value for value, use in zip(integer, core) if use) <= 0:
        raise ValueError("invalid population weights")
    return core, integer


def weighted_ratio(mask, weights, eligible):
    numerator = sum(weights[i] for i in np.flatnonzero(mask & eligible))
    denominator = sum(weights[i] for i in np.flatnonzero(eligible))
    return Fraction(numerator, denominator)


def main(typed_path, baseline_access_path, matrix_path, osm_path, output):
    candidate_path = Path("outputs/phase2/stop_universe_v2/proposed_stop_candidates.csv")
    paths = {"typed": typed_path, "baseline_access": baseline_access_path,
             "walk_matrix": matrix_path, "osm_pedestrian": osm_path,
             "candidates_normalized_newlines": candidate_path,
             "poi_normalized_newlines": Path("data/processed/poi_dataset.csv"),
             "anchors_normalized_newlines": Path(
                 "data/phase2/frozen_gate_d/source/structural_anchor_evidence.csv")}
    for name, path in paths.items():
        if sha256(path, name.endswith("_normalized_newlines")) != EXPECTED[name]:
            raise ValueError(f"pinned source drift: {name}")
    typed = json.loads(typed_path.read_text(encoding="utf-8"))
    baseline_access = json.loads(baseline_access_path.read_text(encoding="utf-8"))
    if (typed.get("network_selected") is not False
            or typed.get("timetable_assigned") is not False
            or baseline_access.get("network_selected") is not False):
        raise ValueError("non-decisional source contract drift")
    with candidate_path.open("r", encoding="utf-8", newline="") as stream:
        candidates = sorted((row for row in csv.DictReader(stream)
                             if row["COMUNE"] == "Olgiate Molgora"),
                            key=lambda row: row["candidate_id"])
    if len(candidates) != 40 or any(row["physical_status"] != "FIELD_CHECK_PENDING"
                                    for row in candidates):
        raise ValueError("Olgiate proposed stop universe drift")
    raw = pd.read_csv(matrix_path, dtype={"population_weight_2025": str,
                                          "population_snap_node_id": str},
                      usecols=["population_unit_id", "population_weight_2025",
                               "population_scope", "population_municipality_code",
                               "population_municipality_name", "stop_place_id",
                               "stop_service_class", "walk_time_min",
                               "reachability_status", "population_snap_node_id",
                               "population_connector_distance_m"])
    weight_rows = raw[["population_unit_id", "population_weight_2025",
                       "population_snap_node_id", "population_connector_distance_m"]].drop_duplicates()
    if weight_rows["population_unit_id"].duplicated().any():
        raise ValueError("population weight/snap drift across stops")
    weight_map = weight_rows.set_index("population_unit_id")["population_weight_2025"].to_dict()
    snap_map = weight_rows.set_index("population_unit_id")[
        ["population_snap_node_id", "population_connector_distance_m"]].to_dict("index")
    substrate = validate_walk_matrix(raw)
    meta = substrate.population_meta
    core, weights = scaled_core_weights(substrate, weight_map)
    codes = meta["population_municipality_code"].astype(str).to_numpy()
    if tuple(sorted(set(codes[core]))) != tuple(MUNICIPALITY_NAMES):
        raise ValueError("municipality universe drift")
    names = sorted(typed["directional_patterns"])
    stop_sets = [typed["directional_patterns"][name]["available_stop_ids"]
                 for name in names]
    baseline_codes, baseline_total, baseline_municipal = detailed_threshold_vectors(
        stop_sets, substrate,
        [weight_map[unit] for unit in meta["population_unit_id"]])
    if tuple(baseline_codes) != tuple(sorted(MUNICIPALITY_NAMES)):
        raise ValueError("baseline code order drift")
    baseline_masks = {}
    for name, stops in zip(names, stop_sets):
        base_time = np.min(substrate.walk_time_matrix[:,
                            [substrate.stop_index[stop] for stop in stops]], axis=1)
        baseline_masks[name] = {t: base_time <= t for t in THRESHOLDS}
        record = baseline_access["directional_patterns"][name]
        for j, t in enumerate(THRESHOLDS):
            if Fraction(record["total_potential_walking_access"][str(t)]) != baseline_total[names.index(name), j]:
                raise ValueError("RT031 baseline total drift")
            for k, code in enumerate(baseline_codes):
                if (Fraction(record["municipal_potential_walking_access"][code]
                             ["threshold_ratios"][str(t)]) != baseline_municipal[names.index(name), k, j]):
                    raise ValueError("RT031 baseline municipality drift")
    graph = parse_osm_pedestrian_graph(osm_path)
    if (graph.osm_sha256 != EXPECTED["osm_pedestrian"]
            or graph.graph_digest != "aaad8a16e4c3715161cce6f686acccbf29e4e9def57424e8ad02594c9a69f1f4"):
        raise ValueError("pedestrian graph OSM digest drift")
    with paths["poi_normalized_newlines"].open("r", encoding="utf-8", newline="") as stream:
        sport = next(row for row in csv.DictReader(stream)
                     if row["nome"] == "Centro Sportivo Comunale Olgiate Molgora")
    with paths["anchors_normalized_newlines"].open("r", encoding="utf-8", newline="") as stream:
        san_zeno = next(row for row in csv.DictReader(stream)
                        if row["anchor_id"] == "SAN_ZENO")
    if san_zeno["epistemic_status"] != "ASSUMPTION":
        raise ValueError("San Zeno target epistemic state drift")
    target_snaps = {
        "centro_sportivo_legacy_approximate_poi": graph.snap(
            float(sport["lat"]), float(sport["lon"])),
        "san_zeno_gate_d_assumption_anchor": graph.snap(
            float(san_zeno["lat"]), float(san_zeno["lon"])),
    }
    population_nodes = [snap_map[unit]["population_snap_node_id"]
                        for unit in meta["population_unit_id"]]
    population_connectors = np.array([
        float(snap_map[unit]["population_connector_distance_m"])
        if pd.notna(snap_map[unit]["population_connector_distance_m"]) else math.inf
        for unit in meta["population_unit_id"]], dtype=float)
    groups = {code: core & (codes == code) for code in sorted(MUNICIPALITY_NAMES)}
    results = {}
    for candidate in candidates:
        snap = graph.snap(float(candidate["lat"]), float(candidate["lon"]))
        distances = (_dijkstra_to_stop(graph.reverse_adjacency, snap.node_id)
                     if snap.status == "REACHABLE" and snap.node_id else {})
        candidate_time = np.array([
            (float(population_connectors[i]) + distances.get(str(node), math.inf)
             + float(snap.connector_distance_m or 0)) / (4.8 * 1000 / 3600) / 60
            for i, node in enumerate(population_nodes)], dtype=float)
        candidate_record = {
            "physical_status": candidate["physical_status"],
            "rt028_snap_status": snap.status,
            "rt028_snap_reason": snap.reason,
            "rt028_connector_m": snap.connector_distance_m,
            "target_origin_walk_min_to_hypothetical_candidate": {
                target: (f"{(distances.get(target_snap.node_id, math.inf)
                              + float(target_snap.connector_distance_m or 0)
                              + float(snap.connector_distance_m or 0)) / 80:.6f}"
                         if target_snap.status == "REACHABLE"
                         and snap.status == "REACHABLE"
                         and target_snap.node_id in distances else None)
                for target, target_snap in target_snaps.items()},
            "conditional_pattern_marginal_walking_access": {},
        }
        for name in names:
            threshold_rows = {}
            for t in THRESHOLDS:
                newly_accessible = (candidate_time <= t) & ~baseline_masks[name][t]
                threshold_rows[str(t)] = {
                    "total": str(weighted_ratio(newly_accessible, weights, core)),
                    "municipal": {code: str(weighted_ratio(newly_accessible, weights, group))
                                  for code, group in groups.items()},
                }
            candidate_record["conditional_pattern_marginal_walking_access"][name] = threshold_rows
        results[candidate["candidate_id"]] = candidate_record
    if all(Fraction(result["conditional_pattern_marginal_walking_access"][names[0]]["10"]["total"]) == 0
           for result in results.values()):
        raise ValueError("all conditional gains zero: likely population-node identity drift")
    payload = {
        "contract": "RT031_CONDITIONAL_NEW_STOP_SAME_RT028_WALK_SUBSTRATE_V3",
        "status": "NON_DECISIONAL_CONDITIONAL_WALKING_ONLY",
        "input_sha256": EXPECTED,
        "pedestrian_graph_digest": graph.graph_digest,
        "target_snap_provenance": {
            target: {"status": snap.status,
                     "connector_m": (f"{snap.connector_distance_m:.6f}"
                                     if snap.connector_distance_m is not None else None),
                     "epistemic_status": ("LEGACY_APPROXIMATE_POI_NOT_SITE_PIN"
                                          if target.startswith("centro_sportivo")
                                          else "DESIGN_ASSUMPTION_NOT_BOARDING_POINT")}
            for target, snap in target_snaps.items()},
        "candidate_count": len(candidates),
        "candidates": results,
        "candidate_stop_is_hypothetical_not_field_certified": True,
        "candidate_stop_included_in_certified_line_service_event": False,
        "counterfactual_assumes_candidate_is_boardable_in_each_pattern": True,
        "counterfactual_does_not_check_bus_path_or_detour_to_candidate": True,
        "marginal_is_relative_to_each_existing_four_pattern_stop_union": True,
        "gain_is_walking_access_not_observed_demand_or_journey_time": True,
        "target_origin_walk_min_is_modelled_not_site_verified": True,
        "barrier_snap_is_model_only_not_field_safety_certification": True,
        "new_stop_selected": False,
        "decision_budget_km": None,
        "uncertainty_band_min": None,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes((json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":")) + "\n").encode("utf-8"))
    print(json.dumps({"candidate_count": len(candidates),
                      "snap_status_counts": {status: sum(r["rt028_snap_status"] == status
                                                        for r in results.values())
                                             for status in sorted({r["rt028_snap_status"]
                                                                   for r in results.values()})}}, sort_keys=True))
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--typed", required=True, type=Path)
    parser.add_argument("--baseline-access", required=True, type=Path)
    parser.add_argument("--matrix", required=True, type=Path)
    parser.add_argument("--osm", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    main(args.typed, args.baseline_access, args.matrix, args.osm, args.output)
