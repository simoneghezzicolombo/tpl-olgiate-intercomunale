"""Check whether the inclusive Linea 8 path was kilometre-shortest on RT017.

This is a fixed-waypoint, per-leg diagnostic, not a global route or service
certificate. Graph-node encounters never imply directional boarding events.
"""

import argparse
import json
from pathlib import Path

from scripts.phase2_audit_rt031_south_road_probe_v3 import EXPECTED, VIRTUAL, digest
from scripts.phase2_export_rt031_line8_inclusive_shape_v3 import NORTH, itinerary
from scripts.phase2_probe_rt031_current_stop_repair_v3 import path_stops
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph, screen_lobe
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter


def build(paths):
    road = json.loads(paths["road_screen"].read_text(encoding="utf-8"))
    west_orders = json.loads(paths["west_orders"].read_text(encoding="utf-8"))
    if (road["contract"] != "RT031_UNIQUE_LINE_ROAD_SCREEN_V3"
            or west_orders["contract"] != "RT031_LINE8_WEST_GROUP_WAYPOINT_ORDER_AUDIT_V3"
            or west_orders["source_sha256"]["road_screen"]
            != digest(paths["road_screen"], True)):
        raise ValueError("source contract drift")
    edges, _, rules, attachments = build_graph(paths)
    nodes = {sid: row["graph_node_id"] for sid, row in attachments.items()
             if row["route_ready"] == "True"}
    nodes[VIRTUAL] = VIRTUAL
    nodes[NORTH] = road["north_proxy"]["graph_node_id"]
    eligible = {sid: row["graph_node_id"] for sid, row in attachments.items()
                if row["route_ready"] == "True"
                and row["service_class"] == "CONVENTIONAL_TPL"}
    west, east = itinerary()
    retained = [row for row in west_orders["orders"]
                if row.get("represented_road_feasible")
                and row.get("pair_km_saved_vs_baseline", 0) > 0
                and not row.get("existing_stop_ids_lost_both_directions")]
    if len(retained) != 1:
        raise ValueError("full-retention west order ambiguity")
    by_id = {sid: (label, sid) for label, sid in west}
    best_west = west[:1] + [by_id[sid] for sid in retained[0]["west_ordered_waypoint_ids"]] + west[6:]
    successor = json.loads(paths["successor"].read_text(encoding="utf-8"))
    via_ways = {way for relation in successor["successor_via_way_relations"]
                for way in relation["via_way_ids"]}
    adapter = FrozenRT017ViaNodeAdapter(edges.values(), rules,
                                         unresolved_external_via_way_count=2)
    variants = {}
    for name, w in (("baseline_order", west), ("full_retention_west_order", best_west)):
        variants[name] = {}
        for objective in ("minutes", "meters"):
            parts = {key: screen_lobe(seq, nodes, edges, rules, objective=objective)
                     for key, seq in (("wf", w), ("ef", east),
                                      ("er", list(reversed(east))),
                                      ("wr", list(reversed(w))))}
            if not all(part["reachable"] for part in parts.values()):
                variants[name][objective] = {"reachable": False}
                continue
            def joined(first, second):
                left, right = parts[first]["_path_edge_ids"][-1], parts[second]["_path_edge_ids"][0]
                return (edges[left]["v_node_id"] == edges[right]["u_node_id"]
                        and adapter.decision((left,), right)["allowed"] is True)
            joins = joined("wf", "ef") and joined("er", "wr")
            bad_turn_count = sum(len(part["via_node_bad_turn_indices_at_leg_seams_or_within_legs"])
                                 for part in parts.values())
            overlap = sorted(via_ways & set().union(*(set(part["osm_way_ids"])
                                                      for part in parts.values())))
            f_stops = path_stops(parts["wf"], edges, eligible) | path_stops(parts["ef"], edges, eligible)
            r_stops = path_stops(parts["er"], edges, eligible) | path_stops(parts["wr"], edges, eligible)
            both = sorted(f_stops & r_stops)
            forward_m = sum(parts[key]["distance_m"] for key in ("wf", "ef"))
            reverse_m = sum(parts[key]["distance_m"] for key in ("er", "wr"))
            forward_min = sum(parts[key]["running_minutes_model"] for key in ("wf", "ef"))
            reverse_min = sum(parts[key]["running_minutes_model"] for key in ("er", "wr"))
            variants[name][objective] = {
                "reachable": True,
                "represented_via_node_bad_turn_count": bad_turn_count,
                "represented_fs_joins_allowed": joins,
                "known_successor_via_way_overlap": overlap,
                "represented_road_feasible": bad_turn_count == 0 and joins and not overlap,
                "forward_complete_cycle_distance_m": round(forward_m, 3),
                "reverse_complete_cycle_distance_m": round(reverse_m, 3),
                "bidirectional_pair_distance_m": round(forward_m + reverse_m, 3),
                "forward_road_running_minutes_excluding_dwell": round(forward_min, 6),
                "reverse_road_running_minutes_excluding_dwell": round(reverse_min, 6),
                "both_direction_encountered_stop_ids_not_boarding_guaranteed": both,
                "annual_10_pairs_260_days_km_before_extras": round((forward_m + reverse_m) * 10 * 260 / 1000, 3),
                "under_111419_km_before_extras": (forward_m + reverse_m) * 10 * 260 / 1000 <= 111419,
                "road_path_edge_ids": {
                    "forward": parts["wf"]["_path_edge_ids"] + parts["ef"]["_path_edge_ids"],
                    "reverse": parts["er"]["_path_edge_ids"] + parts["wr"]["_path_edge_ids"],
                },
            }
    if (variants["baseline_order"]["minutes"]["bidirectional_pair_distance_m"] != 52207.651
            or variants["full_retention_west_order"]["minutes"]["bidirectional_pair_distance_m"]
            != retained[0]["bidirectional_pair_distance_m"]):
        raise ValueError("time-objective baseline drift")
    return {
        "contract": "RT031_LINE8_FIXED_WAYPOINT_DISTANCE_OBJECTIVE_AUDIT_V3",
        "status": "NON_DECISIONAL_ROAD_GRAPH_DIAGNOSTIC",
        "source_sha256": {key: digest(paths[key], key in (
            "candidates_normalized_newlines", "road_screen", "west_orders"))
                          for key in paths},
        "path_objective_semantics": {
            "minutes": "minimum modeled running minutes per independent waypoint leg; meters tie-break",
            "meters": "minimum directed road meters per independent waypoint leg; running minutes tie-break",
        },
        "variants": variants,
        "not_certified": ["global composed-path distance optimum",
                          "full-history via-way legality", "vehicle suitability",
                          "directional boarding", "passenger headways", "depot kilometres"],
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "decision_budget_km": None,
        "uncertainty_band_min": None,
    }


def main(paths, output):
    result = build(paths)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":")) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for key in (*EXPECTED, "road_screen", "west_orders"):
        parser.add_argument("--" + key, required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    main({key: getattr(args, key) for key in (*EXPECTED, "road_screen", "west_orders")},
         args.output)
