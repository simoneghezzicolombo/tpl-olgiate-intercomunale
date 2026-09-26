from src.phase2_rt031_single_line_timetable_surface_v3 import (
    robust_single_line_pareto_frontier,
    route_for_engineering_case,
    single_line_phase_vectors,
    single_line_span_starts,
)


def test_full_h30_phase_and_aligned_ten_hour_span_domains():
    assert single_line_phase_vectors() == tuple((value,) for value in range(30))
    assert single_line_span_starts() == tuple(range(330, 841, 30))
    assert len(single_line_span_starts()) == 18


def test_engineering_case_is_one_closed_public_line():
    route = route_for_engineering_case({
        "recovery_minutes": "10",
        "components": [{
            "component_id": "one-line",
            "cycle_minutes_source_model_sensitivity": "55",
        }],
    })
    assert route.public_runtime_min == 45
    assert route.public_service_returns_to_hub
    assert route.bus_to_rail_passenger_event_supported
    assert route.vehicle_closure_added is False


def test_pareto_keeps_retention_resource_tradeoff_and_drops_dominated():
    def row(identity, retention, quality, annual, fleet, miss):
        return {
            "profile_id": identity,
            "span_start_min": 330,
            "single_line_hub_phase_min": 0,
            "exact_access_ratios": ["1/2"] * 6,
            "retained_current_exact_stop_count": retention,
            "conditional_annual_bus_km": str(annual),
            "robust_min_transfer_quality": quality,
            "robust_unweighted_mean_transfer_quality": quality,
            "maximum_exact_vehicle_count": fleet,
            "worst_deterministic_bus_to_rail_miss_share_by_runtime_stress_min": {
                stress: miss for stress in ("0", "5", "10", "15")},
        }
    best = row("A", 9, .6, 100000, 2, .1)
    dominated = row("B", 8, .5, 101000, 3, .2)
    retained = row("C", 10, .4, 102000, 3, .3)
    assert robust_single_line_pareto_frontier(
        [best, dominated, retained]) == [best, retained]
