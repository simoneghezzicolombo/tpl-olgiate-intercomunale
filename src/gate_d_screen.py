"""Screen validated or provisional Gate D metrics against Gate E sensitivity envelopes.

A screen result is a mathematical comparison only. If the operating envelope is
assumption-driven it can never become a Gate E verdict or route recommendation.
"""
from __future__ import annotations

import math
from typing import Mapping

from src.service_math import ServiceMathError


def _finite(name: str, value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ServiceMathError(f"{name} must be numeric") from exc
    if not math.isfinite(number):
        raise ServiceMathError(f"{name} must be finite")
    return number


def screen_gate_d_metric_against_envelope(
    *, route_km: float, pure_running_min: float,
    maximum_route_km: float, maximum_pure_running_min: float,
) -> dict[str, object]:
    route = _finite("route_km", route_km)
    runtime = _finite("pure_running_min", pure_running_min)
    route_max = _finite("maximum_route_km", maximum_route_km)
    runtime_max = _finite("maximum_pure_running_min", maximum_pure_running_min)
    if route <= 0 or runtime <= 0 or route_max <= 0:
        raise ServiceMathError("route_km, pure_running_min and maximum_route_km must be > 0")

    route_margin = route_max - route
    runtime_margin = runtime_max - runtime
    budget_ok = route_margin >= -1e-12
    runtime_ok = runtime_margin >= -1e-12
    if budget_ok and runtime_ok:
        classification = "WITHIN_ASSUMED_MATH_ENVELOPE"
    elif not budget_ok and not runtime_ok:
        classification = "EXCEEDS_ASSUMED_BUDGET_AND_RUNTIME_THRESHOLDS"
    elif not budget_ok:
        classification = "EXCEEDS_ASSUMED_BUDGET_ROUTE_THRESHOLD"
    else:
        classification = "EXCEEDS_ASSUMED_RUNTIME_THRESHOLD"
    return {
        "route_km_margin_to_threshold": route_margin,
        "pure_running_min_margin_to_threshold": runtime_margin,
        "budget_distance_threshold_met": budget_ok,
        "runtime_threshold_met": runtime_ok,
        "screen_classification": classification,
        "screen_status": "SENSITIVITY_ONLY_NOT_GATE_E_VERDICT",
    }


def screen_rows(d_row: Mapping[str, str], envelope_row: Mapping[str, str]) -> dict[str, object]:
    result = screen_gate_d_metric_against_envelope(
        route_km=d_row["route_km"],
        pure_running_min=d_row["pure_running_min"],
        maximum_route_km=envelope_row["maximum_common_route_km_under_pdb_budget"],
        maximum_pure_running_min=envelope_row["maximum_pure_running_min_compatible_with_headway"],
    )
    return {
        "scenario_id": d_row["scenario_id"],
        "service_day_group": d_row["service_day_group"],
        "band_id": d_row["band_id"],
        "direction": d_row["direction"],
        "gate_d_status": d_row["upstream_gate_d_status"],
        "route_km": d_row["route_km"],
        "route_km_status": d_row["route_km_status"],
        "pure_running_min": d_row["pure_running_min"],
        "pure_running_status": d_row["pure_running_status"],
        "headway_each_direction_min": envelope_row["headway_each_direction_min"],
        "in_service_vehicles_each_direction": envelope_row["in_service_vehicles_each_direction"],
        "dwell_min_assumed": envelope_row["dwell_min"],
        "recovery_min_assumed": envelope_row["recovery_min"],
        "cycles_per_day_each_direction_assumed": envelope_row["cycles_per_day_each_direction"],
        "service_days_year_assumed": envelope_row["service_days_year"],
        "maximum_pure_running_min_threshold": envelope_row["maximum_pure_running_min_compatible_with_headway"],
        "maximum_common_route_km_threshold": envelope_row["maximum_common_route_km_under_pdb_budget"],
        **result,
    }
