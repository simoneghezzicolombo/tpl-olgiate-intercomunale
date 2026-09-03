from __future__ import annotations

from src.phase2_optimizer_core import (
    HardConstraintResult,
    PathLeg,
    ReducedPathMatrix,
    RobustScenarioEvaluation,
    RoutePattern,
    ScenarioSkeleton,
    SensitivityResult,
    ServicePolicy,
    TopologyFamily,
    aggregate_robust_evaluation,
    budget_utility_frontier,
    enumerate_service_policies,
    generate_structural_scenarios,
    select_primary_and_runner_up,
)


def complete_directed_fixture() -> ReducedPathMatrix:
    anchors = ["H", "A", "B", "C", "D"]
    legs = []
    for i, origin in enumerate(anchors):
        for j, destination in enumerate(anchors):
            if origin == destination:
                continue
            legs.append(
                PathLeg(
                    origin,
                    destination,
                    distance_km=1.0 + abs(i - j) * 0.1,
                    runtime_min=3.0 + abs(i - j),
                    uncertainty="RESOLVED",
                )
            )
    return ReducedPathMatrix(legs)


def test_directed_path_matrix_preserves_asymmetry() -> None:
    matrix = ReducedPathMatrix(
        [
            PathLeg("H", "A", 2.0, 5.0),
            PathLeg("A", "H", 3.0, 8.0, "QUANTIFIED"),
        ]
    )
    assert matrix.route_metrics(("H", "A", "H")) == (5.0, 13.0, "QUANTIFIED")


def test_stable_scenario_id_is_order_independent_between_public_routes() -> None:
    left = RoutePattern(("H", "A", "H"))
    right = RoutePattern(("H", "B", "H"))
    one = ScenarioSkeleton(TopologyFamily.TWO_RADIAL_FEEDERS, (left, right))
    two = ScenarioSkeleton(TopologyFamily.TWO_RADIAL_FEEDERS, (right, left))
    assert one.scenario_id == two.scenario_id


def test_structural_generator_is_deterministic_and_multi_family() -> None:
    matrix = complete_directed_fixture()
    first = generate_structural_scenarios(
        hub="H", anchors=["D", "C", "B", "A"], matrix=matrix, max_scenarios=5000
    )
    second = generate_structural_scenarios(
        hub="H", anchors=["A", "B", "C", "D"], matrix=matrix, max_scenarios=5000
    )
    assert [row.scenario_id for row in first] == [row.scenario_id for row in second]
    families = {row.family for row in first}
    assert TopologyFamily.SINGLE_COMPACT_LOOP in families
    assert TopologyFamily.TWO_RADIAL_FEEDERS in families
    assert TopologyFamily.INTERLINED_FIGURE8 in families
    assert TopologyFamily.BIDIRECTIONAL_LOOP_PAIR in families
    assert TopologyFamily.TRUNK_BRANCHES in families
    assert TopologyFamily.SCHEDULED_EXTENSIONS in families
    assert len({row.scenario_id for row in first}) == len(first)


def test_generator_never_uses_missing_directed_leg() -> None:
    matrix = ReducedPathMatrix(
        [
            PathLeg("H", "A", 1.0, 3.0),
            PathLeg("A", "H", 1.0, 3.0),
            PathLeg("H", "B", 1.0, 3.0),
        ]
    )
    scenarios = generate_structural_scenarios(hub="H", anchors=["A", "B"], matrix=matrix)
    assert scenarios
    for scenario in scenarios:
        scenario.validate_paths(matrix)
    assert not any(
        route.anchors == ("H", "B", "H")
        for scenario in scenarios
        for route in scenario.routes
    )


def test_service_policy_grid_contains_only_declared_span_pairs() -> None:
    policies = enumerate_service_policies(
        peak_headways=[15, 30],
        offpeak_headways=[30],
        spans=[(360, 1200), (420, 1320)],
        recovery_minutes=[5.0],
        active_vehicles=[1, 2],
        annual_service_days=[300],
        extension_shares=[0.0, 0.5],
    )
    assert len(policies) == 16
    assert {(p.span_start_min, p.span_end_min) for p in policies} == {(360, 1200), (420, 1320)}
    assert len({p.policy_id for p in policies}) == len(policies)


