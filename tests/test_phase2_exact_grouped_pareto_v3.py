from decimal import Decimal
from fractions import Fraction

import numpy as np

from scripts.phase2_compare_rt031_movement_portfolios_v3 import pareto_indices
from src.phase2_exact_grouped_pareto_v3 import grouped_pareto_indices


def matrix(rows):
    out = np.empty((len(rows), len(rows[0])), dtype=object)
    for i, row in enumerate(rows):
        out[i, :] = tuple(Fraction(value) for value in row)
    return out


def test_grouped_membership_matches_direct_with_identical_vector_cost_ties():
    vectors = matrix([
        (1, 1),
        (1, 1),
        (1, 1),
        (2, 1),
        (1, 2),
        (2, 2),
        (0, 3),
    ])
    costs = [
        Decimal("5"), Decimal("4"), Decimal("4"), Decimal("5"),
        Decimal("5"), Decimal("8"), Decimal("2"),
    ]
    direct = set(pareto_indices(vectors, costs))
    grouped, audit = grouped_pareto_indices(vectors, costs, pareto_indices)

    assert set(grouped) == direct
    assert 0 not in grouped
    assert 1 in grouped and 2 in grouped
    assert audit["unique_exact_benefit_vector_count"] == 5
    assert audit["higher_cost_identical_vector_row_count_pruned"] == 1
    assert audit["minimum_cost_tie_row_count"] == 1


def test_grouped_membership_matches_direct_on_deterministic_grid():
    rows = []
    costs = []
    for a in range(4):
        for b in range(4):
            for repeat in range(3):
                rows.append((Fraction(a, 3), Fraction(b, 3), Fraction(a + b, 6)))
                costs.append(Decimal(a + 2 * b + repeat) / Decimal("10"))
    vectors = np.empty((len(rows), 3), dtype=object)
    for i, row in enumerate(rows):
        vectors[i, :] = row

    direct = set(pareto_indices(vectors, costs))
    grouped, _ = grouped_pareto_indices(vectors, costs, pareto_indices)
    assert set(grouped) == direct


def test_empty_grouped_problem_is_well_defined():
    vectors = np.empty((0, 3), dtype=object)
    grouped, audit = grouped_pareto_indices(vectors, [], pareto_indices)
    assert grouped == []
    assert audit["source_row_count"] == 0
    assert audit["unique_exact_benefit_vector_count"] == 0
