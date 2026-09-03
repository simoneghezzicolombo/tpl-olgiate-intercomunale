from __future__ import annotations

import pytest

from src.phase2_operational_screening import (
    aggregate_route_lower_bounds,
    maximum_equal_pattern_sets_per_year,
    route_operational_lower_bound,
)
from src.phase2_optimizer_core import PathLeg, ReducedPathMatrix


def matrix() -> ReducedPathMatrix:
    return ReducedPathMatrix([
        PathLeg("A", "B", 2.0, 4.0, "RESOLVED"),
        PathLeg("B", "A", 2.5, 5.0, "QUANTIFIED"),
        PathLeg("B", "C", 3.0, 6.0, "UNKNOWN"),
        PathLeg("C", "A", 4.0, 8.0, "RESOLVED"),
    ])


def test_closed_route_needs_no_added_closure() -> None:
    row = route_operational_lower_bound(matrix(), ["A", "B", "A"])
    assert row.is_structurally_closed is True
    assert row.return_closable is True
    assert row.closure_added is False
    assert row.return_distance_km == 0.0
    assert row.operational_cycle_distance_km == pytest.approx(4.5)
    assert row.operational_resolved_distance_km == pytest.approx(2.0)
    assert row.operational_quantified_distance_km == pytest.approx(2.5)


def test_open_route_adds_exact_validated_return_leg() -> None:
    row = route_operational_lower_bound(matrix(), ["A", "B", "C"])
    assert row.is_structurally_closed is False
    assert row.return_closable is True
    assert row.closure_added is True
    assert row.public_distance_km == pytest.approx(5.0)
    assert row.return_distance_km == pytest.approx(4.0)
    assert row.return_runtime_min == pytest.approx(8.0)
    assert row.operational_cycle_distance_km == pytest.approx(9.0)
    assert row.operational_cycle_runtime_min == pytest.approx(18.0)
    assert row.operational_unknown_distance_km == pytest.approx(3.0)


def test_open_route_without_return_fails_closed() -> None:
    m = ReducedPathMatrix([
        PathLeg("A", "B", 1.0, 2.0),
        PathLeg("B", "C", 1.0, 2.0),
    ])
    row = route_operational_lower_bound(m, ["A", "B", "C"])
    assert row.return_closable is False
    assert row.operational_cycle_distance_km is None
    aggregate = aggregate_route_lower_bounds([row])
    assert aggregate["all_return_closable"] is False
    assert aggregate["equal_pattern_set_cycle_distance_km_lower_bound"] is None


def test_aggregate_conserves_uncertainty_distance() -> None:
    rows = [
        route_operational_lower_bound(matrix(), ["A", "B", "A"]),
        route_operational_lower_bound(matrix(), ["A", "B", "C"]),
    ]
    aggregate = aggregate_route_lower_bounds(rows)
    total = (
        aggregate["operational_resolved_distance_km_lower_bound"]
        + aggregate["operational_quantified_distance_km_lower_bound"]
        + aggregate["operational_unknown_distance_km_lower_bound"]
    )
    assert total == pytest.approx(aggregate["equal_pattern_set_cycle_distance_km_lower_bound"])
    assert aggregate["closure_added_route_count"] == 1


def test_budget_capacity_is_floor_not_frequency() -> None:
    assert maximum_equal_pattern_sets_per_year(111_419.0, 19.992512) == 5573
    with pytest.raises(ValueError):
        maximum_equal_pattern_sets_per_year(0.0, 10.0)
    with pytest.raises(ValueError):
        maximum_equal_pattern_sets_per_year(100.0, 0.0)
