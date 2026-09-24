"""Materialise the bounded Rovagnate/Perego waypoint-swap road witness."""

import argparse
import json
from pathlib import Path

from scripts.phase2_audit_rt031_south_road_probe_v3 import EXPECTED, VIRTUAL, digest, rows
from scripts.phase2_export_rt031_line8_inclusive_shape_v3 import NORTH, itinerary
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph, screen_lobe


SWAPPED_IDS = ["FROZEN::300879", "ASF::PEREGO_VIA_STATALE_79"]


def build(paths):
    audit = json.loads(paths["audit"].read_text(encoding="utf-8"))
    if (audit["contract"] != "RT031_LINE8_LOCAL_SHORTCUT_SINGLE_EDIT_AUDIT_V3"
            or audit["network_selected"] is not False):
        raise ValueError("local shortcut audit drift")
    target = next(o for o in audit["options"]
                  if o["edit"] == "SWAP_ADJACENT_EXISTING_WAYPOINTS"
                  and o["wing"] == "west"
                  and o["affected_waypoint_ids"] == SWAPPED_IDS)
    if not target["represented_road_feasible"] or target["pair_km_saved_vs_baseline"] <= 0:
        raise ValueError("west swap no longer modeled as a shorter road path")
    edges, nodes, rules, attachments = build_graph(paths)
    road = json.loads(paths["road_screen"].read_text(encoding="utf-8"))
    west, east = itinerary()
    if [sid for _, sid in west[2:4]] != SWAPPED_IDS:
        raise ValueError("west waypoint order drift")
    west = west[:2] + list(reversed(west[2:4])) + west[4:]
    attachment_nodes = {sid: row["graph_node_id"] for sid, row in attachments.items()
                        if row["route_ready"] == "True"}
    attachment_nodes[VIRTUAL] = VIRTUAL
    attachment_nodes[NORTH] = road["north_proxy"]["graph_node_id"]
    lobes = {
        "wf": screen_lobe(west, attachment_nodes, edges, rules),
        "wr": screen_lobe(list(reversed(west)), attachment_nodes, edges, rules),
        "ef": screen_lobe(east, attachment_nodes, edges, rules),
        "er": screen_lobe(list(reversed(east)), attachment_nodes, edges, rules),
    }
    if any(not part["reachable"] or part["via_node_bad_turn_indices_at_leg_seams_or_within_legs"]
           for part in lobes.values()):
        raise ValueError("west swap road witness not legal under represented via-node rules")
    candidate = next(row for row in rows(paths["candidates_normalized_newlines"])
                     if row["candidate_id"] == "P2V2S_0031")
    coords = {nid: [float(row["lon"]), float(row["lat"])] for nid, row in nodes.items()}
    coords[VIRTUAL] = [float(candidate["lon"]), float(candidate["lat"])]
    features = []
    for direction, first, second, expected in (
        ("forward_west_then_east", "wf", "ef", "forward_complete_cycle_distance_m"),
        ("reverse_east_then_west", "er", "wr", "reverse_complete_cycle_distance_m"),
    ):
        path = lobes[first]["_path_edge_ids"] + lobes[second]["_path_edge_ids"]
        vertices = [edges[path[0]]["u_node_id"]]
        for eid in path:
            if edges[eid]["u_node_id"] != vertices[-1]:
                raise ValueError("discontinuous waypoint-swap road geometry")
            vertices.append(edges[eid]["v_node_id"])
        if vertices[0] != vertices[-1]:
            raise ValueError("waypoint-swap road geometry does not return to FS")
        length = sum(float(edges[eid]["length_m"]) for eid in path)
        if abs(length - target[expected]) > .01:
            raise ValueError("waypoint-swap length differs from audit")
        features.append({
            "type": "Feature",
            "properties": {"feature_type": "MODELED_ROAD_PATH_NOT_APPROVED_TPL_ROUTE",
                           "variant": "ROVAGNATE_PEREGO_ORDER_SWAP",
                           "traversal": direction, "distance_m": target[expected],
                           "ordered_waypoint_ids": (target["west_waypoint_ids"]
                                                    + target["east_waypoint_ids"][1:]
                                                    if direction.startswith("forward") else
                                                    list(reversed(target["east_waypoint_ids"]))
                                                    + list(reversed(target["west_waypoint_ids"]))[1:])},
            "geometry": {"type": "LineString", "coordinates": [coords[n] for n in vertices]},
        })
    for sid in target["both_direction_encountered_stop_ids_not_boarding_guaranteed"]:
        row = attachments[sid]
        features.append({
            "type": "Feature",
            "properties": {"feature_type": "EXISTING_INVENTORY_STOP_ENCOUNTERED_NOT_BOARDING_CERTIFIED",
                           "stop_place_id": sid, "name": row["stop_name"]},
            "geometry": {"type": "Point", "coordinates": [float(row["lon"]), float(row["lat"])]},
        })
    for sid, name, coord, status in (
        (VIRTUAL, "Olgiate sud", coords[VIRTUAL], "FIELD_CHECK_PENDING"),
        (NORTH, "San Zeno", coords[attachment_nodes[NORTH]], "ROAD_NODE_PROXY_NOT_STOP_SITE"),
    ):
        features.append({
            "type": "Feature",
            "properties": {"feature_type": "NEW_STOP_NEED_NOT_APPROVED_STOP",
                           "stop_place_id": sid, "name": name, "physical_status": status},
            "geometry": {"type": "Point", "coordinates": coord},
        })
    return {
        "type": "FeatureCollection",
        "name": "RT031_LINE8_WEST_WAYPOINT_SWAP_MODELED_ROAD_SHAPE_V3",
        "properties": {"status": "NON_DECISIONAL_NOT_APPROVED_TPL_ROUTE",
                       "audit_sha256": digest(paths["audit"], True),
                       "pair_km_saved_vs_inclusive_baseline": target["pair_km_saved_vs_baseline"],
                       "network_selected": False,
                       "primary_selection_authorised": False,
                       "runner_up_selection_authorised": False},
        "features": features,
    }


def main(paths, output):
    result = build(paths)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":")) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for key in (*EXPECTED, "road_screen", "audit"):
        parser.add_argument("--" + key, required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    main({key: getattr(args, key) for key in (*EXPECTED, "road_screen", "audit")},
         args.output)
