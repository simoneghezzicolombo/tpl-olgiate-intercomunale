from __future__ import annotations

import pytest

from scripts.phase2_run_exact_timetable_rt001_v3 import (
    VectorEvidence,
    select_best_budget_feasible,
    stable_timetable_id,
)
from src.phase2_exact_timetable_optimizer_v2 import (
    RouteInput,
    TransferProfile,
    best_continuous_quality_target,
    clockface_times,
    exact_vehicle_blocks,
)
from src.phase2_exact_timetable_contract_v2 import route_phase_cell_values_contract


def profile_mid() -> TransferProfile:
    return TransferProfile(
        profile_id="MID",
        transfer_walk_min=2.0,
        preferred_wait_min=4.0,
        miss_transition_scale_min=2.0,
        wait_decay_min=8.0,
    )


def closed_route(public_runtime: float = 10.0, cycle_runtime: float = 10.0) -> RouteInput:
    return RouteInput(
        route_id="R1",
        public_runtime_min=public_runtime,
        cycle_runtime_min=cycle_runtime,
        public_service_starts_at_hub=True,
        public_service_returns_to_hub=True,
        vehicle_closure_added=False,
        rail_to_bus_passenger_event_supported=True,
        bus_to_rail_passenger_event_supported=True,
    )


def open_route(public_runtime: float = 10.0, cycle_runtime: float = 16.0) -> RouteInput:
    return RouteInput(
        route_id="R2",
        public_runtime_min=public_runtime,
        cycle_runtime_min=cycle_runtime,
        public_service_starts_at_hub=True,
        public_service_returns_to_hub=False,
        vehicle_closure_added=True,
        rail_to_bus_passenger_event_supported=True,
        bus_to_rail_passenger_event_supported=False,
    )


def test_best_continuous_target_not_first_next() -> None:
    profile = profile_mid()
    target = best_continuous_quality_target((102.0, 106.0), 100.0, profile)
    assert target is not None
    chosen, quality = target
    assert chosen == 106.0
    first = best_continuous_quality_target((102.0,), 100.0, profile)
    assert first is not None
    assert quality > first[1]


def test_budget_filter_can_reject_best_unconstrained_and_keep_alternative() -> None:
    vectors = [
        VectorEvidence((0,), 0.90, 0.90, 11.0),
        VectorEvidence((1,), 0.80, 0.80, 10.0),
    ]
    best, count = select_best_budget_feasible(vectors, annual_service_days=10, budget_cap=100.0)
    assert count == 1
    assert best is not None
    assert best.phases == (1,)
    assert best.exact_daily_bus_km * 10 == 100.0


def test_budget_filter_returns_none_if_no_exact_phase_is_feasible() -> None:
    vectors = [VectorEvidence((0,), 1.0, 1.0, 10.1)]
    best, count = select_best_budget_feasible(vectors, annual_service_days=10, budget_cap=100.0)
    assert best is None
    assert count == 0


def test_clockface_departure_count_is_integral_and_phase_dependent() -> None:
    counts = {len(clockface_times(p, 60, 330, 1440)) for p in range(60)}
    assert counts == {18, 19}


def test_out_of_span_public_return_is_not_scored_bus_to_rail() -> None:
    route = closed_route(public_runtime=20.0, cycle_runtime=20.0)
    rail = {
        "MILANO": {"arrivals": (110.0,), "departures": (125.0,)},
        "LECCO": {"arrivals": (110.0,), "departures": (125.0,)},
    }
    # Span 100-130, phase 20 at H30 gives one departure at 110 and public return 130.
    # End is exclusive, so a closed route has no valid in-span BUS_TO_RAIL return and
    # the contract fails closed rather than scoring the out-of-span event.
    with pytest.raises(ValueError, match="no in-span public return events"):
        route_phase_cell_values_contract(
            route,
            phase=20,
            headway=30,
            span_start=100,
            span_end=130,
            rail_index=rail,
            profiles=(profile_mid(),),
        )


def test_technical_return_never_creates_bus_to_rail_cells() -> None:
    route = open_route()
    rail = {
        "MILANO": {"arrivals": (105.0,), "departures": (120.0,)},
        "LECCO": {"arrivals": (105.0,), "departures": (120.0,)},
    }
    cells = route_phase_cell_values_contract(
        route,
        phase=0,
        headway=15,
        span_start=90,
        span_end=150,
        rail_index=rail,
        profiles=(profile_mid(),),
    )
    assert len(cells) == 2


def test_vehicle_blocks_are_recovery_sensitive() -> None:
    route = closed_route(public_runtime=10.0, cycle_runtime=10.0)
    fleet5, _ = exact_vehicle_blocks(
        (route,), (0,), headway=15, span_start=0, span_end=60, recovery_min=5
    )
    fleet10, _ = exact_vehicle_blocks(
        (route,), (0,), headway=15, span_start=0, span_end=60, recovery_min=10
    )
    assert fleet5 == 1
    assert fleet10 == 2


def test_stable_timetable_id_is_deterministic_and_phase_sensitive() -> None:
    a = stable_timetable_id("DINPUT", (1, 2))
    b = stable_timetable_id("DINPUT", (1, 2))
    c = stable_timetable_id("DINPUT", (2, 1))
    assert a == b
    assert a != c
