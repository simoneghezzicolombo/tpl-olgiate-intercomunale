"""Exact set-identification kernel for fine-origin feeder-to-S8 access.

The kernel conditions every BUS_TO_RAIL calculation on one fixed frozen S8
rail event. It never rebinds a missed or infeasible itinerary to a later train,
never uses technical vehicle closure as passenger service, and never imputes an
origin departure-time distribution or half-headway wait.
"""
from __future__ import annotations

from dataclasses import dataclass
import itertools
import math
from typing import Mapping, Sequence

HUB_ANCHOR = "rail:S01514"
RAIL_DIRECTIONS = ("LECCO", "MILANO")
EPS = 1e-9


@dataclass(frozen=True)
class SensitivityCase:
    case_id: str
    station_transfer_walk_min: float
    bus_ivt_weight: float
    walk_weight: float
    wait_weight: float
    transfer_penalty_min: float
    bound_side: str

    def validate(self) -> None:
        vals = (
            self.station_transfer_walk_min,
            self.bus_ivt_weight,
            self.walk_weight,
            self.wait_weight,
            self.transfer_penalty_min,
        )
        if not all(math.isfinite(v) for v in vals):
            raise ValueError("Sensitivity values must be finite")
        if self.station_transfer_walk_min <= 0:
            raise ValueError("Station transfer walk must be positive")
        if min(self.bus_ivt_weight, self.walk_weight, self.wait_weight, self.transfer_penalty_min) <= 0:
            raise ValueError("Generalized-cost coefficients must be positive")
        if self.bound_side not in {"LOW", "HIGH"}:
            raise ValueError("bound_side must be LOW or HIGH")


@dataclass(frozen=True)
class AnchorOccurrence:
    anchor_id: str
    cumulative_from_route_start_min: float
    next_public_hub_cumulative_min: float

    @property
    def bus_ivt_to_hub_min(self) -> float:
        return self.next_public_hub_cumulative_min - self.cumulative_from_route_start_min

    def validate(self) -> None:
        if not self.anchor_id or self.anchor_id == HUB_ANCHOR:
            raise ValueError("Anchor occurrence must be a non-hub public anchor")
        if not math.isfinite(self.cumulative_from_route_start_min) or self.cumulative_from_route_start_min < 0:
            raise ValueError("Invalid cumulative route time")
        if not math.isfinite(self.next_public_hub_cumulative_min):
            raise ValueError("Invalid next-hub cumulative time")
        if self.bus_ivt_to_hub_min <= 0:
            raise ValueError("BUS_TO_RAIL IVT must be positive")


@dataclass(frozen=True)
class RailDeparture:
    event_id: str
    direction: str
    departure_min: float

    def validate(self) -> None:
        if not self.event_id:
            raise ValueError("Rail event id is required")
        if self.direction not in RAIL_DIRECTIONS:
            raise ValueError("Unexpected rail direction")
        if not math.isfinite(self.departure_min):
            raise ValueError("Rail departure must be finite")


@dataclass(frozen=True)
class BusOpportunity:
    anchor_id: str
    route_id: str
    trip_departure_min: float
    bus_hub_arrival_min: float
    bus_ivt_min: float

    def validate(self) -> None:
        if not self.anchor_id or self.anchor_id == HUB_ANCHOR or not self.route_id:
            raise ValueError("Invalid bus opportunity identity")
        vals = (self.trip_departure_min, self.bus_hub_arrival_min, self.bus_ivt_min)
        if not all(math.isfinite(v) for v in vals):
            raise ValueError("Bus opportunity times must be finite")
        if self.bus_ivt_min <= 0 or self.bus_hub_arrival_min <= self.trip_departure_min:
            raise ValueError("Invalid bus opportunity timing")


@dataclass(frozen=True)
class FixedEventComponent:
    anchor_id: str
    route_id: str
    trip_departure_min: float
    bus_hub_arrival_min: float
    bus_ivt_min: float
    rail_event_id: str
    rail_departure_min: float
    exact_transfer_wait_min: float
    base_cost_without_access_walk: float


