from decimal import Decimal

import pytest

from src.phase2_rt031_target_coverage_search_v3 import (
    minimum_cover_portfolios,
    search_target_closed_walks,
)
from src.phase2_rt031_rt023_pairwise_compatibility_v3 import LEGAL


def domain():
    catalog = {
        "ab": {"source_stop_id": "A", "target_stop_id": "B"},
        "ba": {"source_stop_id": "B", "target_stop_id": "A"},
        "bc": {"source_stop_id": "B", "target_stop_id": "C"},
        "cb": {"source_stop_id": "C", "target_stop_id": "B"},
    }
    pairs = [
        {"left_realization_id": left, "right_realization_id": right, "status": LEGAL}
        for left in catalog for right in catalog
        if catalog[left]["target_stop_id"] == catalog[right]["source_stop_id"]
    ]
    stops = {rid: {row["source_stop_id"], row["target_stop_id"]}
             for rid, row in catalog.items()}
    return catalog, pairs, dict.fromkeys(catalog, 1), stops


def test_target_search_discards_irrelevant_stop_dimensions_and_finds_cycle():
    catalog, pairs, weights, stops = domain()
    stops["ab"].add("IRRELEVANT")
    result = search_target_closed_walks(
        catalog, pairs, weights, stops, ["A", "B"], maximum_distance_m=4,
        max_expansions=1000, history_locality_certified=True,
        atomic_legality_certified=True,
    )
    full = next(row for row in result["candidates"] if set(row["target_stop_ids"]) == {"A", "B"})
    assert result["exhaustive"]
    assert Decimal(full["minimum_found_distance_m"]) == 2
    assert "IRRELEVANT" not in result["target_stop_ids"]


def test_target_search_fails_closed_on_missing_target_and_truncation():
    catalog, pairs, weights, stops = domain()
    with pytest.raises(ValueError, match="absent"):
        search_target_closed_walks(
            catalog, pairs, weights, stops, ["Z"], maximum_distance_m=4,
            max_expansions=10, history_locality_certified=True,
            atomic_legality_certified=True,
        )
    result = search_target_closed_walks(
        catalog, pairs, weights, stops, ["A", "B", "C"], maximum_distance_m=4,
        max_expansions=1, history_locality_certified=True,
        atomic_legality_certified=True,
    )
    assert result["status"] == "RESOURCE_LIMIT_INCOMPLETE"
    assert not result["production_search_pass"]


def candidate(stops, cost, witness):
    return {"target_stop_ids": stops, "minimum_found_distance_m": str(cost),
            "realization_ids": [witness]}


def test_portfolio_dp_finds_one_two_and_three_movement_thresholds():
    rows = [candidate(["A"], 2, "a"), candidate(["B"], 3, "b"),
            candidate(["C"], 4, "c"), candidate(["A", "B"], 6, "ab")]
    result = minimum_cover_portfolios(rows, ["A", "B", "C"], max_movements=3)
    assert [row["full_target_cover_found"] for row in result["results"]] == [False, True, True]
    assert result["results"][1]["minimum_found_total_distance_m"] == "10"
    assert result["results"][2]["minimum_found_total_distance_m"] == "9"
    assert not result["vehicle_continuity_inferred"]
    assert not result["passenger_continuity_inferred"]


def test_portfolio_uses_cheapest_exact_subset_witness():
    rows = [candidate(["A", "B"], 8, "slow"), candidate(["A", "B"], 5, "fast")]
    result = minimum_cover_portfolios(rows, ["A", "B"], max_movements=1)
    assert result["results"][0]["minimum_found_total_distance_m"] == "5"
    assert result["results"][0]["candidate_indices"] == [1]
