"""Deterministic Phase 2 network-optimisation core.

This module contains no territorial assumptions and no embedded project outputs.
It consumes validated Phase 2 inputs produced by other workstreams and provides:

- a reduced path-matrix contract;
- deterministic structural scenario generation across multiple topology families;
- stable scenario IDs and duplicate suppression;
- service-policy enumeration from explicit caller-supplied grids;
- hard-constraint eligibility;
- robust passenger-utility aggregation across sensitivity runs;
- lexicographic finalist selection without an arbitrary composite score;
- budget/utility frontier helpers.

No random sampling is used. No coordinates, route lengths, demand volumes, headways,
service spans or topology preferences are hard-coded as evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from itertools import combinations, permutations, product
import json
from statistics import median
from typing import Callable, Iterable, Mapping, Sequence


class TopologyFamily(str, Enum):
    SINGLE_COMPACT_LOOP = "single_compact_loop"
    TWO_INDEPENDENT_LOOPS = "two_independent_loops"
    BIDIRECTIONAL_LOOP_PAIR = "bidirectional_loop_pair"
    INTERLINED_FIGURE8 = "interlined_figure8"
    TWO_RADIAL_FEEDERS = "two_radial_out_and_back_feeders"
    MULTIPLE_SHORT_RADIALS = "multiple_short_radials"
    TRUNK_BRANCHES = "trunk_plus_branches"
    SHORT_TURN_OVERLAY = "short_turn_overlay"
    SCHEDULED_EXTENSIONS = "scheduled_extensions"
    HYBRID_INTERLINED = "hybrid_interlined"
    BLANK_SLATE = "blank_slate"


@dataclass(frozen=True)
class PathLeg:
    origin: str
    destination: str
    distance_km: float
    runtime_min: float
    uncertainty: str = "RESOLVED"

    def __post_init__(self) -> None:
        if not self.origin or not self.destination:
            raise ValueError("PathLeg requires non-empty endpoints")
        if self.origin == self.destination:
            raise ValueError("PathLeg endpoints must differ")
        if self.distance_km <= 0 or self.runtime_min <= 0:
            raise ValueError("PathLeg requires positive distance and runtime")
        if self.uncertainty not in {"RESOLVED", "QUANTIFIED", "UNKNOWN"}:
            raise ValueError("Invalid path uncertainty status")


class ReducedPathMatrix:
    """Directed, validated anchor-to-anchor path matrix."""

    def __init__(self, legs: Iterable[PathLeg]) -> None:
        self._legs: dict[tuple[str, str], PathLeg] = {}
        for leg in legs:
            key = (leg.origin, leg.destination)
            if key in self._legs:
                raise ValueError(f"Duplicate directed path leg: {key}")
            self._legs[key] = leg
        if not self._legs:
            raise ValueError("ReducedPathMatrix cannot be empty")

    def has_leg(self, origin: str, destination: str) -> bool:
        return (origin, destination) in self._legs

    def require_leg(self, origin: str, destination: str) -> PathLeg:
        try:
            return self._legs[(origin, destination)]
        except KeyError as exc:
            raise ValueError(f"Missing directed path leg {origin!r}->{destination!r}") from exc

    def route_metrics(self, anchors: Sequence[str]) -> tuple[float, float, str]:
        if len(anchors) < 2:
            raise ValueError("A route requires at least two anchors")
        distance = 0.0
        runtime = 0.0
        statuses: list[str] = []
        order = {"RESOLVED": 0, "QUANTIFIED": 1, "UNKNOWN": 2}
        for origin, destination in zip(anchors[:-1], anchors[1:]):
            leg = self.require_leg(origin, destination)
            distance += leg.distance_km
            runtime += leg.runtime_min
            statuses.append(leg.uncertainty)
        uncertainty = max(statuses, key=order.__getitem__)
        return distance, runtime, uncertainty


@dataclass(frozen=True)
class RoutePattern:
    anchors: tuple[str, ...]
    public_label: str = ""

    def __post_init__(self) -> None:
        if len(self.anchors) < 2:
            raise ValueError("RoutePattern requires at least two anchors")
        if any(not anchor for anchor in self.anchors):
            raise ValueError("RoutePattern contains an empty anchor")
        if any(a == b for a, b in zip(self.anchors[:-1], self.anchors[1:])):
            raise ValueError("RoutePattern cannot repeat an anchor consecutively")


@dataclass(frozen=True)
class ScenarioSkeleton:
    family: TopologyFamily
    routes: tuple[RoutePattern, ...]
    optional_extensions: tuple[RoutePattern, ...] = ()
    seed_name: str | None = None

    def __post_init__(self) -> None:
        if not self.routes:
            raise ValueError("ScenarioSkeleton requires at least one public route")

    def canonical_payload(self) -> dict:
        route_payload = sorted(
            [{"anchors": list(route.anchors), "label": route.public_label} for route in self.routes],
            key=lambda row: (row["anchors"], row["label"]),
        )
        extension_payload = sorted(
            [{"anchors": list(route.anchors), "label": route.public_label} for route in self.optional_extensions],
            key=lambda row: (row["anchors"], row["label"]),
        )
        return {
            "family": self.family.value,
            "routes": route_payload,
            "optional_extensions": extension_payload,
            "seed_name": self.seed_name,
        }

    @property
    def scenario_id(self) -> str:
        raw = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return f"P2_{sha256(raw.encode('utf-8')).hexdigest()[:16]}"

    def validate_paths(self, matrix: ReducedPathMatrix) -> None:
        for route in self.routes + self.optional_extensions:
            matrix.route_metrics(route.anchors)


@dataclass(frozen=True)
class ServicePolicy:
    peak_headway_min: int
    offpeak_headway_min: int
    span_start_min: int
    span_end_min: int
    recovery_min: float
    active_vehicles: int
    annual_service_days: float
    extension_share: float = 0.0

    def __post_init__(self) -> None:
        if self.peak_headway_min <= 0 or self.offpeak_headway_min <= 0:
            raise ValueError("Headways must be positive")
        if not 0 <= self.span_start_min < self.span_end_min <= 24 * 60:
            raise ValueError("Invalid service span")
        if self.recovery_min < 0 or self.active_vehicles <= 0 or self.annual_service_days <= 0:
            raise ValueError("Invalid operational policy")
        if not 0.0 <= self.extension_share <= 1.0:
            raise ValueError("extension_share must be within [0, 1]")

    @property
    def policy_id(self) -> str:
        raw = json.dumps(self.__dict__, sort_keys=True, separators=(",", ":"))
        return f"SP_{sha256(raw.encode('utf-8')).hexdigest()[:12]}"


def enumerate_service_policies(
    *,
    peak_headways: Sequence[int],
    offpeak_headways: Sequence[int],
    spans: Sequence[tuple[int, int]],
    recovery_minutes: Sequence[float],
    active_vehicles: Sequence[int],
    annual_service_days: Sequence[float],
    extension_shares: Sequence[float] = (0.0,),
) -> list[ServicePolicy]:
    """Enumerate a caller-declared policy grid without hidden defaults."""
    policies = {
        ServicePolicy(*values)
        for values in product(
            peak_headways,
            offpeak_headways,
            (start for start, _ in spans),
            (end for _, end in spans),
            recovery_minutes,
            active_vehicles,
            annual_service_days,
            extension_shares,
        )
        if values[2] < values[3]
    }
    # The Cartesian product above would cross unrelated span starts/ends. Rebuild
    # exactly from declared span pairs to preserve the caller's intended grid.
    policies = set()
    for peak, offpeak, span, recovery, fleet, days, ext_share in product(
        peak_headways,
        offpeak_headways,
        spans,
        recovery_minutes,
        active_vehicles,
        annual_service_days,
        extension_shares,
    ):
        policies.add(
            ServicePolicy(
                peak_headway_min=peak,
                offpeak_headway_min=offpeak,
                span_start_min=span[0],
                span_end_min=span[1],
                recovery_min=recovery,
                active_vehicles=fleet,
                annual_service_days=days,
                extension_share=ext_share,
            )
        )
    return sorted(policies, key=lambda item: item.policy_id)


def _valid_route(matrix: ReducedPathMatrix, anchors: Sequence[str]) -> bool:
    if len(anchors) < 2:
        return False
    return all(matrix.has_leg(a, b) for a, b in zip(anchors[:-1], anchors[1:]))


def generate_structural_scenarios(
    *,
    hub: str,
    anchors: Sequence[str],
    matrix: ReducedPathMatrix,
    max_scenarios: int = 100_000,
    max_loop_intermediate_anchors: int = 4,
) -> list[ScenarioSkeleton]:
    """Generate deterministic structural candidates from real supplied anchors.

    This function does not create anchors or path legs. It only recombines the
    validated anchor universe and keeps sequences whose directed legs exist in the
    supplied reduced path matrix. Generation is deliberately deterministic so the
    same inputs produce the same catalog and IDs.
    """
    if not hub:
        raise ValueError("hub is required")
    if max_scenarios <= 0:
        raise ValueError("max_scenarios must be positive")
    unique_anchors = sorted({a for a in anchors if a and a != hub})
    if not unique_anchors:
        raise ValueError("At least one non-hub anchor is required")

    scenarios: dict[str, ScenarioSkeleton] = {}

    def emit(scenario: ScenarioSkeleton) -> bool:
        try:
            scenario.validate_paths(matrix)
        except ValueError:
            return False
        scenarios.setdefault(scenario.scenario_id, scenario)
        return len(scenarios) >= max_scenarios

    # Radials: useful baseline family and building block for interlining.
    valid_radials: list[RoutePattern] = []
    for anchor in unique_anchors:
        route = (hub, anchor, hub)
        if _valid_route(matrix, route):
            pattern = RoutePattern(route)
            valid_radials.append(pattern)
            if emit(ScenarioSkeleton(TopologyFamily.MULTIPLE_SHORT_RADIALS, (pattern,))):
                return list(scenarios.values())

    for left, right in combinations(valid_radials, 2):
        if emit(ScenarioSkeleton(TopologyFamily.TWO_RADIAL_FEEDERS, (left, right))):
            return list(scenarios.values())
        if emit(ScenarioSkeleton(TopologyFamily.HYBRID_INTERLINED, (left, right))):
            return list(scenarios.values())

    # Compact loops and blank-slate closed sequences. Reversal is retained because
    # the path matrix is directed and the two directions may have different costs.
    loops: list[RoutePattern] = []
    max_k = min(max_loop_intermediate_anchors, len(unique_anchors))
    for k in range(2, max_k + 1):
        for ordered in permutations(unique_anchors, k):
            route = (hub, *ordered, hub)
            if not _valid_route(matrix, route):
                continue
            pattern = RoutePattern(route)
            loops.append(pattern)
            if emit(ScenarioSkeleton(TopologyFamily.SINGLE_COMPACT_LOOP, (pattern,))):
                return list(scenarios.values())
            if emit(ScenarioSkeleton(TopologyFamily.BLANK_SLATE, (pattern,))):
                return list(scenarios.values())

    # Pair compatible loops. These families remain distinct because their public
    # service and operating rules differ even when anchor geometry is identical.
    for left, right in combinations(loops, 2):
        left_set = set(left.anchors[1:-1])
        right_set = set(right.anchors[1:-1])
        if left_set & right_set:
            continue
        for family in (
            TopologyFamily.TWO_INDEPENDENT_LOOPS,
            TopologyFamily.INTERLINED_FIGURE8,
        ):
            if emit(ScenarioSkeleton(family, (left, right))):
                return list(scenarios.values())

    # Bidirectional loop pairs are created only when the exact reverse sequence is
    # independently routable on the directed path matrix.
    loop_by_anchors = {loop.anchors: loop for loop in loops}
    for loop in loops:
        reverse = (hub, *reversed(loop.anchors[1:-1]), hub)
        reverse_pattern = loop_by_anchors.get(reverse)
        if reverse_pattern and loop.anchors < reverse_pattern.anchors:
            if emit(ScenarioSkeleton(TopologyFamily.BIDIRECTIONAL_LOOP_PAIR, (loop, reverse_pattern))):
                return list(scenarios.values())

    # Trunk+branches: hub -> shared trunk -> branch endpoints. No branch/trunk
    # membership is assumed; every feasible directed combination is tested.
    for trunk in unique_anchors:
        branches = [a for a in unique_anchors if a != trunk and matrix.has_leg(hub, trunk) and matrix.has_leg(trunk, a)]
        for b1, b2 in combinations(branches, 2):
            routes = (RoutePattern((hub, trunk, b1)), RoutePattern((hub, trunk, b2)))
            if emit(ScenarioSkeleton(TopologyFamily.TRUNK_BRANCHES, routes)):
                return list(scenarios.values())
            if emit(ScenarioSkeleton(TopologyFamily.SHORT_TURN_OVERLAY, routes)):
                return list(scenarios.values())

    # Scheduled extensions remain explicit: a base radial with an extension that
    # is physically routable beyond the outer anchor. The operating share is a
    # later service-policy decision, not a geometry assumption.
    for base in valid_radials:
        outer = base.anchors[1]
        for extension in unique_anchors:
            if extension == outer:
                continue
            ext = (hub, outer, extension, outer, hub)
            if _valid_route(matrix, ext):
                scenario = ScenarioSkeleton(
                    TopologyFamily.SCHEDULED_EXTENSIONS,
                    (base,),
                    optional_extensions=(RoutePattern(ext),),
                )
                if emit(scenario):
                    return list(scenarios.values())

    return list(scenarios.values())


@dataclass(frozen=True)
class HardConstraintResult:
    road_integrity: bool
    within_budget: bool
    fleet_cycle_feasible: bool
    recovery_feasible: bool
    evidence_valid: bool
    territorial_non_regression: bool

    @property
    def eligible(self) -> bool:
        return all(self.__dict__.values())


@dataclass(frozen=True)
class SensitivityResult:
    scenario_id: str
    sensitivity_id: str
    demand_weighted_gjt_improvement_min: float
    worst_municipality_utility_change_min: float
    missed_connection_probability: float

    def __post_init__(self) -> None:
        if not self.scenario_id or not self.sensitivity_id:
            raise ValueError("SensitivityResult IDs are required")
        if not 0.0 <= self.missed_connection_probability <= 1.0:
            raise ValueError("missed_connection_probability must be within [0, 1]")


@dataclass(frozen=True)
class RobustScenarioEvaluation:
    scenario_id: str
    eligible: bool
    median_gjt_improvement_min: float
    lower_quantile_gjt_improvement_min: float
    median_missed_connection_probability: float
    annual_bus_km: float
    public_pattern_complexity: int
    unverified_elements: int
    retained_existing_stops_share: float
    n_sensitivity_runs: int


def _linear_quantile(values: Sequence[float], q: float) -> float:
    ordered = sorted(float(v) for v in values)
    if not ordered:
        raise ValueError("Cannot compute quantile of empty values")
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be within [0, 1]")
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    fraction = pos - lo
    return ordered[lo] * (1 - fraction) + ordered[hi] * fraction


def aggregate_robust_evaluation(
    *,
    scenario_id: str,
    hard_constraints: HardConstraintResult,
    sensitivity_results: Sequence[SensitivityResult],
    annual_bus_km: float,
    public_pattern_complexity: int,
    unverified_elements: int,
    retained_existing_stops_share: float,
    lower_quantile: float = 0.10,
) -> RobustScenarioEvaluation:
    matching = [row for row in sensitivity_results if row.scenario_id == scenario_id]
    if not matching:
        raise ValueError(f"No sensitivity results for {scenario_id}")
    if annual_bus_km <= 0 or public_pattern_complexity <= 0 or unverified_elements < 0:
        raise ValueError("Invalid operational/tie-break metrics")
    if not 0.0 <= retained_existing_stops_share <= 1.0:
        raise ValueError("retained_existing_stops_share must be within [0, 1]")
    gjt = [row.demand_weighted_gjt_improvement_min for row in matching]
    missed = [row.missed_connection_probability for row in matching]
    return RobustScenarioEvaluation(
        scenario_id=scenario_id,
        eligible=hard_constraints.eligible,
        median_gjt_improvement_min=float(median(gjt)),
        lower_quantile_gjt_improvement_min=_linear_quantile(gjt, lower_quantile),
        median_missed_connection_probability=float(median(missed)),
        annual_bus_km=float(annual_bus_km),
        public_pattern_complexity=int(public_pattern_complexity),
        unverified_elements=int(unverified_elements),
        retained_existing_stops_share=float(retained_existing_stops_share),
        n_sensitivity_runs=len(matching),
    )


def select_primary_and_runner_up(
    evaluations: Sequence[RobustScenarioEvaluation],
    *,
    uncertainty_band_min: float,
) -> tuple[RobustScenarioEvaluation, RobustScenarioEvaluation | None, bool]:
    """Apply hard eligibility, robust utility, then explicit lexicographic tie-break.

    Returns (primary, runner_up, tie_break_invoked).
    """
    if uncertainty_band_min < 0:
        raise ValueError("uncertainty_band_min cannot be negative")
    eligible = [row for row in evaluations if row.eligible]
    if not eligible:
        raise ValueError("No eligible Phase 2 scenarios")
    best_median = max(row.median_gjt_improvement_min for row in eligible)
    contenders = [
        row for row in eligible
        if best_median - row.median_gjt_improvement_min <= uncertainty_band_min
    ]

    def tie_key(row: RobustScenarioEvaluation) -> tuple:
        # Specification section 11: reliability, simplicity, lower production,
        # fewer unverified elements, greater continuity.
        return (
            row.median_missed_connection_probability,
            row.public_pattern_complexity,
            row.annual_bus_km,
            row.unverified_elements,
            -row.retained_existing_stops_share,
            -row.lower_quantile_gjt_improvement_min,
            row.scenario_id,
        )

    if len(contenders) > 1:
        ordered_contenders = sorted(contenders, key=tie_key)
        primary = ordered_contenders[0]
        tie_break_invoked = True
    else:
        primary = contenders[0]
        tie_break_invoked = False

    remaining = [row for row in eligible if row.scenario_id != primary.scenario_id]
    if not remaining:
        return primary, None, tie_break_invoked

    second_best_median = max(row.median_gjt_improvement_min for row in remaining)
    second_contenders = [
        row for row in remaining
        if second_best_median - row.median_gjt_improvement_min <= uncertainty_band_min
    ]
    runner_up = sorted(second_contenders, key=tie_key)[0] if len(second_contenders) > 1 else second_contenders[0]
    return primary, runner_up, tie_break_invoked


def budget_utility_frontier(
    evaluations: Sequence[RobustScenarioEvaluation],
    budget_envelopes_km: Sequence[float],
) -> list[dict[str, float | str | None]]:
    """Return the best eligible robust utility achievable at each declared budget."""
    budgets = sorted({float(value) for value in budget_envelopes_km if value > 0})
    if not budgets:
        raise ValueError("At least one positive budget envelope is required")
    rows: list[dict[str, float | str | None]] = []
    previous_utility: float | None = None
    previous_km: float | None = None
    for budget in budgets:
        feasible = [row for row in evaluations if row.eligible and row.annual_bus_km <= budget]
        if not feasible:
            rows.append({
                "budget_km": budget,
                "scenario_id": None,
                "annual_bus_km": None,
                "median_gjt_improvement_min": None,
                "marginal_utility_per_1000_bus_km": None,
            })
            continue
        winner = sorted(
            feasible,
            key=lambda row: (-row.median_gjt_improvement_min, row.annual_bus_km, row.scenario_id),
        )[0]
        marginal = None
        if previous_utility is not None and previous_km is not None and winner.annual_bus_km > previous_km:
            marginal = (
                (winner.median_gjt_improvement_min - previous_utility)
                / (winner.annual_bus_km - previous_km)
                * 1000.0
            )
        rows.append({
            "budget_km": budget,
            "scenario_id": winner.scenario_id,
            "annual_bus_km": winner.annual_bus_km,
            "median_gjt_improvement_min": winner.median_gjt_improvement_min,
            "marginal_utility_per_1000_bus_km": marginal,
        })
        previous_utility = winner.median_gjt_improvement_min
        previous_km = winner.annual_bus_km
    return rows
