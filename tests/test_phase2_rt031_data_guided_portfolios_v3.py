from src.phase2_rt031_data_guided_portfolios_v3 import (
    enumerate_hub_portfolios,
    service_surface,
)


def movement(identity, stops, cost):
    return {
        "stop_set_id": identity,
        "available_stop_ids": stops,
        "minimum_found_distance_m": cost,
        "realization_ids": [identity + "_witness"],
    }


def test_no_current_stop_template_and_all_movements_serve_hub():
    rows = [
        movement("a", ["H", "A"], 3),
        movement("b", ["H", "B"], 4),
        movement("off", ["Z"], 1),
    ]
    result = enumerate_hub_portfolios(rows, hub_stop_id="H", max_movements=2)
    assert result["source_hub_candidate_count"] == 2
    assert result["unique_portfolio_stop_set_count"] == 3
    pair = next(row for row in result["portfolios"] if row["movement_count"] == 2)
    assert pair["available_stop_ids"] == ["A", "B", "H"]
    assert pair["total_distance_m"] == "7"
    assert result["current_stop_retention_required"] is False


def test_cheapest_equivalent_movement_is_used():
    rows = [
        movement("slow", ["H", "A"], 5),
        movement("fast", ["A", "H"], 3),
    ]
    result = enumerate_hub_portfolios(rows, hub_stop_id="H", max_movements=1)
    assert result["portfolios"][0]["source_walk_ids"] == ["fast"]
    assert result["portfolios"][0]["total_distance_m"] == "3"


def test_service_surface_reports_without_filtering():
    rows = service_surface("10000", 2, headways=(30, 60), spans=(600, 960), annual_days=260)
    assert len(rows) == 4
    assert {row["uniform_headway_min_per_movement"] for row in rows} == {30, 60}
    assert next(row for row in rows if row["uniform_headway_min_per_movement"] == 30
                and row["span_minutes"] == 600)["annual_bus_km"] == "52000"


def test_dynamic_envelope_matches_direct_envelope():
    rows = [
        movement(str(index), ["H", f"S{index:03d}"], index + 1)
        for index in range(201)
    ]
    dynamic = enumerate_hub_portfolios(rows, hub_stop_id="H", max_movements=2)
    assert dynamic["enumeration_method"] == "EXACT_ZERO_ONE_UNION_DYNAMIC_PROGRAM"
    assert dynamic["objective_dominated_movement_count_pruned"] == 0
    assert dynamic["unique_portfolio_stop_set_count"] == 201 + 201 * 200 // 2
