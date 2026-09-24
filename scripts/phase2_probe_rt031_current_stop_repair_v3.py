"""Bounded road screen for omitted Brivio and Santa Maria current stops."""

import argparse
import hashlib
import json
from pathlib import Path

from scripts.phase2_audit_rt031_south_road_probe_v3 import EXPECTED, VIRTUAL, digest
from scripts.phase2_probe_rt031_unique_line_v3 import (
    WEST, EAST, build_graph, screen_lobe,
)
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter


TARGETS = {
    "FROZEN::300086": ("east", "Brivio Beverate Cariplo"),
    "FROZEN::300487": ("east", "Brivio Beverate Quattro Strade"),
    "FROZEN::300634": ("east", "Calco Via Nazionale"),
    "FROZEN::300805": ("west", "Santa Maria Tremonte Via Trento"),
    "FROZEN::300873": ("west", "Santa Maria Hoe"),
}
NORTH = "PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE"
CURRENT_PATH = Path("outputs/phase2/rt031_expanded_pool_current_v4_v3/expanded_pool_current_v4_audit.json")
CURRENT_SHA256 = "3abd5a2c5bb4a8419b4e65cfb2ce63cb6a855fe30087a4c57f4a560ae50c30f5"


def path_stops(screen, edges, eligible):
    path = screen["_path_edge_ids"]
    nodes = {edges[e]["u_node_id"] for e in path}
    nodes.add(edges[path[-1]]["v_node_id"])
    return {stop for stop, node in eligible.items() if node in nodes}


def waypoint_running_to_fs(lobe, forward, reverse):
    """Model road running to the next FS along either declared lobe direction."""
    labels = [label for label, _ in lobe]
    if (forward["ordered_waypoints"] != labels
            or reverse["ordered_waypoints"] != list(reversed(labels))):
        raise ValueError("lobe waypoint ordering drift")
    if (len(forward["legs"]) != len(lobe) - 1
            or len(reverse["legs"]) != len(lobe) - 1):
        raise ValueError("lobe leg count drift")
    result = []
    for index, (label, stop) in enumerate(lobe[1:-1], start=1):
        reverse_index = len(lobe) - 1 - index
        result.append({
            "waypoint_label": label,
            "waypoint_id": stop,
            "forward_running_minutes_from_waypoint_to_next_fs_excluding_dwell": round(
                sum(leg["running_minutes_model"] for leg in forward["legs"][index:]), 6),
            "reverse_running_minutes_from_waypoint_to_next_fs_excluding_dwell": round(
                sum(leg["running_minutes_model"] for leg in reverse["legs"][reverse_index:]), 6),
            "forward_running_minutes_from_fs_to_waypoint_excluding_dwell": round(
                sum(leg["running_minutes_model"] for leg in forward["legs"][:index]), 6),
            "reverse_running_minutes_from_fs_to_waypoint_excluding_dwell": round(
                sum(leg["running_minutes_model"] for leg in reverse["legs"][:reverse_index]), 6),
        })
    return result


