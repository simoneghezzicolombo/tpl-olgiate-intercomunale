"""Fixed-order shortest road path retaining represented turn memory at waypoints.

Only RT017 via-node semantics are enforced. Full-history via-way legality,
boarding and vehicle suitability are explicitly NOT certified.
"""

from collections import defaultdict
import heapq

from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter


def ordered_path(edges, rules, waypoint_nodes, incoming=None, outgoing=None):
    if len(waypoint_nodes) < 2:
        raise ValueError("at least two ordered waypoint nodes required")
    if incoming and edges[incoming]["v_node_id"] != waypoint_nodes[0]:
        raise ValueError("incoming boundary not at source")
    if outgoing and edges[outgoing]["u_node_id"] != waypoint_nodes[-1]:
        raise ValueError("outgoing boundary not at target")
    adapter = FrozenRT017ViaNodeAdapter(edges.values(), rules,
                                       unresolved_external_via_way_count=2)
    adjacency = defaultdict(list)
    for eid, edge in edges.items():
        adjacency[edge["u_node_id"]].append(eid)
    for values in adjacency.values():
        values.sort()
    def advance(index, node):
        while index < len(waypoint_nodes) and waypoint_nodes[index] == node:
            index += 1
        return index
    start = (advance(1, waypoint_nodes[0]), waypoint_nodes[0], incoming or "")
    best, previous, heap = {start: (0., 0.)}, {}, [(0., 0., *start)]
    finish = None
    while heap:
        meters, minutes, index, node, last = heapq.heappop(heap)
        state = (index, node, last)
        if best[state] != (meters, minutes):
            continue
        if index == len(waypoint_nodes) and node == waypoint_nodes[-1]:
            if not outgoing or (last and adapter.decision((last,), outgoing)["allowed"] is True):
                finish = state
                break
        for eid in adjacency.get(node, ()):
            if last and adapter.decision((last,), eid)["allowed"] is not True:
                continue
            edge = edges[eid]
            nxt = (advance(index, edge["v_node_id"]), edge["v_node_id"], eid)
            cost = (meters + float(edge["length_m"]), minutes + float(edge["running_minutes_model"]))
            if nxt not in best or cost < best[nxt]:
                best[nxt], previous[nxt] = cost, (state, eid)
                heapq.heappush(heap, (*cost, *nxt))
    if finish is None:
        return {"reachable": False}
    cursor, path = finish, []
    while cursor != start:
        cursor, eid = previous[cursor]
        path.append(eid)
    path.reverse()
    return {"reachable": True, "distance_m": round(best[finish][0], 3),
            "running_minutes_model": round(best[finish][1], 6),
            "_path_edge_ids": path,
            "osm_way_ids": sorted({edges[eid]["osm_way_id"] for eid in path}),
            "via_node_bad_turn_indices_at_leg_seams_or_within_legs": [],
            "full_history_via_way_legality_certified": False,
            "state_semantics": "ordered-waypoint progress, current road node and incoming directed edge; sufficient only for represented via-node rules"}
