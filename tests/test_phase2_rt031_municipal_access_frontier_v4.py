from fractions import Fraction

from src.phase2_rt031_municipal_access_frontier_v4 import (
    exact_pareto_indices,
    objective_dimensions,
)


def test_municipality_tradeoff_survives_without_worst_only_collapse():
    brivio = (Fraction(3, 4), Fraction(1, 4))
    calco = (Fraction(1, 4), Fraction(3, 4))
    dominated = (Fraction(1, 5), Fraction(1, 5))
    assert exact_pareto_indices(
        (brivio, calco, dominated), (10, 10, 11)) == (0, 1)


def test_equal_objective_vectors_all_survive():
    assert exact_pareto_indices(((1, 2), (1, 2)), (10, 10)) == (0, 1)


def test_dimensions_keep_every_municipality_and_threshold_separate():
    dims = objective_dimensions(("97092", "97010", "97074", "97012", "97058"))
    assert len(dims) == 20
    assert {row["field"] for row in dims if "municipality" in row["field"]} == {
        f"potential_municipality_{code}_share_{threshold}min"
        for code in ("97010", "97012", "97058", "97074", "97092")
        for threshold in (5, 8, 10)
    }
    assert dims[-2:] == (
        {"field": "retained_current_exact_stop_share", "direction": "max"},
        {"field": "total_distance_m", "direction": "min"},
    )