def main(paths, output):
    edges, _, rules, attachments = build_graph(paths)
    road = json.loads(paths["road_screen"].read_text(encoding="utf-8"))
    if (road.get("contract") != "RT031_UNIQUE_LINE_ROAD_SCREEN_V3"
            or road.get("network_selected") is not False
            or road.get("existing_stop_attachment_nodes_encountered_in_both_full_directions") is None):
        raise ValueError("single-line road screen drift")
    if hashlib.sha256(CURRENT_PATH.read_bytes()).hexdigest() != CURRENT_SHA256:
        raise ValueError("current exact stop identity source drift")
    current = set(json.loads(CURRENT_PATH.read_text(encoding="utf-8"))
                  ["current_exact_identity_subset"]["mapped_stop_place_ids"])
    if not set(TARGETS) <= current:
        raise ValueError("repair targets are not in current exact subset")
    selected = {stop for _, stop in WEST + EAST
                if stop.startswith(("FROZEN::", "ASF::"))} | set(TARGETS)
    if any(attachments[s]["route_ready"] != "True" for s in selected):
        raise ValueError("representative or target attachment is not route ready")
    attachment_nodes = {s: attachments[s]["graph_node_id"] for s in selected}
    attachment_nodes[VIRTUAL] = VIRTUAL
    attachment_nodes[NORTH] = road["north_proxy"]["graph_node_id"]
    eligible = {stop: row["graph_node_id"] for stop, row in attachments.items()
                if row["route_ready"] == "True"
                and row["service_class"] == "CONVENTIONAL_TPL"}
    base = {
        "west_forward": screen_lobe(WEST, attachment_nodes, edges, rules),
        "west_reverse": screen_lobe(list(reversed(WEST)), attachment_nodes, edges, rules),
        "east_forward": screen_lobe(EAST, attachment_nodes, edges, rules),
        "east_reverse": screen_lobe(list(reversed(EAST)), attachment_nodes, edges, rules),
    }
    if any(not item["reachable"] for item in base.values()):
        raise ValueError("base lobe drift")
    adapter = FrozenRT017ViaNodeAdapter(edges.values(), rules,
                                         unresolved_external_via_way_count=2)
    successor = json.loads(paths["successor"].read_text(encoding="utf-8"))
    via_ways = {way for row in successor["successor_via_way_relations"]
                for way in row["via_way_ids"]}
    old_both = set(road["existing_stop_attachment_nodes_encountered_in_both_full_directions"])
    probes = {}
    for stop, (wing, label) in TARGETS.items():
        lobe = WEST if wing == "west" else EAST
        options = []
        for position in range(1, len(lobe)):
            sequence = lobe[:position] + [(label, stop)] + lobe[position:]
            forward = screen_lobe(sequence, attachment_nodes, edges, rules)
            reverse = screen_lobe(list(reversed(sequence)), attachment_nodes, edges, rules)
            if not forward["reachable"] or not reverse["reachable"]:
                options.append({"insert_before": lobe[position][0],
                                "reachable_both_directions": False})
                continue
            other_forward = base[("east" if wing == "west" else "west") + "_forward"]
            other_reverse = base[("east" if wing == "west" else "west") + "_reverse"]
            if wing == "west":
                forward_order, reverse_order = ((forward, other_forward),
                                                (other_reverse, reverse))
            else:
                forward_order, reverse_order = ((other_forward, forward),
                                                (reverse, other_reverse))

            def join_ok(pair):
                left, right = pair
                left_edge = left["_path_edge_ids"][-1]
                right_edge = right["_path_edge_ids"][0]
                return (edges[left_edge]["v_node_id"] == edges[right_edge]["u_node_id"]
                        and adapter.decision((left_edge,), right_edge)["allowed"] is True)

            forward_stops = path_stops(forward_order[0], edges, eligible) | path_stops(
                forward_order[1], edges, eligible)
            reverse_stops = path_stops(reverse_order[0], edges, eligible) | path_stops(
                reverse_order[1], edges, eligible)
            both = forward_stops & reverse_stops
            paths_ways = set(forward["osm_way_ids"]) | set(reverse["osm_way_ids"])
            total_forward_m = sum(item["distance_m"] for item in forward_order)
            total_reverse_m = sum(item["distance_m"] for item in reverse_order)
            base_forward_m = base["west_forward"]["distance_m"] + base["east_forward"]["distance_m"]
            base_reverse_m = base["east_reverse"]["distance_m"] + base["west_reverse"]["distance_m"]
            options.append({
                "insert_before": lobe[position][0],
                "reachable_both_directions": True,
                "forward_complete_cycle_distance_m": round(total_forward_m, 3),
                "reverse_complete_cycle_distance_m": round(total_reverse_m, 3),
                "mean_added_distance_m_per_complete_cycle": round(
                    ((total_forward_m - base_forward_m)
                     + (total_reverse_m - base_reverse_m)) / 2, 3),
                "represented_via_node_joins_at_fs_allowed": join_ok(forward_order)
                and join_ok(reverse_order),
                "represented_via_node_bad_turn_count": len(
                    forward["via_node_bad_turn_indices_at_leg_seams_or_within_legs"])
                + len(reverse["via_node_bad_turn_indices_at_leg_seams_or_within_legs"]),
                "known_successor_via_way_overlap": sorted(via_ways & paths_ways),
                "both_direction_encountered_stop_ids": sorted(both),
                "newly_encountered_stop_ids": sorted(both - old_both),
                "previously_encountered_stop_ids_lost": sorted(old_both - both),
                "current_exact_stop_ids_encountered_count": len(both & current),
            })
        probes[stop] = {"wing": wing, "label": label,
                        "insertion_options": options}
    west_repair = WEST[:-2] + [(TARGETS["FROZEN::300805"][1], "FROZEN::300805")] + WEST[-2:]
    combined = {}
    orders = {
        "QUATTRO_STRADE_THEN_CARIPLO": ("FROZEN::300487", "FROZEN::300086"),
        "CARIPLO_THEN_QUATTRO_STRADE": ("FROZEN::300086", "FROZEN::300487"),
    }
    for package in ("THREE", "FOUR", "FIVE"):
      for order_name, east_insertions in orders.items():
        name = package + "_" + order_name
        selected_west = west_repair
        if package == "FIVE":
            selected_west = (WEST[:4] + [(TARGETS["FROZEN::300873"][1], "FROZEN::300873")]
                             + WEST[4:-2] + [(TARGETS["FROZEN::300805"][1], "FROZEN::300805")]
                             + WEST[-2:])
        selected_east = EAST
        if package in ("FOUR", "FIVE"):
            selected_east = (EAST[:2] + [(TARGETS["FROZEN::300634"][1], "FROZEN::300634")]
                             + EAST[2:])
        east_repair = (selected_east[:-2]
                       + [(TARGETS[stop][1], stop) for stop in east_insertions]
                       + selected_east[-2:])
        wf = screen_lobe(selected_west, attachment_nodes, edges, rules)
        wr = screen_lobe(list(reversed(selected_west)), attachment_nodes, edges, rules)
        ef = screen_lobe(east_repair, attachment_nodes, edges, rules)
        er = screen_lobe(list(reversed(east_repair)), attachment_nodes, edges, rules)
        if any(not screen["reachable"] for screen in (wf, wr, ef, er)):
            combined[name] = {"reachable_both_directions": False}
            continue
        f_stops = path_stops(wf, edges, eligible) | path_stops(ef, edges, eligible)
        r_stops = path_stops(wr, edges, eligible) | path_stops(er, edges, eligible)
        both = f_stops & r_stops
        route_ways = set().union(*(set(screen["osm_way_ids"]) for screen in (wf, wr, ef, er)))

        def join(left, right):
            a, b = left["_path_edge_ids"][-1], right["_path_edge_ids"][0]
            return (edges[a]["v_node_id"] == edges[b]["u_node_id"]
                    and adapter.decision((a,), b)["allowed"] is True)

        forward_m = wf["distance_m"] + ef["distance_m"]
        reverse_m = er["distance_m"] + wr["distance_m"]
        base_forward_m = base["west_forward"]["distance_m"] + base["east_forward"]["distance_m"]
        base_reverse_m = base["east_reverse"]["distance_m"] + base["west_reverse"]["distance_m"]
        combined[name] = {
            "reachable_both_directions": True,
            "west_ordered_waypoints": [label for label, _ in selected_west],
            "east_ordered_waypoints": [label for label, _ in east_repair],
            "forward_complete_cycle_distance_m": round(forward_m, 3),
            "reverse_complete_cycle_distance_m": round(reverse_m, 3),
            "west_forward_lobe_distance_m": wf["distance_m"],
            "west_reverse_lobe_distance_m": wr["distance_m"],
            "east_forward_lobe_distance_m": ef["distance_m"],
            "east_reverse_lobe_distance_m": er["distance_m"],
            "west_waypoint_road_running_minutes": waypoint_running_to_fs(
                selected_west, wf, wr),
            "east_waypoint_road_running_minutes": waypoint_running_to_fs(
                east_repair, ef, er),
            "forward_running_minutes_model_excluding_dwell_recovery": round(
                wf["running_minutes_model"] + ef["running_minutes_model"], 6),
            "reverse_running_minutes_model_excluding_dwell_recovery": round(
                er["running_minutes_model"] + wr["running_minutes_model"], 6),
            "mean_added_distance_m_per_complete_cycle": round(
                ((forward_m - base_forward_m) + (reverse_m - base_reverse_m)) / 2, 3),
            "represented_via_node_joins_at_fs_allowed": join(wf, ef) and join(er, wr),
            "represented_via_node_bad_turn_count": sum(len(
                screen["via_node_bad_turn_indices_at_leg_seams_or_within_legs"])
                for screen in (wf, wr, ef, er)),
            "known_successor_via_way_overlap": sorted(via_ways & route_ways),
            "both_direction_encountered_stop_ids": sorted(both),
            "newly_encountered_stop_ids": sorted(both - old_both),
            "previously_encountered_stop_ids_lost": sorted(old_both - both),
            "current_exact_stop_ids_encountered_count": len(both & current),
        }
    payload = {
        "contract": "RT031_CURRENT_STOP_REPAIR_ROAD_SCREEN_V3",
        "status": "NON_DECISIONAL_SINGLE_AND_COMBINED_STOP_INSERTION_DIAGNOSTIC",
        "source_sha256": {key: digest(paths[key], key.endswith("normalized_newlines")
                                      or key in ("anchor", "road_screen")) for key in paths},
        "current_exact_stop_source_sha256": CURRENT_SHA256,
        "targets": probes,
        "combined_repair_order_options": combined,
        "single_insertion_options_are_separate_from_combined_options": True,
        "road_node_encounter_is_not_a_passenger_boarding_event": True,
        "waypoint_road_running_minutes_are_passenger_journeys": False,
        "full_history_via_way_composition_certified": False,
        "vehicle_suitability_and_stop_safety_certified": False,
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
    for key in (*EXPECTED, "anchor", "road_screen"):
        parser.add_argument("--" + key, required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    main({key: getattr(args, key) for key in (*EXPECTED, "anchor", "road_screen")}, args.output)
