"""Demand-weighted S8 transfer-opportunity utility for Phase 2.

This is deliberately narrower than Passenger GJT. It weights the four hub
connection cells by empirical ISTAT 2021 work-destination counts that are
addressable by direct S8 service. It does not infer worker origins, modal share,
walking time, full journey time or a final topology ranking.

A round-trip score is only valid when both BUS_TO_RAIL and RAIL_TO_BUS hub
events are supported by the public-service geometry. Vehicle-only return
closures must never be supplied as passenger BUS_TO_RAIL service.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import mean
from typing import Mapping


CONNECTION_TYPES = ("BUS_TO_RAIL", "RAIL_TO_BUS")
DIRECTIONS = ("LECCO", "MILANO")
FORBIDDEN_SUPPORT_EVIDENCE = {"", "ASSUMED", "INFERRED_FROM_VEHICLE_CLOSURE", "PLACEHOLDER", "INVALIDATED"}


@dataclass(frozen=True)
class WorkDirectionWeights:
    outbound_bus_to_rail: Mapping[str, float]
    return_rail_to_bus: Mapping[str, float]

    def validate(self) -> None:
        for label, values in (
            ("outbound_bus_to_rail", self.outbound_bus_to_rail),
            ("return_rail_to_bus", self.return_rail_to_bus),
        ):
            if set(values) != set(DIRECTIONS):
                raise ValueError(f"{label} must contain exactly {DIRECTIONS}")
            if any(not math.isfinite(float(v)) or float(v) < 0 for v in values.values()):
                raise ValueError(f"{label} weights must be finite and non-negative")
            if sum(float(v) for v in values.values()) <= 0:
                raise ValueError(f"{label} weights must sum positive")
        out_total = sum(float(v) for v in self.outbound_bus_to_rail.values())
        ret_total = sum(float(v) for v in self.return_rail_to_bus.values())
        if not math.isclose(out_total, ret_total, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("Outbound and return demand totals must match")

    @property
    def worker_count(self) -> float:
        self.validate()
        return sum(float(v) for v in self.outbound_bus_to_rail.values())


@dataclass(frozen=True)
class PassengerConnectionSupport:
    """Route/service evidence needed before a round-trip transfer score exists."""

    route_id: str
    bus_to_rail_supported: bool
    rail_to_bus_supported: bool
    evidence_status: str = "DERIVED_FROM_PUBLIC_SERVICE_GEOMETRY"

    def validate_roundtrip(self) -> None:
        if not self.route_id:
            raise ValueError("Passenger connection support requires route_id")
        status = self.evidence_status.strip().upper()
        if status in FORBIDDEN_SUPPORT_EVIDENCE:
            raise ValueError("Passenger connection support has forbidden evidence status")
        if not self.rail_to_bus_supported:
            raise ValueError("RAIL_TO_BUS passenger service is not supported for this route")
        if not self.bus_to_rail_supported:
            raise ValueError(
                "Round-trip transfer utility requires passenger-supported BUS_TO_RAIL service; "
                "a vehicle-only return closure is not sufficient"
            )


@dataclass(frozen=True)
class WeightedTransferUtility:
    route_id: str
    profile_quality: Mapping[str, float]
    worst_profile_quality: float
    mean_profile_quality: float
    best_profile_quality: float
    worker_count: float
    weighted_connection_count: float
    roundtrip_passenger_supported: bool
    support_evidence_status: str


def _parse_profile_cells(profile_cell_quality: Mapping[str, float]) -> dict[str, dict[tuple[str, str], float]]:
    profiles: dict[str, dict[tuple[str, str], float]] = {}
    for raw_key, raw_value in profile_cell_quality.items():
        parts = str(raw_key).split("|")
        if len(parts) != 3:
            raise ValueError(f"Invalid S8 profile cell key {raw_key!r}")
        profile_id, connection_type, direction = parts
        if not profile_id or connection_type not in CONNECTION_TYPES or direction not in DIRECTIONS:
            raise ValueError(f"Invalid S8 profile cell dimensions {raw_key!r}")
        value = float(raw_value)
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError(f"S8 transfer quality outside [0,1] for {raw_key!r}")
        cell = (connection_type, direction)
        bucket = profiles.setdefault(profile_id, {})
        if cell in bucket:
            raise ValueError(f"Duplicate S8 profile cell {raw_key!r}")
        bucket[cell] = value
    expected_cells = {(c, d) for c in CONNECTION_TYPES for d in DIRECTIONS}
    if not profiles:
        raise ValueError("No S8 profile cells supplied")
    for profile_id, cells in profiles.items():
        if set(cells) != expected_cells:
            missing = sorted(expected_cells - set(cells))
            extra = sorted(set(cells) - expected_cells)
            raise ValueError(f"Profile {profile_id} cells incomplete: missing={missing}, extra={extra}")
    return profiles


def weight_transfer_quality(
    profile_cell_quality: Mapping[str, float],
    weights: WorkDirectionWeights,
    support: PassengerConnectionSupport,
) -> WeightedTransferUtility:
    """Weight a fully passenger-supported round-trip hub transfer opportunity.

    Every worker contributes one outbound BUS_TO_RAIL direction and one return
    RAIL_TO_BUS direction. This is a round-trip directional weighting only; it
    makes no claim about daily rail use frequency or modal share. The function
    fails closed when either passenger connection direction is unsupported.
    """
    weights.validate()
    support.validate_roundtrip()
    profiles = _parse_profile_cells(profile_cell_quality)
    worker_count = weights.worker_count
    denominator = 2.0 * worker_count
    profile_quality: dict[str, float] = {}
    for profile_id, cells in profiles.items():
        numerator = 0.0
        for direction in DIRECTIONS:
            numerator += (
                float(weights.outbound_bus_to_rail[direction])
                * cells[("BUS_TO_RAIL", direction)]
            )
            numerator += (
                float(weights.return_rail_to_bus[direction])
                * cells[("RAIL_TO_BUS", direction)]
            )
        profile_quality[profile_id] = numerator / denominator
    values = tuple(profile_quality.values())
    return WeightedTransferUtility(
        route_id=support.route_id,
        profile_quality=dict(sorted(profile_quality.items())),
        worst_profile_quality=min(values),
        mean_profile_quality=mean(values),
        best_profile_quality=max(values),
        worker_count=worker_count,
        weighted_connection_count=denominator,
        roundtrip_passenger_supported=True,
        support_evidence_status=support.evidence_status,
    )
