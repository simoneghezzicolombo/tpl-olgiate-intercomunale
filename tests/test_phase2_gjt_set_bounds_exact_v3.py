from __future__ import annotations

import itertools
import math

from src.phase2_gjt_set_bounds_exact_v3 import (
    HUB_ANCHOR,
    AnchorOccurrence,
    RailDeparture,
    SensitivityCase,
    build_public_to_hub_occurrences,
    bus_generalized_cost,
    direct_walk_generalized_cost,
    first_feasible_rail_departure,
    full_sensitivity_cases,
    reduced_sensitivity_cases,
)
from scripts.phase2_run_gjt_set_bounds_exact_v3 import (
    SpanAwareRouteDepartures,
    build_anchor_components_in_span,
)


GRID = {
    "bus_ivt_weight": [1.0, 1.2, 1.4],
    "walk_weight": [1.5, 1.75, 2.0],
    "wait_weight": [1.5, 2.0, 2.5],
    "transfer_penalty_min": [2.0, 6.0, 10.0],
    "station_transfer_walk_min": [1.5, 2.0, 3.0],
}


def test_next_explicit_public_hub_occurrence_is_used():
    anchors = (HUB_ANCHOR, "A", HUB_ANCHOR, "B", HUB_ANCHOR)
    runtime = {
        (HUB_ANCHOR, "A"): 4.0,
        ("A", HUB_ANCHOR): 6.0,
        (HUB_ANCHOR, "B"): 3.0,
        ("B", HUB_ANCHOR): 7.0,
    }
    occ = build_public_to_hub_occurrences(
        anchors, runtime, bus_to_rail_passenger_event_supported=True
    )
    assert [(x.anchor_id, x.cumulative_from_route_start_min, x.next_public_hub_cumulative_min) for x in occ] == [
        ("A", 4.0, 10.0),
        ("B", 13.0, 20.0),
    ]
    assert [x.bus_ivt_to_hub_min for x in occ] == [6.0, 7.0]


def test_technical_closure_never_creates_passenger_return():
    anchors = (HUB_ANCHOR, "A")
    runtime = {(HUB_ANCHOR, "A"): 5.0}
    assert build_public_to_hub_occurrences(
        anchors, runtime, bus_to_rail_passenger_event_supported=False
    ) == ()


def test_first_feasible_train_is_direction_specific():
    lecco = (
        RailDeparture("L1", "LECCO", 100.0),
        RailDeparture("L2", "LECCO", 120.0),
    )
    milano = (
        RailDeparture("M1", "MILANO", 105.0),
        RailDeparture("M2", "MILANO", 125.0),
    )
    assert first_feasible_rail_departure(
        lecco, bus_hub_arrival_min=99.0, station_transfer_walk_min=2.0
    ).event_id == "L2"
    assert first_feasible_rail_departure(
        milano, bus_hub_arrival_min=99.0, station_transfer_walk_min=2.0
    ).event_id == "M1"


def test_out_of_span_public_hub_arrival_is_not_passenger_source():
    case = SensitivityCase("LOW_SW2", 2.0, 1.0, 1.5, 1.5, 2.0, "LOW")
    occ = AnchorOccurrence("A", 5.0, 15.0)
    rail = {
        "LECCO": (RailDeparture("L", "LECCO", 110.0),),
        "MILANO": (RailDeparture("M", "MILANO", 110.0),),
    }
    out_of_span = SpanAwareRouteDepartures({"R": [90.0]}, span_start=0, span_end=100)
    assert build_anchor_components_in_span(
        timetable_route_departures=out_of_span,
        route_occurrences={"R": (occ,)},
        rail_departures=rail,
        case=case,
        direction="MILANO",
    ) == {}
    in_span = SpanAwareRouteDepartures({"R": [80.0]}, span_start=0, span_end=100)
    got = build_anchor_components_in_span(
        timetable_route_departures=in_span,
        route_occurrences={"R": (occ,)},
        rail_departures=rail,
        case=case,
        direction="MILANO",
    )
    assert got["A"]["bus_hub_arrival_min"] == 95.0
    assert got["A"]["rail_event_id"] == "M"


def test_conditional_cost_contains_no_half_headway_or_origin_wait():
    case = SensitivityCase("LOW_SW2", 2.0, 1.0, 1.5, 1.5, 2.0, "LOW")
    cost, exact_wait = bus_generalized_cost(
        access_walk_min=3.0,
        bus_ivt_min=10.0,
        bus_hub_arrival_min=100.0,
        rail_departure_min=106.0,
        case=case,
    )
    assert exact_wait == 4.0
    assert cost == 1.0 * 10.0 + 1.5 * (3.0 + 2.0) + 1.5 * 4.0 + 2.0


def test_direct_walk_uses_only_certified_rail_anchor_walk():
    low = SensitivityCase("LOW_SW1.5", 1.5, 1.0, 1.5, 1.5, 2.0, "LOW")
    high = SensitivityCase("HIGH_SW3", 3.0, 1.4, 2.0, 2.5, 10.0, "HIGH")
    assert direct_walk_generalized_cost(hub_walk_min=7.0, case=low) == 10.5
    assert direct_walk_generalized_cost(hub_walk_min=7.0, case=high) == 14.0


def _best_fixture_cost(case: SensitivityCase) -> float:
    departures = (
        RailDeparture("T1", "MILANO", 111.0),
        RailDeparture("T2", "MILANO", 116.0),
    )
    candidates = []
    # Two different bus opportunities, deliberately making the preferred target
    # change with station-transfer walk in some cases.
    for access_walk, ivt, hub_arrival in ((2.0, 8.0, 108.5), (5.0, 5.0, 111.5)):
        rail = first_feasible_rail_departure(
            departures,
            bus_hub_arrival_min=hub_arrival,
            station_transfer_walk_min=case.station_transfer_walk_min,
        )
        if rail is None:
            continue
        cost, _ = bus_generalized_cost(
            access_walk_min=access_walk,
            bus_ivt_min=ivt,
            bus_hub_arrival_min=hub_arrival,
            rail_departure_min=rail.departure_min,
            case=case,
        )
        candidates.append(cost)
    return min(candidates)


def test_six_case_reduction_equals_full_243_case_envelope():
    full = full_sensitivity_cases(GRID)
    reduced = reduced_sensitivity_cases(GRID)
    assert len(full) == 243
    assert len(reduced) == 6
    full_values = [_best_fixture_cost(case) for case in full]
    reduced_low = [_best_fixture_cost(case) for case in reduced if case.bound_side == "LOW"]
    reduced_high = [_best_fixture_cost(case) for case in reduced if case.bound_side == "HIGH"]
    assert math.isclose(min(full_values), min(reduced_low), rel_tol=0.0, abs_tol=1e-12)
    assert math.isclose(max(full_values), max(reduced_high), rel_tol=0.0, abs_tol=1e-12)


def test_reduced_grid_enumerates_every_station_walk_without_selection():
    cases = reduced_sensitivity_cases(GRID)
    assert sorted({c.station_transfer_walk_min for c in cases}) == [1.5, 2.0, 3.0]
    for station_walk in (1.5, 2.0, 3.0):
        assert {c.bound_side for c in cases if c.station_transfer_walk_min == station_walk} == {"LOW", "HIGH"}
