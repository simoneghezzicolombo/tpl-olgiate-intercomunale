from decimal import Decimal

import pytest

from src.phase2_rt031_joint_target_shortest_cycle_v3 import shortest_joint_cycle
from src.phase2_rt031_rt023_pairwise_compatibility_v3 import LEGAL


def domain():
    catalog = {
        "hub_out": {"source_stop_id": "H", "target_stop_id": "B"},
        "brivio": {"source_stop_id": "B", "target_stop_id": "H"},
        "santa_out": {"source_stop_id": "H", "target_stop_id": "S"},
        "santa_back": {"source_stop_id": "S", "target_stop_id": "H"},
    }
    pairs = [
        {"left_realization_id": left, "right_realization_id": right,
         "status": LEGAL}
        for left in catalog for right in catalog
        if catalog[left]["target_stop_id"] == catalog[right]["source_stop_id"]
    ]
    stops = {"hub_out": {"H"}, "brivio": {"B"},
             "santa_out": {"S"}, "santa_back": {"H"}}
    weights = {"hub_out": 2, "brivio": 3,
               "santa_out": 5, "santa_back": 7}
    return catalog, pairs, weights, stops


def solve(catalog, pairs, weights, stops):
    return shortest_joint_cycle(
        catalog, pairs, weights, stops, hub_stop_id="H",
        brivio_stop_id="B", santa_maria_stop_ids=("S",),
        history_locality_certified=True, atomic_legality_certified=True)


def test_exact_shortest_joint_cycle_with_repeated_hub_and_no_stop_filter():
    catalog, pairs, weights, stops = domain()
    result = solve(catalog, pairs, weights, stops)
    assert result["search_exhaustive_for_target"]
    assert Decimal(result["minimum_joint_distance_m"]) == 17
    path = result["minimum_joint_realization_ids"]
    assert set().union(*(stops[r] for r in path)) >= {"H", "B", "S"}
    assert sum(weights[r] for r in path) == 17
    assert not result["public_service_certified"]
    assert not result["network_selected"]


def test_no_legal_joint_cycle_is_a_target_exhaustion():
    catalog, pairs, weights, stops = domain()
    pairs = [p for p in pairs if not (
        p["left_realization_id"] == "brivio"
        and p["right_realization_id"] == "santa_out")
        and not (p["left_realization_id"] == "santa_back"
                 and p["right_realization_id"] == "hub_out")]
    # Keep a complete pairwise matrix: the removed turns are explicitly illegal.
    from src.phase2_rt031_rt023_pairwise_compatibility_v3 import ILLEGAL
    pairs += [
        {"left_realization_id": "brivio", "right_realization_id": "santa_out",
         "status": ILLEGAL},
        {"left_realization_id": "santa_back", "right_realization_id": "hub_out",
         "status": ILLEGAL},
    ]
    result = solve(catalog, pairs, weights, stops)
    assert result["minimum_joint_distance_m"] is None
    assert result["search_exhaustive_for_target"]


def test_missing_pair_or_uncertified_history_fails_closed():
    catalog, pairs, weights, stops = domain()
    with pytest.raises(ValueError, match="missing relevant"):
        solve(catalog, pairs[1:], weights, stops)
    with pytest.raises(ValueError, match="certified physical"):
        shortest_joint_cycle(catalog, pairs, weights, stops,
            hub_stop_id="H", brivio_stop_id="B", santa_maria_stop_ids=("S",),
            history_locality_certified=False, atomic_legality_certified=True)


def test_additional_locality_group_is_targeted_feasibility_not_service_filter():
    catalog, pairs, weights, stops = domain()
    stops["hub_out"].add("ARLATE_A")
    result = shortest_joint_cycle(
        catalog, pairs, weights, stops, hub_stop_id="H",
        brivio_stop_id="B", santa_maria_stop_ids=("S",),
        additional_target_groups=(("ARLATE_A", "ARLATE_B"),),
        history_locality_certified=True, atomic_legality_certified=True)
    assert result["minimum_joint_distance_m"] == "17"
    with pytest.raises(ValueError, match="target stop is absent"):
        shortest_joint_cycle(
            catalog, pairs, weights, stops, hub_stop_id="H",
            brivio_stop_id="B", santa_maria_stop_ids=("S",),
            additional_target_groups=(("MISSING",),),
            history_locality_certified=True, atomic_legality_certified=True)
