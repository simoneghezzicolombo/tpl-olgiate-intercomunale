from scripts.phase2_run_exact_timetable_integration_fix_v2 import (
    VectorEvidence,
    select_best_budget_feasible_vector,
)
from src.phase2_exact_timetable_optimizer_v2 import RouteInput, exact_vehicle_blocks


def vector(phase, daily_km, minimum_quality, mean_quality):
    return VectorEvidence(
        phases=(phase,),
        robust_min_transfer_quality=minimum_quality,
        robust_unweighted_mean_transfer_quality=mean_quality,
        exact_daily_bus_km=daily_km,
    )


def test_some_phases_survives_when_continuous_audit_value_would_exceed_cap():
    # The continuous value is intentionally not passed to the selector.  Only
    # phase-specific exact production is allowed to decide hard-cap eligibility.
    continuous_annual_km = 101.0
    cap = 100.0
    vectors = (
        vector(0, 9.9, 0.4, 0.5),
        vector(1, 10.1, 0.9, 0.9),
    )
    selected, feasible_count = select_best_budget_feasible_vector(vectors, 10, cap)
    assert continuous_annual_km > cap
    assert feasible_count == 1
    assert selected is not None
    assert selected.phases == (0,)
    assert selected.exact_daily_bus_km * 10 <= cap


def test_exact_phase_vector_above_hard_cap_is_excluded_before_s8_optimisation():
    vectors = (
        vector(0, 10.0, 0.2, 0.2),
        vector(1, 10.2, 1.0, 1.0),
    )
    selected, feasible_count = select_best_budget_feasible_vector(vectors, 10, 101.0)
    assert feasible_count == 1
    assert selected is not None
    assert selected.phases == (0,)
    assert selected.exact_daily_bus_km * 10 == 100.0


def test_recovery_sensitivities_remain_separate_and_unselected():
    route = RouteInput("R", 20.0, 20.0, True, True, False, True, True)
    fleet = {
        recovery: exact_vehicle_blocks(
            (route,), (0,), headway=30, span_start=300, span_end=391,
            recovery_min=recovery,
        )[0]
        for recovery in (5, 10, 15)
    }
    assert tuple(fleet) == (5, 10, 15)
    assert all(value > 0 for value in fleet.values())


def test_selected_annual_km_is_derived_from_selected_exact_vector():
    vectors = (
        vector(0, 12.5, 0.5, 0.5),
        vector(1, 13.0, 0.4, 0.4),
    )
    selected, _ = select_best_budget_feasible_vector(vectors, 260, 4000.0)
    assert selected is not None
    assert selected.exact_daily_bus_km * 260 == 3250.0
