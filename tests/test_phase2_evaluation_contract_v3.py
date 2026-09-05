from src.phase2_evaluation_contract_v3 import (
    ServiceAreaDiagnostic,
    WalkingObservation,
    normalize_service_area_diagnostics,
    pareto_front,
    population_share_at_or_below,
    summarize_walking_burden,
    territorial_policy_guard,
)


def obs(values):
    return [
        WalkingObservation(point_id=f"P{i}", population_weight=weight, walk_minutes=minutes)
        for i, (weight, minutes) in enumerate(values, start=1)
    ]


def test_same_15_minute_coverage_can_hide_large_walking_difference():
    near = obs([(100, 3), (100, 4), (100, 5), (100, 5)])
    far = obs([(100, 11), (100, 12), (100, 13), (100, 14)])
    assert population_share_at_or_below(near, 15) == 1.0
    assert population_share_at_or_below(far, 15) == 1.0

    near_s = summarize_walking_burden(near)
    far_s = summarize_walking_burden(far)
    assert near_s["weighted_mean_walk_min"] < 5
    assert far_s["weighted_mean_walk_min"] > 12
    assert near_s["weighted_p90_walk_min"] == 5
    assert far_s["weighted_p90_walk_min"] == 14
    assert near_s["share_le_5_min"] == 1.0
    assert far_s["share_le_5_min"] == 0.0


def test_shorter_route_does_not_automatically_beat_better_walking_candidate():
    candidates = [
        {
            "candidate_id": "SHORT",
            "annual_km": 80000,
            "weighted_mean_walk_min": 11.5,
            "continuous_accessibility": 0.62,
        },
        {
            "candidate_id": "ACCESS",
            "annual_km": 87000,
            "weighted_mean_walk_min": 4.2,
            "continuous_accessibility": 0.81,
        },
    ]
    dimensions = {
        "annual_km": "min",
        "weighted_mean_walk_min": "min",
        "continuous_accessibility": "max",
    }
    assert pareto_front(candidates, dimensions) == ("ACCESS", "SHORT")


def test_strictly_dominated_candidate_is_removed():
    candidates = [
        {
            "candidate_id": "A",
            "annual_km": 81000,
            "weighted_mean_walk_min": 5.0,
            "continuous_accessibility": 0.80,
        },
        {
            "candidate_id": "B",
            "annual_km": 85000,
            "weighted_mean_walk_min": 6.0,
            "continuous_accessibility": 0.70,
        },
        {
            "candidate_id": "C",
            "annual_km": 79000,
            "weighted_mean_walk_min": 8.0,
            "continuous_accessibility": 0.68,
        },
    ]
    dimensions = {
        "annual_km": "min",
        "weighted_mean_walk_min": "min",
        "continuous_accessibility": "max",
    }
    assert pareto_front(candidates, dimensions) == ("A", "C")


def test_required_policy_group_guard_is_generic_and_fail_closed():
    result = territorial_policy_guard({"G1", "G2", "G3"}, {"G1", "G3"})
    assert result["passes"] is False
    assert result["missing_policy_groups"] == ("G2",)


def test_service_area_diagnostics_do_not_force_service():
    rows = normalize_service_area_diagnostics(
        [
            ServiceAreaDiagnostic(
                area_id="A2",
                served=False,
                nearest_stop_id="S9",
                nearest_walk_minutes=13.0,
                marginal_extra_km=1.2,
                marginal_extra_runtime_min=3.1,
            ),
            ServiceAreaDiagnostic(
                area_id="A1",
                served=True,
                nearest_stop_id="S1",
                nearest_walk_minutes=2.0,
            ),
        ]
    )
    assert tuple(r.area_id for r in rows) == ("A1", "A2")
    assert rows[1].served is False
    assert rows[1].marginal_extra_km == 1.2


def test_walking_summary_and_frontier_are_input_order_invariant():
    rows = obs([(10, 8), (40, 2), (30, 6), (20, 4)])
    a = summarize_walking_burden(rows)
    b = summarize_walking_burden(list(reversed(rows)))
    assert a == b

    candidates = [
        {"candidate_id": "X", "km": 10, "walk": 4},
        {"candidate_id": "Y", "km": 9, "walk": 6},
        {"candidate_id": "Z", "km": 12, "walk": 8},
    ]
    dims = {"km": "min", "walk": "min"}
    assert pareto_front(candidates, dims) == pareto_front(list(reversed(candidates)), dims)
    assert pareto_front(candidates, dims) == ("X", "Y")


def test_ties_remain_on_frontier():
    candidates = [
        {"candidate_id": "X", "km": 10, "walk": 4},
        {"candidate_id": "Y", "km": 10, "walk": 4},
    ]
    assert pareto_front(candidates, {"km": "min", "walk": "min"}) == ("X", "Y")
