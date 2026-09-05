from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable, Mapping, Sequence


DEFAULT_WALK_THRESHOLDS = (5.0, 8.0, 10.0, 12.0)


@dataclass(frozen=True)
class WalkingObservation:
    point_id: str
    population_weight: float
    walk_minutes: float


@dataclass(frozen=True)
class ServiceAreaDiagnostic:
    area_id: str
    served: bool
    nearest_stop_id: str | None = None
    nearest_walk_minutes: float | None = None
    marginal_extra_km: float | None = None
    marginal_extra_runtime_min: float | None = None


def _validate_walking(observations: Iterable[WalkingObservation]) -> list[WalkingObservation]:
    rows = list(observations)
    if not rows:
        raise ValueError("walking observations must not be empty")
    seen: set[str] = set()
    for row in rows:
        if not row.point_id or row.point_id in seen:
            raise ValueError("point_id values must be unique and non-empty")
        seen.add(row.point_id)
        if not isfinite(row.population_weight) or row.population_weight <= 0:
            raise ValueError("population weights must be finite and positive")
        if not isfinite(row.walk_minutes) or row.walk_minutes < 0:
            raise ValueError("walk minutes must be finite and non-negative")
    return rows


def population_share_at_or_below(
    observations: Iterable[WalkingObservation], threshold_minutes: float
) -> float:
    rows = _validate_walking(observations)
    if not isfinite(threshold_minutes) or threshold_minutes < 0:
        raise ValueError("threshold must be finite and non-negative")
    total = sum(r.population_weight for r in rows)
    inside = sum(r.population_weight for r in rows if r.walk_minutes <= threshold_minutes)
    return inside / total


def weighted_quantile_walk_minutes(
    observations: Iterable[WalkingObservation], quantile: float
) -> float:
    rows = _validate_walking(observations)
    if not isfinite(quantile) or not 0 <= quantile <= 1:
        raise ValueError("quantile must be between 0 and 1")
    ordered = sorted(rows, key=lambda r: (r.walk_minutes, r.point_id))
    total = sum(r.population_weight for r in ordered)
    target = quantile * total
    cumulative = 0.0
    for row in ordered:
        cumulative += row.population_weight
        if cumulative >= target:
            return row.walk_minutes
    return ordered[-1].walk_minutes


def summarize_walking_burden(
    observations: Iterable[WalkingObservation],
    thresholds: Sequence[float] = DEFAULT_WALK_THRESHOLDS,
) -> dict[str, float]:
    rows = _validate_walking(observations)
    clean_thresholds = tuple(float(t) for t in thresholds)
    if len(set(clean_thresholds)) != len(clean_thresholds):
        raise ValueError("thresholds must be unique")
    if any((not isfinite(t) or t < 0) for t in clean_thresholds):
        raise ValueError("thresholds must be finite and non-negative")

    total = sum(r.population_weight for r in rows)
    mean = sum(r.population_weight * r.walk_minutes for r in rows) / total
    summary = {
        "population_weight": total,
        "weighted_mean_walk_min": mean,
        "weighted_median_walk_min": weighted_quantile_walk_minutes(rows, 0.50),
        "weighted_p90_walk_min": weighted_quantile_walk_minutes(rows, 0.90),
        "weighted_p95_walk_min": weighted_quantile_walk_minutes(rows, 0.95),
    }
    for threshold in sorted(clean_thresholds):
        key = f"share_le_{threshold:g}_min"
        summary[key] = population_share_at_or_below(rows, threshold)
    summary["share_gt_10_min"] = 1.0 - population_share_at_or_below(rows, 10.0)
    summary["share_gt_12_min"] = 1.0 - population_share_at_or_below(rows, 12.0)
    return summary


def territorial_policy_guard(
    required_policy_groups: Iterable[str], boarding_policy_groups: Iterable[str]
) -> dict[str, object]:
    required = {str(x) for x in required_policy_groups if str(x)}
    boarding = {str(x) for x in boarding_policy_groups if str(x)}
    missing = tuple(sorted(required - boarding))
    return {
        "passes": not missing,
        "required_policy_groups": tuple(sorted(required)),
        "boarding_policy_groups": tuple(sorted(boarding)),
        "missing_policy_groups": missing,
    }


def normalize_service_area_diagnostics(
    diagnostics: Iterable[ServiceAreaDiagnostic],
) -> tuple[ServiceAreaDiagnostic, ...]:
    rows = list(diagnostics)
    seen: set[str] = set()
    for row in rows:
        if not row.area_id or row.area_id in seen:
            raise ValueError("area_id values must be unique and non-empty")
        seen.add(row.area_id)
        for value in (
            row.nearest_walk_minutes,
            row.marginal_extra_km,
            row.marginal_extra_runtime_min,
        ):
            if value is not None and (not isfinite(value) or value < 0):
                raise ValueError("diagnostic numeric values must be finite and non-negative")
    return tuple(sorted(rows, key=lambda r: r.area_id))


def _validate_metric_value(candidate_id: str, name: str, value: float) -> float:
    numeric = float(value)
    if not isfinite(numeric):
        raise ValueError(f"candidate {candidate_id} metric {name} must be finite")
    return numeric


def dominates(
    candidate_a: Mapping[str, object],
    candidate_b: Mapping[str, object],
    dimensions: Mapping[str, str],
) -> bool:
    if not dimensions:
        raise ValueError("at least one Pareto dimension is required")
    a_id = str(candidate_a["candidate_id"])
    b_id = str(candidate_b["candidate_id"])
    no_worse_everywhere = True
    strictly_better_somewhere = False
    for name, direction in sorted(dimensions.items()):
        if direction not in {"min", "max"}:
            raise ValueError("dimension direction must be 'min' or 'max'")
        if name not in candidate_a or name not in candidate_b:
            raise ValueError(f"missing Pareto dimension: {name}")
        a = _validate_metric_value(a_id, name, candidate_a[name])
        b = _validate_metric_value(b_id, name, candidate_b[name])
        if direction == "min":
            no_worse = a <= b
            strict = a < b
        else:
            no_worse = a >= b
            strict = a > b
        no_worse_everywhere = no_worse_everywhere and no_worse
        strictly_better_somewhere = strictly_better_somewhere or strict
    return no_worse_everywhere and strictly_better_somewhere


def pareto_front(
    candidates: Iterable[Mapping[str, object]],
    dimensions: Mapping[str, str],
) -> tuple[str, ...]:
    rows = [dict(row) for row in candidates]
    ids = [str(row.get("candidate_id", "")) for row in rows]
    if any(not x for x in ids) or len(set(ids)) != len(ids):
        raise ValueError("candidate_id values must be unique and non-empty")
    frontier: list[str] = []
    for i, candidate in enumerate(rows):
        if not any(
            dominates(other, candidate, dimensions)
            for j, other in enumerate(rows)
            if i != j
        ):
            frontier.append(str(candidate["candidate_id"]))
    return tuple(sorted(frontier))
