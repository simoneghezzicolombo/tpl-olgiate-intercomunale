"""Bounded open-path and reciprocal-corridor physical search for RT031.

A reciprocal corridor is one A->B physical path plus one independently declared
B->A path.  Pairing establishes neither a vehicle turn nor passenger continuity
at termini.  Stop availability is not public service.
"""
from __future__ import annotations

from decimal import Decimal
import hashlib
import heapq

from src.phase2_rt031_rt023_pairwise_compatibility_v3 import LEGAL, ILLEGAL


def _physical_domain(catalog, pairs, weights, stop_sets, budget_m):
    budget = Decimal(str(budget_m))
    if not budget.is_finite() or budget <= 0 or not catalog:
        raise ValueError("positive budget and nonempty catalog required")
    ids = sorted(catalog)
    costs = {rid: Decimal(str(weights[rid])) for rid in ids}
    if any(not x.is_finite() or x <= 0 for x in costs.values()):
        raise ValueError("positive finite realization weights required")
    universe = sorted(set().union(*(set(stop_sets[r]) for r in ids)))
    if not universe:
        raise ValueError("nonempty stop availability required")
    bits = {s: 1 << i for i, s in enumerate(universe)}
    masks = {r: sum(bits[s] for s in set(stop_sets[r])) for r in ids}
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
    return ids, costs, universe, bits, masks, adjacent, budget


def search_open_paths(catalog, pairs, weights, stop_sets, *, budget_m,
                      max_expansions, history_locality_certified,
                      atomic_legality_certified):
    if history_locality_certified is not True or atomic_legality_certified is not True:
        raise ValueError("certified physical scope required")
    if type(max_expansions) is not int or max_expansions <= 0:
        raise ValueError("positive explicit execution budget required")
    ids, costs, universe, bits, masks, adjacent, budget = _physical_domain(
        catalog, pairs, weights, stop_sets, budget_m)
    best, queue, results = {}, [], {}
    for root in ids:
        if costs[root] <= budget:
            key = (root, root, masks[root])
            best[key] = costs[root]
            heapq.heappush(queue, (costs[root], root, root, masks[root], (root,)))
    expanded = 0
    while queue and expanded < max_expansions:
        distance, root, last, mask, path = heapq.heappop(queue)
        if distance != best[root, last, mask]:
            continue
        expanded += 1
        source = catalog[root]["source_stop_id"]
        target = catalog[last]["target_stop_id"]
        if source != target:
            key = (source, target, mask)
            old = results.get(key)
            if old is None or (distance, path) < old:
                results[key] = (distance, path)
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
    for (source, target, mask), (distance, path) in sorted(results.items()):
        stops = [s for s in universe if mask & bits[s]]
        identity = source + "|" + target + "|" + ";".join(stops)
        rows.append({
            "open_path_id": "OPEN_" + hashlib.sha256(identity.encode()).hexdigest()[:20],
            "source_stop_id": source,
            "target_stop_id": target,
            "available_stop_ids": stops,
            "minimum_found_distance_m": str(distance),
            "realization_ids": list(path),
            "distance_optimality_certified": exhaustive,
            "public_service_assigned": False,
        })
    return {
        "contract": "RT031_BUDGETED_OPEN_PHYSICAL_PATH_SEARCH_V3",
        "status": "EXHAUSTIVE_WITHIN_DECLARED_PHYSICAL_DOMAIN" if exhaustive else "RESOURCE_LIMIT_INCOMPLETE",
        "exhaustive": exhaustive,
        "expanded_states": expanded,
        "execution_expansion_limit": max_expansions,
        "retained_label_count": len(best),
        "pending_heap_entries": len(queue),
        "distance_budget_m": str(budget),
        "open_path_count": len(rows),
        "paths": rows,
        "closed_paths_excluded": True,
        "full_ordered_realization_witness_retained": True,
        "restriction_state_equivalence_basis": (
            "CALLER_CERTIFIED_HISTORY_LOCALITY_FOR_THE_FROZEN_RT023_ATOMIC_DOMAIN"
        ),
        "named_endpoint_forced": False,
        "public_service_assigned": False,
        "production_search_pass": False,
    }


def reciprocal_availability_envelope(paths, *, shared_budget_m):
    budget = Decimal(str(shared_budget_m))
    if not budget.is_finite() or budget <= 0:
        raise ValueError("positive finite shared budget required")
    records = {}
    for row in paths:
        pid = str(row.get("open_path_id", "")).strip()
        source = str(row.get("source_stop_id", "")).strip()
        target = str(row.get("target_stop_id", "")).strip()
        stops = tuple(row.get("available_stop_ids", ()))
        cost = Decimal(str(row.get("minimum_found_distance_m", "")))
        if (not pid or pid in records or not source or not target or source == target
                or not stops or len(stops) != len(set(stops))
                or not cost.is_finite() or cost <= 0 or not row.get("realization_ids")):
            raise ValueError("invalid open physical path")
        records[pid] = (source, target, frozenset(stops), cost)
    if not records:
        raise ValueError("empty open-path pool")
    by_endpoints = {}
    for pid, (source, target, stops, cost) in records.items():
        by_endpoints.setdefault((source, target), []).append((pid, stops, cost))
    summaries, considered, feasible = {}, 0, 0
    endpoint_pairs = 0
    for source, target in sorted(by_endpoints):
        if source >= target or (target, source) not in by_endpoints:
            continue
        endpoint_pairs += 1
        for left in sorted(by_endpoints[source, target]):
            for right in sorted(by_endpoints[target, source]):
                considered += 1
                cost = left[2] + right[2]
                if cost > budget:
                    continue
                feasible += 1
                stops = tuple(sorted(left[1] | right[1]))
                witness = {"endpoint_a": source, "endpoint_b": target,
                           "a_to_b_open_path_id": left[0], "b_to_a_open_path_id": right[0]}
                old = summaries.get(stops)
                if old is None or cost < old["cost"]:
                    summaries[stops] = {"cost": cost, "witnesses": [witness]}
                elif cost == old["cost"]:
                    old["witnesses"].append(witness)
    return {
        "availability_summaries": [
            {"available_stop_ids": list(stops), "distance_m": str(value["cost"]),
             "minimum_distance_witnesses": value["witnesses"]}
            for stops, value in sorted(summaries.items())],
        "reciprocal_endpoint_pair_count": endpoint_pairs,
        "considered_reciprocal_path_pairs": considered,
        "feasible_reciprocal_path_pairs": feasible,
        "unique_availability_set_count": len(summaries),
        "shared_budget_m": str(budget),
        "terminus_vehicle_continuity_inferred": False,
        "terminus_passenger_continuity_inferred": False,
        "cross_direction_transfer_inferred": False,
        "stop_identity_availability_only": True,
        "directional_stop_occurrence_guaranteed": False,
        "ordered_service_event_guaranteed": False,
        "public_service_assigned": False,
        "network_selected": False,
    }
