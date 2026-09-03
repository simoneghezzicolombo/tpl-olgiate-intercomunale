"""Deterministic Phase 2 service-policy search.

This module searches explicit caller-declared timetable choices over already
validated operating cycles. It never invents headways, service spans, calendars,
recovery or fleet assumptions.

The structural optimiser answers "where can the network go?". This module answers
"given that structure, how should the service be operated within declared resource
constraints?".
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from itertools import product
import json
from typing import Sequence

from src.phase2_service_engine import (
    OperatingCycle,
    OperatingPlan,
    OperationalSummary,
    ServiceWindow,
    summarise_operating_plan,
)


@dataclass(frozen=True)
class WindowChoice:
    headway_min: int
    phase_offset_min: int = 0

    def __post_init__(self) -> None:
        if self.headway_min <= 0:
            raise ValueError("headway_min must be positive")
        if not 0 <= self.phase_offset_min < self.headway_min:
            raise ValueError("phase_offset_min must be in [0, headway_min)")


@dataclass(frozen=True)
class ServiceWindowTemplate:
    """One explicit search slot for one block and day type."""

    template_id: str
    block_id: str
    day_type: str
    start_min: int
    end_min: int
    annual_days: float
    choices: tuple[WindowChoice, ...]

    def __post_init__(self) -> None:
        if not self.template_id or not self.block_id or not self.day_type:
            raise ValueError("Template identifiers are required")
        if not 0 <= self.start_min < self.end_min <= 24 * 60:
            raise ValueError("Invalid template service window")
        if self.annual_days <= 0:
            raise ValueError("annual_days must be positive")
        if not self.choices:
            raise ValueError("A template requires at least one explicit choice")
        if len(set(self.choices)) != len(self.choices):
            raise ValueError("Duplicate WindowChoice values are not allowed")


@dataclass(frozen=True)
class OperationalScreenResult:
    plan: OperatingPlan
    summary: OperationalSummary
    within_budget: bool
    within_fleet_cap: bool
    recovery_feasible: bool

    @property
    def operationally_feasible(self) -> bool:
        return (
            self.within_budget
            and self.within_fleet_cap
            and self.recovery_feasible
            and self.summary.evidence_valid
        )


def _plan_id(scenario_id: str, windows: Sequence[ServiceWindow]) -> str:
    payload = {
        "scenario_id": scenario_id,
        "windows": [
            {
                "window_id": row.window_id,
                "block_id": row.block_id,
                "day_type": row.day_type,
                "start_min": row.start_min,
                "end_min": row.end_min,
                "headway_min": row.headway_min,
                "annual_days": row.annual_days,
                "phase_offset_min": row.phase_offset_min,
            }
            for row in sorted(windows, key=lambda item: item.window_id)
        ],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"PLAN_{sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def _validate_templates(
    cycles: Sequence[OperatingCycle],
    templates: Sequence[ServiceWindowTemplate],
) -> None:
    if not cycles or not templates:
        raise ValueError("cycles and templates cannot be empty")
    cycle_ids = {cycle.block_id for cycle in cycles}
    if len(cycle_ids) != len(cycles):
        raise ValueError("Duplicate cycle block_id")
    template_ids = {row.template_id for row in templates}
    if len(template_ids) != len(templates):
        raise ValueError("Duplicate template_id")
    unknown = sorted({row.block_id for row in templates} - cycle_ids)
    if unknown:
        raise ValueError(f"Templates reference unknown blocks: {unknown}")

    # Overlap is a property of templates, independent from which headway option
    # is selected, so reject it once before the Cartesian search.
    by_key: dict[tuple[str, str], list[ServiceWindowTemplate]] = {}
    for row in templates:
        by_key.setdefault((row.block_id, row.day_type), []).append(row)
    for key, rows in by_key.items():
        ordered = sorted(rows, key=lambda item: (item.start_min, item.end_min))
        for left, right in zip(ordered[:-1], ordered[1:]):
            if right.start_min < left.end_min:
                raise ValueError(f"Overlapping service templates for {key}")


def enumerate_operating_plans(
    *,
    scenario_id: str,
    cycles: Sequence[OperatingCycle],
    templates: Sequence[ServiceWindowTemplate],
    budget_cap_km: float,
    fleet_cap: int,
    minimum_recovery_min: float,
    max_plans: int = 100_000,
    keep_infeasible: bool = False,
) -> list[OperationalScreenResult]:
    """Enumerate explicit service choices and apply cheap operational screening.

    Search order is deterministic. No random sampling is used. `max_plans` is a
    safety ceiling over evaluated unique plans, not a claim that 100,000 service
    plans are intrinsically required for every topology.
    """
    if not scenario_id:
        raise ValueError("scenario_id is required")
    if budget_cap_km <= 0 or fleet_cap <= 0 or minimum_recovery_min < 0:
        raise ValueError("Invalid operational constraints")
    if max_plans <= 0:
        raise ValueError("max_plans must be positive")
    _validate_templates(cycles, templates)

    ordered_templates = sorted(templates, key=lambda row: row.template_id)
    option_sets = [tuple(sorted(row.choices, key=lambda c: (c.headway_min, c.phase_offset_min))) for row in ordered_templates]

    results: list[OperationalScreenResult] = []
    seen: set[str] = set()
    evaluated = 0
    for selected in product(*option_sets):
        windows = tuple(
            ServiceWindow(
                window_id=template.template_id,
                block_id=template.block_id,
                day_type=template.day_type,
                start_min=template.start_min,
                end_min=template.end_min,
                headway_min=choice.headway_min,
                annual_days=template.annual_days,
                phase_offset_min=choice.phase_offset_min,
            )
            for template, choice in zip(ordered_templates, selected)
        )
        plan_id = _plan_id(scenario_id, windows)
        if plan_id in seen:
            continue
        seen.add(plan_id)
        evaluated += 1
        if evaluated > max_plans:
            break

        plan = OperatingPlan(
            scenario_id=scenario_id,
            plan_id=plan_id,
            cycles=tuple(cycles),
            windows=windows,
        )
        summary = summarise_operating_plan(plan)
        result = OperationalScreenResult(
            plan=plan,
            summary=summary,
            within_budget=summary.annual_bus_km <= budget_cap_km,
            within_fleet_cap=summary.max_active_vehicles <= fleet_cap,
            recovery_feasible=summary.min_recovery_min >= minimum_recovery_min,
        )
        if keep_infeasible or result.operationally_feasible:
            results.append(result)

    return results


def budget_envelopes_from_reference(
    reference_bus_km: float,
    proportional_changes: Sequence[float],
) -> list[float]:
    """Create declared budget envelopes without embedding a project reference."""
    if reference_bus_km <= 0:
        raise ValueError("reference_bus_km must be positive")
    values = sorted({reference_bus_km * (1.0 + float(change)) for change in proportional_changes})
    if not values or any(value <= 0 for value in values):
        raise ValueError("Budget changes produce a non-positive envelope")
    return values
