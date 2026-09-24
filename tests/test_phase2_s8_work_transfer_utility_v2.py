import pytest

from src.phase2_s8_work_transfer_utility_v2 import (
    PassengerConnectionSupport,
    WorkDirectionWeights,
    validate_s8_phase_opportunity_support,
    weight_transfer_quality,
)


def cells():
    return {
        "A|BUS_TO_RAIL|LECCO": 0.8,
        "A|BUS_TO_RAIL|MILANO": 0.6,
        "A|RAIL_TO_BUS|LECCO": 0.4,
        "A|RAIL_TO_BUS|MILANO": 1.0,
        "B|BUS_TO_RAIL|LECCO": 0.5,
        "B|BUS_TO_RAIL|MILANO": 0.5,
        "B|RAIL_TO_BUS|LECCO": 0.5,
        "B|RAIL_TO_BUS|MILANO": 0.5,
    }


def supported_route():
    return PassengerConnectionSupport(
        route_id="R2_closed",
        bus_to_rail_supported=True,
        rail_to_bus_supported=True,
    )


def phase_validation():
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


def route_rows():
    return [
        {
            "route_id": "R2_closed",
            "public_service_starts_at_hub": "true",
            "public_service_returns_to_hub": "true",
            "vehicle_closure_added": "false",
            "rail_to_bus_passenger_event_supported": "true",
            "bus_to_rail_passenger_event_supported": "true",
        },
        {
            "route_id": "R2_open",
            "public_service_starts_at_hub": "true",
            "public_service_returns_to_hub": "false",
            "vehicle_closure_added": "true",
            "rail_to_bus_passenger_event_supported": "true",
            "bus_to_rail_passenger_event_supported": "false",
        },
    ]


def test_s8_phase_contract_builds_fail_closed_support_mask():
    supports = validate_s8_phase_opportunity_support(phase_validation(), route_rows())
    assert supports["R2_closed"].bus_to_rail_supported is True
    assert supports["R2_open"].bus_to_rail_supported is False
    assert supports["R2_open"].rail_to_bus_supported is True


def test_superseded_selected_phase_contract_is_rejected():
    validation = phase_validation()
    validation["status"] = "PASS_S8_PHASING_V2_BUILD"
    validation["contract"] = "PHASE2_S8_CLOCKFACE_PHASE_SEARCH_V2"
    validation["phase_selected"] = True
    with pytest.raises(ValueError, match="not certified PASS|superseded"):
        validate_s8_phase_opportunity_support(validation, route_rows())


def test_route_support_cannot_promote_vehicle_closure_to_passenger_return():
    rows = route_rows()
    rows[1]["bus_to_rail_passenger_event_supported"] = "true"
    with pytest.raises(ValueError, match="BUS_TO_RAIL support"):
        validate_s8_phase_opportunity_support(phase_validation(), rows)


def test_empirical_roundtrip_direction_weighting_is_exact():
    weights = WorkDirectionWeights(
        outbound_bus_to_rail={"LECCO": 1.0, "MILANO": 3.0},
        return_rail_to_bus={"LECCO": 3.0, "MILANO": 1.0},
    )
    out = weight_transfer_quality(cells(), weights, supported_route())
    assert out.profile_quality["A"] == pytest.approx(0.6)
    assert out.profile_quality["B"] == pytest.approx(0.5)
    assert out.worst_profile_quality == pytest.approx(0.5)
    assert out.mean_profile_quality == pytest.approx(0.55)
    assert out.best_profile_quality == pytest.approx(0.6)
    assert out.worker_count == pytest.approx(4.0)
    assert out.weighted_connection_count == pytest.approx(8.0)
    assert out.roundtrip_passenger_supported is True


def test_open_public_route_cannot_use_vehicle_closure_as_bus_to_rail_passenger_service():
    weights = WorkDirectionWeights(
        outbound_bus_to_rail={"LECCO": 1.0, "MILANO": 3.0},
        return_rail_to_bus={"LECCO": 3.0, "MILANO": 1.0},
    )
    support = PassengerConnectionSupport(
        route_id="R2_open",
        bus_to_rail_supported=False,
        rail_to_bus_supported=True,
        evidence_status="DERIVED_FROM_PUBLIC_SERVICE_GEOMETRY",
    )
    with pytest.raises(ValueError, match="vehicle-only return closure"):
        weight_transfer_quality(cells(), weights, support)


def test_inferred_vehicle_closure_evidence_is_forbidden_even_if_boolean_is_true():
    support = PassengerConnectionSupport(
        route_id="R2_bad",
        bus_to_rail_supported=True,
        rail_to_bus_supported=True,
        evidence_status="INFERRED_FROM_VEHICLE_CLOSURE",
    )
    with pytest.raises(ValueError, match="forbidden evidence"):
        support.validate_roundtrip()


def test_direction_weights_require_same_outbound_and_return_total():
    weights = WorkDirectionWeights(
        outbound_bus_to_rail={"LECCO": 1.0, "MILANO": 3.0},
        return_rail_to_bus={"LECCO": 2.0, "MILANO": 1.0},
    )
    with pytest.raises(ValueError, match="totals must match"):
        weights.validate()


def test_profile_cells_fail_closed_when_incomplete():
    weights = WorkDirectionWeights(
        outbound_bus_to_rail={"LECCO": 1.0, "MILANO": 1.0},
        return_rail_to_bus={"LECCO": 1.0, "MILANO": 1.0},
    )
    incomplete = cells()
    del incomplete["B|RAIL_TO_BUS|MILANO"]
    with pytest.raises(ValueError, match="incomplete"):
        weight_transfer_quality(incomplete, weights, supported_route())
