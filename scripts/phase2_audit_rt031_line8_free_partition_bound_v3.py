"""Exact two-cycle bound freeing every fixed waypoint's wing assignment.

The distance metric uses independent shortest legs with represented via-node
rules. This relaxes composition, boarding, vehicle and full-history legality.
"""

import argparse
import json
from pathlib import Path

from scripts.phase2_audit_rt031_south_road_probe_v3 import EXPECTED, VIRTUAL, digest, shortest
from scripts.phase2_export_rt031_line8_inclusive_shape_v3 import NORTH, itinerary
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph, screen_lobe
from scripts.phase2_probe_rt031_current_stop_repair_v3 import path_stops
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter


def two_cycles(cost):
    """All-subset Held-Karp; vertex 0 is the common depot; integer costs."""
    n = len(cost) - 1
    if n < 2:
        raise ValueError("two nonempty cycles require at least two waypoints")
    full = (1 << n) - 1
    dp, parent, cycles, endings = {}, {}, {0: 0}, {}
    for mask in range(1, full + 1):
        members = [i for i in range(n) if mask & (1 << i)]
        best_cycle = None
        for last in members:
            previous = mask ^ (1 << last)
            if previous == 0:
                value, prev = cost[0][last + 1], -1
            else:
                value, prev = min((dp[previous, p] + cost[p + 1][last + 1], p)
                                  for p in members if p != last)
            dp[mask, last], parent[mask, last] = value, prev
            closed = (value + cost[last + 1][0], last)
            if best_cycle is None or closed < best_cycle:
                best_cycle = closed
        cycles[mask], endings[mask] = best_cycle
    # Keep waypoint 1 in the first wing to remove wing-label symmetry.
    total, chosen = min((cycles[m] + cycles[full ^ m], m)
                        for m in range(1, full) if m & 1)
    def reconstruct(mask):
        original, last, order = mask, endings[mask], []
        while mask:
            order.append(last + 1)
            prev = parent[mask, last]
            mask ^= 1 << last
            last = prev
        return [0] + list(reversed(order)) + [0], cycles[original]
    return total, reconstruct(chosen), reconstruct(full ^ chosen), cycles


