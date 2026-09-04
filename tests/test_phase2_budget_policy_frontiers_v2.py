import math

import pytest

from scripts.phase2_build_budget_policy_frontiers_v2 import (
    ANNUAL_KM_AXIS,
    FLEET_AXIS,
    MAX_AXES,
    MIN_AXES,
    finite_float,
    dominates,
    pareto,
)


def row(scenario_id: str) -> dict[str, object]:
    result: dict[str, object] = {"scenario_id": scenario_id}
    for field in MAX_AXES:
        result[field] = 0.0
    for field in MIN_AXES:
        result[field] = 0.0
    return result


def test_operational_resource_axes_are_explicit_minimisation_axes():
    assert ANNUAL_KM_AXIS in MIN_AXES
    assert FLEET_AXIS in MIN_AXES


def test_componentwise_better_candidate_dominates_within_fixed_policy_context():
    strong = row("strong")
    weak = row("weak")
    for field in MAX_AXES:
        strong[field] = 1.0
        weak[field] = 0.5
    for field in MIN_AXES:
        strong[field] = 0.5
        weak[field] = 1.0
    assert dominates(strong, weak)
    assert not dominates(weak, strong)
    assert [r["scenario_id"] for r in pareto([weak, strong])] == ["strong"]


def test_resource_tradeoff_is_preserved_without_weighting():
    coverage = row("coverage")
    efficiency = row("efficiency")
    coverage["public_population_coverage_share_10min"] = 0.90
    coverage[ANNUAL_KM_AXIS] = 100000.0
    coverage[FLEET_AXIS] = 4
    efficiency["public_population_coverage_share_10min"] = 0.85
    efficiency[ANNUAL_KM_AXIS] = 90000.0
    efficiency[FLEET_AXIS] = 3
    assert not dominates(coverage, efficiency)
    assert not dominates(efficiency, coverage)
    assert {r["scenario_id"] for r in pareto([coverage, efficiency])} == {
        "coverage",
        "efficiency",
    }


def test_equal_metric_profiles_do_not_dominate_each_other_and_order_is_deterministic():
    a = row("a")
    b = row("b")
    assert not dominates(a, b)
    assert not dominates(b, a)
    assert [r["scenario_id"] for r in pareto([b, a])] == ["a", "b"]


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_finite_float_rejects_non_finite_values(value):
    with pytest.raises(ValueError, match="Non-finite"):
        finite_float({"metric": value}, "metric")
