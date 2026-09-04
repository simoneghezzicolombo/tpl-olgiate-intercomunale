"""Exact set-identification kernel for fine-origin feeder-to-S8 access.

This module deliberately does not estimate expected daily GJT. It provides
pure helpers for exact public-route geometry, exact train matching and an exact
reduction of the certified 243-case generalized-access sensitivity grid.
"""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
import itertools
import math
from typing import Mapping, Sequence

HUB_ANCHOR = "rail:S01514"
RAIL_DIRECTIONS = ("LECCO", "MILANO")


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
    """Return every public non-hub anchor that has a later explicit public hub.

    Technical vehicle closures are not present in ``anchors`` and cannot create
    a passenger return. If the certified route flag says BUS_TO_RAIL is not
    public, this function returns no occurrences even if a vehicle closure exists
    elsewhere in the cycle representation.
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


def first_feasible_rail_departure(
    departures: Sequence[RailDeparture],
    *,
    bus_hub_arrival_min: float,
    station_transfer_walk_min: float,
) -> RailDeparture | None:
    """Return the first explicit rail departure catchable after station walk."""
    if not departures:
        return None
    values = [d.departure_min for d in departures]
    threshold = float(bus_hub_arrival_min) + float(station_transfer_walk_min)
    index = bisect_left(values, threshold - 1e-12)
    return None if index >= len(departures) else departures[index]


def bus_generalized_cost(
    *,
    access_walk_min: float,
    bus_ivt_min: float,
    bus_hub_arrival_min: float,
    rail_departure_min: float,
    case: SensitivityCase,
) -> tuple[float, float]:
    """Conditional feeder-to-S8 cost, explicitly excluding origin bus wait."""
    case.validate()
    values = (access_walk_min, bus_ivt_min, bus_hub_arrival_min, rail_departure_min)
    if not all(math.isfinite(float(v)) for v in values):
        raise ValueError("Itinerary components must be finite")
    if access_walk_min < 0 or bus_ivt_min <= 0:
        raise ValueError("Invalid access walk or bus IVT")
    wait_after_station_walk = (
        float(rail_departure_min)
        - float(bus_hub_arrival_min)
        - case.station_transfer_walk_min
    )
    if wait_after_station_walk < -1e-9:
        raise ValueError("Selected rail departure is not catchable")
    wait_after_station_walk = max(0.0, wait_after_station_walk)
    cost = (
        case.bus_ivt_weight * float(bus_ivt_min)
        + case.walk_weight * (float(access_walk_min) + case.station_transfer_walk_min)
        + case.wait_weight * wait_after_station_walk
        + case.transfer_penalty_min
    )
    return cost, wait_after_station_walk


def direct_walk_generalized_cost(*, hub_walk_min: float, case: SensitivityCase) -> float:
    """Certified direct rail-anchor access inherited from EX_039 catchment.

    The Access Equity bridge already treats the station walking catchment as
    pedestrian access to ``rail:S01514``. No bus transfer penalty or bus waiting
    is added to this candidate-invariant direct option.
    """
    case.validate()
    if not math.isfinite(hub_walk_min) or hub_walk_min < 0:
        raise ValueError("Invalid direct hub walk")
    return case.walk_weight * hub_walk_min


def reduced_sensitivity_cases(parameter_grid: Mapping[str, Sequence[float]]) -> tuple[SensitivityCase, ...]:
    """Exact six-case reduction of the certified 243-case grid.

    Station-transfer walk is enumerated exhaustively because it changes both
    feasibility and train target. Conditional on a fixed station walk, the four
    remaining generalized-cost coefficients multiply/add non-negative terms, so
    the minimum of itinerary costs is monotone in every coefficient. Hence the
    full-grid lower and upper envelopes occur at the all-low/all-high coefficient
    corners for one of the three station-walk values.
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
    """Full factorial helper used only by tests/proofs, never as a hidden score."""
    keys = (
        "bus_ivt_weight", "walk_weight", "wait_weight",
        "transfer_penalty_min", "station_transfer_walk_min",
    )
    vals = [tuple(float(v) for v in parameter_grid[k]) for k in keys]
    out = []
    for i, combo in enumerate(itertools.product(*vals)):
        row = dict(zip(keys, combo))
        out.append(SensitivityCase(
            case_id=f"FULL_{i:03d}",
            station_transfer_walk_min=row["station_transfer_walk_min"],
            bus_ivt_weight=row["bus_ivt_weight"],
            walk_weight=row["walk_weight"],
            wait_weight=row["wait_weight"],
            transfer_penalty_min=row["transfer_penalty_min"],
            bound_side="LOW",
        ))
    return tuple(out)


def exact_envelope_from_case_costs(
    costs_by_case: Mapping[str, Sequence[float]],
    cases: Sequence[SensitivityCase],
) -> tuple[float | None, float | None, bool]:
    """Envelope over unknown origin and the certified sensitivity grid.

    ``math.inf`` represents an admissible origin that cannot use the timetable
    under that station-walk case. Any such admissible state makes the upper set
    bound unbounded. The lower bound is the minimum finite low-corner cost.
    """
    low_values: list[float] = []
    high_values: list[float] = []
    unbounded = False
    for case in cases:
        vals = tuple(float(v) for v in costs_by_case[case.case_id])
        finite = [v for v in vals if math.isfinite(v)]
        if case.bound_side == "LOW":
            low_values.extend(finite)
        else:
            if len(finite) != len(vals):
                unbounded = True
            high_values.extend(finite)
    lower = min(low_values) if low_values else None
    upper = None if unbounded or not high_values else max(high_values)
    return lower, upper, unbounded
