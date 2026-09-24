"""Materialise the pinned inclusive Linea 8 road paths as an auditable GeoJSON.

The lines are modeled road paths, not an approved bus itinerary. Stop points
are inventory locations/proxies, not certified directional boarding events.
"""

import argparse
import hashlib
import json
from pathlib import Path

from scripts.phase2_audit_rt031_south_road_probe_v3 import EXPECTED, VIRTUAL, digest, rows
from scripts.phase2_probe_rt031_unique_line_v3 import WEST, EAST, build_graph, screen_lobe


VARIANT = "FIVE_QUATTRO_STRADE_THEN_CARIPLO"
NORTH = "PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE"


def itinerary():
    west = (WEST[:4] + [("Santa Maria Hoe", "FROZEN::300873")]
            + WEST[4:-2] + [("Santa Maria Tremonte Via Trento", "FROZEN::300805")]
            + WEST[-2:])
    east = (EAST[:2] + [("Calco Via Nazionale", "FROZEN::300634")]
            + EAST[2:-2] + [("Brivio Beverate Quattro Strade", "FROZEN::300487"),
                           ("Brivio Beverate Cariplo", "FROZEN::300086")]
            + EAST[-2:])
    return west, east


def materialise(paths):
    edges, nodes, rules, attachments = build_graph(paths)
    repair = json.loads(paths["repair"].read_text(encoding="utf-8"))
    road = json.loads(paths["road_screen"].read_text(encoding="utf-8"))
    if repair["contract"] != "RT031_CURRENT_STOP_REPAIR_ROAD_SCREEN_V3":
        raise ValueError("repair contract mismatch")
    if road["contract"] != "RT031_UNIQUE_LINE_ROAD_SCREEN_V3":
        raise ValueError("road screen contract mismatch")
    if repair["source_sha256"]["road_screen"] != digest(paths["road_screen"], True):
        raise ValueError("road screen source drift")
    if any(repair[key] is not False for key in
           ("network_selected", "primary_selection_authorised", "runner_up_selection_authorised")):
        raise ValueError("repair evidence unexpectedly decisional")
    reference = repair["combined_repair_order_options"][VARIANT]
    if reference["current_exact_stop_ids_encountered_count"] != 11:
        raise ValueError("inclusive variant drift")
    west, east = itinerary()
    if ([label for label, _ in west] != reference["west_ordered_waypoints"]
            or [label for label, _ in east] != reference["east_ordered_waypoints"]):
        raise ValueError("waypoint order drift")
    candidate = next(row for row in rows(paths["candidates_normalized_newlines"])
                     if row["candidate_id"] == "P2V2S_0031")
    if candidate["physical_status"] != "FIELD_CHECK_PENDING":
        raise ValueError("south candidate status drift")
    attachment_nodes = {sid: row["graph_node_id"] for sid, row in attachments.items()
                        if row["route_ready"] == "True"}
    attachment_nodes[VIRTUAL] = VIRTUAL
    attachment_nodes[NORTH] = road["north_proxy"]["graph_node_id"]
    lobes = {
        "west_forward": screen_lobe(west, attachment_nodes, edges, rules),
        "east_forward": screen_lobe(east, attachment_nodes, edges, rules),
        "east_reverse": screen_lobe(list(reversed(east)), attachment_nodes, edges, rules),
        "west_reverse": screen_lobe(list(reversed(west)), attachment_nodes, edges, rules),
    }
    if any(not part["reachable"] or part["via_node_bad_turn_indices_at_leg_seams_or_within_legs"]
           for part in lobes.values()):
        raise ValueError("lobe path not validated at represented via-node turns")
    pairs = (("forward_west_then_east", "west_forward", "east_forward",
              "forward_complete_cycle_distance_m"),
             ("reverse_east_then_west", "east_reverse", "west_reverse",
              "reverse_complete_cycle_distance_m"))
    node_coords = {nid: [float(row["lon"]), float(row["lat"])]
                   for nid, row in nodes.items()}
    node_coords[VIRTUAL] = [float(candidate["lon"]), float(candidate["lat"])]
    features = []
    traversals = {}
    for direction, first, second, distance_key in pairs:
        path = lobes[first]["_path_edge_ids"] + lobes[second]["_path_edge_ids"]
        vertex_ids = [edges[path[0]]["u_node_id"]]
        for eid in path:
            if edges[eid]["u_node_id"] != vertex_ids[-1]:
                raise ValueError("discontinuous ordered road path")
            vertex_ids.append(edges[eid]["v_node_id"])
        if abs(sum(float(edges[eid]["length_m"]) for eid in path)
               - reference[distance_key]) > 0.01:
            raise ValueError("exported route length differs from frozen result")
        if vertex_ids[0] != vertex_ids[-1]:
            raise ValueError("full traversal does not return to FS")
        traversals[direction] = {
            "distance_m": reference[distance_key],
            "directed_edge_count": len(path),
            "ordered_edge_ids_sha256": hashlib.sha256(
                "\n".join(path).encode("utf-8")).hexdigest(),
            "vertex_ids": vertex_ids,
        }
        features.append({
            "type": "Feature",
            "properties": {
                "feature_type": "MODELED_ROAD_PATH_NOT_APPROVED_TPL_ROUTE",
                "variant_id": VARIANT,
                "traversal": direction,
                "distance_m": reference[distance_key],
                "directed_edge_count": len(path),
                "ordered_edge_ids_sha256": traversals[direction]["ordered_edge_ids_sha256"],
                "waypoint_labels": (reference["west_ordered_waypoints"]
                                    + reference["east_ordered_waypoints"][1:]
                                    if direction.startswith("forward") else
                                    list(reversed(reference["east_ordered_waypoints"]))
                                    + list(reversed(reference["west_ordered_waypoints"]))[1:]),
            },
            "geometry": {"type": "LineString", "coordinates": [node_coords[n]
                                                          for n in vertex_ids]},
        })
    expected_stops = set(reference["both_direction_encountered_stop_ids"])
    if len(expected_stops) != 25:
        raise ValueError("existing stop count drift")
    forward_nodes = set(traversals["forward_west_then_east"]["vertex_ids"])
    reverse_nodes = set(traversals["reverse_east_then_west"]["vertex_ids"])
    for sid in sorted(expected_stops):
        row = attachments[sid]
        if row["graph_node_id"] not in forward_nodes or row["graph_node_id"] not in reverse_nodes:
            raise ValueError(f"inventory attachment not on both modeled paths: {sid}")
        features.append({
            "type": "Feature",
            "properties": {"feature_type": "EXISTING_INVENTORY_STOP_ENCOUNTERED_NOT_BOARDING_CERTIFIED",
                           "stop_place_id": sid, "name": row["stop_name"],
                           "municipality": row["municipality"],
                           "attachment_distance_m": float(row["attachment_distance_m"]),
                           "existence_confidence": row["existence_confidence"]},
            "geometry": {"type": "Point", "coordinates": [float(row["lon"]),
                                                          float(row["lat"])]},
        })
    for sid, name, coord, status in (
        ("P2V2S_0031", "Olgiate sud / Via Aldo Moro",
         [float(candidate["lon"]), float(candidate["lat"])], "FIELD_CHECK_PENDING"),
        (NORTH, "San Zeno / Via Cantù",
         node_coords[attachment_nodes[NORTH]], "ROAD_NODE_PROXY_NOT_STOP_SITE"),
    ):
        features.append({"type": "Feature",
                         "properties": {"feature_type": "NEW_STOP_NEED_NOT_APPROVED_STOP",
                                        "stop_place_id": sid, "name": name,
                                        "physical_status": status},
                         "geometry": {"type": "Point", "coordinates": coord}})
    return {
        "type": "FeatureCollection",
        "name": "RT031_LINE8_INCLUSIVE_MODELED_ROAD_SHAPE_V3",
        "properties": {
            "status": "NON_DECISIONAL_NOT_A_CERTIFIED_TPL_ROUTE_OR_STOP_PLAN",
            "variant_id": VARIANT,
            "source_sha256": {key: digest(paths[key], key == "candidates_normalized_newlines"
                                               or key == "road_screen") for key in paths},
            "existing_inventory_stop_points_encountered": 25,
            "new_stop_needs_not_certified": 2,
            "geometry_crs": "EPSG:4326",
            "distance_source": "pinned directed road edges in EPSG:32632",
            "limitations": ["full-history via-way restrictions not certified",
                            "vehicle suitability and safety not field certified",
                            "inventory stop encounter is not a boarding event",
                            "new south site pending field check",
                            "San Zeno point is a road-node proxy, not a stop",
                            "no timetable, rail synchronization, or annual bus-km certified"],
            "network_selected": False,
            "primary_selection_authorised": False,
            "runner_up_selection_authorised": False,
            "decision_budget_km": None,
            "uncertainty_band_min": None,
        },
        "features": features,
    }


def main(paths, output):
    result = materialise(paths)
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
