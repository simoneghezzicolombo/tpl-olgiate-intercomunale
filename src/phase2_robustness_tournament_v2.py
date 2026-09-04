"""Deterministic robustness helpers for the Phase 2 final tournament V2."""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Sequence

D = Decimal
EPS = 1e-9


@dataclass(frozen=True)
class GapSummary:
    source_count: int
    matched_count: int
    unmatched_count: int
    mean_gap_min: float | None


def margin_gap_summary(
    sources_min: Sequence[Decimal],
    targets_min: Sequence[Decimal],
    *,
    margin_min: Decimal,
) -> GapSummary:
    if margin_min < 0:
        raise ValueError("connection margin must be non-negative")
    targets = tuple(sorted(targets_min))
    gaps: list[float] = []
    unmatched = 0
    for source in sources_min:
        idx = bisect_left(targets, source + margin_min)
        if idx >= len(targets):
            unmatched += 1
        else:
            gaps.append(float(targets[idx] - source))
    return GapSummary(
        source_count=len(sources_min),
        matched_count=len(gaps),
        unmatched_count=unmatched,
        mean_gap_min=(sum(gaps) / len(gaps)) if gaps else None,
    )


def weighted_cell_mean(cells: Sequence[tuple[float, float | None]]) -> float | None:
    used = [(float(weight), float(value)) for weight, value in cells if weight > 0 and value is not None]
    if not used:
        return None
    return sum(weight * value for weight, value in used) / sum(weight for weight, _ in used)


def dominates(
    a: Mapping[str, float],
    b: Mapping[str, float],
    *,
    maximize: Sequence[str],
    minimize: Sequence[str],
    eps: float = EPS,
) -> bool:
    """Return True when a weakly dominates b and is strictly better somewhere."""
    strict = False
    for key in maximize:
        av, bv = float(a[key]), float(b[key])
        if av < bv - eps:
            return False
        if av > bv + eps:
            strict = True
    for key in minimize:
        av, bv = float(a[key]), float(b[key])
        if av > bv + eps:
            return False
        if av < bv - eps:
            strict = True
    return strict


def nondominated_indices(
    rows: Sequence[Mapping[str, float]],
    *,
    maximize: Sequence[str],
    minimize: Sequence[str],
) -> tuple[int, ...]:
    keep: list[int] = []
    for i, row in enumerate(rows):
        if any(
            j != i and dominates(other, row, maximize=maximize, minimize=minimize)
            for j, other in enumerate(rows)
        ):
            continue
        keep.append(i)
    return tuple(keep)
