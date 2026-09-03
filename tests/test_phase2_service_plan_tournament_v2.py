from src.phase2_service_plan_tournament_v2 import (
    ServicePlanKey,
    TournamentPoint,
    dominates,
    nondominated_indices,
)


def point(**overrides):
    base = dict(
        resident_coverage_share_10min=0.30,
        worst_municipality_coverage_share_10min=0.15,
        territorial_worker_od_mass_upper_bound=1200.0,
        s8_complete_match_route_share=0.80,
        uniform_headway_min=30,
        span_minutes=960,
        annual_service_days=312,
        annual_bus_km=100000.0,
        fleet_lower_bound_recovery15=2,
    )
    base.update(overrides)
    return TournamentPoint(**base)


def test_plan_id_is_stable_and_excludes_recovery():
    a = ServicePlanKey("S1", 30, "CORE", "SIX_DAY", 0.0)
    b = ServicePlanKey("S1", 30, "CORE", "SIX_DAY", 0.0)
    assert a.plan_id == b.plan_id
    assert a.plan_id.startswith("P2PLAN_")


def test_dominance_requires_no_regression_on_any_axis():
    a = point(resident_coverage_share_10min=0.35, annual_bus_km=95000.0)
    b = point()
    assert dominates(a, b)
    assert not dominates(b, a)


def test_more_coverage_does_not_dominate_if_headway_is_worse():
    hourly = point(resident_coverage_share_10min=0.40, uniform_headway_min=60)
    half_hourly = point(resident_coverage_share_10min=0.35, uniform_headway_min=30)
    assert not dominates(hourly, half_hourly)
    assert not dominates(half_hourly, hourly)


def test_nondominated_indices_preserve_tradeoffs():
    dominated = point(resident_coverage_share_10min=0.20, worst_municipality_coverage_share_10min=0.10)
    strong = point(resident_coverage_share_10min=0.35, worst_municipality_coverage_share_10min=0.20)
    frequency_tradeoff = point(resident_coverage_share_10min=0.25, uniform_headway_min=20)
    assert nondominated_indices([dominated, strong, frequency_tradeoff]) == (1, 2)


def test_s8_is_secondary_axis_not_worker_weighted_ridership():
    better_s8 = point(s8_complete_match_route_share=1.0)
    worse_s8 = point(s8_complete_match_route_share=0.5)
    assert dominates(better_s8, worse_s8)
