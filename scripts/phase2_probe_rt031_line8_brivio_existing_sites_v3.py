"""Replace Brivio-centre representative with every route-ready Brivio inventory site.

Municipal membership does NOT certify equivalence to serving Brivio centre.
West wing stays at the 25-identity reference's fastest path. For each site,
probe inherited order (time/distance) and one all-order minimum-distance witness.
"""

import argparse
import json
from pathlib import Path

from scripts.phase2_audit_rt031_south_road_probe_v3 import EXPECTED, VIRTUAL, digest
from scripts.phase2_export_rt031_line8_inclusive_shape_v3 import NORTH, itinerary
from scripts.phase2_audit_rt031_line8_waypoint_lower_bound_v3 import minimum_pair_cycle
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph, screen_lobe
from scripts.phase2_probe_rt031_current_stop_repair_v3 import path_stops
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter
from scripts.phase2_rt031_ordered_via_node_path_v3 import ordered_path


def build(paths):
    road = json.loads(paths["road_screen"].read_text(encoding="utf-8"))
    baseline = json.loads(paths["distance_audit"].read_text(encoding="utf-8"))
    if (road["contract"] != "RT031_UNIQUE_LINE_ROAD_SCREEN_V3"
            or baseline["contract"] != "RT031_LINE8_FIXED_WAYPOINT_DISTANCE_OBJECTIVE_AUDIT_V3"
            or baseline["source_sha256"]["road_screen"] != digest(paths["road_screen"], True)):
        raise ValueError("source contract drift")
    edges, _, rules, attachments = build_graph(paths)
    nodes = {sid: row["graph_node_id"] for sid, row in attachments.items()
             if row["route_ready"] == "True"}
    nodes[VIRTUAL], nodes[NORTH] = VIRTUAL, road["north_proxy"]["graph_node_id"]
    eligible = {sid: row["graph_node_id"] for sid, row in attachments.items()
                if row["route_ready"] == "True" and row["service_class"] == "CONVENTIONAL_TPL"}
    candidates = sorted(sid for sid in eligible if attachments[sid]["municipality"] == "Brivio")
    west, east = itinerary()
    west = west[:2] + list(reversed(west[2:4])) + list(reversed(west[4:6])) + west[6:]
    wf = screen_lobe(west, nodes, edges, rules)
    wr = screen_lobe(list(reversed(west)), nodes, edges, rules)
    adapter = FrozenRT017ViaNodeAdapter(edges.values(), rules,
                                       unresolved_external_via_way_count=2)
    successor = json.loads(paths["successor"].read_text(encoding="utf-8"))
    via_ways = {way for row in successor["successor_via_way_relations"] for way in row["via_way_ids"]}
    cache, options = {}, []
    reference = baseline["variants"]["full_retention_west_order"]["minutes"]
    reference_ids = set(reference["both_direction_encountered_stop_ids_not_boarding_guaranteed"])
    for sid in candidates:
        replacement = (attachments[sid]["stop_name"], sid)
        raw = [replacement if old == "FROZEN::300063" else (label, old)
               for label, old in east]
        # A replacement already among the anchors need not be visited twice.
        seen, middle = set(), []
        for point in raw[1:-1]:
            if point[1] not in seen:
                middle.append(point)
                seen.add(point[1])
        inherited = raw[:1] + middle + raw[-1:]
        bound = minimum_pair_cycle(inherited, nodes, edges, rules, cache=cache)
        lookup = {key: (label, key) for label, key in inherited}
        ordered = [lookup[key] for key in bound["ordered_waypoint_ids_at_optimistic_minimum"]]
        modes = [("INHERITED_ORDER_FASTEST", inherited, "minutes"),
                 ("INHERITED_ORDER_SHORTEST_KM", inherited, "meters"),
                 ("ALL_ORDER_SHORTEST_KM_WITNESS", ordered, "meters")]
        if sid == "FROZEN::300063":
            western_both = path_stops(wf, edges, eligible) & path_stops(wr, edges, eligible)
            required = sorted(reference_ids - western_both - {east[0][1]})
            retained = [east[0]] + [(attachments[key]["stop_name"], key) for key in required]
            retained += [("San Zeno/Via Cantu", NORTH), east[-1]]
            retained_bound = minimum_pair_cycle(retained, nodes, edges, rules, cache=cache)
            retained_lookup = {key: (label, key) for label, key in retained}
            modes.append(("ALL_REFERENCE_IDS_REQUIRED_SHORTEST_KM",
                          [retained_lookup[key] for key in retained_bound[
                              "ordered_waypoint_ids_at_optimistic_minimum"]], "meters"))
            modes.append(("ALL_REFERENCE_IDS_CONTEXTUAL_SHORTEST_KM", modes[-1][1], "meters"))
        for mode, sequence, objective in modes:
            if mode == "ALL_REFERENCE_IDS_CONTEXTUAL_SHORTEST_KM":
                ordered_nodes = [nodes[key] for _, key in sequence]
                ef = ordered_path(edges, rules, ordered_nodes, incoming=wf["_path_edge_ids"][-1])
                er = ordered_path(edges, rules, list(reversed(ordered_nodes)), outgoing=wr["_path_edge_ids"][0])
            else:
                ef = screen_lobe(sequence, nodes, edges, rules, objective=objective)
                er = screen_lobe(list(reversed(sequence)), nodes, edges, rules, objective=objective)
            parts = (wf, ef, er, wr)
            if not all(p["reachable"] for p in parts):
                options.append({"replacement_id": sid, "mode": mode, "reachable": False})
                continue
            def join(a, b):
                left, right = a["_path_edge_ids"][-1], b["_path_edge_ids"][0]
                return (edges[left]["v_node_id"] == edges[right]["u_node_id"]
                        and adapter.decision((left,), right)["allowed"] is True)
            bad = sum(len(p["via_node_bad_turn_indices_at_leg_seams_or_within_legs"]) for p in parts)
            overlap = sorted(via_ways & set().union(*(set(p["osm_way_ids"]) for p in parts)))
            both = (path_stops(wf, edges, eligible) | path_stops(ef, edges, eligible)) & (
                path_stops(wr, edges, eligible) | path_stops(er, edges, eligible))
            pair_m = sum(p["distance_m"] for p in parts)
            options.append({
                "replacement_id": sid, "replacement_name": attachments[sid]["stop_name"],
                "replacement_lat": float(attachments[sid]["lat"]),
                "replacement_lon": float(attachments[sid]["lon"]),
                "mode": mode, "reachable": True,
                "east_ordered_waypoint_ids": [key for _, key in sequence],
                "represented_road_feasible": bad == 0 and not overlap and join(wf, ef) and join(er, wr),
                "represented_via_node_bad_turn_count": bad,
                "known_successor_via_way_overlap": overlap,
                "pair_distance_m": round(pair_m, 3),
                "forward_complete_cycle_distance_m": round(wf["distance_m"] + ef["distance_m"], 3),
                "reverse_complete_cycle_distance_m": round(wr["distance_m"] + er["distance_m"], 3),
                "annual_10_pairs_260_days_km_before_extras": round(pair_m * 2.6, 3),
                "forward_running_minutes_excluding_dwell": round(wf["running_minutes_model"] + ef["running_minutes_model"], 6),
                "reverse_running_minutes_excluding_dwell": round(wr["running_minutes_model"] + er["running_minutes_model"], 6),
                "both_direction_encountered_stop_ids_not_boarding_guaranteed": sorted(both),
                "lost_reference_inventory_ids": sorted(reference_ids - both),
                "gained_reference_inventory_ids": sorted(both - reference_ids),
                "road_path_edge_ids": {"forward": wf["_path_edge_ids"] + ef["_path_edge_ids"],
                                       "reverse": er["_path_edge_ids"] + wr["_path_edge_ids"]},
            })
    reference_row = next(row for row in options if row["replacement_id"] == "FROZEN::300063"
                         and row["mode"] == "INHERITED_ORDER_FASTEST")
    if (reference_row["pair_distance_m"] != reference["bidirectional_pair_distance_m"]
            or reference_row["lost_reference_inventory_ids"]):
        raise ValueError("reference path not reproduced")
    return {
        "contract": "RT031_LINE8_BRIVIO_EXISTING_SITE_REPLACEMENT_PROBE_V3",
        "status": "NON_DECISIONAL_BOUNDED_SPATIAL_REPLACEMENT_SEARCH",
        "source_sha256": {key: digest(path, key in ("road_screen", "distance_audit",
                                                     "candidates_normalized_newlines"))
                          for key, path in paths.items()},
        "inventory_candidate_ids": candidates, "options": options,
        "scope": "All conventional route-ready inventory identities in municipality Brivio, replacing only the Brivio-centre representative; west fixed to the full-retention fastest reference. Three witnesses per identity plus two all-25-reference comparators (independent legs and fixed-order turn-memory path); not all equal-length paths/orders, not all proposed/new sites.",
        "centre_service_equivalence_certified": False,
        "not_certified": ["full-history legality", "bus suitability", "boarding events",
                          "Brivio-centre service equivalence", "H30/H60", "depot kilometres"],
        "network_selected": False, "primary_selection_authorised": False,
        "runner_up_selection_authorised": False, "decision_budget_km": None,
        "uncertainty_band_min": None,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for key in (*EXPECTED, "road_screen", "distance_audit"):
        parser.add_argument("--" + key, required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build({key: getattr(args, key) for key in (*EXPECTED, "road_screen", "distance_audit")})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":")) + "\n", encoding="utf-8")
