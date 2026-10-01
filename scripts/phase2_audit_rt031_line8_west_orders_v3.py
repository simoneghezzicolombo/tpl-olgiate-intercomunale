"""Bounded west-wing waypoint-order audit preserving every requested anchor."""

import argparse
import hashlib
from itertools import permutations, product
import json
from pathlib import Path

from scripts.phase2_audit_rt031_south_road_probe_v3 import EXPECTED, VIRTUAL, digest
from scripts.phase2_export_rt031_line8_inclusive_shape_v3 import NORTH, itinerary
from scripts.phase2_probe_rt031_current_stop_repair_v3 import (
    CURRENT_PATH, CURRENT_SHA256, path_stops, waypoint_running_to_fs,
)
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph, screen_lobe
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter


def build(paths):
    local = json.loads(paths["local_audit"].read_text(encoding="utf-8"))
    road = json.loads(paths["road_screen"].read_text(encoding="utf-8"))
    if (local["contract"] != "RT031_LINE8_LOCAL_SHORTCUT_SINGLE_EDIT_AUDIT_V3"
            or local["network_selected"] is not False
            or local["source_sha256"]["road_screen"] != digest(paths["road_screen"], True)
            or hashlib.sha256(CURRENT_PATH.read_bytes()).hexdigest() != CURRENT_SHA256):
        raise ValueError("pinned source drift")
    current = set(json.loads(CURRENT_PATH.read_text(encoding="utf-8"))
                  ["current_exact_identity_subset"]["mapped_stop_place_ids"])
    west, east = itinerary()
    if ([sid for _, sid in west[1:4]] != ["ASF::OLGIATE_MOLGORA_SCARPONE",
                                           "FROZEN::300879", "ASF::PEREGO_VIA_STATALE_79"]
            or [sid for _, sid in west[4:6]] != ["FROZEN::300873", "FROZEN::300782"]):
        raise ValueError("west group waypoint order drift")
    edges, _, rules, attachments = build_graph(paths)
    attachment_nodes = {sid: row["graph_node_id"] for sid, row in attachments.items()
                        if row["route_ready"] == "True"}
    attachment_nodes[VIRTUAL] = VIRTUAL
    attachment_nodes[NORTH] = road["north_proxy"]["graph_node_id"]
    eligible = {sid: row["graph_node_id"] for sid, row in attachments.items()
                if row["route_ready"] == "True"
                and row["service_class"] == "CONVENTIONAL_TPL"}
    successor = json.loads(paths["successor"].read_text(encoding="utf-8"))
    via_ways = {way for relation in successor["successor_via_way_relations"]
                for way in relation["via_way_ids"]}
    adapter = FrozenRT017ViaNodeAdapter(edges.values(), rules,
                                         unresolved_external_via_way_count=2)
    ef = screen_lobe(east, attachment_nodes, edges, rules)
    er = screen_lobe(list(reversed(east)), attachment_nodes, edges, rules)
    if any(not part["reachable"] for part in (ef, er)):
        raise ValueError("east wing baseline unreachable")
    results = []
    for western_three, hoe_two in product(permutations(west[1:4]),
                                          permutations(west[4:6])):
        edited = west[:1] + list(western_three) + list(hoe_two) + west[6:]
        wf = screen_lobe(edited, attachment_nodes, edges, rules)
        wr = screen_lobe(list(reversed(edited)), attachment_nodes, edges, rules)
        order_ids = [sid for _, sid in edited[1:6]]
        if not wf["reachable"] or not wr["reachable"]:
            results.append({"west_ordered_waypoint_ids": order_ids,
                            "represented_road_feasible": False,
                            "reason": "unreachable_leg"})
            continue
        parts = (wf, wr, ef, er)
        bad = sum(len(p["via_node_bad_turn_indices_at_leg_seams_or_within_legs"])
                  for p in parts)
        overlap = sorted(via_ways & set().union(*(set(p["osm_way_ids"]) for p in parts)))

        def join(a, b):
            left, right = a["_path_edge_ids"][-1], b["_path_edge_ids"][0]
            return (edges[left]["v_node_id"] == edges[right]["u_node_id"]
                    and adapter.decision((left,), right)["allowed"] is True)

        joins = join(wf, ef) and join(er, wr)
        forward = wf["distance_m"] + ef["distance_m"]
        reverse = er["distance_m"] + wr["distance_m"]
        f_stops = path_stops(wf, edges, eligible) | path_stops(ef, edges, eligible)
        r_stops = path_stops(er, edges, eligible) | path_stops(wr, edges, eligible)
        both = f_stops & r_stops
        results.append({
            "west_ordered_waypoint_ids": order_ids,
            "west_ordered_waypoint_labels": [label for label, _ in edited[1:6]],
            "represented_road_feasible": bad == 0 and not overlap and joins,
            "represented_via_node_bad_turn_count": bad,
            "known_successor_via_way_overlap": overlap,
            "represented_fs_joins_allowed": joins,
            "forward_complete_cycle_distance_m": round(forward, 3),
            "reverse_complete_cycle_distance_m": round(reverse, 3),
            "bidirectional_pair_distance_m": round(forward + reverse, 3),
            "both_direction_encountered_stop_ids_not_boarding_guaranteed": sorted(both),
            "current_exact_stop_ids_encountered_count": len(both & current),
            "west_waypoint_road_running_minutes": waypoint_running_to_fs(edited, wf, wr),
        })
    baseline_ids = [sid for _, sid in west[1:6]]
    baseline = next(r for r in results if r["west_ordered_waypoint_ids"] == baseline_ids)
    if (baseline["bidirectional_pair_distance_m"]
            != local["baseline"]["bidirectional_pair_distance_m"]
            or baseline["both_direction_encountered_stop_ids_not_boarding_guaranteed"]
            != local["baseline"]["both_direction_encountered_stop_ids_not_boarding_guaranteed"]):
        raise ValueError("west baseline differs from pinned inclusive geometry")
    baseline_stops = set(baseline["both_direction_encountered_stop_ids_not_boarding_guaranteed"])
    baseline_running = {row["waypoint_id"]: row for row in baseline["west_waypoint_road_running_minutes"]}
    for result in results:
        if not result["represented_road_feasible"]:
            continue
        stops = set(result["both_direction_encountered_stop_ids_not_boarding_guaranteed"])
        result["pair_km_saved_vs_baseline"] = round(
            (baseline["bidirectional_pair_distance_m"]
             - result["bidirectional_pair_distance_m"]) / 1000, 6)
        result["existing_stop_ids_lost_both_directions"] = sorted(baseline_stops - stops)
        result["existing_stop_ids_gained_both_directions"] = sorted(stops - baseline_stops)
        result["road_running_to_next_fs_delta_min_by_west_waypoint_excluding_dwell"] = {
            row["waypoint_id"]: {
                direction: round(row[key] - baseline_running[row["waypoint_id"]][key], 6)
                for direction, key in (
                    ("forward", "forward_running_minutes_from_waypoint_to_next_fs_excluding_dwell"),
                    ("reverse", "reverse_running_minutes_from_waypoint_to_next_fs_excluding_dwell"))}
            for row in result["west_waypoint_road_running_minutes"]}
    return {
        "contract": "RT031_LINE8_WEST_GROUP_WAYPOINT_ORDER_AUDIT_V3",
        "status": "NON_DECISIONAL_BOUNDED_ROAD_PERMUTATION_SEARCH",
        "source_sha256": {key: digest(paths[key], key in (
            "anchor", "candidates_normalized_newlines", "road_screen", "local_audit"))
                          for key in paths},
        "baseline_west_group_waypoint_ids": baseline_ids,
        "baseline": baseline,
        "orders": results,
        "search_scope": "All 3! x 2! = 12 within-group west waypoint orders, preserving every waypoint, Olgiate south, San Zeno, FS and east wing; not global optimization.",
        "road_node_encounter_is_not_boarding_event": True,
        "full_history_via_way_composition_certified": False,
        "vehicle_suitability_certified": False,
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
    for key in (*EXPECTED, "anchor", "road_screen", "local_audit"):
        parser.add_argument("--" + key, required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    main({key: getattr(args, key) for key in (*EXPECTED, "anchor", "road_screen",
                                             "local_audit")}, args.output)
