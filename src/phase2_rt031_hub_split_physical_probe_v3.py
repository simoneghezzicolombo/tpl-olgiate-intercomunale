"""Exact pairwise-graph lower bound for two hub-separated physical lobes.

This is a scoped physical diagnostic. It does not certify a passenger service,
directional symmetry, a clockface timetable, or the caller's full itinerary.
"""

from decimal import Decimal
import heapq

from src.phase2_rt031_rt023_pairwise_compatibility_v3 import LEGAL, ILLEGAL


def shortest_hub_split_walk(
    catalog, pairs, weights, stop_sets, *, hub_stop_id,
    west_target_groups, east_target_groups,
    history_locality_certified, atomic_legality_certified,
    ordered_within_lobes=False,
):
    if history_locality_certified is not True or atomic_legality_certified is not True:
        raise ValueError("certified physical transition scope required")
    ids = sorted(catalog)
    if not ids or set(ids) != set(weights) or set(ids) != set(stop_sets):
        raise ValueError("nonempty aligned realization domain required")
    west = tuple(frozenset(group) for group in west_target_groups)
    east = tuple(frozenset(group) for group in east_target_groups)
    if not west or not east or any(not group for group in west + east):
        raise ValueError("both lobes need nonempty target groups")
    observed = set().union(*(set(stop_sets[r]) for r in ids))
    if hub_stop_id not in observed or any(not group & observed for group in west + east):
        raise ValueError("hub or target absent from physical domain")
    costs = {r: Decimal(str(weights[r])) for r in ids}
    if any(not c.is_finite() or c <= 0 for c in costs.values()):
        raise ValueError("positive finite realization distances required")

    pair_index = {}
    for pair in pairs:
        key = (pair["left_realization_id"], pair["right_realization_id"])
        if key in pair_index or pair["status"] not in (LEGAL, ILLEGAL):
            raise ValueError("duplicate or unknown pairwise transition")
        pair_index[key] = pair["status"]
    adjacency = {}
    for left in ids:
        successors = []
        for right in ids:
            if catalog[left]["target_stop_id"] != catalog[right]["source_stop_id"]:
                continue
            if (left, right) not in pair_index:
                raise ValueError("missing relevant pairwise transition")
            if pair_index[left, right] == LEGAL:
                successors.append(right)
        adjacency[left] = successors

    def advance(rid, groups, current):
        if ordered_within_lobes:
            for stop_id in stop_sets[rid]:
                if current < len(groups) and stop_id in groups[current]:
                    current += 1
            return current
        stops = set(stop_sets[rid])
        return current | sum(1 << i for i, group in enumerate(groups) if stops & group)

    full_west = len(west) if ordered_within_lobes else (1 << len(west)) - 1
    full_east = len(east) if ordered_within_lobes else (1 << len(east)) - 1
    roots = [rid for rid in ids if catalog[rid]["source_stop_id"] == hub_stop_id]
    if not roots:
        raise ValueError("no hub-origin realization")
    best, predecessor, queue = {}, {}, []
    for rid in roots:
        state = (0, rid, advance(rid, west, 0))
        best[state] = costs[rid]
        heapq.heappush(queue, (costs[rid], state))
    winner = None
    settled = 0
    while queue:
        distance, state = heapq.heappop(queue)
        if distance != best[state]:
            continue
        settled += 1
        phase, last, mask = state
        at_hub = catalog[last]["target_stop_id"] == hub_stop_id
        if phase == 1 and at_hub and mask == full_east:
            winner = state
            break
        if at_hub and (phase == 1 or mask != full_west):
            continue
        for nxt in adjacency[last]:
            next_phase = 1 if phase == 0 and at_hub else phase
            groups = east if next_phase == 1 else west
            next_mask = advance(nxt, groups, 0 if next_phase != phase else mask)
            successor = (next_phase, nxt, next_mask)
            next_distance = distance + costs[nxt]
            if successor not in best or next_distance < best[successor]:
                best[successor] = next_distance
                predecessor[successor] = state
                heapq.heappush(queue, (next_distance, successor))
    states = []
    if winner is not None:
        state = winner
        while state in predecessor:
            states.append(state)
            state = predecessor[state]
        states.append(state)
        states.reverse()
    split_index = next((i for i, s in enumerate(states) if s[0] == 1), None)
    return {
        "contract": "RT031_HUB_SPLIT_PHYSICAL_PROBE_V3",
        "search_exhaustive_for_pairwise_graph": True,
        "pairwise_graph_lower_bound_m": str(best[winner]) if winner else None,
        "west_realization_ids": [s[1] for s in states[:split_index]] if states else [],
        "east_realization_ids": [s[1] for s in states[split_index:]] if states else [],
        "root_realization_count": len(roots),
        "settled_states": settled,
        "ordered_within_lobes_required": ordered_within_lobes,
        "ordered_physical_target_presence_certified": bool(states) and ordered_within_lobes,
        "public_service_certified": False,
    }
