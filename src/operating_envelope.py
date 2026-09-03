"""Inverse service-math constraints for Gate E.

These functions answer threshold questions without inventing route metrics. They
are deterministic algebra and become project evidence only when their inputs do.
"""
from __future__ import annotations

import math

from src.service_math import ServiceMathError


def _positive(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ServiceMathError(f"{name} must be finite and > 0")
    return value


def _nonnegative(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ServiceMathError(f"{name} must be finite and >= 0")
    return value


def _positive_int(name: str, value: int) -> int:
    try:
        ivalue = int(value)
    except (TypeError, ValueError) as exc:
        raise ServiceMathError(f"{name} must be a positive integer") from exc
    if ivalue != value or ivalue <= 0:
        raise ServiceMathError(f"{name} must be a positive integer")
    return ivalue


def theoretical_regular_headway_min(cycle_min: float, in_service_vehicles: int) -> float:
    """Even-spacing theoretical headway, not a timetable-derived observed gap."""
    return _positive("cycle_min", cycle_min) / _positive_int("in_service_vehicles", in_service_vehicles)


def maximum_cycle_min_for_headway(target_headway_min: float, in_service_vehicles: int) -> float:
    """Largest cycle compatible with an evenly spaced target headway."""
    return _positive("target_headway_min", target_headway_min) * _positive_int(
        "in_service_vehicles", in_service_vehicles
    )


def maximum_pure_running_min_for_headway(
    target_headway_min: float,
    in_service_vehicles: int,
    dwell_min: float,
    recovery_min: float,
) -> float:
    """Maximum pure running time before the target headway becomes impossible.

    A negative result means dwell+recovery alone exceed the available cycle.
    """
    capacity = maximum_cycle_min_for_headway(target_headway_min, in_service_vehicles)
    return capacity - _nonnegative("dwell_min", dwell_min) - _nonnegative("recovery_min", recovery_min)


def cycle_slack_min(cycle_min: float, target_headway_min: float, in_service_vehicles: int) -> float:
    """Positive slack means the target headway fits the supplied in-service fleet."""
    return maximum_cycle_min_for_headway(target_headway_min, in_service_vehicles) - _positive(
        "cycle_min", cycle_min
    )


def max_total_directional_cycles_year_for_budget(budget_bus_km: float, route_km: float) -> int:
    """Maximum whole directional vehicle-cycles affordable under a bus-km cap."""
    budget = _positive("budget_bus_km", budget_bus_km)
    distance = _positive("route_km", route_km)
    return math.floor(budget / distance + 1e-12)


def max_symmetric_daily_cycles_each_direction_for_budget(
    budget_bus_km: float,
    route_km: float,
    service_days_year: int,
) -> int:
    """Maximum equal CW and CCW full cycles/day under a bus-km cap."""
    days = _positive_int("service_days_year", service_days_year)
    total_cycles = max_total_directional_cycles_year_for_budget(budget_bus_km, route_km)
    return total_cycles // (2 * days)


def max_symmetric_route_km_for_budget(
    budget_bus_km: float,
    cycles_per_day_each_direction: int,
    service_days_year: int,
) -> float:
    """Maximum common CW/CCW route length under a bus-km cap."""
    cycles = _positive_int("cycles_per_day_each_direction", cycles_per_day_each_direction)
    days = _positive_int("service_days_year", service_days_year)
    return _positive("budget_bus_km", budget_bus_km) / (2 * cycles * days)
