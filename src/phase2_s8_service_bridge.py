"""Bridge explicit Phase 2 bus service plans to the validated S8 scorer.

The S8 model is topology-neutral. This bridge therefore does not infer where a
hub event occurs from route geometry. The caller must explicitly declare hub
event offsets for each operating block. This prevents a radial, loop or interlined
block from being silently treated as if it started/ended at Olgiate FS.

Outputs are timetable/service-event quality indicators, NOT passenger counts and
NOT rail mode share. Passenger weighting belongs to a separate, evidence-backed
journey-demand layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Mapping, Sequence

from src.phase2_s8_interchange import (
    DelayCase,
    S8ModelError,
    TransferQualityProfile,
    robust_connection_quality,
    score_bus_hub_timetable,
)
from src.phase2_service_engine import OperatingPlan


VALID_BUS_EVENT_TYPES = {"BUS_ARRIVAL", "BUS_DEPARTURE"}


@dataclass(frozen=True)
class HubEventOffset:
    """One explicit hub event relative to a block's scheduled cycle departure."""

    block_id: str
    event_type: str
    offset_min: float
    event_label: str = ""

    def __post_init__(self) -> None:
        if not self.block_id:
            raise ValueError("HubEventOffset.block_id is required")
        if self.event_type.upper() not in VALID_BUS_EVENT_TYPES:
            raise ValueError(f"event_type must be one of {sorted(VALID_BUS_EVENT_TYPES)}")
        if self.offset_min < 0:
            raise ValueError("Hub event offsets must be non-negative")


@dataclass(frozen=True)
class S8ServiceQualitySummary:
    scenario_id: str
    plan_id: str
    connection_type: str
    rail_direction: str
    bus_event_count: int
    scheduled_quality_mean: float
    scheduled_quality_min: float
    robust_expected_quality_mean: float
    robust_worst_case_quality_min: float
    robust_hard_miss_probability_mean: float
    robust_expected_slack_mean_min: float
    semantics: str = "SERVICE_EVENT_TIMETABLE_QUALITY_NOT_RIDERSHIP_OR_MODAL_SHARE"


def materialise_bus_hub_events(
    plan: OperatingPlan,
    hub_offsets: Sequence[HubEventOffset],
) -> list[dict[str, object]]:
    """Expand recurring windows into explicit bus arrival/departure events at FS.

    A service window defines cycle departure times. Hub offsets declare where the
    hub event lies inside that cycle. This separation permits, for example, a loop
    that departs FS at offset 0 and returns at offset `running_min`, or an interlined
    block whose relevant hub passage occurs in the middle of the cycle.
    """
    if not hub_offsets:
        raise ValueError("At least one explicit HubEventOffset is required")

    cycle_ids = {cycle.block_id for cycle in plan.cycles}
    offset_blocks = {offset.block_id for offset in hub_offsets}
    unknown = sorted(offset_blocks - cycle_ids)
    if unknown:
        raise ValueError(f"Hub offsets reference unknown blocks: {unknown}")

    by_block: dict[str, list[HubEventOffset]] = {}
    for offset in hub_offsets:
        by_block.setdefault(offset.block_id, []).append(offset)

    rows: list[dict[str, object]] = []
    for window in sorted(plan.windows, key=lambda item: item.window_id):
        offsets = by_block.get(window.block_id)
        if not offsets:
            continue
        first_departure = window.start_min + window.phase_offset_min
        for ordinal in range(window.departures_per_day):
            cycle_departure = first_departure + ordinal * window.headway_min
            for offset in sorted(offsets, key=lambda item: (item.offset_min, item.event_type, item.event_label)):
                event_time = cycle_departure + offset.offset_min
                rows.append(
                    {
                        "scenario_id": plan.scenario_id,
                        "plan_id": plan.plan_id,
                        "window_id": window.window_id,
                        "block_id": window.block_id,
                        "day_type": window.day_type,
                        "cycle_departure_ordinal": ordinal,
                        "event_type": offset.event_type.upper(),
                        "event_time": float(event_time),
                        "event_label": offset.event_label,
                        "epistemic_status": "DERIVED_FROM_EXPLICIT_SERVICE_PLAN_AND_HUB_OFFSET",
                    }
                )

    if not rows:
        raise ValueError("No hub events were materialised from the declared plan/offsets")
    rows.sort(
        key=lambda row: (
            str(row["day_type"]),
            float(row["event_time"]),
            str(row["block_id"]),
            str(row["event_type"]),
        )
    )
    return rows


