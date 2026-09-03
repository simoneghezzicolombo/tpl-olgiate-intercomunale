"""Exact phase-retained S8 transfer-gap envelopes for Passenger GJT V2.

The 1,882 ISTAT workers are used only to weight Milano vs Lecco interchange
directions. They are never assigned to a bus route. Every declared integer
clock phase remains in the evaluated domain and no phase is selected.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import math
from typing import Mapping, Sequence

from src.phase2_s8_phasing_v2 import RailEvent, Span, phase_raw_gap_metrics
from src.phase2_s8_work_transfer_utility_v2 import WorkDirectionWeights


TRANSFER_GAP_CONTRACT = "PHASE2_S8_TRANSFER_GAP_ENVELOPE_V2"
TRANSFER_GAP_STATUS = "PASS_S8_TRANSFER_GAP_ENVELOPE_V2_BUILD"
REPRESENTATIVE_FRACTION = Decimal("0.5")


@dataclass(frozen=True)
class PhaseGapEnvelope:
    evaluated_phase_count: int
    complete_match_phase_count: int
    best_complete_phase_weighted_mean_gap_min: float | None
    worst_complete_phase_weighted_mean_gap_min: float | None


def runtime_parts(runtime_min: str | float | Decimal) -> tuple[int, Decimal]:
    value = Decimal(str(runtime_min))
    if value <= 0:
        raise ValueError("Route runtime must be positive")
    integer = int(value)
    fraction = value - Decimal(integer)
    if not Decimal("0") < fraction < Decimal("1"):
        raise ValueError("Audited S8 V2 runtime class requires a positive fractional runtime")
    return integer, fraction


def build_representative_phase_metrics(
    *,
    rail_events: Sequence[RailEvent],
    headway_min: int,
    span: Span,
    runtime_integer_mod_headway: int,
) -> list[dict[str, object]]:
    if not 0 <= runtime_integer_mod_headway < headway_min:
        raise ValueError("runtime integer modulo must be inside headway domain")
    representative_runtime = Decimal(runtime_integer_mod_headway) + REPRESENTATIVE_FRACTION
    return [
        phase_raw_gap_metrics(
            rail_events=rail_events,
            cycle_runtime_min=representative_runtime,
            headway_min=headway_min,
            span=span,
            phase_min=phase,
        )
        for phase in range(headway_min)
    ]


def _finite_mean(metrics: Mapping[str, object], prefix: str) -> float:
    unmatched = int(metrics[f"{prefix}_unmatched_count"])
    value = metrics[f"{prefix}_mean_gap_min"]
    if unmatched != 0 or value is None:
        raise ValueError("Phase cell is not a complete-match mean gap")
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError("Phase mean gap must be finite and non-negative")
    return value


def exact_weighted_phase_envelope(
    *,
    phase_metrics: Sequence[Mapping[str, object]],
    weights: WorkDirectionWeights,
    roundtrip_passenger_supported: bool,
    actual_fractional_runtime: Decimal,
) -> PhaseGapEnvelope:
    """Return exact min/max across common phases, restricted to full matches.

    `phase_metrics` must use a representative +0.5 runtime with the same
    runtime-integer modulo as the route. For positive fractional runtimes and
    integer-minute rail events, BUS_TO_RAIL gaps translate by the exact
    constant 0.5 - actual_fraction. RAIL_TO_BUS gaps are unchanged.
    """
    weights.validate()
    if not Decimal("0") < actual_fractional_runtime < Decimal("1"):
        raise ValueError("actual_fractional_runtime must lie strictly inside (0,1)")
    if not phase_metrics:
        raise ValueError("No phase metrics supplied")
    delta = float(REPRESENTATIVE_FRACTION - actual_fractional_runtime)
    worker_count = weights.worker_count
    complete: list[float] = []
    for metrics in phase_metrics:
        try:
            r2b = (
                float(weights.return_rail_to_bus["MILANO"])
                * _finite_mean(metrics, "rail_to_bus_milano")
                + float(weights.return_rail_to_bus["LECCO"])
                * _finite_mean(metrics, "rail_to_bus_lecco")
            )
            if roundtrip_passenger_supported:
                b2r = (
                    float(weights.outbound_bus_to_rail["MILANO"])
                    * (_finite_mean(metrics, "vehicle_cycle_to_rail_milano") + delta)
                    + float(weights.outbound_bus_to_rail["LECCO"])
                    * (_finite_mean(metrics, "vehicle_cycle_to_rail_lecco") + delta)
                )
                value = (b2r + r2b) / (2.0 * worker_count)
            else:
                value = r2b / worker_count
        except ValueError:
            continue
        if value < -1e-9:
            raise ValueError("Translated weighted transfer gap became negative")
        complete.append(max(0.0, value))
    return PhaseGapEnvelope(
        evaluated_phase_count=len(phase_metrics),
        complete_match_phase_count=len(complete),
        best_complete_phase_weighted_mean_gap_min=min(complete) if complete else None,
        worst_complete_phase_weighted_mean_gap_min=max(complete) if complete else None,
    )
