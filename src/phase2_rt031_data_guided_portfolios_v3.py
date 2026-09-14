"""Pool-scoped, no-weight portfolio construction for hub-serving movements."""
from __future__ import annotations

from decimal import Decimal
from itertools import combinations


def enumerate_hub_portfolios(candidates, *, hub_stop_id: str, max_movements: int):
    if not hub_stop_id or type(max_movements) is not int or max_movements < 1:
        raise ValueError("hub identity and positive movement bound required")
    source = []
    seen_ids = set()
    for row in candidates:
        candidate_id = str(row.get("stop_set_id", ""))
        stops = tuple(sorted(set(row.get("available_stop_ids", ()))))
        cost = Decimal(str(row.get("minimum_found_distance_m", "")))
        witness = tuple(row.get("realization_ids", ()))
        if not candidate_id or candidate_id in seen_ids:
            raise ValueError("unique movement candidate identity required")
        seen_ids.add(candidate_id)
        if hub_stop_id not in stops:
            continue
        if not cost.is_finite() or cost <= 0 or not witness:
            raise ValueError("invalid hub-serving physical witness")
        source.append((candidate_id, frozenset(stops), cost))
    if not source:
        raise ValueError("no hub-serving movement candidates")

    # Equivalent availability sets are represented by their cheapest physical
    # witness. Equal-cost identities are retained for audit.
    by_stops = {}
    for candidate_id, stops, cost in source:
        old = by_stops.get(stops)
        if old is None or cost < old["cost"]:
            by_stops[stops] = {"cost": cost, "ids": [candidate_id]}
        elif cost == old["cost"]:
            old["ids"].append(candidate_id)
    movements = [
        (tuple(sorted(value["ids"]))[0], stops, value["cost"])
        for stops, value in sorted(by_stops.items(), key=lambda item: tuple(item[0]))
    ]

    summaries = {}
    considered = {}
    for size in range(1, min(max_movements, len(movements)) + 1):
        considered[size] = 0
        for picked in combinations(movements, size):
            considered[size] += 1
            stops = frozenset().union(*(row[1] for row in picked))
            cost = sum((row[2] for row in picked), Decimal(0))
            ids = tuple(row[0] for row in picked)
            old = summaries.get(stops)
            proposal = (cost, size, ids)
            if old is None or proposal < old:
                summaries[stops] = proposal
    rows = [
        {
            "available_stop_ids": sorted(stops),
            "total_distance_m": str(value[0]),
            "movement_count": value[1],
            "source_walk_ids": list(value[2]),
        }
        for stops, value in sorted(summaries.items(), key=lambda item: tuple(item[0]))
    ]
    return {
        "hub_stop_id": hub_stop_id,
        "source_hub_candidate_count": len(source),
        "unique_hub_movement_stop_set_count": len(movements),
        "maximum_movement_count": max_movements,
        "considered_combinations_by_movement_count": considered,
        "unique_portfolio_stop_set_count": len(rows),
        "portfolios": rows,
        "within_supplied_pool_complete": True,
        "upstream_physical_search_complete": False,
        "closed_walk_domain_only": True,
        "current_stop_retention_required": False,
        "weighted_score": False,
        "network_selected": False,
    }


def service_surface(distance_m, movement_count, *, headways, spans, annual_days):
    distance = Decimal(str(distance_m))
    if distance <= 0 or movement_count < 1 or annual_days < 1:
        raise ValueError("positive service inputs required")
    rows = []
    for headway in sorted(set(headways)):
        for span in sorted(set(spans)):
            if headway <= 0 or span <= 0:
                raise ValueError("positive headway/span required")
            annual_km = distance * Decimal(span) / Decimal(headway) * Decimal(annual_days) / 1000
            rows.append({
                "uniform_headway_min_per_movement": headway,
                "span_minutes": span,
                "annual_service_days": annual_days,
                "annual_bus_km": str(annual_km),
                "movement_count": movement_count,
            })
    return rows
