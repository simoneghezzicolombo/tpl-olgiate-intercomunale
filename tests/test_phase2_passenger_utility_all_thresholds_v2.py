from scripts import phase2_build_passenger_utility_frontier_v2_all_thresholds as stage


def test_all_certified_access_thresholds_are_passenger_axes():
    for threshold in (5, 8, 10):
        assert f"public_population_coverage_share_{threshold}min" in stage.PASSENGER_MAX_AXES
        assert f"public_worst_municipality_coverage_share_{threshold}min" in stage.PASSENGER_MAX_AXES


def test_technical_resource_axes_remain_outside_passenger_dominance():
    forbidden = {
        "annual_bus_km",
        "public_route_count",
        "public_explicit_field_check_pending_count",
        "public_operational_unknown_distance_share_lower_bound",
    }
    assert forbidden.isdisjoint(stage.PASSENGER_MAX_AXES)
    assert forbidden.isdisjoint(stage.PASSENGER_MIN_AXES)