def test_hard_constraints_are_all_required() -> None:
    passed = HardConstraintResult(True, True, True, True, True, True)
    failed = HardConstraintResult(True, True, True, True, True, False)
    assert passed.eligible
    assert not failed.eligible


def test_robust_aggregation_uses_sensitivity_distribution() -> None:
    constraints = HardConstraintResult(True, True, True, True, True, True)
    rows = [
        SensitivityResult("S1", "low", 3.0, 0.2, 0.08),
        SensitivityResult("S1", "mid", 5.0, 0.4, 0.04),
        SensitivityResult("S1", "high", 7.0, 0.1, 0.12),
    ]
    result = aggregate_robust_evaluation(
        scenario_id="S1",
        hard_constraints=constraints,
        sensitivity_results=rows,
        annual_bus_km=100000,
        public_pattern_complexity=2,
        unverified_elements=1,
        retained_existing_stops_share=0.9,
    )
    assert result.eligible
    assert result.median_gjt_improvement_min == 5.0
    assert 3.0 <= result.lower_quantile_gjt_improvement_min <= 5.0
    assert result.median_missed_connection_probability == 0.08
    assert result.n_sensitivity_runs == 3


def evaluation(
    scenario_id: str,
    median_gjt: float,
    *,
    missed: float,
    complexity: int,
    km: float,
    unverified: int = 0,
    retained: float = 1.0,
    eligible: bool = True,
) -> RobustScenarioEvaluation:
    return RobustScenarioEvaluation(
        scenario_id=scenario_id,
        eligible=eligible,
        median_gjt_improvement_min=median_gjt,
        lower_quantile_gjt_improvement_min=median_gjt - 1.0,
        median_missed_connection_probability=missed,
        annual_bus_km=km,
        public_pattern_complexity=complexity,
        unverified_elements=unverified,
        retained_existing_stops_share=retained,
        n_sensitivity_runs=10,
    )


def test_selection_uses_lexicographic_tie_break_only_inside_uncertainty_band() -> None:
    a = evaluation("A", 6.0, missed=0.10, complexity=2, km=110000)
    b = evaluation("B", 5.9, missed=0.03, complexity=3, km=105000)
    c = evaluation("C", 4.0, missed=0.00, complexity=1, km=80000)
    primary, runner_up, invoked = select_primary_and_runner_up(
        [a, b, c], uncertainty_band_min=0.2
    )
    assert invoked
    assert primary.scenario_id == "B"
    assert runner_up is not None
    assert runner_up.scenario_id == "A"

    primary_strict, _, strict_invoked = select_primary_and_runner_up(
        [a, b, c], uncertainty_band_min=0.05
    )
    assert not strict_invoked
    assert primary_strict.scenario_id == "A"


def test_ineligible_candidate_can_never_win() -> None:
    ineligible = evaluation("X", 100.0, missed=0.0, complexity=1, km=50000, eligible=False)
    valid = evaluation("Y", 2.0, missed=0.2, complexity=4, km=100000)
    primary, runner_up, _ = select_primary_and_runner_up(
        [ineligible, valid], uncertainty_band_min=0.5
    )
    assert primary.scenario_id == "Y"
    assert runner_up is None


def test_budget_frontier_reports_marginal_utility() -> None:
    low = evaluation("LOW", 2.0, missed=0.1, complexity=2, km=80000)
    mid = evaluation("MID", 4.0, missed=0.1, complexity=2, km=100000)
    high = evaluation("HIGH", 4.5, missed=0.1, complexity=2, km=120000)
    rows = budget_utility_frontier([low, mid, high], [70000, 90000, 110000, 130000])
    assert rows[0]["scenario_id"] is None
    assert rows[1]["scenario_id"] == "LOW"
    assert rows[2]["scenario_id"] == "MID"
    assert rows[3]["scenario_id"] == "HIGH"
    assert rows[2]["marginal_utility_per_1000_bus_km"] == 0.1