@dataclass(frozen=True)
class ItineraryWitness:
    mode: str
    cost: float
    anchor_id: str = ""
    route_id: str = ""
    trip_departure_min: float | None = None
    bus_hub_arrival_min: float | None = None
    rail_event_id: str = ""
    rail_departure_min: float | None = None
    access_walk_min: float | None = None
    bus_ivt_min: float | None = None
    station_transfer_walk_min: float | None = None
    exact_transfer_wait_min: float | None = None
    sensitivity_case_id: str = ""


def strict_bool(value: object) -> bool:
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"Expected explicit boolean, got {value!r}")


def build_public_to_hub_occurrences(
    anchors: Sequence[str],
    leg_runtime: Mapping[tuple[str, str], float],
    *,
    bus_to_rail_passenger_event_supported: bool,
) -> tuple[AnchorOccurrence, ...]:
    """Return public non-hub anchors with a later explicit public hub.

    Technical vehicle closures are never present in this passenger path. A route
    without certified BUS_TO_RAIL passenger support yields no occurrences.
    """
    if not anchors or anchors[0] != HUB_ANCHOR:
        raise ValueError("Public route must start at the certified rail hub")
    if not bus_to_rail_passenger_event_supported:
        return ()
    cumulative = [0.0]
    for a, b in zip(anchors[:-1], anchors[1:]):
        value = float(leg_runtime[(str(a), str(b))])
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"Invalid public leg runtime {a}->{b}")
        cumulative.append(cumulative[-1] + value)
    next_hub_index: list[int | None] = [None] * len(anchors)
    upcoming: int | None = None
    for i in range(len(anchors) - 1, -1, -1):
        if str(anchors[i]) == HUB_ANCHOR:
            upcoming = i
        next_hub_index[i] = upcoming
    out: list[AnchorOccurrence] = []
    for i, anchor in enumerate(anchors):
        if str(anchor) == HUB_ANCHOR:
            continue
        j = next_hub_index[i]
        if j is None or j <= i:
            continue
        occ = AnchorOccurrence(
            anchor_id=str(anchor),
            cumulative_from_route_start_min=cumulative[i],
            next_public_hub_cumulative_min=cumulative[j],
        )
        occ.validate()
        out.append(occ)
    return tuple(out)


def build_timetable_bus_opportunities(
    route_departures: Mapping[str, Sequence[float]],
    route_occurrences: Mapping[str, Sequence[AnchorOccurrence]],
    *,
    span_start_min: float,
    span_end_min: float,
) -> dict[str, tuple[BusOpportunity, ...]]:
    """Materialise passenger BUS_TO_RAIL opportunities with end-exclusive span.

    A physical trip may continue after the span for vehicle blocking, but a hub
    return outside ``[span_start, span_end)`` is not a passenger transfer source.
    """
    if not (math.isfinite(span_start_min) and math.isfinite(span_end_min) and span_start_min < span_end_min):
        raise ValueError("Invalid service span")
    grouped: dict[str, list[BusOpportunity]] = {}
    for route_id in sorted(route_departures):
        occurrences = tuple(route_occurrences.get(route_id, ()))
        for occ in occurrences:
            occ.validate()
            for departure in route_departures[route_id]:
                dep = float(departure)
                hub = dep + occ.next_public_hub_cumulative_min
                if not (span_start_min <= hub < span_end_min):
                    continue
                item = BusOpportunity(
                    anchor_id=occ.anchor_id,
                    route_id=str(route_id),
                    trip_departure_min=dep,
                    bus_hub_arrival_min=hub,
                    bus_ivt_min=occ.bus_ivt_to_hub_min,
                )
                item.validate()
                grouped.setdefault(item.anchor_id, []).append(item)
    return {
        anchor: tuple(sorted(rows, key=lambda x: (x.bus_hub_arrival_min, x.route_id, x.trip_departure_min, x.bus_ivt_min)))
        for anchor, rows in sorted(grouped.items())
    }


