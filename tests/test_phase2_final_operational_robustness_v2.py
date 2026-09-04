from src.phase2_final_operational_robustness_v2 import (
    ExactTrip,
    RailEvent,
    TransferProfile,
    audit_nominal_block_assignment,
    build_bus_departure_index,
    build_rail_departure_index,
    evaluate_bus_to_rail_connection,
    evaluate_rail_to_bus_connection,
    minimum_vehicle_requirement,
    plan_bus_to_rail_connections,
    plan_rail_to_bus_connections,
)

P = (TransferProfile("MID", 2.0, 4.0, 1.5, 12.0),)


def rails():
    return (
        RailEvent("M1", "MILANO", 97.0, 100.0),
        RailEvent("M2", "MILANO", 127.0, 130.0),
        RailEvent("L1", "LECCO", 98.0, 101.0),
        RailEvent("L2", "LECCO", 128.0, 131.0),
    )


def trip(
    ordinal,
    departure,
    public_return,
    vehicle_return,
    *,
    route_id="R",
    blocks=None,
):
    return ExactTrip(
        stage_d_input_id="D1",
        scenario_id="S1",
        route_id=route_id,
        trip_ordinal=ordinal,
        hub_departure_min=float(departure),
        public_hub_return_min=None if public_return is None else float(public_return),
        vehicle_hub_return_min=float(vehicle_return),
        block_by_recovery=blocks or {5: 0, 10: 0, 15: 0},
    )


def test_planned_connection_is_not_rebound_to_later_train_as_success():
    t = trip(0, 60, 97, 97)
    candidate = plan_bus_to_rail_connections((t,), rails(), P)[0]
    assert candidate.direction == "LECCO"
    assert candidate.planned_target_event_id == "L1"
    result = evaluate_bus_to_rail_connection(
        candidate,
        bus_runtime_delay_min=5,
        rail_index=build_rail_departure_index(rails()),
    )
    assert result.planned_connection_retained is False
    assert result.next_alternative_event_id == "L2"


def test_next_alternative_wait_is_reported_separately_after_miss():
    t = trip(0, 60, 97, 97)
    candidates = plan_bus_to_rail_connections((t,), rails(), P)
    candidate = next(c for c in candidates if c.direction == "MILANO")
    result = evaluate_bus_to_rail_connection(
        candidate,
        bus_runtime_delay_min=5,
        rail_index=build_rail_departure_index(rails()),
    )
    assert result.planned_connection_retained is False
    assert result.next_alternative_event_id == "M2"
    assert result.next_alternative_wait_min == 26.0
    assert result.additional_wait_vs_planned_target_min == 30.0


def test_planned_connection_retention_cannot_improve_with_more_runtime_delay():
    t = trip(0, 60, 97, 97)
    candidate = next(
        c for c in plan_bus_to_rail_connections((t,), rails(), P)
        if c.direction == "MILANO"
    )
    index = build_rail_departure_index(rails())
    retained = [
        evaluate_bus_to_rail_connection(
            candidate, bus_runtime_delay_min=delay, rail_index=index
        ).planned_connection_retained
        for delay in (0, 2, 5, 10)
    ]
    assert retained == [True, False, False, False]


def test_technical_return_never_creates_bus_to_rail_connection():
    technical_return = trip(0, 60, None, 97)
    candidates = plan_bus_to_rail_connections((technical_return,), rails(), P)
    assert candidates == []


def test_recovery_15_can_require_more_vehicles_than_recovery_5():
    trips = (
        trip(0, 0, 20, 20, blocks={5: 0, 10: 0, 15: 0}),
        trip(1, 30, 50, 50, blocks={5: 0, 10: 0, 15: 1}),
    )
    assert minimum_vehicle_requirement(trips, recovery_min=5, runtime_stress_min=0) == 1
    assert minimum_vehicle_requirement(trips, recovery_min=15, runtime_stress_min=0) == 2


def test_runtime_stress_exposes_nominal_block_conflict_and_additional_vehicle():
    trips = (
        trip(0, 0, 20, 20, blocks={5: 0, 10: 0, 15: 0}),
        trip(1, 30, 50, 50, blocks={5: 0, 10: 0, 15: 1}),
    )
    result = audit_nominal_block_assignment(trips, recovery_min=5, runtime_stress_min=10)
    assert result["vehicle_conflict_count_on_nominal_blocks"] == 1
    assert result["nominal_block_assignment_infeasible_under_case"] is True
    assert result["minimum_vehicle_requirement"] == 2
    assert result["minimum_additional_vehicle_requirement"] == 1


def test_bus_to_rail_and_rail_to_bus_directionality_are_distinct():
    trips = (
        trip(0, 60, 97, 110),
        trip(1, 120, 127, 140),
        trip(2, 150, 157, 170),
    )
    b2r = next(
        c for c in plan_bus_to_rail_connections(trips, rails(), P)
        if c.direction == "MILANO" and c.source_event_id == "R:0"
    )
    r2b = next(
        c for c in plan_rail_to_bus_connections(
            trips, rails(), P, span_start_min=90, span_end_min=160
        )
        if c.direction == "MILANO" and c.source_event_id == "M1"
    )
    assert b2r.connection_type == "BUS_TO_RAIL"
    assert b2r.source_time_min == 97.0
    assert b2r.planned_target_time_min == 100.0
    assert r2b.connection_type == "RAIL_TO_BUS"
    assert r2b.source_time_min == 97.0
    assert r2b.planned_target_time_min == 120.0


def test_rail_to_bus_planned_target_remains_fixed_under_rail_delay():
    trips = (
        trip(0, 60, 97, 110),
        trip(1, 120, 127, 140),
        trip(2, 150, 157, 170),
    )
    candidate = next(
        c for c in plan_rail_to_bus_connections(
            trips, rails(), P, span_start_min=90, span_end_min=160
        )
        if c.direction == "MILANO" and c.source_event_id == "M1"
    )
    result = evaluate_rail_to_bus_connection(
        candidate,
        rail_arrival_delay_min=25,
        bus_index=build_bus_departure_index(trips),
    )
    assert candidate.planned_target_event_id == "R:1"
    assert result.planned_connection_retained is False
    assert result.next_alternative_event_id == "R:2"


def test_connection_generation_is_deterministic_for_unsorted_input():
    trips = (
        trip(1, 120, 127, 140),
        trip(0, 60, 97, 110),
    )
    a = plan_bus_to_rail_connections(trips, rails(), P)
    b = plan_bus_to_rail_connections(tuple(reversed(trips)), tuple(reversed(rails())), P)
    assert a == b
