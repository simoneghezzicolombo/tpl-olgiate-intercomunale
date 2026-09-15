"""Exact lossless compression for large Pareto comparisons."""
from __future__ import annotations

import numpy as np


def grouped_pareto_indices(vectors, costs, pareto_fn):
    """Return the exact Pareto membership after lossless objective grouping.

    Rows with an identical benefit vector differ only by cost in the supplied
    Pareto problem. Every member above the minimum cost is therefore strictly
    dominated by a minimum-cost member of the same group. All members tied at
    the minimum cost are preserved because identical objective tuples do not
    strictly dominate one another.

    The reduced one-row-per-benefit-vector problem is then delegated to the
    same exact Pareto implementation used by the uncompressed path. Re-expanding
    every minimum-cost tie from nondominated groups yields exactly the original
    Pareto membership, without tolerance, weighting or approximation.
    """
    if len(vectors) != len(costs):
        raise ValueError("vector/cost length mismatch")
    if len(costs) == 0:
        return [], {
            "source_row_count": 0,
            "unique_exact_benefit_vector_count": 0,
            "higher_cost_identical_vector_row_count_pruned": 0,
            "minimum_cost_tie_row_count": 0,
        }
    if getattr(vectors, "ndim", None) != 2:
        raise ValueError("2D objective matrix required")

    groups = {}
    for index, cost in enumerate(costs):
        key = tuple(vectors[index, axis] for axis in range(vectors.shape[1]))
        current = groups.get(key)
        if current is None or cost < current[0]:
            groups[key] = (cost, [index])
        elif cost == current[0]:
            current[1].append(index)

    ordered = sorted(
        groups.items(),
        key=lambda item: (item[1][0], item[1][1][0]),
    )
    reduced = np.empty((len(ordered), vectors.shape[1]), dtype=object)
    reduced_costs = []
    tied_indices = []
    for group_index, (key, (cost, indices)) in enumerate(ordered):
        reduced[group_index, :] = key
        reduced_costs.append(cost)
        tied_indices.append(tuple(indices))

    nondominated_groups = pareto_fn(reduced, reduced_costs)
    result = sorted(
        index
        for group_index in nondominated_groups
        for index in tied_indices[group_index]
    )
    minimum_cost_rows = sum(len(indices) for indices in tied_indices)
    return result, {
        "source_row_count": len(costs),
        "unique_exact_benefit_vector_count": len(ordered),
        "higher_cost_identical_vector_row_count_pruned": (
            len(costs) - minimum_cost_rows),
        "minimum_cost_tie_row_count": minimum_cost_rows - len(ordered),
    }