def _rail_event_index(rail_events: Sequence[Mapping[str, object]]) -> dict[str, Mapping[str, object]]:
    index: dict[str, Mapping[str, object]] = {}
    for event in rail_events:
        trip_id = str(event.get("trip_id", ""))
        if not trip_id:
            raise S8ModelError("rail event lacks trip_id")
        if trip_id in index:
            raise S8ModelError(f"duplicate rail trip_id {trip_id}")
        index[trip_id] = event
    if not index:
        raise S8ModelError("rail event set cannot be empty")
    return index


def score_service_plan_s8(
    *,
    plan: OperatingPlan,
    hub_offsets: Sequence[HubEventOffset],
    rail_events: Sequence[Mapping[str, object]],
    profile: TransferQualityProfile,
    delay_cases: Sequence[DelayCase],
    day_type: str | None = None,
) -> tuple[list[dict[str, object]], list[S8ServiceQualitySummary]]:
    """Score one explicit bus plan against S8, including deterministic robustness.

    If the operating plan contains multiple day types, `day_type` must be supplied
    before comparison with a single-day S8 event set. This prevents mixing weekday,
    Saturday or holiday bus events against one validated rail service day.
    """
    bus_events = materialise_bus_hub_events(plan, hub_offsets)
    observed_day_types = {str(row["day_type"]) for row in bus_events}
    if day_type is None:
        if len(observed_day_types) != 1:
            raise ValueError(
                "day_type is required when a plan contains multiple day types and rail_events represent one service day"
            )
        selected = bus_events
    else:
        selected = [row for row in bus_events if row["day_type"] == day_type]
        if not selected:
            raise ValueError(f"No bus hub events for requested day_type {day_type!r}")

    scheduled = score_bus_hub_timetable(selected, rail_events, profile)
    rail_index = _rail_event_index(rail_events)
    detail: list[dict[str, object]] = []
    for row in scheduled:
        rail_trip_id = str(row["rail_trip_id"])
        try:
            rail_event = rail_index[rail_trip_id]
        except KeyError as exc:
            raise S8ModelError(f"scheduled scorer returned unknown rail trip {rail_trip_id}") from exc
        robust = robust_connection_quality(
            bus_time_min=float(row["event_time_min"]),
            rail_event=rail_event,
            connection_type=str(row["connection_type"]),
            profile=profile,
            delay_cases=delay_cases,
        )
        detail.append(
            {
                **row,
                **robust,
                "plan_id": plan.plan_id,
                "service_quality_semantics": "SERVICE_EVENT_TIMETABLE_QUALITY_NOT_RIDERSHIP_OR_MODAL_SHARE",
                "profile_status": "ASSUMPTION_SENSITIVITY_INPUT",
                "delay_cases_status": "ASSUMPTION_SENSITIVITY_INPUT",
            }
        )

    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in detail:
        key = (str(row["connection_type"]), str(row["rail_direction"]))
        grouped.setdefault(key, []).append(row)

    summaries: list[S8ServiceQualitySummary] = []
    for (connection_type, rail_direction), rows in sorted(grouped.items()):
        summaries.append(
            S8ServiceQualitySummary(
                scenario_id=plan.scenario_id,
                plan_id=plan.plan_id,
                connection_type=connection_type,
                rail_direction=rail_direction,
                bus_event_count=len(rows),
                scheduled_quality_mean=mean(float(row["quality"]) for row in rows),
                scheduled_quality_min=min(float(row["quality"]) for row in rows),
                robust_expected_quality_mean=mean(float(row["expected_quality"]) for row in rows),
                robust_worst_case_quality_min=min(float(row["worst_case_quality"]) for row in rows),
                robust_hard_miss_probability_mean=mean(float(row["hard_miss_probability"]) for row in rows),
                robust_expected_slack_mean_min=mean(float(row["expected_slack_after_walk_min"]) for row in rows),
            )
        )
    return detail, summaries
