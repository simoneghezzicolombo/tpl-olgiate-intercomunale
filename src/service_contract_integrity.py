"""Cross-row integrity checks for the Gate E V2 service contract."""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Sequence

from src.service_math import ServiceBandDirectionPlan, ServiceMathError, parse_gtfs_time_to_minutes


def validate_nonoverlapping_bands(plans: Sequence[ServiceBandDirectionPlan]) -> None:
    """Reject additive operating bands that overlap within one service-day group.

    CW and CCW rows for the same band are collapsed to one interval. Different
    service_day_groups are not compared because their calendar-date sets are an
    upstream/service-policy concern rather than a clock-band concern.
    """
    grouped: dict[tuple[str, str], dict[str, tuple[float, float]]] = defaultdict(dict)
    for plan in plans:
        key = (plan.scenario_id, plan.service_day_group)
        start = parse_gtfs_time_to_minutes(plan.band_start_time)
        end = parse_gtfs_time_to_minutes(plan.band_end_time)
        existing = grouped[key].get(plan.band_id)
        if existing is not None and existing != (start, end):
            raise ServiceMathError(f"{key}/{plan.band_id}: inconsistent interval across rows")
        grouped[key][plan.band_id] = (start, end)

    for key, bands in grouped.items():
        ordered = sorted((start, end, band_id) for band_id, (start, end) in bands.items())
        for (_, prev_end, prev_id), (next_start, _, next_id) in zip(ordered, ordered[1:]):
            if next_start < prev_end - 1e-12:
                raise ServiceMathError(
                    f"{key}: overlapping additive bands {prev_id!r} and {next_id!r} would double-count production"
                )


def regular_pattern_departure_count_bounds(plan: ServiceBandDirectionPlan) -> tuple[int, int]:
    """Possible departure count in [band_start, band_end) for an exact regular headway.

    Phase is unknown, so a non-integer span/headway ratio permits floor or ceil.
    An integer ratio has one exact count.
    """
    ratio = plan.band_span_min / plan.target_headway_min
    nearest = round(ratio)
    if math.isclose(ratio, nearest, abs_tol=1e-12):
        return int(nearest), int(nearest)
    return math.floor(ratio), math.ceil(ratio)


def headway_cycle_count_audit(plan: ServiceBandDirectionPlan) -> dict[str, object]:
    low, high = regular_pattern_departure_count_bounds(plan)
    if low <= plan.daily_cycles <= high:
        status = "CONSISTENT_WITH_EXACT_REGULAR_HEADWAY_FOR_SOME_PHASE"
    elif plan.daily_cycles < low:
        status = "FEWER_CYCLES_THAN_EXACT_REGULAR_HEADWAY_IMPLIES"
    else:
        status = "MORE_CYCLES_THAN_EXACT_REGULAR_HEADWAY_IMPLIES"
    return {
        "regular_pattern_departure_count_min": low,
        "regular_pattern_departure_count_max": high,
        "daily_cycles": plan.daily_cycles,
        "headway_cycle_count_audit": status,
        "headway_cycle_count_semantics": "DIAGNOSTIC_ONLY_TARGET_HEADWAY_MAY_BE_POLICY_NOT_EXACT_TIMETABLE",
    }


def validate_contract_cross_rows(plans: Sequence[ServiceBandDirectionPlan]) -> None:
    validate_nonoverlapping_bands(plans)
