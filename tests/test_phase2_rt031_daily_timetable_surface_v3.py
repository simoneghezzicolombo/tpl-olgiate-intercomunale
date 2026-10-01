from src.phase2_rt031_daily_timetable_surface_v3 import (
    aligned_span_starts,
    regular_h15_phase_vectors,
    robust_pareto_frontier,
    routes_for_engineering_case,
)


def test_all_aligned_twelve_hour_windows_are_exhaustive():
    starts = aligned_span_starts()
    assert starts == tuple(range(330, 721, 30))
    assert len(starts) == 14


def test_regular_phase_vectors_cover_every_clock_rotation():
    vectors = regular_h15_phase_vectors()
    assert len(vectors) == 30
    assert len(set(vectors)) == 30
    assert vectors[0] == (0, 15)
    assert vectors[15] == (15, 0)


def test_engineering_case_removes_recovery_from_public_runtime():
    case = {
        "recovery_minutes": "5",
        "components": [
            {"component_id": "A", "cycle_minutes_source_model_sensitivity": "25"},
            {"component_id": "B", "cycle_minutes_source_model_sensitivity": "26"},
        ],
    }
    routes = routes_for_engineering_case(case)
    assert [r.public_runtime_min for r in routes] == [20.0, 21.0]
    assert all(r.public_service_returns_to_hub for r in routes)


def test_robust_pareto_keeps_tradeoffs_and_drops_dominated():
    def row(identity, quality, mean, fleet, miss):
        return {
            "profile_id": identity, "span_start_min": 330,
            "route_1_hub_phase_min": 0, "route_2_hub_phase_min": 15,
            "exact_access_ratios": ["1/2"] * 6,
            "robust_min_transfer_quality": quality,
            "robust_unweighted_mean_transfer_quality": mean,
            "maximum_exact_interlinable_vehicle_count": fleet,
            "worst_bus_to_rail_miss_share_by_runtime_stress_min": {
                key: miss for key in ("0", "5", "10", "15")},
        }
    best = row("A", .5, .6, 3, .1)
    dominated = row("B", .4, .5, 4, .2)
    tradeoff = row("C", .6, .7, 5, .3)
    assert robust_pareto_frontier([best, dominated, tradeoff]) == [best, tradeoff]