def bus_generalized_cost(
    *,
    access_walk_min: float,
    opportunity: BusOpportunity,
    rail_event: RailDeparture,
    case: SensitivityCase,
) -> tuple[float, float] | None:
    """Cost to one fixed rail event, excluding any origin bus wait.

    ``None`` means this bus opportunity cannot catch the fixed event. The helper
    never searches for or rebinds to another train.
    """
    case.validate()
    opportunity.validate()
    rail_event.validate()
    if access_walk_min < 0 or not math.isfinite(access_walk_min):
        raise ValueError("Invalid access walk")
    ready = opportunity.bus_hub_arrival_min + case.station_transfer_walk_min
    if ready > rail_event.departure_min + EPS:
        return None
    wait = max(0.0, rail_event.departure_min - ready)
    cost = (
        case.bus_ivt_weight * opportunity.bus_ivt_min
        + case.walk_weight * (float(access_walk_min) + case.station_transfer_walk_min)
        + case.wait_weight * wait
        + case.transfer_penalty_min
    )
    return cost, wait


def direct_walk_generalized_cost(*, hub_walk_min: float, case: SensitivityCase) -> float:
    """Certified direct rail-anchor access inherited from EX_039 catchment."""
    case.validate()
    if not math.isfinite(hub_walk_min) or hub_walk_min < 0:
        raise ValueError("Invalid direct hub walk")
    return case.walk_weight * hub_walk_min


def fixed_event_anchor_components(
    opportunities_by_anchor: Mapping[str, Sequence[BusOpportunity]],
    rail_events: Sequence[RailDeparture],
    case: SensitivityCase,
) -> dict[str, dict[str, FixedEventComponent]]:
    """Exact optimized anchor components for every fixed rail event.

    For fixed sensitivity coefficients, the event-dependent term is common to
    all feasible opportunities at an anchor. As events progress in time, the
    feasible opportunity set only expands. Maintaining the best eligible
    ``bus_weight*IVT - wait_weight*hub_arrival`` is therefore algebraically
    identical to brute-force enumeration of all feasible opportunities.
    """
    case.validate()
    events = tuple(sorted(rail_events, key=lambda e: (e.departure_min, e.event_id)))
    for event in events:
        event.validate()
    if len({e.event_id for e in events}) != len(events):
        raise ValueError("Duplicate rail event id")
    result: dict[str, dict[str, FixedEventComponent]] = {e.event_id: {} for e in events}
    for anchor in sorted(opportunities_by_anchor):
        rows = tuple(sorted(opportunities_by_anchor[anchor], key=lambda x: (x.bus_hub_arrival_min, x.route_id, x.trip_departure_min, x.bus_ivt_min)))
        for row in rows:
            row.validate()
            if row.anchor_id != anchor:
                raise ValueError("Opportunity grouped under wrong anchor")
        pointer = 0
        best_key: tuple[float, str, float, float] | None = None
        best: BusOpportunity | None = None
        for event in events:
            threshold = event.departure_min - case.station_transfer_walk_min
            while pointer < len(rows) and rows[pointer].bus_hub_arrival_min <= threshold + EPS:
                candidate = rows[pointer]
                static = case.bus_ivt_weight * candidate.bus_ivt_min - case.wait_weight * candidate.bus_hub_arrival_min
                key = (static, candidate.route_id, candidate.trip_departure_min, candidate.bus_hub_arrival_min)
                if best_key is None or key < best_key:
                    best_key = key
                    best = candidate
                pointer += 1
            if best is None:
                continue
            evaluated = bus_generalized_cost(access_walk_min=0.0, opportunity=best, rail_event=event, case=case)
            if evaluated is None:
                raise AssertionError("Incremental fixed-event selector admitted infeasible opportunity")
            cost, wait = evaluated
            result[event.event_id][anchor] = FixedEventComponent(
                anchor_id=anchor,
                route_id=best.route_id,
                trip_departure_min=best.trip_departure_min,
                bus_hub_arrival_min=best.bus_hub_arrival_min,
                bus_ivt_min=best.bus_ivt_min,
                rail_event_id=event.event_id,
                rail_departure_min=event.departure_min,
                exact_transfer_wait_min=wait,
                base_cost_without_access_walk=cost,
            )
    return result


