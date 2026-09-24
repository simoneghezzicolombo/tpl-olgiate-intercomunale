"""Non-dominated frontier helpers for Phase 2 finalist screening.

The frontier is not a weighted score. It preserves eligible alternatives that
represent genuine trade-offs between passenger utility, robustness, reliability
and production.
"""
from __future__ import annotations

from typing import Sequence

from src.phase2_optimizer_core import RobustScenarioEvaluation


def _dominates(
    left: RobustScenarioEvaluation,
    right: RobustScenarioEvaluation,
    *,
    tolerance: float,
) -> bool:
    """Return True when left is no worse on all primary frontier dimensions.

    Maximise:
    - median GJT improvement
    - lower-quantile GJT improvement

    Minimise:
    - missed-connection probability
    - annual bus-km

    Public-pattern simplicity, unverified elements and stop continuity remain
    lexicographic tie-break criteria from the decision specification rather than
    being silently converted into Pareto objectives.
    """
    no_worse = (
        left.median_gjt_improvement_min + tolerance >= right.median_gjt_improvement_min
        and left.lower_quantile_gjt_improvement_min + tolerance >= right.lower_quantile_gjt_improvement_min
        and left.median_missed_connection_probability <= right.median_missed_connection_probability + tolerance
        and left.annual_bus_km <= right.annual_bus_km + tolerance
    )
    strictly_better = (
        left.median_gjt_improvement_min > right.median_gjt_improvement_min + tolerance
        or left.lower_quantile_gjt_improvement_min > right.lower_quantile_gjt_improvement_min + tolerance
        or left.median_missed_connection_probability + tolerance < right.median_missed_connection_probability
        or left.annual_bus_km + tolerance < right.annual_bus_km
    )
    return no_worse and strictly_better


def non_dominated_frontier(
    evaluations: Sequence[RobustScenarioEvaluation],
    *,
    tolerance: float = 1e-9,
) -> list[RobustScenarioEvaluation]:
    """Return eligible evaluations not dominated on the primary frontier."""
    if tolerance < 0:
        raise ValueError("tolerance cannot be negative")
    eligible = sorted(
        (row for row in evaluations if row.eligible),
        key=lambda row: row.scenario_id,
    )
    frontier = [
        row
        for row in eligible
        if not any(
            other.scenario_id != row.scenario_id
            and _dominates(other, row, tolerance=tolerance)
            for other in eligible
        )
    ]
    return sorted(
        frontier,
        key=lambda row: (
            -row.median_gjt_improvement_min,
            -row.lower_quantile_gjt_improvement_min,
            row.median_missed_connection_probability,
            row.annual_bus_km,
            row.scenario_id,
        ),
    )


def apply_robustness_floor(
    evaluations: Sequence[RobustScenarioEvaluation],
    *,
    minimum_lower_quantile_gjt_improvement_min: float,
) -> list[RobustScenarioEvaluation]:
    """Apply an explicit caller-declared fragility screen before final selection.

    The engine does not choose this threshold. A future decision run must declare
    it and expose it in outputs/sensitivity documentation.
    """
    return [
        row
        for row in evaluations
        if row.eligible
        and row.lower_quantile_gjt_improvement_min >= minimum_lower_quantile_gjt_improvement_min
    ]
