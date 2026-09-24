"""Passenger GJT V2 contracts for empirically weighted Phase 2 journeys.

This module deliberately separates the empirical OD universe from spatial
allocation. The ISTAT 2021 work matrix supports municipality-to-municipality
weights, but not a 2021 worker origin building/stop. A journey may therefore be
weighted only after its spatial/service components have an explicit evidence
lineage. No population-proportional or nearest-stop imputation happens here.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence


FORBIDDEN_EVIDENCE = {"INVALIDATED", "PLACEHOLDER"}


@dataclass(frozen=True)
class EmpiricalJourneyDemand:
    journey_key: str
    origin_code: str
    origin_municipality: str
    destination_code: str
    destination_municipality: str
    demand_weight: float
    layer: str = "ISTAT_2021_WORK_S8_DIRECT"
    source_resolution: str = "MUNICIPAL_OD"
    evidence_status: str = "DERIVED"

    def __post_init__(self) -> None:
        if not all((self.journey_key, self.origin_code, self.origin_municipality,
                    self.destination_code, self.destination_municipality, self.layer,
                    self.source_resolution)):
            raise ValueError("EmpiricalJourneyDemand requires non-empty identifiers")
        if not math.isfinite(self.demand_weight) or self.demand_weight <= 0:
            raise ValueError("Empirical demand weight must be finite and positive")
        if self.evidence_status.strip().upper() in FORBIDDEN_EVIDENCE:
            raise ValueError("EmpiricalJourneyDemand cannot use forbidden evidence")


@dataclass(frozen=True)
class GJTSensitivity:
    sensitivity_id: str
    bus_ivt_weight: float
    walk_weight: float
    wait_weight: float
    transfer_penalty_min: float
    missed_connection_cost_multiplier: float = 1.0

    def __post_init__(self) -> None:
        if not self.sensitivity_id:
            raise ValueError("sensitivity_id is required")
        values = (
            self.bus_ivt_weight,
            self.walk_weight,
            self.wait_weight,
            self.transfer_penalty_min,
            self.missed_connection_cost_multiplier,
        )
        if any(not math.isfinite(v) for v in values):
            raise ValueError("GJT sensitivity values must be finite")
        if self.bus_ivt_weight <= 0 or self.walk_weight <= 0 or self.wait_weight <= 0:
            raise ValueError("IVT/walk/wait weights must be positive")
        if self.transfer_penalty_min < 0 or self.missed_connection_cost_multiplier < 0:
            raise ValueError("GJT penalties cannot be negative")


@dataclass(frozen=True)
class PassengerJourneyComponents:
    """One fully addressable passenger chain for GJT comparison.

    Access and service components must already be derived by an upstream
    addressability model. This class refuses partial/unknown components rather
    than filling them with zero. Rail IVT is kept separate from bus IVT so the
    published TAG bus-IVT sensitivity can be applied without distorting rail.
    """

    journey_key: str
    layer: str
    origin_municipality: str
    demand_weight: float
    walk_min: float
    wait_min: float
    bus_ivt_min: float
    rail_ivt_min: float
    transfer_walk_min: float = 0.0
    transfer_wait_min: float = 0.0
    transfers: int = 0
    missed_connection_probability: float = 0.0
    missed_connection_cost_min: float = 0.0
    spatial_allocation_status: str = ""
    evidence_status: str = "DERIVED"

    def __post_init__(self) -> None:
        if not all((self.journey_key, self.layer, self.origin_municipality,
                    self.spatial_allocation_status)):
            raise ValueError("PassengerJourneyComponents requires identifiers and spatial allocation status")
        if self.spatial_allocation_status == "MUNICIPAL_OD_ONLY_NO_SPATIAL_ALLOCATION":
            raise ValueError("Full GJT cannot be materialised from municipal OD alone")
        if not math.isfinite(self.demand_weight) or self.demand_weight <= 0:
            raise ValueError("demand_weight must be finite and positive")
        numeric = (
            self.walk_min, self.wait_min, self.bus_ivt_min, self.rail_ivt_min,
            self.transfer_walk_min, self.transfer_wait_min,
            self.missed_connection_probability, self.missed_connection_cost_min,
        )
        if any(not math.isfinite(v) for v in numeric):
            raise ValueError("Journey components must be finite")
        if any(v < 0 for v in numeric[:-2]) or self.missed_connection_cost_min < 0 or self.transfers < 0:
            raise ValueError("Journey times/counts cannot be negative")
        if not 0.0 <= self.missed_connection_probability <= 1.0:
            raise ValueError("missed_connection_probability must be in [0,1]")
        if self.evidence_status.strip().upper() in FORBIDDEN_EVIDENCE:
            raise ValueError("PassengerJourneyComponents cannot use forbidden evidence")


def generalised_journey_time(
    record: PassengerJourneyComponents,
    sensitivity: GJTSensitivity,
) -> float:
    return (
        sensitivity.bus_ivt_weight * record.bus_ivt_min
        + record.rail_ivt_min
        + sensitivity.walk_weight * (record.walk_min + record.transfer_walk_min)
        + sensitivity.wait_weight * (record.wait_min + record.transfer_wait_min)
        + sensitivity.transfer_penalty_min * record.transfers
        + sensitivity.missed_connection_cost_multiplier
        * record.missed_connection_probability
        * record.missed_connection_cost_min
    )


@dataclass(frozen=True)
class GJTComparison:
    sensitivity_id: str
    demand_weighted_gjt_improvement_min: float
    municipal_gjt_improvement_min: Mapping[str, float]
    worst_municipality_gjt_improvement_min: float
    candidate_weighted_missed_connection_probability: float
    demand_weight_sum: float
    journey_count: int


def compare_weighted_journeys(
    baseline: Sequence[PassengerJourneyComponents],
    candidate: Sequence[PassengerJourneyComponents],
    sensitivity: GJTSensitivity,
) -> GJTComparison:
    base = {row.journey_key: row for row in baseline}
    cand = {row.journey_key: row for row in candidate}
    if not base or set(base) != set(cand):
        raise ValueError("Baseline/candidate must contain the same non-empty journey universe")

    total_weight = 0.0
    improvement_sum = 0.0
    missed_sum = 0.0
    municipal_num: dict[str, float] = {}
    municipal_den: dict[str, float] = {}
    for key in sorted(base):
        left, right = base[key], cand[key]
        if left.layer != right.layer or left.origin_municipality != right.origin_municipality:
            raise ValueError(f"Journey semantics differ for {key}")
        if not math.isclose(left.demand_weight, right.demand_weight, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError(f"Demand weight differs for {key}")
        improvement = generalised_journey_time(left, sensitivity) - generalised_journey_time(right, sensitivity)
        weight = left.demand_weight
        total_weight += weight
        improvement_sum += weight * improvement
        missed_sum += weight * right.missed_connection_probability
        municipality = left.origin_municipality
        municipal_num[municipality] = municipal_num.get(municipality, 0.0) + weight * improvement
        municipal_den[municipality] = municipal_den.get(municipality, 0.0) + weight

    municipal = {name: municipal_num[name] / municipal_den[name] for name in sorted(municipal_num)}
    return GJTComparison(
        sensitivity_id=sensitivity.sensitivity_id,
        demand_weighted_gjt_improvement_min=improvement_sum / total_weight,
        municipal_gjt_improvement_min=municipal,
        worst_municipality_gjt_improvement_min=min(municipal.values()),
        candidate_weighted_missed_connection_probability=missed_sum / total_weight,
        demand_weight_sum=total_weight,
        journey_count=len(base),
    )
