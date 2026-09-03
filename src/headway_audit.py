"""Observed departure headway audit for Gate E.

This module distinguishes a mathematical service-rate equivalent from the actual
inter-departure gaps produced by phased departures at a stop. It contains no
project timetable constants.
"""
from __future__ import annotations

from collections import Counter
import math
from statistics import mean, median
from typing import Iterable

from src.service_math import ServiceMathError, combined_headway_rate_equivalent, parse_gtfs_time_to_minutes, validate_epistemic_status


def _times_minutes(values: Iterable[str | float]) -> list[float]:
    out = []
    for value in values:
        minutes = parse_gtfs_time_to_minutes(value) if isinstance(value, str) else float(value)
        if not math.isfinite(minutes) or minutes < 0:
            raise ServiceMathError(f"invalid departure time {value!r}")
        out.append(minutes)
    return sorted(out)


def _nearest_rank(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(probability * len(ordered)))
    return ordered[rank - 1]


def observed_headway_stats(departures: Iterable[str | float]) -> dict[str, object]:
    """Interior observed gaps only. Boundary-to-first/last-to-boundary are excluded."""
    times = _times_minutes(departures)
    gaps = [b - a for a, b in zip(times, times[1:])]
    return {
        "n_departures": len(times),
        "first_departure_min": times[0] if times else None,
        "last_departure_min": times[-1] if times else None,
        "n_observed_interior_gaps": len(gaps),
        "min_headway_min": min(gaps) if gaps else None,
        "mean_headway_min": mean(gaps) if gaps else None,
        "median_headway_min": median(gaps) if gaps else None,
        "p90_headway_min": _nearest_rank(gaps, 0.90),
        "max_headway_min": max(gaps) if gaps else None,
        "zero_gap_count": sum(g == 0 for g in gaps),
        "boundary_gap_semantics": "EXCLUDED_REQUIRES_ADJACENT_BANDS_OR_FULL_DAY_TIMETABLE",
    }


def combined_observed_headway_stats(
    cw_departures: Iterable[str | float],
    ccw_departures: Iterable[str | float],
) -> dict[str, object]:
    cw = _times_minutes(cw_departures)
    ccw = _times_minutes(ccw_departures)
    combined = sorted(cw + ccw)
    stats = observed_headway_stats(combined)
    shared = Counter(cw) & Counter(ccw)
    simultaneous = sum(shared.values())
    cw_stats = observed_headway_stats(cw)
    ccw_stats = observed_headway_stats(ccw)
    mean_cw = cw_stats["mean_headway_min"]
    mean_ccw = ccw_stats["mean_headway_min"]
    rate_equiv = (
        combined_headway_rate_equivalent(float(mean_cw), float(mean_ccw))
        if mean_cw is not None and mean_ccw is not None and mean_cw > 0 and mean_ccw > 0
        else None
    )
    max_gap = stats["max_headway_min"]
    return {
        **stats,
        "simultaneous_CW_CCW_departures": simultaneous,
        "directional_mean_headway_CW_min": mean_cw,
        "directional_mean_headway_CCW_min": mean_ccw,
        "rate_equivalent_from_directional_observed_means_min": rate_equiv,
        "max_gap_to_rate_equivalent_ratio": (
            float(max_gap) / rate_equiv
            if max_gap is not None and rate_equiv not in (None, 0)
            else None
        ),
    }


def headway_evidence_status(
    upstream_gate_c_status: str,
    epistemic_statuses: Iterable[str],
    analysis_mode: str,
    gate_c_artifact: str,
    gate_c_commit: str,
) -> str:
    statuses = list(epistemic_statuses)
    for status in statuses:
        validate_epistemic_status(status, analysis_mode, "departure_time")
    if upstream_gate_c_status.strip().upper() == "PASS" and (
        not gate_c_artifact.strip() or not gate_c_commit.strip()
    ):
        raise ServiceMathError("Gate C PASS headway evidence requires artifact and commit lineage")
    if any(s.strip().upper() == "ASSUMPTION" for s in statuses):
        return "SENSITIVITY_ONLY_NOT_GATE_E_EVIDENCE"
    if upstream_gate_c_status.strip().upper() != "PASS":
        return "PROVISIONAL/BLOCKED_BY_GATE_C"
    return "ELIGIBLE_FOR_GATE_E_HEADWAY_EVIDENCE"
