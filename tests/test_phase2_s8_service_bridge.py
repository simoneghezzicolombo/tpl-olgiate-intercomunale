"""Tests for the central service-plan -> validated S8 scorer bridge.

All timetable values in this test are TEST_FIXTURE_ONLY. They verify contracts and
must never be interpreted as Meratese service evidence.
"""
import pytest

from src.phase2_s8_interchange import DelayCase, TransferQualityProfile
from src.phase2_s8_service_bridge import (
    HubEventOffset,
    materialise_bus_hub_events,
    score_service_plan_s8,
)
from src.phase2_service_engine import OperatingCycle, OperatingPlan, ServiceWindow


def _plan(*, multi_day=False):
    cycle = OperatingCycle("B1", ("R1",), 10.0, 50.0, 10.0, "DERIVED")
    windows = [ServiceWindow("WK_AM", "B1", "WEEKDAY", 360, 420, 30, 250, 5)]
    if multi_day:
        windows.append(ServiceWindow("SAT_AM", "B1", "SATURDAY", 360, 420, 60, 52, 0))
    return OperatingPlan("SCENARIO", "PLAN", (cycle,), tuple(windows))


def _rail_events():
    # Minimal topology-neutral S8-like fixture. Both directions are required by
    # score_bus_hub_timetable(); values are not project evidence.
    return [
        {
            "trip_id": "M1",
            "direction": "MILANO",
            "arrival_min": 370.0,
            "departure_min": 371.0,
        },
        {
            "trip_id": "M2",
            "direction": "MILANO",
            "arrival_min": 400.0,
            "departure_min": 401.0,
        },
        {
            "trip_id": "M3",
            "direction": "MILANO",
            "arrival_min": 430.0,
            "departure_min": 431.0,
        },
        {
            "trip_id": "L1",
            "direction": "LECCO",
            "arrival_min": 377.0,
            "departure_min": 378.0,
        },
        {
            "trip_id": "L2",
            "direction": "LECCO",
            "arrival_min": 407.0,
            "departure_min": 408.0,
        },
        {
            "trip_id": "L3",
            "direction": "LECCO",
            "arrival_min": 437.0,
            "departure_min": 438.0,
        },
    ]


def _profile():
    return TransferQualityProfile(
        transfer_walk_min=2.0,
        preferred_wait_min=6.0,
        miss_transition_scale_min=2.0,
        wait_decay_min=10.0,
    )


def _delays():
    return (
        DelayCase(0.0, 0.0, 0.5, "on_time"),
        DelayCase(3.0, 0.0, 0.25, "bus_late"),
        DelayCase(0.0, 3.0, 0.25, "rail_late"),
    )


def test_materialise_hub_events_uses_explicit_offsets_and_window_phase():
    events = materialise_bus_hub_events(
        _plan(),
        (
            HubEventOffset("B1", "BUS_DEPARTURE", 0.0, "leave_hub"),
            HubEventOffset("B1", "BUS_ARRIVAL", 50.0, "return_hub"),
        ),
    )
    assert [row["event_time"] for row in events] == [365.0, 395.0, 415.0, 445.0]
    assert [row["event_type"] for row in events] == [
        "BUS_DEPARTURE",
        "BUS_DEPARTURE",
        "BUS_ARRIVAL",
        "BUS_ARRIVAL",
    ]
    assert all(row["scenario_id"] == "SCENARIO" for row in events)


def test_bridge_does_not_assume_every_block_has_a_hub_event():
    plan = _plan()
    with pytest.raises(ValueError, match="At least one explicit HubEventOffset"):
        materialise_bus_hub_events(plan, ())
    with pytest.raises(ValueError, match="unknown blocks"):
        materialise_bus_hub_events(plan, (HubEventOffset("NOT_A_BLOCK", "BUS_ARRIVAL", 0),))


def test_s8_scoring_is_topology_neutral_and_returns_robust_summaries():
    offsets = (
        HubEventOffset("B1", "BUS_DEPARTURE", 0.0),
        HubEventOffset("B1", "BUS_ARRIVAL", 50.0),
    )
    detail, summaries = score_service_plan_s8(
        plan=_plan(),
        hub_offsets=offsets,
        rail_events=_rail_events(),
        profile=_profile(),
        delay_cases=_delays(),
    )

    # Four bus events x two S8 directions.
    assert len(detail) == 8
    assert len(summaries) == 4
    assert {row.connection_type for row in summaries} == {"BUS_TO_RAIL", "RAIL_TO_BUS"}
    assert {row.rail_direction for row in summaries} == {"MILANO", "LECCO"}
    assert all(0.0 <= row.robust_hard_miss_probability_mean <= 1.0 for row in summaries)
    assert all("NOT_RIDERSHIP_OR_MODAL_SHARE" in row.semantics for row in summaries)
    assert all(item["scenario_id"] == "SCENARIO" for item in detail)
    assert all("topology" not in item for item in detail)


def test_same_plan_and_assumptions_produce_identical_s8_result():
    kwargs = dict(
        plan=_plan(),
        hub_offsets=(
            HubEventOffset("B1", "BUS_DEPARTURE", 0.0),
            HubEventOffset("B1", "BUS_ARRIVAL", 50.0),
        ),
        rail_events=_rail_events(),
        profile=_profile(),
        delay_cases=_delays(),
    )
    first = score_service_plan_s8(**kwargs)
    second = score_service_plan_s8(**kwargs)
    assert first == second


def test_multi_day_bus_plan_requires_explicit_day_type_for_single_day_rail_evidence():
    offsets = (HubEventOffset("B1", "BUS_DEPARTURE", 0.0),)
    with pytest.raises(ValueError, match="day_type is required"):
        score_service_plan_s8(
            plan=_plan(multi_day=True),
            hub_offsets=offsets,
            rail_events=_rail_events(),
            profile=_profile(),
            delay_cases=_delays(),
        )

    detail, _ = score_service_plan_s8(
        plan=_plan(multi_day=True),
        hub_offsets=offsets,
        rail_events=_rail_events(),
        profile=_profile(),
        delay_cases=_delays(),
        day_type="WEEKDAY",
    )
    # Two weekday bus departures x two rail directions.
    assert len(detail) == 4
