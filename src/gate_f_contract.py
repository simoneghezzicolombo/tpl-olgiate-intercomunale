"""Canonical Gate F metric units and semantics.

Column names alone are not sufficient evidence of units. This contract rejects
plausible-looking values supplied in incompatible units or with ambiguous
service-frequency semantics.
"""
from __future__ import annotations

from typing import Mapping

import pandas as pd


METRIC_CONTRACT: dict[str, dict[str, str | None]] = {
    "road_feasible": {"unit": "boolean", "semantics": "HARD_ELIGIBILITY_CONSTRAINT"},
    "population_covered_pct": {"unit": "%", "semantics": "PERCENT_OF_DEFINED_POPULATION_DENOMINATOR"},
    "territories_served_count": {"unit": "count", "semantics": "COUNT_OF_DEFINED_TERRITORIAL_UNITS"},
    "s8_useful_connection_pct": {"unit": "%", "semantics": "PERCENT_OF_DEFINED_S8_CONNECTION_DENOMINATOR"},
    "headway_combined_min": {"unit": "min", "semantics": "RATE_EQUIVALENT_NOT_MAX_GAP"},
    "annual_bus_km": {"unit": "bus-km/year", "semantics": "ANNUAL_SCHEDULED_BUS_DISTANCE"},
    "peak_buses_required": {"unit": "vehicles", "semantics": "SIMULTANEOUS_PEAK_VEHICLES"},
}


def metric_contract_manifest() -> dict[str, dict[str, str | None]]:
    return {metric: dict(spec) for metric, spec in METRIC_CONTRACT.items()}


def validate_gate_f_metric_contract(df: pd.DataFrame) -> None:
    """Require exact canonical unit and semantics metadata for every Gate F metric."""
    for metric, spec in METRIC_CONTRACT.items():
        if metric not in df.columns:
            raise ValueError(f"Gate F metric contract missing metric column: {metric}")
        unit_col = f"{metric}__unit"
        if unit_col not in df.columns:
            raise ValueError(f"Gate F metric contract missing unit column: {unit_col}")
        units = df[unit_col]
        if units.isna().any() or not units.astype(str).str.strip().eq(str(spec["unit"])).all():
            bad = sorted(set(units.astype(str)))
            raise ValueError(
                f"Gate F metric {metric} requires canonical unit {spec['unit']!r}, found {bad}"
            )
        semantics_col = f"{metric}__semantics"
        expected_semantics = spec["semantics"]
        if semantics_col not in df.columns:
            raise ValueError(f"Gate F metric contract missing semantics column: {semantics_col}")
        semantics = df[semantics_col]
        if semantics.isna().any() or not semantics.astype(str).str.strip().eq(str(expected_semantics)).all():
            bad = sorted(set(semantics.astype(str)))
            raise ValueError(
                f"Gate F metric {metric} requires semantics {expected_semantics!r}, found {bad}"
            )
