"""Exact pool-scoped portfolios connected to a required hub by shared stop IDs."""
from __future__ import annotations

from decimal import Decimal


def enumerate_network_connected_portfolios(
        candidates, *, hub_stop_id: str, max_movements: int):
    """Return cheapest witness for every reachable connected union of stop IDs.

    Connectivity is deliberately weak: movements form a connected intersection
    graph and at least one contains the hub identity.  It does not certify a
    directional occurrence, ordered service event, or passenger transfer.
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
    encoded = [
        (identity, sum(bits[stop] for stop in stops), cost)
        for stops, (cost, identity) in by_stops.items()
    ]
    encoded.sort()

    # A cheaper superset is safe dominance here: it preserves every possible
    # shared-stop connection and cannot reduce any stop-union access/retention.
    retained = []
    for index, row in enumerate(encoded):
        _, mask, cost = row
        dominated = any(
            other_index != index
            and other_cost <= cost
            and mask | other_mask == other_mask
            and (other_cost < cost or other_mask != mask)
            for other_index, (_, other_mask, other_cost) in enumerate(encoded)
        )
        if not dominated:
            retained.append(row)

    hub_bit = bits.get(hub_stop_id)
    if hub_bit is None:
        raise ValueError("hub absent from candidate universe")
    limit = min(max_movements, len(retained))
    # State is the union mask.  That is sufficient memory for whether a future
    # movement intersects the connected component; cheapest same-mask witness wins.
    layers = [{} for _ in range(limit + 1)]
    for identity, mask, cost in retained:
        if mask & hub_bit:
            proposal = (cost, (identity,))
            if mask not in layers[1] or proposal < layers[1][mask]:
                layers[1][mask] = proposal

    by_stop = [[] for _ in universe]
    for movement in retained:
        mask = movement[1]
        for bit_index in range(len(universe)):
            if mask & (1 << bit_index):
                by_stop[bit_index].append(movement)
    for size in range(2, limit + 1):
        target = layers[size]
        for union_mask, (base_cost, base_ids) in layers[size - 1].items():
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
    return {
        "hub_stop_id": hub_stop_id,
        "source_candidate_count": len(source),
        "unique_movement_stop_set_count": len(by_stops),
        "objective_dominated_movement_count_pruned": len(encoded) - len(retained),
        "retained_movement_count": len(retained),
        "retained_hub_serving_movement_count": sum(
            bool(mask & hub_bit) for _, mask, _ in retained),
        "maximum_movement_count": max_movements,
        "dynamic_program_states_by_movement_count": {
            str(size): len(layers[size]) for size in range(1, limit + 1)},
        "unique_portfolio_stop_set_count": len(rows),
        "portfolios": rows,
        "enumeration_method": "EXACT_CONNECTED_UNION_DYNAMIC_PROGRAM",
        "within_supplied_pool_complete": True,
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
