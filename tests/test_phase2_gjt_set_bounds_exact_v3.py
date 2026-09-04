from __future__ import annotations

import math

from src.phase2_gjt_set_bounds_exact_v3 import (
    HUB_ANCHOR,
    AnchorOccurrence,
    BusOpportunity,
    RailDeparture,
    SensitivityCase,
    brute_force_fixed_event_anchor_components,
    build_public_to_hub_occurrences,
    build_timetable_bus_opportunities,
    bus_generalized_cost,
    direct_walk_generalized_cost,
    fixed_event_anchor_components,
    full_sensitivity_cases,
    reduced_sensitivity_cases,
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
    occ = build_public_to_hub_occurrences(anchors, runtime, bus_to_rail_passenger_event_supported=True)
    assert [(x.anchor_id, x.cumulative_from_route_start_min, x.next_public_hub_cumulative_min) for x in occ] == [
        ("A", 4.0, 10.0), ("B", 13.0, 20.0)
    ]


def test_technical_closure_never_creates_passenger_return():
    anchors = (HUB_ANCHOR, "A")
    runtime = {(HUB_ANCHOR, "A"): 5.0}
    assert build_public_to_hub_occurrences(anchors, runtime, bus_to_rail_passenger_event_supported=False) == ()


def test_span_end_is_exclusive_for_passenger_hub_return():
    occ = AnchorOccurrence("A", 5.0, 15.0)
    got = build_timetable_bus_opportunities(
        {"R": [80.0, 85.0]}, {"R": (occ,)}, span_start_min=0.0, span_end_min=100.0
    )
    assert [x.bus_hub_arrival_min for x in got["A"]] == [95.0]


def test_fixed_event_never_rebinds_to_later_train():
    case = SensitivityCase("LOW_SW3", 3.0, 1.0, 1.5, 1.5, 2.0, "LOW")
    opportunity = BusOpportunity("A", "R", 80.0, 99.0, 8.0)
    fixed = RailDeparture("M1", "MILANO", 101.0)
    later = RailDeparture("M2", "MILANO", 120.0)
    assert bus_generalized_cost(access_walk_min=2.0, opportunity=opportunity, rail_event=fixed, case=case) is None
    assert bus_generalized_cost(access_walk_min=2.0, opportunity=opportunity, rail_event=later, case=case) is not None


def test_conditional_cost_contains_no_half_headway_or_origin_wait():
    case = SensitivityCase("LOW_SW2", 2.0, 1.0, 1.5, 1.5, 2.0, "LOW")
    opportunity = BusOpportunity("A", "R", 80.0, 100.0, 10.0)
    event = RailDeparture("M", "MILANO", 106.0)
    cost, exact_wait = bus_generalized_cost(access_walk_min=3.0, opportunity=opportunity, rail_event=event, case=case)
    assert exact_wait == 4.0
    assert cost == 1.0 * 10.0 + 1.5 * (3.0 + 2.0) + 1.5 * 4.0 + 2.0


def test_direct_walk_uses_only_certified_rail_anchor_walk():
    low = SensitivityCase("LOW_SW1.5", 1.5, 1.0, 1.5, 1.5, 2.0, "LOW")
    high = SensitivityCase("HIGH_SW3", 3.0, 1.4, 2.0, 2.5, 10.0, "HIGH")
    assert direct_walk_generalized_cost(hub_walk_min=7.0, case=low) == 10.5
    assert direct_walk_generalized_cost(hub_walk_min=7.0, case=high) == 14.0


def test_optimized_fixed_event_components_equal_all_opportunity_oracle():
    opportunities = {
        "A": (
            BusOpportunity("A", "R1", 70.0, 96.0, 12.0),
            BusOpportunity("A", "R2", 75.0, 101.0, 7.0),
            BusOpportunity("A", "R3", 81.0, 109.0, 4.0),
        ),
        "B": (
            BusOpportunity("B", "R4", 60.0, 93.0, 9.0),
            BusOpportunity("B", "R5", 86.0, 112.0, 6.0),
        ),
    }
    events = (
        RailDeparture("M1", "MILANO", 100.0),
        RailDeparture("M2", "MILANO", 110.0),
        RailDeparture("M3", "MILANO", 120.0),
    )
    for case in reduced_sensitivity_cases(GRID):
        assert fixed_event_anchor_components(opportunities, events, case) == brute_force_fixed_event_anchor_components(opportunities, events, case)


def _best_fixed_event_unit_cost(case: SensitivityCase):
    event = RailDeparture("M", "MILANO", 120.0)
    options = [
        (BusOpportunity("A", "R1", 80.0, 108.5, 8.0), 2.0, "R1"),
        (BusOpportunity("B", "R2", 84.0, 111.5, 5.0), 5.0, "R2"),
        (BusOpportunity("C", "R3", 90.0, 117.5, 3.0), 1.0, "R3"),
    ]
    scored = [(direct_walk_generalized_cost(hub_walk_min=9.0, case=case), "DIRECT")]
    for opportunity, walk, label in options:
        value = bus_generalized_cost(access_walk_min=walk, opportunity=opportunity, rail_event=event, case=case)
        if value is not None:
            scored.append((value[0], label))
    return min(scored)


def test_six_case_reduction_equals_full_243_fixed_event_envelope_with_route_switching():
    full = full_sensitivity_cases(GRID)
    reduced = reduced_sensitivity_cases(GRID)
    assert len(full) == 243
    assert len(reduced) == 6
    full_scored = [_best_fixed_event_unit_cost(case) for case in full]
    reduced_low = [_best_fixed_event_unit_cost(case) for case in reduced if case.bound_side == "LOW"]
    reduced_high = [_best_fixed_event_unit_cost(case) for case in reduced if case.bound_side == "HIGH"]
    assert math.isclose(min(v for v, _ in full_scored), min(v for v, _ in reduced_low), rel_tol=0.0, abs_tol=1e-12)
    assert math.isclose(max(v for v, _ in full_scored), max(v for v, _ in reduced_high), rel_tol=0.0, abs_tol=1e-12)
    assert len({label for _, label in full_scored}) >= 2


def test_station_walk_is_enumerated_because_it_changes_feasibility():
    event = RailDeparture("M", "MILANO", 120.0)
    opportunity = BusOpportunity("A", "R", 90.0, 117.5, 5.0)
    low_walk = SensitivityCase("L", 1.5, 1.0, 1.5, 1.5, 2.0, "LOW")
    high_walk = SensitivityCase("H", 3.0, 1.0, 1.5, 1.5, 2.0, "LOW")
    assert bus_generalized_cost(access_walk_min=1.0, opportunity=opportunity, rail_event=event, case=low_walk) is not None
    assert bus_generalized_cost(access_walk_min=1.0, opportunity=opportunity, rail_event=event, case=high_walk) is None


def test_reduced_grid_enumerates_every_station_walk_without_selection():
    cases = reduced_sensitivity_cases(GRID)
    assert sorted({c.station_transfer_walk_min for c in cases}) == [1.5, 2.0, 3.0]
    for station_walk in (1.5, 2.0, 3.0):
        assert {c.bound_side for c in cases if c.station_transfer_walk_min == station_walk} == {"LOW", "HIGH"}
