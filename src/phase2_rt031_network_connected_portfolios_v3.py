"""Exact pool-scoped portfolios connected to a required hub by shared stop IDs."""
from __future__ import annotations

from decimal import Decimal


def _prune_superset_cost_dominated_states(states):
    """Return states not safely dominated by a cheaper/equal strict superset.

    ``states`` maps a stop-union bitmask to ``(cost, witness_ids)``. A state is
    safely dominated when another state covers every stop it covers and costs
    no more. For this model that relation preserves every monotone access and
    stop-retention objective and every future shared-stop connection.

    The implementation is exact. States are processed by nondecreasing cost
    and, for equal cost, decreasing stop count. Per-stop integer bitsets then
    answer whether any already-retained state is a strict superset.
    """
    if not states:
        return {}, 0
    ordered = sorted(
        states.items(),
        key=lambda item: (
            item[1][0], -item[0].bit_count(), item[0], item[1][1],
        ),
    )
    bit_count = max(mask.bit_length() for mask, _ in ordered)
    retained_by_stop = [0] * bit_count
    retained = {}
    retained_count = 0
    for mask, value in ordered:
        possible = (1 << retained_count) - 1
        pending = mask
        while pending and possible:
            least = pending & -pending
            possible &= retained_by_stop[least.bit_length() - 1]
            pending ^= least
        if possible:
            continue
        retained[mask] = value
        flag = 1 << retained_count
        pending = mask
        while pending:
            least = pending & -pending
            retained_by_stop[least.bit_length() - 1] |= flag
            pending ^= least
        retained_count += 1
    return retained, len(states) - len(retained)


