from decimal import Decimal
from itertools import product

import pytest

from src.phase2_rt031_reciprocal_corridor_search_v3 import (
    reciprocal_availability_envelope, search_open_paths,
)
from src.phase2_rt031_rt023_pairwise_compatibility_v3 import LEGAL


def fixture():
    catalog = {
        "ab": {"source_stop_id": "A", "target_stop_id": "B"},
        "ba": {"source_stop_id": "B", "target_stop_id": "A"},
        "bc": {"source_stop_id": "B", "target_stop_id": "C"},
        "cb": {"source_stop_id": "C", "target_stop_id": "B"},
    }
    pairs = [{"left_realization_id": a, "right_realization_id": b, "status": LEGAL}
             for a in catalog for b in catalog
             if catalog[a]["target_stop_id"] == catalog[b]["source_stop_id"]]
    stops = {rid: {row["source_stop_id"], row["target_stop_id"]}
             for rid, row in catalog.items()}
    return catalog, pairs, dict.fromkeys(catalog, 1), stops


def test_open_search_matches_independent_bounded_enumeration():
    catalog, pairs, weights, stops = fixture()
    result = search_open_paths(catalog, pairs, weights, stops, budget_m=3,
        max_expansions=1000, history_locality_certified=True,
        atomic_legality_certified=True)
    arcs = {(x["left_realization_id"], x["right_realization_id"]) for x in pairs}
    expected = {}
    for length in range(1, 4):
        for path in product(catalog, repeat=length):
            if not all(edge in arcs for edge in zip(path, path[1:])):
                continue
            source = catalog[path[0]]["source_stop_id"]
            target = catalog[path[-1]]["target_stop_id"]
            if source == target:
                continue
            key = (source, target, frozenset().union(*(stops[x] for x in path)))
            expected[key] = min(expected.get(key, length), length)
    got = {(x["source_stop_id"], x["target_stop_id"], frozenset(x["available_stop_ids"])):
           int(Decimal(x["minimum_found_distance_m"])) for x in result["paths"]}
    assert result["exhaustive"]
    assert got == expected


def test_open_search_truncation_and_scope_fail_closed():
    catalog, pairs, weights, stops = fixture()
    result = search_open_paths(catalog, pairs, weights, stops, budget_m=3,
        max_expansions=1, history_locality_certified=True,
        atomic_legality_certified=True)
    assert result["status"] == "RESOURCE_LIMIT_INCOMPLETE"
    assert not result["production_search_pass"]
    with pytest.raises(ValueError, match="certified physical scope"):
        search_open_paths(catalog, pairs, weights, stops, budget_m=3,
            max_expansions=10, history_locality_certified=False,
            atomic_legality_certified=True)


def path(pid, source, target, stops, cost):
    return {"open_path_id": pid, "source_stop_id": source, "target_stop_id": target,
            "available_stop_ids": stops, "minimum_found_distance_m": str(cost),
            "realization_ids": [pid]}


def test_reciprocal_pair_requires_opposite_endpoints_and_charges_both_paths():
    rows = [path("ab", "A", "B", ["A", "X", "B"], 2),
            path("ba", "B", "A", ["B", "Y", "A"], 3),
            path("ac", "A", "C", ["A", "C"], 1)]
    result = reciprocal_availability_envelope(rows, shared_budget_m=5)
    assert result["reciprocal_endpoint_pair_count"] == 1
    assert result["feasible_reciprocal_path_pairs"] == 1
    assert result["availability_summaries"][0]["available_stop_ids"] == ["A", "B", "X", "Y"]
    assert result["availability_summaries"][0]["distance_m"] == "5"
    assert not result["terminus_vehicle_continuity_inferred"]
    assert not result["terminus_passenger_continuity_inferred"]
    assert result["stop_identity_availability_only"]
    assert not result["directional_stop_occurrence_guaranteed"]
    assert not result["ordered_service_event_guaranteed"]


def test_reciprocal_budget_and_equal_cost_witnesses_are_exact():
    rows = [path("ab1", "A", "B", ["A", "B"], 2),
            path("ab2", "A", "B", ["A", "B"], 2),
            path("ba", "B", "A", ["A", "B"], 3)]
    result = reciprocal_availability_envelope(rows, shared_budget_m=5)
    summary = result["availability_summaries"][0]
    assert len(summary["minimum_distance_witnesses"]) == 2
    assert reciprocal_availability_envelope(rows, shared_budget_m=4)["feasible_reciprocal_path_pairs"] == 0


def test_missing_reverse_or_invalid_path_never_becomes_corridor():
    assert reciprocal_availability_envelope(
        [path("ab", "A", "B", ["A", "B"], 2)], shared_budget_m=5
    )["availability_summaries"] == []
    with pytest.raises(ValueError):
        reciprocal_availability_envelope(
            [path("loop", "A", "A", ["A"], 1)], shared_budget_m=5)
