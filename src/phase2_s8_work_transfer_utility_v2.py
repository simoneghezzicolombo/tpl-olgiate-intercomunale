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
from typing import Mapping, Sequence


CONNECTION_TYPES = ("BUS_TO_RAIL", "RAIL_TO_BUS")
DIRECTIONS = ("LECCO", "MILANO")
EXPECTED_S8_PHASE_CONTRACT = "PHASE2_S8_PHASE_OPPORTUNITY_SURFACE_V2"
EXPECTED_S8_PHASE_STATUS = "PASS_S8_PHASE_OPPORTUNITY_V2_BUILD"
FORBIDDEN_SUPPORT_EVIDENCE = {"", "ASSUMED", "INFERRED_FROM_VEHICLE_CLOSURE", "PLACEHOLDER", "INVALIDATED"}


def _strict_bool(value: object, *, field: str) -> bool:
    if value is True or value == "true":
        return True
    if value is False or value == "false":
        return False
    raise ValueError(f"{field} must be explicit true/false")


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


def validate_s8_phase_opportunity_support(
    validation: Mapping[str, object],
    route_rows: Sequence[Mapping[str, object]],
) -> dict[str, PassengerConnectionSupport]:
    """Fail closed unless the audited S8 opportunity surface is GJT-safe.

    In particular this rejects the superseded winner-search contract and any
    route table that promotes an operational vehicle closure to passenger
    BUS_TO_RAIL service.
    """
    if validation.get("status") != EXPECTED_S8_PHASE_STATUS:
        raise ValueError("S8 phase opportunity artifact is not certified PASS")
    if validation.get("contract") != EXPECTED_S8_PHASE_CONTRACT:
        raise ValueError("Unsupported or superseded S8 phasing contract")
    required_false = (
        "phase_selected",
        "phase_pruned",
        "passenger_demand_weights_applied",
        "passenger_utility_calculated",
        "topology_ranked",
        "service_policy_selected",
    )
    for field in required_false:
        if validation.get(field) is not False:
            raise ValueError(f"S8 phase contract requires {field}=false")
    if validation.get("all_integer_phases_evaluated") is not True:
        raise ValueError("S8 phase contract did not evaluate all integer phases")
    if validation.get("all_phases_retained_downstream") is not True:
        raise ValueError("S8 phase contract pruned the downstream phase domain")
    if validation.get("vehicle_cycle_return_is_passenger_event_for_open_routes") is not False:
        raise ValueError("S8 contract promotes vehicle closure to passenger event")
    if validation.get("passenger_bus_to_rail_event_requires_public_return_to_hub") is not True:
        raise ValueError("S8 contract lacks public-return BUS_TO_RAIL protection")

    supports: dict[str, PassengerConnectionSupport] = {}
    open_count = 0
    closed_count = 0
    for row in route_rows:
        route_id = str(row.get("route_id", "")).strip()
        if not route_id or route_id in supports:
            raise ValueError("S8 route universe has missing or duplicate route_id")
        starts = _strict_bool(row.get("public_service_starts_at_hub"), field="public_service_starts_at_hub")
        returns = _strict_bool(row.get("public_service_returns_to_hub"), field="public_service_returns_to_hub")
        closure = _strict_bool(row.get("vehicle_closure_added"), field="vehicle_closure_added")
        r2b = _strict_bool(row.get("rail_to_bus_passenger_event_supported"), field="rail_to_bus_passenger_event_supported")
        b2r = _strict_bool(row.get("bus_to_rail_passenger_event_supported"), field="bus_to_rail_passenger_event_supported")
        if not starts or not r2b:
            raise ValueError("Current Phase 2 route universe must expose passenger RAIL_TO_BUS service from the hub")
        if returns == closure:
            raise ValueError("S8 route public-return and vehicle-closure semantics conflict")
        if b2r != returns:
            raise ValueError("BUS_TO_RAIL support must equal explicit public return-to-hub geometry")
        if closure and b2r:
            raise ValueError("Vehicle-only closure cannot support passenger BUS_TO_RAIL")
        if returns:
            closed_count += 1
        else:
            open_count += 1
        supports[route_id] = PassengerConnectionSupport(
            route_id=route_id,
            bus_to_rail_supported=b2r,
            rail_to_bus_supported=r2b,
            evidence_status="DERIVED_FROM_S8_PHASE_OPPORTUNITY_V2_PUBLIC_SERVICE_GEOMETRY",
        )

    if not supports:
        raise ValueError("S8 route universe is empty")
    expected_routes = int(validation.get("unique_route_count", -1))
    if expected_routes != len(supports):
        raise ValueError("S8 route count does not match validation contract")
    if int(validation.get("vehicle_closure_route_count", -1)) != open_count:
        raise ValueError("S8 vehicle-closure route count does not match route universe")
    if int(validation.get("public_service_return_hub_route_count", -1)) != closed_count:
        raise ValueError("S8 public-return route count does not match route universe")
    if int(validation.get("rail_to_bus_passenger_supported_route_count", -1)) != len(supports):
        raise ValueError("S8 RAIL_TO_BUS support count mismatch")
    if int(validation.get("bus_to_rail_passenger_supported_route_count", -1)) != closed_count:
        raise ValueError("S8 BUS_TO_RAIL support count mismatch")
    return supports


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
