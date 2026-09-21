"""Exact physical co-presence query on certified atomic pairwise transitions.

This is a target-specific feasibility calculation, not candidate admission,
passenger-service certification, or an optimisation over access outcomes.
"""
from decimal import Decimal
import heapq

from src.phase2_rt031_rt023_pairwise_compatibility_v3 import LEGAL, ILLEGAL


def shortest_joint_cycle(catalog, pairs, weights, stop_sets, *, hub_stop_id,
                         brivio_stop_id, santa_maria_stop_ids,
                         history_locality_certified, atomic_legality_certified):
    if history_locality_certified is not True or atomic_legality_certified is not True:
        raise ValueError("certified physical transition scope required")
    ids = sorted(catalog)
    if not ids:
        raise ValueError("nonempty realization domain required")
    santa = frozenset(santa_maria_stop_ids)
    if not santa or brivio_stop_id in santa or hub_stop_id in santa:
        raise ValueError("distinct nonempty target stop groups required")
    observed = set().union(*(set(stop_sets[r]) for r in ids))
    if not {hub_stop_id, brivio_stop_id}.issubset(observed) or not santa <= observed:
        raise ValueError("target stop is absent from the physical domain")
    costs = {r: Decimal(str(weights[r])) for r in ids}
    if any(not c.is_finite() or c <= 0 for c in costs.values()):
        raise ValueError("positive finite realization distances required")
    flags = {r: (int(brivio_stop_id in stop_sets[r]) |
                 (2 if set(stop_sets[r]) & santa else 0)) for r in ids}
    index = {}
    for pair in pairs:
        key = (pair["left_realization_id"], pair["right_realization_id"])
        if key in index or pair["status"] not in (LEGAL, ILLEGAL):
            raise ValueError("duplicate or unknown pairwise transition")
        index[key] = pair["status"]
    adjacent = {}
    for left in ids:
        next_ids = []
        for right in ids:
            if catalog[left]["target_stop_id"] != catalog[right]["source_stop_id"]:
                continue
            if (left, right) not in index:
                raise ValueError("missing relevant pairwise transition")
            if index[left, right] == LEGAL:
                next_ids.append(right)
        adjacent[left] = next_ids
    roots = [r for r in ids if hub_stop_id in stop_sets[r]]
    queue = []
    best = {}
    predecessor = {}
    for root in roots:
        state = (root, root, flags[root])
        best[state] = costs[root]
        heapq.heappush(queue, (costs[root], state))
    settled = 0
    winner = None
    while queue:
        distance, state = heapq.heappop(queue)
        if distance != best[state]:
            continue
        settled += 1
        root, last, mask = state
        if mask == 3 and root in adjacent[last]:
            winner = state
            break
        for nxt in adjacent[last]:
            successor = (root, nxt, mask | flags[nxt])
            next_distance = distance + costs[nxt]
            if successor not in best or next_distance < best[successor]:
                best[successor] = next_distance
                predecessor[successor] = state
                heapq.heappush(queue, (next_distance, successor))
    path = []
    if winner is not None:
        state = winner
        while state in predecessor:
            path.append(state[1])
            state = predecessor[state]
        path.append(state[1])
        path.reverse()
    return {
        "contract": "RT031_JOINT_TARGET_SHORTEST_PHYSICAL_CYCLE_V3",
        "search_exhaustive_for_target": True,
        "root_realization_count": len(roots),
        "unfiltered_realization_count": len(ids),
        "settled_target_states": settled,
        "minimum_joint_distance_m": str(best[winner]) if winner else None,
        "minimum_joint_realization_ids": path,
        "public_service_certified": False,
        "network_selected": False,
    }
