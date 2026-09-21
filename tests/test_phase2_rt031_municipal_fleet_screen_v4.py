from src.phase2_rt031_mixed_frequency_surface_v4 import (
    exact_vehicle_count_for_departures,
    mixed_service_templates,
    phased_departures,
)
from src.phase2_exact_timetable_optimizer_v2 import RouteInput
from scripts.phase2_screen_rt031_municipal_fleet_v4 import build_screen


def test_common_clock_rotation_preserves_exact_fleet_for_all_templates():
    route = RouteInput(
        route_id="test", public_runtime_min=62.0, cycle_runtime_min=62.0,
        public_service_starts_at_hub=True, public_service_returns_to_hub=True,
        vehicle_closure_added=False,
        rail_to_bus_passenger_event_supported=True,
        bus_to_rail_passenger_event_supported=True)
    for template in mixed_service_templates():
        for recovery in (5, 10, 15):
            assert exact_vehicle_count_for_departures(
                route, phased_departures(template, 0), recovery) == (
                exact_vehicle_count_for_departures(
                    route, phased_departures(template, 29), recovery))


def test_screen_fails_closed_on_incomplete_typed_input():
    try:
        build_screen({"contract": "RT031_MUNICIPAL_FRONTIER_TYPED_BINDING_V4",
                      "status": "PASS_FULL_WITHIN_CAP_FRONTIER_TYPED_PENDING_OPERATIONS",
                      "within_cap_profile_count": 735,
                      "within_cap_frontier_binding_complete": True,
                      "network_selected": False, "profiles": []})
    except ValueError as error:
        assert "drift" in str(error)
    else:
        raise AssertionError("incomplete typed binding was accepted")
