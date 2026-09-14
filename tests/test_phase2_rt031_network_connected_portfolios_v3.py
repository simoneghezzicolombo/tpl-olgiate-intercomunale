from src.phase2_rt031_network_connected_portfolios_v3 import (
    enumerate_network_connected_portfolios,
)


def movement(identity, stops, cost):
    return {
        "candidate_id": identity,
        "available_stop_ids": stops,
        "minimum_found_distance_m": cost,
        "realization_ids": [identity + "_witness"],
    }


def test_network_can_reach_hub_through_shared_stop_identity():
    result = enumerate_network_connected_portfolios([
        movement("hub", ["H", "A"], 3),
        movement("link", ["A", "B"], 4),
        movement("isolated", ["Z"], 1),
    ], hub_stop_id="H", max_movements=2)
    pair = next(row for row in result["portfolios"]
                if row["available_stop_ids"] == ["A", "B", "H"])
    assert pair["source_walk_ids"] == ["hub", "link"]
    assert pair["total_distance_m"] == "7"
    assert result["every_movement_serves_hub_required"] is False
    assert result["shared_stop_identity_is_certified_transfer"] is False
    assert not any("Z" in row["available_stop_ids"] for row in result["portfolios"])


def test_disconnected_pair_is_not_admitted():
    result = enumerate_network_connected_portfolios([
        movement("hub", ["H", "A"], 3),
        movement("off", ["B", "C"], 2),
    ], hub_stop_id="H", max_movements=2)
    assert result["unique_portfolio_stop_set_count"] == 1


def test_cheaper_superset_safely_dominates_for_union_and_connectivity():
    result = enumerate_network_connected_portfolios([
        movement("small", ["H", "A"], 5),
        movement("large", ["H", "A", "B"], 4),
        movement("tail", ["B", "C"], 2),
    ], hub_stop_id="H", max_movements=2)
    assert result["objective_dominated_movement_count_pruned"] == 1
    assert any(row["available_stop_ids"] == ["A", "B", "C", "H"]
               for row in result["portfolios"])


def test_same_union_keeps_cheapest_connected_witness():
    result = enumerate_network_connected_portfolios([
        movement("hub-a", ["H", "A"], 5),
        movement("hub-b", ["H", "B"], 3),
        movement("ab", ["A", "B"], 1),
    ], hub_stop_id="H", max_movements=2)
    union = next(row for row in result["portfolios"]
                 if row["available_stop_ids"] == ["A", "B", "H"])
    assert union["total_distance_m"] == "4"
    assert union["source_walk_ids"] == ["hub-b", "ab"]
