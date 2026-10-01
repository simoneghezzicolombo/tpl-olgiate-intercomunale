"""Targeted closed-walk coverage search for the frozen RT-023 physical domain.

Only caller-declared target stop identities participate in label dominance. This
is valid for the narrow objective of finding minimum physical distance needed to
cover those identities; it makes no statement about service events or journeys.
"""
from __future__ import annotations

from decimal import Decimal
import heapq

from src.phase2_rt031_rt023_pairwise_compatibility_v3 import LEGAL, ILLEGAL


def search_target_closed_walks(
    catalog,
    pairs,
    weights,
    stop_sets,
    target_stop_ids,
    *,
    maximum_distance_m,
    max_expansions,
    history_locality_certified,
    atomic_legality_certified,
):
    if history_locality_certified is not True or atomic_legality_certified is not True:
        raise ValueError("certified physical scope required")
    if type(max_expansions) is not int or max_expansions <= 0:
        raise ValueError("positive explicit execution budget required")
    budget = Decimal(str(maximum_distance_m))
    if not budget.is_finite() or budget <= 0:
        raise ValueError("positive finite maximum distance required")
    ids = sorted(catalog)
    if not ids:
        raise ValueError("nonempty catalog required")
    targets = tuple(sorted(set(target_stop_ids)))
    if not targets:
        raise ValueError("nonempty target stop set required")
    universe = set().union(*(set(stop_sets[rid]) for rid in ids))
    missing = sorted(set(targets) - universe)
    if missing:
        raise ValueError("target stops absent from physical domain: " + ",".join(missing))

    costs = {rid: Decimal(str(weights[rid])) for rid in ids}
    if any(not value.is_finite() or value <= 0 for value in costs.values()):
        raise ValueError("positive finite realization weights required")
    bits = {stop: 1 << index for index, stop in enumerate(targets)}
    masks = {
        rid: sum(bits[stop] for stop in set(stop_sets[rid]) if stop in bits)
        for rid in ids
    }
    pair_index = {}
    for row in pairs:
        key = (row["left_realization_id"], row["right_realization_id"])
        if key in pair_index or row["status"] not in (LEGAL, ILLEGAL):
            raise ValueError("duplicate or unknown pairwise evidence")
        pair_index[key] = row["status"]
    adjacent = {}
    for left in ids:
        following = []
        for right in ids:
            if catalog[left]["target_stop_id"] != catalog[right]["source_stop_id"]:
                continue
            if (left, right) not in pair_index:
                raise ValueError("missing relevant pairwise evidence")
            if pair_index[left, right] == LEGAL:
                following.append(right)
        adjacent[left] = following

    # Any useful closed walk contains a target-bearing atom and can be rotated to
    # one. Retaining the root still preserves the closing-seam legality check.
    roots = [rid for rid in ids if masks[rid]]
    best, queue = {}, []
    for root in roots:
        if costs[root] <= budget:
            key = (root, root, masks[root])
            best[key] = costs[root]
            heapq.heappush(queue, (costs[root], root, root, masks[root], (root,)))

    results = {}
    expanded = 0
    while queue and expanded < max_expansions:
        distance, root, last, mask, path = heapq.heappop(queue)
        if distance != best[root, last, mask]:
            continue
        expanded += 1
        if root in adjacent[last]:
            previous = results.get(mask)
            if previous is None or (distance, path) < previous:
                results[mask] = (distance, path)
        for nxt in adjacent[last]:
            new_distance = distance + costs[nxt]
            if new_distance > budget:
                continue
            new_mask = mask | masks[nxt]
            key = (root, nxt, new_mask)
            if key not in best or new_distance < best[key]:
                best[key] = new_distance
                heapq.heappush(queue, (new_distance, root, nxt, new_mask, path + (nxt,)))

    exhaustive = not queue
    rows = []
    for mask, (distance, path) in sorted(results.items()):
        rows.append({
            "target_stop_ids": [stop for stop in targets if mask & bits[stop]],
            "target_mask": mask,
            "minimum_found_distance_m": str(distance),
            "realization_ids": list(path),
            "distance_optimality_certified": exhaustive,
            "public_service_assigned": False,
        })
    return {
        "contract": "RT031_TARGETED_CLOSED_WALK_COVERAGE_SEARCH_V3",
        "status": "EXHAUSTIVE_WITHIN_DECLARED_PHYSICAL_DOMAIN" if exhaustive else "RESOURCE_LIMIT_INCOMPLETE",
        "exhaustive": exhaustive,
        "expanded_states": expanded,
        "execution_expansion_limit": max_expansions,
        "retained_label_count": len(best),
        "pending_heap_entries": len(queue),
        "maximum_distance_m": str(budget),
        "target_stop_ids": list(targets),
        "target_stop_count": len(targets),
        "target_bearing_root_count": len(roots),
        "found_target_subset_count": len(rows),
        "target_mask_only_dominance": True,
        "restriction_state_equivalence_basis": "CALLER_CERTIFIED_HISTORY_LOCALITY_FOR_FROZEN_RT023_ATOMIC_DOMAIN",
        "full_ordered_realization_witness_retained": True,
        "stop_identity_guarantee_only": True,
        "ordered_service_event_guaranteed": False,
        "production_search_pass": False,
        "candidates": rows,
    }


