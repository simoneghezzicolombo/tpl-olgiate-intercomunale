from src.phase2_s8_passenger_support_mask_v2 import (
    build_route_support_rows,
    build_scenario_support_rows,
    summarise_support,
)


def _validation():
    return {
        "status": "PASS_S8_PHASE_OPPORTUNITY_V2_BUILD",
        "contract": "PHASE2_S8_PHASE_OPPORTUNITY_SURFACE_V2",
        "phase_selected": False,
        "phase_pruned": False,
        "passenger_demand_weights_applied": False,
        "passenger_utility_calculated": False,
        "topology_ranked": False,
        "service_policy_selected": False,
        "all_integer_phases_evaluated": True,
        "all_phases_retained_downstream": True,
        "vehicle_cycle_return_is_passenger_event_for_open_routes": False,
        "passenger_bus_to_rail_event_requires_public_return_to_hub": True,
        "unique_route_count": 2,
        "vehicle_closure_route_count": 1,
        "public_service_return_hub_route_count": 1,
        "rail_to_bus_passenger_supported_route_count": 2,
        "bus_to_rail_passenger_supported_route_count": 1,
    }


def _routes():
    return [
        {
            "route_id": "R_closed",
            "runtime_archetype_id": "RT_closed",
            "roles": "PUBLIC",
            "public_runtime_min": "30",
            "cycle_runtime_min": "30",
            "public_service_starts_at_hub": "true",
            "public_service_returns_to_hub": "true",
            "vehicle_closure_added": "false",
            "rail_to_bus_passenger_event_supported": "true",
            "bus_to_rail_passenger_event_supported": "true",
        },
        {
            "route_id": "R_open",
            "runtime_archetype_id": "RT_open",
            "roles": "PUBLIC",
            "public_runtime_min": "20",
            "cycle_runtime_min": "31",
            "public_service_starts_at_hub": "true",
            "public_service_returns_to_hub": "false",
            "vehicle_closure_added": "true",
            "rail_to_bus_passenger_event_supported": "true",
            "bus_to_rail_passenger_event_supported": "false",
        },
    ]


def test_support_mask_preserves_open_route_as_directional_only():
    rows, supports = build_route_support_rows(_validation(), _routes())
    by_id = {row["route_id"]: row for row in rows}
    assert by_id["R_closed"]["roundtrip_passenger_supported"] is True
    assert by_id["R_closed"]["passenger_support_class"] == "ROUNDTRIP_HUB_PASSENGER_SUPPORTED"
    assert by_id["R_open"]["roundtrip_passenger_supported"] is False
    assert by_id["R_open"]["rail_to_bus_passenger_supported"] is True
    assert by_id["R_open"]["bus_to_rail_passenger_supported"] is False
    assert by_id["R_open"]["passenger_support_class"] == "RAIL_TO_BUS_ONLY_PUBLIC_ROUTE_OPEN_AWAY_FROM_HUB"
    assert all(row["passenger_demand_assigned_to_route"] is False for row in rows)
    assert all(row["passenger_utility_calculated"] is False for row in rows)
    assert supports["R_open"].bus_to_rail_supported is False


def test_scenario_support_counts_routes_without_allocating_demand():
    route_rows, supports = build_route_support_rows(_validation(), _routes())
    scenarios = build_scenario_support_rows(
        [
            {
                "scenario_id": "S1",
                "topology_family": "test",
                "public_route_ids_json": '["R_closed","R_open"]',
                "extension_route_ids_json": "[]",
            }
        ],
        supports,
    )
    assert scenarios == [
        {
            "scenario_id": "S1",
            "topology_family": "test",
            "public_route_count": 2,
            "public_roundtrip_supported_route_count": 1,
            "public_rail_to_bus_only_route_count": 1,
            "extension_route_count": 0,
            "extension_roundtrip_supported_route_count": 0,
            "extension_rail_to_bus_only_route_count": 0,
            "passenger_demand_assigned_to_routes": False,
            "scenario_passenger_utility_calculated": False,
            "topology_ranked": False,
        }
    ]
    summary = summarise_support(route_rows, scenarios)
    assert summary["route_count"] == 2
    assert summary["roundtrip_passenger_supported_route_count"] == 1
    assert summary["rail_to_bus_only_route_count"] == 1
    assert summary["scenario_count"] == 1


def test_unknown_scenario_route_fails_closed():
    _, supports = build_route_support_rows(_validation(), _routes())
    try:
        build_scenario_support_rows(
            [{
                "scenario_id": "S_bad",
                "topology_family": "test",
                "public_route_ids_json": '["R_missing"]',
                "extension_route_ids_json": "[]",
            }],
            supports,
        )
    except ValueError as exc:
        assert "unknown route IDs" in str(exc)
    else:
        raise AssertionError("Expected unknown route ID to fail closed")
