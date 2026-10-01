import pytest

from src.phase2_rt031_single_line_frontier_v3 import (
    combine_single_walk_candidates,
)


def pool(candidates, *, priority=None):
    result = {
        "contract": "RT031_BUDGETED_PHYSICAL_CLOSED_WALK_SEARCH_V3",
        "status": "RESOURCE_LIMIT_INCOMPLETE",
        "exhaustive": False,
        "required_root_stop_id": "H",
        "candidates": candidates,
    }
    if priority:
        result["search_priority_mode"] = priority
    return result


def walk(path, stops, distance=5):
    return {
        "realization_ids": path,
        "available_stop_ids": stops,
        "minimum_found_distance_m": distance,
    }


def test_one_physical_walk_is_one_candidate_line_not_a_portfolio():
    got = combine_single_walk_candidates([
        ("distance", pool([walk(["a", "b"], ["H", "A"])])),
        ("retention", pool([walk(["c", "d"], ["H", "B"])])),
    ], hub_stop_id="H")
    assert got["unique_ordered_single_walk_candidate_count"] == 2
    assert all(row["physical_closed_walk_count"] == 1 for row in got["candidates"])
    assert all(row["intended_public_route_identity_count"] == 1
               for row in got["candidates"])
    assert got["recognizable_public_line_certified"] is False


def test_same_path_across_lanes_is_merged_but_distinct_order_is_preserved():
    got = combine_single_walk_candidates([
        ("a", pool([walk(["x", "y"], ["H", "A"]),
                    walk(["y", "x"], ["A", "H"])])),
        ("b", pool([walk(["x", "y"], ["A", "H"])])),
    ], hub_stop_id="H")
    assert got["unique_ordered_single_walk_candidate_count"] == 2
    shared = next(row for row in got["candidates"]
                  if row["realization_ids"] == ["x", "y"])
    assert shared["discovery_lanes"] == ["a", "b"]
    assert got["same_stop_union_different_order_collapsed"] is False


def test_invalid_or_semantically_drifting_path_fails_closed():
    with pytest.raises(ValueError):
        combine_single_walk_candidates([
            ("a", pool([walk(["x"], ["H"], 5)])),
            ("b", pool([walk(["x"], ["H", "A"], 5)])),
        ], hub_stop_id="H")
