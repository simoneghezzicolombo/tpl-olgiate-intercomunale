"""Operational and passenger-utility engine for Phase 2 service design.

This module is deliberately topology-agnostic and data-agnostic. It consumes
validated route-cycle, timetable and journey records produced by other Phase 2
workstreams. It does not embed territorial values, route preferences, demand
volumes, headways or service calendars.

Key separation:
- operational production/fleet is computed from explicit vehicle blocks;
- empirically weighted journey utility is evaluated only where a defensible
  demand weight exists;
- population walking access and opportunity access remain separate outcomes;
- municipal non-regression is a hard decision safeguard, not a hidden score.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor
from typing import Mapping, Sequence

from src.phase2_optimizer_core import HardConstraintResult, SensitivityResult


VALID_EVIDENCE = {
    "FACT",
    "FACT_OSM_OBSERVATION",
    "DERIVED",
    "ESTIMATE",
    "ASSUMPTION",
    "RECONSTRUCTED",
    "MODEL OUTPUT",
    "FIELD CHECK",
}
FORBIDDEN_EVIDENCE = {"INVALIDATED", "PLACEHOLDER"}


@dataclass(frozen=True)
class OperatingCycle:
    """One repeating vehicle block.

    A block may correspond to one public route, several interlined routes, or a
    short-turn/extension pattern. Its distance and running time must come from
    validated routing/timetable inputs, not from this engine.
    """

    block_id: str
    route_ids: tuple[str, ...]
    distance_km: float
    running_min: float
    recovery_min: float
    evidence_status: str
    unverified_elements: int = 0

    def __post_init__(self) -> None:
        if not self.block_id or not self.route_ids or any(not item for item in self.route_ids):
            raise ValueError("OperatingCycle requires block_id and route_ids")
        if self.distance_km <= 0 or self.running_min <= 0 or self.recovery_min < 0:
            raise ValueError("OperatingCycle requires positive distance/running time and non-negative recovery")
        status = self.evidence_status.strip().upper()
        if status in FORBIDDEN_EVIDENCE or status not in VALID_EVIDENCE:
            raise ValueError(f"OperatingCycle has unusable evidence status: {self.evidence_status}")
        if self.unverified_elements < 0:
            raise ValueError("unverified_elements cannot be negative")

    @property
    def cycle_min(self) -> float:
        return self.running_min + self.recovery_min


@dataclass(frozen=True)
class ServiceWindow:
    """Explicit recurring timetable window for a vehicle block."""

    window_id: str
    block_id: str
    day_type: str
    start_min: int
    end_min: int
    headway_min: int
    annual_days: float
    phase_offset_min: int = 0

    def __post_init__(self) -> None:
        if not self.window_id or not self.block_id or not self.day_type:
            raise ValueError("ServiceWindow IDs/day_type are required")
        if not 0 <= self.start_min < self.end_min <= 24 * 60:
            raise ValueError("Invalid service window")
        if self.headway_min <= 0 or self.annual_days <= 0:
            raise ValueError("headway_min and annual_days must be positive")
        if not 0 <= self.phase_offset_min < self.headway_min:
            raise ValueError("phase_offset_min must be in [0, headway_min)")

    @property
    def departures_per_day(self) -> int:
        first = self.start_min + self.phase_offset_min
        if first >= self.end_min:
            return 0
        return floor((self.end_min - 1 - first) / self.headway_min) + 1


@dataclass(frozen=True)
class OperatingPlan:
    scenario_id: str
    plan_id: str
    cycles: tuple[OperatingCycle, ...]
    windows: tuple[ServiceWindow, ...]

    def __post_init__(self) -> None:
        if not self.scenario_id or not self.plan_id:
            raise ValueError("OperatingPlan IDs are required")
        if not self.cycles or not self.windows:
            raise ValueError("OperatingPlan requires cycles and service windows")

        cycle_ids = {cycle.block_id for cycle in self.cycles}
        if len(cycle_ids) != len(self.cycles):
            raise ValueError("Duplicate OperatingCycle block_id")
        unknown = sorted({window.block_id for window in self.windows} - cycle_ids)
        if unknown:
            raise ValueError(f"Service windows reference unknown blocks: {unknown}")

        # A block cannot have two simultaneous timetable regimes on the same
        # day type. Adjacent windows are allowed.
        by_key: dict[tuple[str, str], list[ServiceWindow]] = {}
        for window in self.windows:
            by_key.setdefault((window.block_id, window.day_type), []).append(window)
        for key, rows in by_key.items():
            ordered = sorted(rows, key=lambda row: (row.start_min, row.end_min))
            for left, right in zip(ordered[:-1], ordered[1:]):
                if right.start_min < left.end_min:
                    raise ValueError(f"Overlapping service windows for {key}")


@dataclass(frozen=True)
class OperationalSummary:
    scenario_id: str
    plan_id: str
    annual_bus_km: float
    annual_vehicle_hours: float
    max_active_vehicles: int
    total_annual_departures: float
    min_recovery_min: float
    max_unverified_elements_per_block: int
    evidence_valid: bool


def _fleet_for_window(cycle: OperatingCycle, window: ServiceWindow) -> int:
    """Minimum steady-state fleet for a repeating block/headway."""
    return int(ceil(cycle.cycle_min / window.headway_min))


def summarise_operating_plan(plan: OperatingPlan) -> OperationalSummary:
    cycles = {cycle.block_id: cycle for cycle in plan.cycles}
    annual_bus_km = 0.0
    annual_vehicle_hours = 0.0
    annual_departures = 0.0

    for window in plan.windows:
        cycle = cycles[window.block_id]
        departures = window.departures_per_day * window.annual_days
        annual_departures += departures
        annual_bus_km += departures * cycle.distance_km
        annual_vehicle_hours += departures * cycle.cycle_min / 60.0

    # Fleet is evaluated independently by day type. For each time slice, sum
    # block requirements active in that slice and retain the maximum.
    max_fleet = 0
    day_types = sorted({window.day_type for window in plan.windows})
    for day_type in day_types:
        rows = [window for window in plan.windows if window.day_type == day_type]
        boundaries = sorted({value for row in rows for value in (row.start_min, row.end_min)})
        for start, end in zip(boundaries[:-1], boundaries[1:]):
            if start == end:
                continue
            probe = (start + end) / 2.0
            active = [row for row in rows if row.start_min <= probe < row.end_min]
            fleet = sum(_fleet_for_window(cycles[row.block_id], row) for row in active)
            max_fleet = max(max_fleet, fleet)

    return OperationalSummary(
        scenario_id=plan.scenario_id,
        plan_id=plan.plan_id,
        annual_bus_km=annual_bus_km,
        annual_vehicle_hours=annual_vehicle_hours,
        max_active_vehicles=max_fleet,
        total_annual_departures=annual_departures,
        min_recovery_min=min(cycle.recovery_min for cycle in plan.cycles),
        max_unverified_elements_per_block=max(cycle.unverified_elements for cycle in plan.cycles),
        evidence_valid=True,
    )


@dataclass(frozen=True)
class BehaviouralWeights:
    """Published/declared behavioural coefficients for one sensitivity case."""

    sensitivity_id: str
    walk_weight: float
    wait_weight: float
    transfer_penalty_min: float
    missed_connection_cost_multiplier: float = 1.0

    def __post_init__(self) -> None:
        if not self.sensitivity_id:
            raise ValueError("sensitivity_id is required")
        if self.walk_weight <= 0 or self.wait_weight <= 0:
            raise ValueError("walk_weight and wait_weight must be positive")
        if self.transfer_penalty_min < 0 or self.missed_connection_cost_multiplier < 0:
            raise ValueError("Penalty values cannot be negative")


@dataclass(frozen=True)
class JourneyRecord:
    """Passenger journey components for one empirically weighted movement.

    demand_weight must be traceable to a supported demand layer. This class is
    not intended for unweighted POIs or guessed passenger volumes.
    """

    journey_key: str
    layer: str
    origin_municipality: str
    demand_weight: float
    walk_min: float
    wait_min: float
    in_vehicle_min: float
    transfer_walk_min: float = 0.0
    transfer_wait_min: float = 0.0
    transfers: int = 0
    missed_connection_probability: float = 0.0
    missed_connection_cost_min: float = 0.0
    evidence_status: str = "DERIVED"

    def __post_init__(self) -> None:
        if not self.journey_key or not self.layer or not self.origin_municipality:
            raise ValueError("JourneyRecord identifiers are required")
        if self.demand_weight <= 0:
            raise ValueError("demand_weight must be positive and empirically supported")
        numeric = (
            self.walk_min,
            self.wait_min,
            self.in_vehicle_min,
            self.transfer_walk_min,
            self.transfer_wait_min,
            self.missed_connection_cost_min,
        )
        if any(value < 0 for value in numeric) or self.transfers < 0:
            raise ValueError("Journey times/counts cannot be negative")
        if not 0.0 <= self.missed_connection_probability <= 1.0:
            raise ValueError("missed_connection_probability must be within [0,1]")
        status = self.evidence_status.strip().upper()
        if status in FORBIDDEN_EVIDENCE or status not in VALID_EVIDENCE:
            raise ValueError(f"JourneyRecord has unusable evidence status: {self.evidence_status}")


def generalised_journey_time(record: JourneyRecord, weights: BehaviouralWeights) -> float:
    return (
        record.in_vehicle_min
        + weights.walk_weight * (record.walk_min + record.transfer_walk_min)
        + weights.wait_weight * (record.wait_min + record.transfer_wait_min)
        + weights.transfer_penalty_min * record.transfers
        + weights.missed_connection_cost_multiplier
        * record.missed_connection_probability
        * record.missed_connection_cost_min
    )


@dataclass(frozen=True)
class JourneyComparison:
    sensitivity_id: str
    demand_weighted_gjt_improvement_min: float
    municipal_gjt_improvement_min: Mapping[str, float]
    worst_municipality_gjt_improvement_min: float
    candidate_weighted_missed_connection_probability: float
    demand_weight_sum: float
    journey_count: int


def compare_weighted_journeys(
    baseline: Sequence[JourneyRecord],
    candidate: Sequence[JourneyRecord],
    weights: BehaviouralWeights,
) -> JourneyComparison:
    base = {row.journey_key: row for row in baseline}
    cand = {row.journey_key: row for row in candidate}
    if not base or set(base) != set(cand):
        raise ValueError("Baseline and candidate must contain the same non-empty journey_key universe")

    total_weight = 0.0
    improvement_sum = 0.0
    missed_sum = 0.0
    municipal_num: dict[str, float] = {}
    municipal_den: dict[str, float] = {}

    for key in sorted(base):
        left = base[key]
        right = cand[key]
        if left.layer != right.layer or left.origin_municipality != right.origin_municipality:
            raise ValueError(f"Journey semantics differ for {key}")
        if abs(left.demand_weight - right.demand_weight) > 1e-9:
            raise ValueError(f"Demand weight differs between baseline/candidate for {key}")
        weight = left.demand_weight
        improvement = generalised_journey_time(left, weights) - generalised_journey_time(right, weights)
        total_weight += weight
        improvement_sum += weight * improvement
        missed_sum += weight * right.missed_connection_probability
        municipality = left.origin_municipality
        municipal_num[municipality] = municipal_num.get(municipality, 0.0) + weight * improvement
        municipal_den[municipality] = municipal_den.get(municipality, 0.0) + weight

    municipal = {
        name: municipal_num[name] / municipal_den[name]
        for name in sorted(municipal_num)
    }
    return JourneyComparison(
        sensitivity_id=weights.sensitivity_id,
        demand_weighted_gjt_improvement_min=improvement_sum / total_weight,
        municipal_gjt_improvement_min=municipal,
        worst_municipality_gjt_improvement_min=min(municipal.values()),
        candidate_weighted_missed_connection_probability=missed_sum / total_weight,
        demand_weight_sum=total_weight,
        journey_count=len(base),
    )


def to_sensitivity_result(
    *,
    scenario_id: str,
    comparison: JourneyComparison,
) -> SensitivityResult:
    return SensitivityResult(
        scenario_id=scenario_id,
        sensitivity_id=comparison.sensitivity_id,
        demand_weighted_gjt_improvement_min=comparison.demand_weighted_gjt_improvement_min,
        worst_municipality_utility_change_min=comparison.worst_municipality_gjt_improvement_min,
        missed_connection_probability=comparison.candidate_weighted_missed_connection_probability,
    )


@dataclass(frozen=True)
class PopulationAccessRecord:
    cell_id: str
    municipality: str
    population: float
    walk_min_to_useful_stop: float
    evidence_status: str = "DERIVED"

    def __post_init__(self) -> None:
        if not self.cell_id or not self.municipality:
            raise ValueError("PopulationAccessRecord identifiers are required")
        if self.population < 0 or self.walk_min_to_useful_stop < 0:
            raise ValueError("Population/walking time cannot be negative")
        status = self.evidence_status.strip().upper()
        if status in FORBIDDEN_EVIDENCE or status not in VALID_EVIDENCE:
            raise ValueError(f"PopulationAccessRecord has unusable evidence status: {self.evidence_status}")


def population_access_summary(
    rows: Sequence[PopulationAccessRecord],
    *,
    thresholds_min: Sequence[float] = (5.0, 8.0, 10.0, 12.0),
) -> list[dict[str, float | str]]:
    if not rows:
        raise ValueError("Population access rows cannot be empty")
    thresholds = sorted({float(value) for value in thresholds_min if value >= 0})
    if not thresholds:
        raise ValueError("At least one non-negative threshold is required")

    municipalities = sorted({row.municipality for row in rows})
    groups: list[tuple[str, list[PopulationAccessRecord]]] = [("ALL", list(rows))]
    groups.extend((name, [row for row in rows if row.municipality == name]) for name in municipalities)

    output: list[dict[str, float | str]] = []
    for municipality, group in groups:
        total = sum(row.population for row in group)
        for threshold in thresholds:
            served = sum(
                row.population for row in group
                if row.walk_min_to_useful_stop <= threshold
            )
            output.append(
                {
                    "municipality": municipality,
                    "threshold_min": threshold,
                    "population_total": total,
                    "population_served": served,
                    "population_served_share": served / total if total > 0 else 0.0,
                }
            )
    return output


@dataclass(frozen=True)
class OpportunityAccessRecord:
    cell_id: str
    municipality: str
    opportunity_type: str
    population: float
    travel_time_min: float
    evidence_status: str = "DERIVED"

    def __post_init__(self) -> None:
        if not self.cell_id or not self.municipality or not self.opportunity_type:
            raise ValueError("OpportunityAccessRecord identifiers are required")
        if self.population < 0 or self.travel_time_min < 0:
            raise ValueError("Population/travel time cannot be negative")
        status = self.evidence_status.strip().upper()
        if status in FORBIDDEN_EVIDENCE or status not in VALID_EVIDENCE:
            raise ValueError(f"OpportunityAccessRecord has unusable evidence status: {self.evidence_status}")


def opportunity_access_summary(
    rows: Sequence[OpportunityAccessRecord],
    *,
    thresholds_min: Sequence[float],
) -> list[dict[str, float | str]]:
    """Report opportunity accessibility separately from demand-weighted utility."""
    if not rows:
        raise ValueError("Opportunity access rows cannot be empty")
    thresholds = sorted({float(value) for value in thresholds_min if value >= 0})
    if not thresholds:
        raise ValueError("At least one non-negative threshold is required")

    output: list[dict[str, float | str]] = []
    types = sorted({row.opportunity_type for row in rows})
    for opportunity_type in types:
        subset = [row for row in rows if row.opportunity_type == opportunity_type]
        total = sum(row.population for row in subset)
        for threshold in thresholds:
            reached = sum(row.population for row in subset if row.travel_time_min <= threshold)
            output.append(
                {
                    "opportunity_type": opportunity_type,
                    "threshold_min": threshold,
                    "population_total": total,
                    "population_reached": reached,
                    "population_reached_share": reached / total if total > 0 else 0.0,
                }
            )
    return output


def build_hard_constraints(
    *,
    summary: OperationalSummary,
    road_integrity: bool,
    budget_km: float,
    fleet_cap: int,
    minimum_recovery_min: float,
    territorial_non_regression: bool,
    upstream_evidence_valid: bool,
) -> HardConstraintResult:
    if budget_km <= 0 or fleet_cap <= 0 or minimum_recovery_min < 0:
        raise ValueError("Invalid hard-constraint thresholds")
    return HardConstraintResult(
        road_integrity=bool(road_integrity),
        within_budget=summary.annual_bus_km <= budget_km,
        fleet_cycle_feasible=summary.max_active_vehicles <= fleet_cap,
        recovery_feasible=summary.min_recovery_min >= minimum_recovery_min,
        evidence_valid=bool(summary.evidence_valid and upstream_evidence_valid),
        territorial_non_regression=bool(territorial_non_regression),
    )


def municipal_non_regression(
    comparison: JourneyComparison,
    *,
    tolerance_min: float = 0.0,
) -> bool:
    """Positive improvement means lower candidate GJT than baseline."""
    if tolerance_min < 0:
        raise ValueError("tolerance_min cannot be negative")
    return comparison.worst_municipality_gjt_improvement_min >= -tolerance_min