def build(paths):
    road = json.loads(paths["road_screen"].read_text(encoding="utf-8"))
    prior = json.loads(paths["fixed_bound"].read_text(encoding="utf-8"))
    if (road["contract"] != "RT031_UNIQUE_LINE_ROAD_SCREEN_V3"
            or prior["contract"] != "RT031_LINE8_ALL_FIXED_WAYPOINT_ORDERS_KM_LOWER_BOUND_V3"
            or prior["source_sha256"]["road_screen"] != digest(paths["road_screen"], True)):
        raise ValueError("source contract drift")
    edges, _, rules, attachments = build_graph(paths)
    nodes = {sid: row["graph_node_id"] for sid, row in attachments.items()
             if row["route_ready"] == "True"}
    nodes[VIRTUAL], nodes[NORTH] = VIRTUAL, road["north_proxy"]["graph_node_id"]
    w, e = itinerary()
    points = [w[0]] + w[1:-1] + e[1:-1]
    ids = [sid for _, sid in points]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate representative waypoint")
    directed = {}
    for a in ids:
        for b in ids:
            if a == b:
                continue
            leg = shortest(edges, rules, nodes[a], nodes[b], objective="meters")
            if leg is None:
                raise ValueError("unreachable waypoint pair")
            directed[a, b] = int(round(leg["distance_m"] * 1000))
    costs = [[0 if a == b else directed[a, b] + directed[b, a]
              for b in ids] for a in ids]
    optimum, first, second, cycles = two_cycles(costs)
    directed_costs = [[0 if a == b else directed[a, b] for b in ids] for a in ids]
    relaxed_directed, relaxed_first, relaxed_second, _ = two_cycles(directed_costs)
    original_mask = sum(1 << (ids.index(sid) - 1) for _, sid in w[1:-1])
    full = (1 << (len(ids) - 1)) - 1
    reproduced = (cycles[original_mask] + cycles[full ^ original_mask]) / 1000
    if abs(reproduced - prior["total_optimistic_bidirectional_pair_distance_m"]) > .01:
        raise ValueError("fixed-wing lower bound not reproduced")
    sequences = [[points[i] for i in result[0]] for result in (first, second)]
    parts = {key: screen_lobe(seq, nodes, edges, rules, objective="meters")
             for key, seq in (("af", sequences[0]), ("bf", sequences[1]),
                              ("br", list(reversed(sequences[1]))),
                              ("ar", list(reversed(sequences[0]))))}
    if not all(part["reachable"] for part in parts.values()):
        raise ValueError("reconstructed bound path unreachable")
    adapter = FrozenRT017ViaNodeAdapter(edges.values(), rules,
                                       unresolved_external_via_way_count=2)
    joins = {}
    for a, b in (("af", "bf"), ("br", "ar")):
        left, right = parts[a]["_path_edge_ids"][-1], parts[b]["_path_edge_ids"][0]
        joins[a + "_to_" + b] = (edges[left]["v_node_id"] == edges[right]["u_node_id"]
                                 and adapter.decision((left,), right)["allowed"] is True)
    eligible = {sid: row["graph_node_id"] for sid, row in attachments.items()
                if row["route_ready"] == "True" and row["service_class"] == "CONVENTIONAL_TPL"}
    f_stops = path_stops(parts["af"], edges, eligible) | path_stops(parts["bf"], edges, eligible)
    r_stops = path_stops(parts["ar"], edges, eligible) | path_stops(parts["br"], edges, eligible)
    successor = json.loads(paths["successor"].read_text(encoding="utf-8"))
    via_ways = {way for relation in successor["successor_via_way_relations"]
                for way in relation["via_way_ids"]}
    return {
        "contract": "RT031_LINE8_FREE_TWO_WING_PARTITION_DISTANCE_BOUND_V3",
        "status": "NON_DECISIONAL_OPTIMISTIC_GRAPH_BOUND",
        "source_sha256": {key: digest(path, key in (
            "road_screen", "fixed_bound", "candidates_normalized_newlines"))
                          for key, path in paths.items()},
        "waypoint_count_excluding_fs": len(ids) - 1,
        "all_nonempty_unlabelled_partitions_count": (1 << (len(ids) - 2)) - 1,
        "directed_shortest_leg_count": len(directed),
        "fixed_wing_pair_distance_lower_bound_m_reproduced": reproduced,
        "free_partition_pair_distance_lower_bound_m": optimum / 1000,
        "annual_10_pairs_260_days_lower_bound_km_before_extras": round(optimum * 2600 / 1000000, 3),
        "independent_orientation_relaxation": {
            "one_two_wing_traversal_lower_bound_m": relaxed_directed / 1000,
            "annual_20_traversals_260_days_lower_bound_km_before_extras":
                round(relaxed_directed * 5200 / 1000000, 3),
            "semantics": "Even more permissive bound: both nominal orientations may independently choose any partition and order, including the same directed tour. Not reciprocal service or a timetable.",
            "relaxed_orders": [[ids[i] for i in row[0]]
                                for row in (relaxed_first, relaxed_second)],
        },
        "optimal_relaxed_wing_orders": [[{"label": label, "waypoint_id": sid}
                                          for label, sid in seq] for seq in sequences],
        "reconstructed_leg_path_pair_distance_m": round(sum(p["distance_m"] for p in parts.values()), 3),
        "represented_via_node_bad_turn_count": sum(len(p[
            "via_node_bad_turn_indices_at_leg_seams_or_within_legs"]) for p in parts.values()),
        "represented_fs_joins_allowed": joins,
        "known_successor_via_way_overlap": sorted(via_ways & set().union(*(
            set(p["osm_way_ids"]) for p in parts.values()))),
        "both_direction_encountered_stop_ids_not_boarding_guaranteed": sorted(f_stops & r_stops),
        "scope": "All partitions into two nonempty FS-rooted wings and all orders of the same 15 fixed representative waypoint nodes; no deletion or relocation. Main bound uses reciprocal waypoint orders; independent-orientation relaxation removes even that requirement. Independent shortest legs relax composition and unmodeled restrictions.",
        "not_certified": ["full-history restriction legality", "global physical street completeness",
                          "vehicle suitability", "stop events", "passenger headways", "depot kilometres"],
        "network_selected": False, "primary_selection_authorised": False,
        "runner_up_selection_authorised": False, "decision_budget_km": None,
        "uncertainty_band_min": None,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for key in (*EXPECTED, "road_screen", "fixed_bound"):
        parser.add_argument("--" + key, required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build({key: getattr(args, key) for key in (*EXPECTED, "road_screen", "fixed_bound")})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":")) + "\n", encoding="utf-8")
