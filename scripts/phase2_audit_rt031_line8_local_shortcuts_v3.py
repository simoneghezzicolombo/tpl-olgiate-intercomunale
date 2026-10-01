"""Bounded, non-decisional single-edit shortcut audit of the inclusive Linea 8.

This searches one existing waypoint deletion or one adjacent existing-waypoint
swap on the pinned road graph. It does not certify global optimality, stops,
vehicle suitability, full-history restrictions or passenger journeys.
"""

import argparse
import hashlib
import json
from pathlib import Path

from scripts.phase2_audit_rt031_south_road_probe_v3 import EXPECTED, VIRTUAL, digest
from scripts.phase2_export_rt031_line8_inclusive_shape_v3 import NORTH, itinerary
from scripts.phase2_probe_rt031_current_stop_repair_v3 import (
    CURRENT_PATH, CURRENT_SHA256, path_stops, waypoint_running_to_fs,
)
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph, screen_lobe
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter


VARIANT = "FIVE_QUATTRO_STRADE_THEN_CARIPLO"


def build(paths):
    edges, _, rules, attachments = build_graph(paths)
    repair = json.loads(paths["repair"].read_text(encoding="utf-8"))
    road = json.loads(paths["road_screen"].read_text(encoding="utf-8"))
    if (repair["contract"] != "RT031_CURRENT_STOP_REPAIR_ROAD_SCREEN_V3"
            or road["contract"] != "RT031_UNIQUE_LINE_ROAD_SCREEN_V3"
            or repair["source_sha256"]["road_screen"] != digest(paths["road_screen"], True)
            or repair["network_selected"] is not False):
        raise ValueError("pinned source contract drift")
    reference = repair["combined_repair_order_options"][VARIANT]
    if hashlib.sha256(CURRENT_PATH.read_bytes()).hexdigest() != CURRENT_SHA256:
        raise ValueError("current exact-stop identity source drift")
    current = set(json.loads(CURRENT_PATH.read_text(encoding="utf-8"))
                  ["current_exact_identity_subset"]["mapped_stop_place_ids"])
    west, east = itinerary()
    if ([label for label, _ in west] != reference["west_ordered_waypoints"]
            or [label for label, _ in east] != reference["east_ordered_waypoints"]):
        raise ValueError("inclusive waypoint order drift")
    attachment_nodes = {sid: row["graph_node_id"] for sid, row in attachments.items()
                        if row["route_ready"] == "True"}
    attachment_nodes[VIRTUAL] = VIRTUAL
    attachment_nodes[NORTH] = road["north_proxy"]["graph_node_id"]
    eligible = {sid: row["graph_node_id"] for sid, row in attachments.items()
                if row["route_ready"] == "True"
                and row["service_class"] == "CONVENTIONAL_TPL"}
    successor = json.loads(paths["successor"].read_text(encoding="utf-8"))
    via_way_ids = {way for relation in successor["successor_via_way_relations"]
                   for way in relation["via_way_ids"]}
    adapter = FrozenRT017ViaNodeAdapter(edges.values(), rules,
                                         unresolved_external_via_way_count=2)
    cache = {}

    def screen(sequence):
        key = tuple(stop for _, stop in sequence)
        if key not in cache:
            cache[key] = screen_lobe(sequence, attachment_nodes, edges, rules)
        return cache[key]

    def evaluate(w, e):
        lobes = {"wf": screen(w), "wr": screen(list(reversed(w))),
                 "ef": screen(e), "er": screen(list(reversed(e)))}
        if any(not part["reachable"] for part in lobes.values()):
            return {"represented_road_feasible": False, "reason": "unreachable_leg"}
        bad = sum(len(part["via_node_bad_turn_indices_at_leg_seams_or_within_legs"])
                  for part in lobes.values())
        overlap = sorted(via_way_ids & set().union(*(
            set(part["osm_way_ids"]) for part in lobes.values())))

        def join(a, b):
            left, right = lobes[a]["_path_edge_ids"][-1], lobes[b]["_path_edge_ids"][0]
            return (edges[left]["v_node_id"] == edges[right]["u_node_id"]
                    and adapter.decision((left,), right)["allowed"] is True)

        joins = join("wf", "ef") and join("er", "wr")
        f_stops = path_stops(lobes["wf"], edges, eligible) | path_stops(
            lobes["ef"], edges, eligible)
        r_stops = path_stops(lobes["er"], edges, eligible) | path_stops(
            lobes["wr"], edges, eligible)
        forward = lobes["wf"]["distance_m"] + lobes["ef"]["distance_m"]
        reverse = lobes["er"]["distance_m"] + lobes["wr"]["distance_m"]
        return {
            "represented_road_feasible": bad == 0 and not overlap and joins,
            "represented_via_node_bad_turn_count": bad,
            "known_successor_via_way_overlap": overlap,
            "represented_fs_joins_allowed": joins,
            "forward_complete_cycle_distance_m": round(forward, 3),
            "reverse_complete_cycle_distance_m": round(reverse, 3),
            "bidirectional_pair_distance_m": round(forward + reverse, 3),
            "both_direction_encountered_stop_ids_not_boarding_guaranteed": sorted(
                f_stops & r_stops),
            "forward_encountered_stop_ids_not_boarding_guaranteed": sorted(f_stops),
            "reverse_encountered_stop_ids_not_boarding_guaranteed": sorted(r_stops),
            "west_waypoint_ids": [sid for _, sid in w],
            "east_waypoint_ids": [sid for _, sid in e],
            "west_waypoint_road_running_minutes": waypoint_running_to_fs(
                w, lobes["wf"], lobes["wr"]),
            "east_waypoint_road_running_minutes": waypoint_running_to_fs(
                e, lobes["ef"], lobes["er"]),
        }

    baseline = evaluate(west, east)
    if (baseline["represented_road_feasible"] is not True
            or abs(baseline["forward_complete_cycle_distance_m"]
                   - reference["forward_complete_cycle_distance_m"]) > .01
            or abs(baseline["reverse_complete_cycle_distance_m"]
                   - reference["reverse_complete_cycle_distance_m"]) > .01
            or baseline["both_direction_encountered_stop_ids_not_boarding_guaranteed"]
            != reference["both_direction_encountered_stop_ids"]):
        raise ValueError("baseline route or stop encounter drift")
    baseline_stops = set(baseline["both_direction_encountered_stop_ids_not_boarding_guaranteed"])
    if len(baseline_stops & current) != 11:
        raise ValueError("inclusive current exact-stop encounter count drift")
    baseline["current_exact_stop_ids_encountered_count"] = 11
    baseline_running = {row["waypoint_id"]: row for key in (
        "west_waypoint_road_running_minutes", "east_waypoint_road_running_minutes")
        for row in baseline[key]}
    options = []
    for wing, sequence in (("west", west), ("east", east)):
        for index in range(1, len(sequence) - 1):
            label, sid = sequence[index]
            if sid in (VIRTUAL, NORTH):
                continue
            edited = sequence[:index] + sequence[index + 1:]
            option = evaluate(edited if wing == "west" else west,
                              edited if wing == "east" else east)
            option.update({"edit": "DROP_ONE_EXISTING_WAYPOINT",
                           "wing": wing, "affected_waypoint_ids": [sid],
                           "affected_waypoint_labels": [label]})
            options.append(option)
        for index in range(1, len(sequence) - 2):
            pair = sequence[index:index + 2]
            if any(sid in (VIRTUAL, NORTH) for _, sid in pair):
                continue
            edited = sequence[:index] + list(reversed(pair)) + sequence[index + 2:]
            option = evaluate(edited if wing == "west" else west,
                              edited if wing == "east" else east)
            option.update({"edit": "SWAP_ADJACENT_EXISTING_WAYPOINTS",
                           "wing": wing, "affected_waypoint_ids": [sid for _, sid in pair],
                           "affected_waypoint_labels": [label for label, _ in pair]})
            options.append(option)
    for option in options:
        if not option["represented_road_feasible"]:
            continue
        stops = set(option["both_direction_encountered_stop_ids_not_boarding_guaranteed"])
        option["pair_km_saved_vs_baseline"] = round(
            (baseline["bidirectional_pair_distance_m"]
             - option["bidirectional_pair_distance_m"]) / 1000, 6)
        option["existing_stop_ids_lost_both_directions"] = sorted(baseline_stops - stops)
        option["existing_stop_ids_gained_both_directions"] = sorted(stops - baseline_stops)
        option["retains_all_baseline_both_direction_stop_identities"] = baseline_stops <= stops
        option["current_exact_stop_ids_encountered_count"] = len(stops & current)
        option["retains_both_new_waypoint_needs"] = (
            VIRTUAL in option["west_waypoint_ids"] + option["east_waypoint_ids"]
            and NORTH in option["west_waypoint_ids"] + option["east_waypoint_ids"])
        option["road_running_to_next_fs_delta_min_by_waypoint_excluding_dwell"] = {
            row["waypoint_id"]: {
                direction: round(row[key] - baseline_running[row["waypoint_id"]][key], 6)
                for direction, key in (
                    ("forward", "forward_running_minutes_from_waypoint_to_next_fs_excluding_dwell"),
                    ("reverse", "reverse_running_minutes_from_waypoint_to_next_fs_excluding_dwell"))}
            for key in ("west_waypoint_road_running_minutes", "east_waypoint_road_running_minutes")
            for row in option[key] if row["waypoint_id"] in baseline_running}
    return {
        "contract": "RT031_LINE8_LOCAL_SHORTCUT_SINGLE_EDIT_AUDIT_V3",
        "status": "NON_DECISIONAL_BOUNDED_ROAD_SEARCH",
        "source_sha256": {key: digest(paths[key], key in (
            "anchor", "candidates_normalized_newlines", "road_screen", "repair"))
                          for key in paths},
        "current_exact_stop_source_sha256": CURRENT_SHA256,
        "baseline": baseline,
        "options": options,
        "search_scope": "Exactly one existing waypoint removed OR one adjacent pair of existing waypoints swapped, with Olgiate south and San Zeno retained in their wings and FS fixed; not global route optimization.",
        "stop_semantics": "Graph attachment-node encounter in both directions, not certified directional boarding events or passenger journeys.",
        "not_certified": ["full-history via-way legality", "vehicle suitability",
                          "stop safety and passenger events", "global optimum",
                          "walking access or time-to-FS after edits", "timetable and fleet"],
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
    for key in (*EXPECTED, "anchor", "road_screen", "repair"):
        parser.add_argument("--" + key, required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    main({key: getattr(args, key) for key in (*EXPECTED, "anchor", "road_screen", "repair")},
         args.output)