def enumerate_network_connected_portfolios(
        candidates, *, hub_stop_id: str, max_movements: int):
    """Return frontier-sufficient connected unions of stop IDs.

    Connectivity is deliberately weak: movements form a connected intersection
    graph and at least one contains the hub identity. It does not certify a
    directional occurrence, ordered service event, or passenger transfer.

    Intermediate layers may discard states safely dominated by cheaper/equal
    strict supersets before they are expanded. This cannot remove a possible
    Pareto point under the current monotone stop-union objectives, but it can
    avoid enumerating dominated descendants when ``max_movements`` exceeds 2.
    """
    if not hub_stop_id or type(max_movements) is not int or max_movements < 1:
        raise ValueError("hub identity and positive movement bound required")
    source = []
    seen_ids = set()
    for row in candidates:
        identity = str(row.get("candidate_id", ""))
        stops = frozenset(str(value) for value in row.get("available_stop_ids", ()))
        cost = Decimal(str(row.get("minimum_found_distance_m", "")))
        witnesses = tuple(row.get("realization_ids", ()))
        if not identity or identity in seen_ids:
            raise ValueError("unique movement candidate identity required")
        seen_ids.add(identity)
        if not stops or not cost.is_finite() or cost <= 0 or not witnesses:
            raise ValueError("invalid physical movement witness")
        source.append((identity, stops, cost))
    if not source or not any(hub_stop_id in row[1] for row in source):
        raise ValueError("at least one hub-serving movement candidate required")

    # Equal stop sets have identical union/connectivity/access/retention effects.
    # Keep their cheapest deterministic physical witness.
    by_stops = {}
    for identity, stops, cost in source:
        proposal = (cost, identity)
        if stops not in by_stops or proposal < by_stops[stops]:
            by_stops[stops] = proposal

    universe = sorted(set().union(*by_stops))
    bits = {stop: 1 << index for index, stop in enumerate(universe)}
    encoded_states = {
        sum(bits[stop] for stop in stops): (cost, (identity,))
        for stops, (cost, identity) in by_stops.items()
    }
    retained_states, movement_pruned = _prune_superset_cost_dominated_states(
        encoded_states)
    retained = [
        (identities[0], mask, cost)
        for mask, (cost, identities) in retained_states.items()
    ]
    retained.sort()

    hub_bit = bits.get(hub_stop_id)
    if hub_bit is None:
        raise ValueError("hub absent from candidate universe")
    limit = min(max_movements, len(retained))
    # State is the union mask. That is sufficient memory for whether a future
    # movement intersects the connected component; cheapest same-mask witness wins.
    layers = [{} for _ in range(limit + 1)]
    expansion_layers = [{} for _ in range(limit + 1)]
    expansion_pruned = {str(size): 0 for size in range(1, limit + 1)}
    for identity, mask, cost in retained:
        if mask & hub_bit:
            proposal = (cost, (identity,))
            if mask not in layers[1] or proposal < layers[1][mask]:
                layers[1][mask] = proposal
    expansion_layers[1] = layers[1]

    by_stop = [[] for _ in universe]
    for movement in retained:
        mask = movement[1]
        pending = mask
        while pending:
            least = pending & -pending
            by_stop[least.bit_length() - 1].append(movement)
            pending ^= least
    for size in range(2, limit + 1):
        target = layers[size]
        for union_mask, (base_cost, base_ids) in expansion_layers[size - 1].items():
            eligible = {}
            pending = union_mask
            while pending:
                least = pending & -pending
                bit_index = least.bit_length() - 1
                for movement in by_stop[bit_index]:
                    eligible[movement[0]] = movement
                pending ^= least
            for identity, movement_mask, movement_cost in eligible.values():
                new_mask = union_mask | movement_mask
                if new_mask == union_mask:
                    continue
                proposal = (base_cost + movement_cost, base_ids + (identity,))
                if new_mask not in target or proposal < target[new_mask]:
                    target[new_mask] = proposal
        if size < limit:
            expansion_layers[size], expansion_pruned[str(size)] = (
                _prune_superset_cost_dominated_states(target))
        else:
            expansion_layers[size] = target

    summaries = {}
    for size in range(1, limit + 1):
        for mask, (cost, identities) in layers[size].items():
            proposal = (cost, size, identities)
            if mask not in summaries or proposal < summaries[mask]:
                summaries[mask] = proposal
    rows = []
    for mask, (cost, size, identities) in summaries.items():
        rows.append({
            "available_stop_ids": [
                stop for stop in universe if mask & bits[stop]],
            "total_distance_m": str(cost),
            "movement_count": size,
            "source_walk_ids": list(identities),
        })
    rows.sort(key=lambda row: tuple(row["available_stop_ids"]))
    any_expansion_pruning = any(expansion_pruned.values())
    return {
        "hub_stop_id": hub_stop_id,
        "source_candidate_count": len(source),
        "unique_movement_stop_set_count": len(by_stops),
        "objective_dominated_movement_count_pruned": movement_pruned,
        "retained_movement_count": len(retained),
        "retained_hub_serving_movement_count": sum(
            bool(mask & hub_bit) for _, mask, _ in retained),
        "maximum_movement_count": max_movements,
        "dynamic_program_states_by_movement_count": {
            str(size): len(layers[size]) for size in range(1, limit + 1)},
        "expansion_states_by_movement_count": {
            str(size): len(expansion_layers[size]) for size in range(1, limit + 1)},
        "objective_dominated_intermediate_state_count_pruned_by_movement_count": (
            expansion_pruned),
        "unique_portfolio_stop_set_count": len(rows),
        "portfolios": rows,
        "enumeration_method": (
            "EXACT_CONNECTED_UNION_DYNAMIC_PROGRAM_WITH_SAFE_INTERMEDIATE_DOMINANCE"),
        "within_supplied_pool_complete": not any_expansion_pruning,
        "within_supplied_pool_pareto_complete_for_monotone_stop_union_objectives": True,
        "intermediate_dominance_semantics": (
            "CHEAPER_OR_EQUAL_STRICT_STOP_SUPERSET_SAFELY_DOMINATES_FOR_FUTURE_SHARED_STOP_CONNECTIONS"),
        "upstream_physical_search_complete": False,
        "closed_walk_domain_only": True,
        "at_least_one_movement_serves_hub_required": True,
        "every_movement_serves_hub_required": False,
        "network_hub_connectivity_semantics": (
            "POTENTIAL_INTERCHANGE_GRAPH_BY_SHARED_STOP_IDENTITY"),
        "shared_stop_identity_is_certified_transfer": False,
        "current_stop_retention_required": False,
        "weighted_score": False,
        "network_selected": False,
    }
