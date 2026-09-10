"""Exact carrier-distance optimization for a declared finite ordered route.

Not a territorial network optimizer. Requires certified atomic legality and
history locality. Cyclic routes check the final-to-first transition explicitly.
"""
from decimal import Decimal
from src.phase2_rt031_rt023_pairwise_compatibility_v3 import LEGAL, ILLEGAL, UNKNOWN


def optimize_chain(slots, by_slot, pairwise, distances, *, closed,
                   atomic_legality_certified, history_locality_certified):
    if not slots or any(type(v) is not bool for v in
                        (closed, atomic_legality_certified, history_locality_certified)):
        raise ValueError('nonempty route and explicit certification flags required')
    layers = []
    for slot in slots:
        ids = sorted(r['realization_id'] for r in by_slot[tuple(slot)])
        if not ids or len(set(ids)) != len(ids):
            raise ValueError('empty or duplicate alternatives')
        layers.append(ids)
    weights = {rid: Decimal(str(distances[rid])) for layer in layers for rid in layer}
    if any(not w.is_finite() or w <= 0 for w in weights.values()):
        raise ValueError('positive finite carrier distances required')
    index = {}
    for row in pairwise:
        key = (row['left_realization_id'], row['right_realization_id'])
        if key in index or row['status'] not in (LEGAL, ILLEGAL, UNKNOWN):
            raise ValueError('duplicate or invalid pairwise record')
        index[key] = row['status']
    adjacency = list(zip(layers, layers[1:]))
    if closed:
        adjacency.append((layers[-1], layers[0]))
    # Conservative: any missing/unknown relevant arc prevents exact optimality.
    complete = atomic_legality_certified and history_locality_certified and all(
        index.get((a, b)) in (LEGAL, ILLEGAL)
        for left, right in adjacency for a in left for b in right)
    result = dict(exact=complete, closed=closed, slot_count=len(layers),
                  compatible_sequence_count=None, minimum_distance_m=None,
                  realization_ids=None, service_semantics_assigned=False,
                  network_selected=False, global_network_optimality_claimed=False)
    if not complete:
        return dict(result, status='UNKNOWN_COMPLETE_CHAIN_DISTANCE')
    total, best = 0, None
    # First alternative is retained as a state to enforce the cycle seam.
    for first in layers[0]:
        counts = {first: 1}
        costs = {first: (weights[first], (first,))}
        for layer in layers[1:]:
            next_counts, next_costs = {}, {}
            for right in layer:
                eligible = [left for left in counts if index[(left, right)] == LEGAL]
                if eligible:
                    next_counts[right] = sum(counts[left] for left in eligible)
                    next_costs[right] = min((costs[left][0] + weights[right],
                                            costs[left][1] + (right,)) for left in eligible)
            counts, costs = next_counts, next_costs
        for last in counts:
            if closed and index[(last, first)] != LEGAL:
                continue
            total += counts[last]
            if best is None or costs[last] < best:
                best = costs[last]
    result.update(compatible_sequence_count=total,
                  minimum_distance_m=None if best is None else str(best[0]),
                  realization_ids=None if best is None else list(best[1]),
                  status='EXACT_COMPLETE_CHAIN_DISTANCE' if best else 'PROVEN_NO_COMPATIBLE_CHAIN')
    return result