def minimum_cover_portfolios(candidates, target_stop_ids, *, max_movements):
    if type(max_movements) is not int or max_movements <= 0:
        raise ValueError("positive movement limit required")
    targets = tuple(sorted(set(target_stop_ids)))
    if not targets:
        raise ValueError("nonempty target stop set required")
    bits = {stop: 1 << index for index, stop in enumerate(targets)}
    full_mask = (1 << len(targets)) - 1
    normalized = []
    for index, row in enumerate(candidates):
        stops = set(row.get("target_stop_ids", ()))
        if not stops or not stops <= set(targets):
            raise ValueError("invalid target subset candidate")
        mask = sum(bits[stop] for stop in stops)
        if row.get("target_mask") not in (None, mask):
            raise ValueError("target mask drift")
        cost = Decimal(str(row.get("minimum_found_distance_m", "")))
        witness = tuple(row.get("realization_ids", ()))
        if not cost.is_finite() or cost <= 0 or not witness:
            raise ValueError("invalid target coverage candidate")
        normalized.append((mask, cost, index, witness))

    # One cheapest physical witness is sufficient for every exact target mask.
    cheapest = {}
    for item in normalized:
        mask, cost, index, witness = item
        previous = cheapest.get(mask)
        if previous is None or (cost, witness) < (previous[1], previous[3]):
            cheapest[mask] = item
    choices = [cheapest[mask] for mask in sorted(cheapest)]

    layer = {0: (Decimal(0), ())}
    results = []
    for movement_count in range(1, max_movements + 1):
        next_layer = dict(layer)
        for covered, (cost, selected) in layer.items():
            for mask, candidate_cost, index, witness in choices:
                union = covered | mask
                if union == covered:
                    continue
                proposal = (cost + candidate_cost, selected + (index,))
                previous = next_layer.get(union)
                if previous is None or proposal < previous:
                    next_layer[union] = proposal
        layer = next_layer
        solution = layer.get(full_mask)
        results.append({
            "maximum_movement_count": movement_count,
            "full_target_cover_found": solution is not None,
            "minimum_found_total_distance_m": str(solution[0]) if solution else None,
            "candidate_indices": list(solution[1]) if solution else [],
        })
    return {
        "target_stop_ids": list(targets),
        "maximum_movement_count_evaluated": max_movements,
        "candidate_target_subset_count": len(choices),
        "results": results,
        "weighted_score": False,
        "public_service_assigned": False,
        "vehicle_continuity_inferred": False,
        "passenger_continuity_inferred": False,
    }
