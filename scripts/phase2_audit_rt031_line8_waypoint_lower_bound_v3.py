"""Optimistic kilometre lower bound over every order of fixed wing waypoints.

Independent shortest legs may fail to compose legally and may skip inventory
stops. This is a lower bound, never an operational Linea 8 proposal.
"""

import argparse
from functools import lru_cache
import json
from pathlib import Path

from scripts.phase2_audit_rt031_south_road_probe_v3 import EXPECTED, VIRTUAL, digest, shortest
from scripts.phase2_export_rt031_line8_inclusive_shape_v3 import NORTH, itinerary
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph


def minimum_pair_cycle(points, node_ids, edges, rules, dropped=frozenset(), cache=None):
    """Held-Karp on symmetric out+back leg distance; FS is points[0]."""
    if points[0][1] != points[-1][1] or len(points) < 4:
        raise ValueError("wing must start and end at FS")
    internal = [point for point in points[1:-1] if point[1] not in dropped]
    ids = [points[0][1]] + [sid for _, sid in internal]
    directed = {} if cache is None else cache
    for a in ids:
        for b in ids:
            if a == b:
                continue
            if (a, b) not in directed:
                result = shortest(edges, rules, node_ids[a], node_ids[b], objective="meters")
                if result is None:
                    raise ValueError(f"unreachable ordered waypoint leg: {a} -> {b}")
                directed[a, b] = result["distance_m"]
    def pair(a, b):
        return directed[a, b] + directed[b, a]
    @lru_cache(None)
    def solve(mask, last):
        if mask == (1 << len(internal)) - 1:
            return pair(ids[last], ids[0]), ()
        best = (float("inf"), ())
        for nxt in range(1, len(ids)):
            if mask & (1 << (nxt - 1)):
                continue
            rest, order = solve(mask | (1 << (nxt - 1)), nxt)
            candidate = (pair(ids[last], ids[nxt]) + rest, (nxt,) + order)
            if candidate < best:
                best = candidate
        return best
    lower_m, indexes = solve(0, 0)
    ordered = [ids[0]] + [ids[i] for i in indexes] + [ids[0]]
    return {"optimistic_pair_distance_m": round(lower_m, 3),
            "ordered_waypoint_ids_at_optimistic_minimum": ordered,
            "directed_pairwise_shortest_leg_count": len(ids) * (len(ids) - 1),
            "not_certified": "Independent shortest legs may not compose, preserve other stop identities, or be bus-suitable."}


def build(paths):
    road = json.loads(paths["road_screen"].read_text(encoding="utf-8"))
    if road["contract"] != "RT031_UNIQUE_LINE_ROAD_SCREEN_V3":
        raise ValueError("road screen contract drift")
    edges, _, rules, attachments = build_graph(paths)
    nodes = {sid: row["graph_node_id"] for sid, row in attachments.items()
             if row["route_ready"] == "True"}
    nodes[VIRTUAL] = VIRTUAL
    nodes[NORTH] = road["north_proxy"]["graph_node_id"]
    west, east = itinerary()
    caches = {"west": {}, "east": {}}
    wings = {"west": minimum_pair_cycle(west, nodes, edges, rules, cache=caches["west"]),
             "east": minimum_pair_cycle(east, nodes, edges, rules, cache=caches["east"])}
    total = sum(w["optimistic_pair_distance_m"] for w in wings.values())
    removable = {"west": [(label, sid) for label, sid in west[1:-1]
                          if sid != VIRTUAL],
                 "east": [(label, sid) for label, sid in east[1:-1]
                          if sid != NORTH]}
    single_drops = []
    for wing, points in (("west", west), ("east", east)):
        for label, sid in removable[wing]:
            shortened = minimum_pair_cycle(points, nodes, edges, rules,
                                           dropped=frozenset((sid,)), cache=caches[wing])
            pair_m = shortened["optimistic_pair_distance_m"] + wings[
                "east" if wing == "west" else "west"]["optimistic_pair_distance_m"]
            single_drops.append({"wing": wing, "dropped_waypoint_id": sid,
                                 "dropped_waypoint_label": label,
                                 "optimistic_pair_distance_m": round(pair_m, 3),
                                 "annual_10_pairs_260_days_optimistic_km_before_extras":
                                     round(pair_m * 10 * 260 / 1000, 3),
                                 "optimistic_order_after_drop":
                                     shortened["ordered_waypoint_ids_at_optimistic_minimum"]})
    single_drops.sort(key=lambda row: (row["optimistic_pair_distance_m"],
                                       row["wing"], row["dropped_waypoint_id"]))
    return {
        "contract": "RT031_LINE8_ALL_FIXED_WAYPOINT_ORDERS_KM_LOWER_BOUND_V3",
        "status": "NON_DECISIONAL_OPTIMISTIC_GRAPH_BOUND",
        "source_sha256": {key: digest(paths[key], key in (
            "candidates_normalized_newlines", "road_screen"))
                          for key in paths},
        "wings": wings,
        "single_existing_waypoint_drop_sensitivity_optimistic_not_stop_loss": single_drops,
        "total_optimistic_bidirectional_pair_distance_m": round(total, 3),
        "annual_10_pairs_260_days_optimistic_km_before_extras": round(total * 10 * 260 / 1000, 3),
        "required_pair_distance_m_for_111419_km_at_10_pairs_260_days_before_extras":
            round(111419 * 1000 / (10 * 260), 3),
        "interpretation": "Lower bound over every order of current fixed waypoint nodes within the same west/east wings; independent distance-shortest legs, no stop-event or composition guarantee.",
        "not_certified": ["composed path legality", "full-history via-way restrictions",
                          "vehicle suitability", "retention of other inventory stops",
                          "directional boarding", "timetable", "depot kilometres"],
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
    for key in (*EXPECTED, "road_screen"):
        parser.add_argument("--" + key, required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    main({key: getattr(args, key) for key in (*EXPECTED, "road_screen")}, args.output)
