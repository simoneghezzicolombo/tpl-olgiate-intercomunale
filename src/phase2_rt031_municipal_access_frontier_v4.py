"""Exact no-weight municipal-access frontier helpers for RT031 V4."""
from __future__ import annotations

from decimal import Decimal
from fractions import Fraction


def exact_pareto_indices(benefits, costs):
    """Return nondominated indices; equal objective vectors all survive."""
    vectors = [tuple(Fraction(value) for value in row) for row in benefits]
    exact_costs = [Decimal(str(value)) for value in costs]
    if not vectors or len(vectors) != len(exact_costs):
        raise ValueError("non-empty aligned benefits and costs required")
    width = len(vectors[0])
    if width == 0 or any(len(row) != width for row in vectors):
        raise ValueError("benefit vectors require one consistent non-empty width")

    def dominates(left, right):
        weak = (exact_costs[left] <= exact_costs[right]
                and all(a >= b for a, b in zip(vectors[left], vectors[right])))
        strict = (exact_costs[left] < exact_costs[right]
                  or vectors[left] != vectors[right])
        return weak and strict

    frontier = []
    for candidate in sorted(range(len(vectors)),
                            key=lambda index: (exact_costs[index], index)):
        if any(dominates(other, candidate) for other in frontier):
            continue
        frontier = [other for other in frontier
                    if not dominates(candidate, other)]
        frontier.append(candidate)
    return tuple(sorted(frontier))


def objective_dimensions(municipality_codes):
    codes = tuple(sorted(str(value) for value in municipality_codes))
    if len(codes) != 5 or len(set(codes)) != len(codes):
        raise ValueError("exactly five distinct core municipality codes required")
    dimensions = [
        {"field": f"potential_core_share_{threshold}min", "direction": "max"}
        for threshold in (5, 8, 10)
    ]
    dimensions.extend(
        {"field": f"potential_municipality_{code}_share_{threshold}min",
         "direction": "max"}
        for code in codes for threshold in (5, 8, 10)
    )
    dimensions.extend((
        {"field": "retained_current_exact_stop_share", "direction": "max"},
        {"field": "total_distance_m", "direction": "min"},
    ))
    return tuple(dimensions)
