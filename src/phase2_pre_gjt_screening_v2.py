"""Pre-GJT multi-layer screening helpers for Phase 2 V2.

This layer is deliberately non-decisional. It joins certified topology/service
feasibility, building-population access/equity and S8 passenger-support timing
opportunities without allocating municipal OD demand to routes, calculating
full passenger GJT, selecting a phase, ranking topologies or selecting a service
policy.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence


CONTRACT = "PHASE2_PRE_GJT_MULTI_LAYER_SCREENING_V2"
STATUS = "PASS_PRE_GJT_MULTI_LAYER_SCREENING_V2_BUILD"


def strict_bool(value: object, *, field: str) -> bool:
    if value is True or value == "true":
        return True
    if value is False or value == "false":
        return False
    raise ValueError(f"{field} must be explicit true/false")


@dataclass(frozen=True)
class TimingKey:
    headway_min: int
    span_id: str
    span_start_min: int
    span_end_min: int

    def __post_init__(self) -> None:
        if self.headway_min <= 0 or not self.span_id:
            raise ValueError("Invalid timing key")
        if not 0 <= self.span_start_min < self.span_end_min <= 1440:
            raise ValueError("Invalid timing span")


@dataclass(frozen=True)
class TimingPolicyMasks:
    all_policies: int
    no_extension: int
    positive_extension: int

    def count(self, feasible_mask: int) -> tuple[int, int, int]:
        if feasible_mask < 0:
            raise ValueError("Policy mask cannot be negative")
        total = (feasible_mask & self.all_policies).bit_count()
        no_ext = (feasible_mask & self.no_extension).bit_count()
        positive_ext = (feasible_mask & self.positive_extension).bit_count()
        if total != no_ext + positive_ext:
            raise AssertionError("Timing policy masks do not partition extension state")
        return total, no_ext, positive_ext


def build_timing_policy_masks(policy_rows: Sequence[Mapping[str, object]]) -> dict[TimingKey, TimingPolicyMasks]:
    if not policy_rows:
        raise ValueError("Policy grid is empty")
    indexes: set[int] = set()
    buckets: dict[TimingKey, list[int]] = {}
    no_ext: dict[TimingKey, list[int]] = {}
    positive_ext: dict[TimingKey, list[int]] = {}
    for row in policy_rows:
        idx = int(row["policy_index"])
        if idx < 0 or idx in indexes:
            raise ValueError("Policy grid has invalid or duplicate policy_index")
        indexes.add(idx)
        key = TimingKey(
            headway_min=int(row["uniform_headway_min"]),
            span_id=str(row["span_id"]),
            span_start_min=int(row["span_start_min"]),
            span_end_min=int(row["span_end_min"]),
        )
        buckets.setdefault(key, []).append(idx)
        share = float(row["extension_share"])
        if not math.isfinite(share) or not 0.0 <= share <= 1.0:
            raise ValueError("Invalid extension_share in policy grid")
        (no_ext if math.isclose(share, 0.0, abs_tol=1e-12) else positive_ext).setdefault(key, []).append(idx)
    if indexes != set(range(len(policy_rows))):
        raise ValueError("policy_index must be a complete zero-based domain")
    result: dict[TimingKey, TimingPolicyMasks] = {}
    for key in sorted(buckets, key=lambda k: (k.headway_min, k.span_id)):
        def mask(values: Sequence[int]) -> int:
            out = 0
            for idx in values:
                out |= 1 << idx
            return out
        result[key] = TimingPolicyMasks(
            all_policies=mask(buckets[key]),
            no_extension=mask(no_ext.get(key, ())),
            positive_extension=mask(positive_ext.get(key, ())),
        )
    return result


@dataclass(frozen=True)
class RouteTimingSummary:
    route_count: int
    roundtrip_route_count: int
    directional_only_route_count: int
    roundtrip_complete_route_count: int
    directional_complete_route_count: int
    roundtrip_best_min: float | None
    roundtrip_best_max: float | None
    roundtrip_worst_min: float | None
    roundtrip_worst_max: float | None
    directional_best_min: float | None
    directional_best_max: float | None
    directional_worst_min: float | None
    directional_worst_max: float | None

    @property
    def roundtrip_incomplete_route_count(self) -> int:
        return self.roundtrip_route_count - self.roundtrip_complete_route_count

    @property
    def directional_incomplete_route_count(self) -> int:
        return self.directional_only_route_count - self.directional_complete_route_count


def _range(values: Sequence[float]) -> tuple[float | None, float | None]:
    return (min(values), max(values)) if values else (None, None)


def summarise_route_timing(
    route_ids: Sequence[str],
    *,
    timing_key: TimingKey,
    gap_lookup: Mapping[tuple[str, int, str], Mapping[str, object]],
) -> RouteTimingSummary:
    if len(route_ids) != len(set(route_ids)):
        raise ValueError("Route list contains duplicates")
    roundtrip_count = 0
    directional_count = 0
    roundtrip_best: list[float] = []
    roundtrip_worst: list[float] = []
    directional_best: list[float] = []
    directional_worst: list[float] = []
    for route_id in route_ids:
        key = (route_id, timing_key.headway_min, timing_key.span_id)
        if key not in gap_lookup:
            raise ValueError(f"Missing S8 transfer-gap row for {key}")
        row = gap_lookup[key]
        roundtrip = strict_bool(row["roundtrip_passenger_supported"], field="roundtrip_passenger_supported")
        complete = int(row["complete_match_phase_count"])
        evaluated = int(row["evaluated_phase_count"])
        if evaluated != timing_key.headway_min or not 0 <= complete <= evaluated:
            raise ValueError("Invalid phase counts in S8 transfer-gap row")
        best_raw = str(row.get("best_complete_phase_weighted_mean_gap_min", "")).strip()
        worst_raw = str(row.get("worst_complete_phase_weighted_mean_gap_min", "")).strip()
        if complete == 0:
            if best_raw or worst_raw:
                raise ValueError("No-complete-match row unexpectedly contains gap values")
            if roundtrip:
                roundtrip_count += 1
            else:
                directional_count += 1
            continue
        if not best_raw or not worst_raw:
            raise ValueError("Complete-match row is missing gap values")
        best = float(best_raw)
        worst = float(worst_raw)
        if not all(math.isfinite(v) and v >= 0 for v in (best, worst)) or best > worst + 1e-9:
            raise ValueError("Invalid S8 transfer-gap envelope")
        if roundtrip:
            roundtrip_count += 1
            roundtrip_best.append(best)
            roundtrip_worst.append(worst)
        else:
            directional_count += 1
            directional_best.append(best)
            directional_worst.append(worst)
    rb_min, rb_max = _range(roundtrip_best)
    rw_min, rw_max = _range(roundtrip_worst)
    db_min, db_max = _range(directional_best)
    dw_min, dw_max = _range(directional_worst)
    return RouteTimingSummary(
        route_count=len(route_ids),
        roundtrip_route_count=roundtrip_count,
        directional_only_route_count=directional_count,
        roundtrip_complete_route_count=len(roundtrip_best),
        directional_complete_route_count=len(directional_best),
        roundtrip_best_min=rb_min,
        roundtrip_best_max=rb_max,
        roundtrip_worst_min=rw_min,
        roundtrip_worst_max=rw_max,
        directional_best_min=db_min,
        directional_best_max=db_max,
        directional_worst_min=dw_min,
        directional_worst_max=dw_max,
    )
