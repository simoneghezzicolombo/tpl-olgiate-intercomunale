from src.phase2_exact_timetable_optimizer_v2 import TransferProfile
from src.phase2_rt031_hub_phase_frontier_v3 import (
    circular_max_gap,
    exact_surface,
    next_cyclic_wait,
    pareto_frontier,
)


def test_cyclic_wait_and_gap():
    assert next_cyclic_wait(58, (3, 33)) == 5
    assert circular_max_gap((0, 30)) == 30
    assert circular_max_gap((7, 7)) == 60


def test_pareto_respects_min_gap_and_max_quality():
    rows = [
        {"route_1_hub_phase_min": 0, "route_2_hub_phase_min": 0,
         "combined_hub_max_gap_min": 60, "quality": 0.5},
        {"route_1_hub_phase_min": 0, "route_2_hub_phase_min": 30,
         "combined_hub_max_gap_min": 30, "quality": 0.5},
        {"route_1_hub_phase_min": 1, "route_2_hub_phase_min": 31,
         "combined_hub_max_gap_min": 30, "quality": 0.4},
    ]
    assert pareto_frontier(rows) == [rows[1]]


def test_exact_surface_keeps_all_ordered_route_phases():
    profile = TransferProfile("P", 2.0, 4.0, 1.5, 12.0)
    rail = [
        {"direction": "MILANO", "arrival_min": 5, "departure_min": 6},
        {"direction": "LECCO", "arrival_min": 12, "departure_min": 13},
    ]
    result = exact_surface(rail, (profile,), period=3)
    assert result["evaluated_phase_vector_count"] == 9
    assert len(result["phase_vectors"]) == 9
    assert result["frontier"]
