from decimal import Decimal

from src.phase2_exact_timetable_v2 import (
    RouteCycle,
    clockface_departures,
    materialise_route_trips,
    minimum_common_hub_blocks,
    next_gap_with_minimum_margin,
    summarise_margin_gaps,
)


def route(route_id='R', runtime='25', returns=True):
    return RouteCycle(route_id, Decimal(runtime), Decimal(runtime), Decimal('5'), returns)


def test_clockface_departures_preserve_phase_and_span():
    assert clockface_departures(phase_min=5, headway_min=20, span_start_min=360, span_end_min=420) == (
        Decimal(365), Decimal(385), Decimal(405)
    )


def test_open_route_vehicle_cycle_can_exceed_public_runtime():
    r = RouteCycle('R', Decimal('20'), Decimal('30'), Decimal('5'), False)
    trips = materialise_route_trips(r, phase_min=0, headway_min=30, span_start_min=360, span_end_min=420)
    assert trips[0].public_service_end_min == Decimal(380)
    assert trips[0].vehicle_return_hub_min == Decimal(390)


def test_common_hub_blocking_reuses_vehicle_after_recovery():
    trips = materialise_route_trips(route(runtime='20'), phase_min=0, headway_min=30, span_start_min=360, span_end_min=450)
    fleet, blocked = minimum_common_hub_blocks(trips, recovery_min=5)
    assert fleet == 1
    assert {row.vehicle_index for row in blocked} == {0}


def test_common_hub_blocking_requires_two_when_cycles_overlap():
    trips = materialise_route_trips(route(runtime='40'), phase_min=0, headway_min=30, span_start_min=360, span_end_min=450)
    fleet, _ = minimum_common_hub_blocks(trips, recovery_min=5)
    assert fleet == 2


def test_independent_route_phases_can_reduce_peak_fleet():
    a = materialise_route_trips(route('A', '10'), phase_min=0, headway_min=30, span_start_min=360, span_end_min=450)
    b_same = materialise_route_trips(route('B', '10'), phase_min=0, headway_min=30, span_start_min=360, span_end_min=450)
    b_offset = materialise_route_trips(route('B', '10'), phase_min=15, headway_min=30, span_start_min=360, span_end_min=450)
    fleet_same, _ = minimum_common_hub_blocks((*a, *b_same), recovery_min=5)
    fleet_offset, _ = minimum_common_hub_blocks((*a, *b_offset), recovery_min=5)
    assert fleet_same == 2
    assert fleet_offset == 1


def test_minimum_margin_skips_too_close_target():
    targets = (Decimal(10), Decimal(20), Decimal(30))
    assert next_gap_with_minimum_margin(Decimal(9), targets, 0) == Decimal(1)
    assert next_gap_with_minimum_margin(Decimal(9), targets, 2) == Decimal(11)


def test_margin_gap_summary_counts_unmatched():
    summary = summarise_margin_gaps((Decimal(9), Decimal(29)), (Decimal(10), Decimal(20), Decimal(30)), margin_min=2)
    assert summary.source_count == 2
    assert summary.matched_count == 1
    assert summary.unmatched_count == 1
    assert summary.mean_gap_min == 11.0
