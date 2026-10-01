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
    full_retention = "west_orders" in paths
    if full_retention:
        west_orders = json.loads(paths["west_orders"].read_text(encoding="utf-8"))
        if (west_orders["contract"] != "RT031_LINE8_WEST_GROUP_WAYPOINT_ORDER_AUDIT_V3"
                or west_orders["source_sha256"]["local_audit"] != digest(paths["audit"], True)):
            raise ValueError("west group order audit drift")
        wanted = ["ASF::OLGIATE_MOLGORA_SCARPONE", "ASF::PEREGO_VIA_STATALE_79",
                  "FROZEN::300879", "FROZEN::300782", "FROZEN::300873"]
        target = next(o for o in west_orders["orders"]
                      if o["west_ordered_waypoint_ids"] == wanted)
        if (target["existing_stop_ids_lost_both_directions"]
                or target["current_exact_stop_ids_encountered_count"] != 11):
            raise ValueError("full-retention west order no longer retains stops")
        variant = "ROVAGNATE_PEREGO_AND_HOE_ORDER_SWAP"
        shape_name = "RT031_LINE8_WEST_FULL_RETENTION_ORDER_MODELED_ROAD_SHAPE_V3"
        audit_key = "west_orders"
    else:
        target = next(o for o in audit["options"]
                      if o["edit"] == "SWAP_ADJACENT_EXISTING_WAYPOINTS"
                      and o["wing"] == "west"
                      and o["affected_waypoint_ids"] == SWAPPED_IDS)
        variant = "ROVAGNATE_PEREGO_ORDER_SWAP"
        shape_name = "RT031_LINE8_WEST_WAYPOINT_SWAP_MODELED_ROAD_SHAPE_V3"
        audit_key = "audit"
    if not target["represented_road_feasible"] or target["pair_km_saved_vs_baseline"] <= 0:
        raise ValueError("west swap no longer modeled as a shorter road path")
    edges, nodes, rules, attachments = build_graph(paths)
    road = json.loads(paths["road_screen"].read_text(encoding="utf-8"))
    west, east = itinerary()
    if [sid for _, sid in west[2:4]] != SWAPPED_IDS:
        raise ValueError("west waypoint order drift")
    west = (west[:2] + list(reversed(west[2:4]))
            + (list(reversed(west[4:6])) if full_retention else west[4:6])
            + west[6:])
    west_ids = [sid for _, sid in west]
    east_ids = [sid for _, sid in east]
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
                           "variant": variant,
                           "traversal": direction, "distance_m": target[expected],
                           "ordered_waypoint_ids": (west_ids
                                                    + east_ids[1:]
                                                    if direction.startswith("forward") else
                                                    list(reversed(east_ids))
                                                    + list(reversed(west_ids))[1:])},
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
        "name": shape_name,
        "properties": {"status": "NON_DECISIONAL_NOT_APPROVED_TPL_ROUTE",
                       "audit_sha256": digest(paths[audit_key], True),
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
    parser.add_argument("--west-orders", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    paths = {key: getattr(args, key) for key in (*EXPECTED, "road_screen", "audit")}
    if args.west_orders is not None:
        paths["west_orders"] = args.west_orders
    main(paths, args.output)
