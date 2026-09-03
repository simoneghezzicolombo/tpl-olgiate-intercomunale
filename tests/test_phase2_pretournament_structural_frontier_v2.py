from decimal import Decimal

import pytest

from src.phase2_pretournament_structural_frontier_v2 import (
    MetricPoint,
    dominates,
    nondominated_metric_points,
)


def p(a: str, b: str, c: str) -> MetricPoint:
    return MetricPoint(Decimal(a), Decimal(b), Decimal(c))


def test_dominance_requires_one_strict_improvement() -> None:
    strong = p("0.40", "0.30", "100")
    weak = p("0.35", "0.25", "90")
    assert dominates(strong, weak)
    assert not dominates(strong, strong)


def test_three_way_tradeoffs_all_survive() -> None:
    points = {
        p("0.50", "0.20", "100"),
        p("0.40", "0.40", "100"),
        p("0.40", "0.20", "150"),
    }
    assert nondominated_metric_points(points) == frozenset(points)


def test_dominated_point_is_removed() -> None:
    strong = p("0.50", "0.40", "150")
    weak = p("0.40", "0.30", "100")
    assert nondominated_metric_points([strong, weak]) == frozenset({strong})


def test_equal_metric_triplets_are_equivalent_not_mutually_dominating() -> None:
    point = p("0.45", "0.30", "120")
    assert nondominated_metric_points([point, point]) == frozenset({point})


def test_same_population_dimension_still_checks_other_dimensions() -> None:
    strong = p("0.45", "0.35", "120")
    weak = p("0.45", "0.30", "120")
    tradeoff = p("0.45", "0.25", "140")
    assert nondominated_metric_points([strong, weak, tradeoff]) == frozenset({strong, tradeoff})


def test_metric_point_rejects_invalid_shares_and_negative_mass() -> None:
    with pytest.raises(ValueError):
        MetricPoint.from_values("1.1", "0.2", "10")
    with pytest.raises(ValueError):
        MetricPoint.from_values("0.2", "-0.1", "10")
    with pytest.raises(ValueError):
        MetricPoint.from_values("0.2", "0.1", "-1")