def brute_force_fixed_event_anchor_components(
    opportunities_by_anchor: Mapping[str, Sequence[BusOpportunity]],
    rail_events: Sequence[RailDeparture],
    case: SensitivityCase,
) -> dict[str, dict[str, FixedEventComponent]]:
    """Independent all-opportunity oracle used by tests/red-team proofs."""
    out: dict[str, dict[str, FixedEventComponent]] = {}
    for event in rail_events:
        event.validate()
        per_anchor: dict[str, FixedEventComponent] = {}
        for anchor in sorted(opportunities_by_anchor):
            best_key = None
            best_component = None
            for opportunity in opportunities_by_anchor[anchor]:
                evaluated = bus_generalized_cost(access_walk_min=0.0, opportunity=opportunity, rail_event=event, case=case)
                if evaluated is None:
                    continue
                cost, wait = evaluated
                key = (cost, opportunity.route_id, opportunity.trip_departure_min, opportunity.bus_hub_arrival_min)
                if best_key is None or key < best_key:
                    best_key = key
                    best_component = FixedEventComponent(
                        anchor_id=anchor,
                        route_id=opportunity.route_id,
                        trip_departure_min=opportunity.trip_departure_min,
                        bus_hub_arrival_min=opportunity.bus_hub_arrival_min,
                        bus_ivt_min=opportunity.bus_ivt_min,
                        rail_event_id=event.event_id,
                        rail_departure_min=event.departure_min,
                        exact_transfer_wait_min=wait,
                        base_cost_without_access_walk=cost,
                    )
            if best_component is not None:
                per_anchor[anchor] = best_component
        out[event.event_id] = per_anchor
    return out


def reduced_sensitivity_cases(parameter_grid: Mapping[str, Sequence[float]]) -> tuple[SensitivityCase, ...]:
    """Exact six-case envelope reduction of the certified 243-case grid.

    Station-transfer walk is exhaustively enumerated because it changes temporal
    feasibility. Conditional on a fixed event and station walk, feasibility does
    not depend on the remaining four coefficients. Every feasible itinerary cost
    is coordinate-wise nondecreasing in those positive coefficients over
    non-negative components. Minimum over itineraries, then minimum/maximum over
    admissible origins, preserves that monotonicity. Therefore only all-low and
    all-high coefficient corners are required for each station-walk value.
    """
    required = (
        "bus_ivt_weight", "walk_weight", "wait_weight",
        "transfer_penalty_min", "station_transfer_walk_min",
    )
    grid: dict[str, tuple[float, ...]] = {}
    for key in required:
        vals = tuple(float(v) for v in parameter_grid.get(key, ()))
        if not vals or any(not math.isfinite(v) or v <= 0 for v in vals):
            raise ValueError(f"Invalid sensitivity grid {key}")
        grid[key] = vals
    out: list[SensitivityCase] = []
    for station_walk in sorted(set(grid["station_transfer_walk_min"])):
        for side in ("LOW", "HIGH"):
            chooser = min if side == "LOW" else max
            case = SensitivityCase(
                case_id=f"{side}_SW{station_walk:g}",
                station_transfer_walk_min=station_walk,
                bus_ivt_weight=chooser(grid["bus_ivt_weight"]),
                walk_weight=chooser(grid["walk_weight"]),
                wait_weight=chooser(grid["wait_weight"]),
                transfer_penalty_min=chooser(grid["transfer_penalty_min"]),
                bound_side=side,
            )
            case.validate()
            out.append(case)
    return tuple(out)


def full_sensitivity_cases(parameter_grid: Mapping[str, Sequence[float]]) -> tuple[SensitivityCase, ...]:
    """Full factorial oracle helper. It is never used as a score or weighting."""
    keys = (
        "bus_ivt_weight", "walk_weight", "wait_weight",
        "transfer_penalty_min", "station_transfer_walk_min",
    )
    vals = [tuple(float(v) for v in parameter_grid[k]) for k in keys]
    out = []
    for i, combo in enumerate(itertools.product(*vals)):
        row = dict(zip(keys, combo))
        case = SensitivityCase(
            case_id=f"FULL_{i:03d}",
            station_transfer_walk_min=row["station_transfer_walk_min"],
            bus_ivt_weight=row["bus_ivt_weight"],
            walk_weight=row["walk_weight"],
            wait_weight=row["wait_weight"],
            transfer_penalty_min=row["transfer_penalty_min"],
            bound_side="LOW",
        )
        case.validate()
        out.append(case)
    return tuple(out)
