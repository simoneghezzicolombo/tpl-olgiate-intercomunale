"""Canonical Gate F metric units, semantics and comparison bases.

Column names alone are not sufficient evidence of comparability. This contract
rejects plausible-looking values supplied in incompatible units, with ambiguous
semantics, or on different denominators/evaluation bases across scenarios.
"""
from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


METRIC_CONTRACT: dict[str, dict[str, str]] = {
    "road_feasible": {"unit": "boolean", "semantics": "HARD_ELIGIBILITY_CONSTRAINT"},
    "population_covered_pct": {"unit": "%", "semantics": "PERCENT_OF_DEFINED_POPULATION_DENOMINATOR"},
    "territories_served_count": {"unit": "count", "semantics": "COUNT_OF_DEFINED_TERRITORIAL_UNITS"},
    "s8_useful_connection_pct": {"unit": "%", "semantics": "PERCENT_OF_DEFINED_S8_CONNECTION_DENOMINATOR"},
    "headway_combined_min": {"unit": "min", "semantics": "RATE_EQUIVALENT_NOT_MAX_GAP"},
    "annual_bus_km": {"unit": "bus-km/year", "semantics": "ANNUAL_SCHEDULED_BUS_DISTANCE"},
    "peak_buses_required": {"unit": "vehicles", "semantics": "SIMULTANEOUS_PEAK_VEHICLES"},
}


def metric_contract_manifest() -> dict[str, dict[str, str]]:
    return {
        metric: {
            **dict(spec),
            "comparison_basis_rule": "NONEMPTY_AND_IDENTICAL_ACROSS_COMPARED_SCENARIOS",
        }
        for metric, spec in METRIC_CONTRACT.items()
    }


def validate_gate_f_metric_subset(df: pd.DataFrame, metrics: Iterable[str]) -> None:
    """Validate canonical metadata for a selected set of metrics."""
    for metric in metrics:
        if metric not in METRIC_CONTRACT:
            raise ValueError(f"Unknown Gate F metric contract key: {metric}")
        spec = METRIC_CONTRACT[metric]
        if metric not in df.columns:
            raise ValueError(f"Gate F metric contract missing metric column: {metric}")

        unit_col = f"{metric}__unit"
        if unit_col not in df.columns:
            raise ValueError(f"Gate F metric contract missing unit column: {unit_col}")
        units = df[unit_col]
        if units.isna().any() or not units.astype(str).str.strip().eq(spec["unit"]).all():
            bad = sorted(set(units.astype(str)))
            raise ValueError(f"Gate F metric {metric} requires canonical unit {spec['unit']!r}, found {bad}")

        semantics_col = f"{metric}__semantics"
        if semantics_col not in df.columns:
            raise ValueError(f"Gate F metric contract missing semantics column: {semantics_col}")
        semantics = df[semantics_col]
        if semantics.isna().any() or not semantics.astype(str).str.strip().eq(spec["semantics"]).all():
            bad = sorted(set(semantics.astype(str)))
            raise ValueError(f"Gate F metric {metric} requires semantics {spec['semantics']!r}, found {bad}")

        basis_col = f"{metric}__comparison_basis"
        if basis_col not in df.columns:
            raise ValueError(f"Gate F metric contract missing comparison-basis column: {basis_col}")
        basis = df[basis_col]
        normalized = basis.astype(str).str.strip()
        if basis.isna().any() or normalized.eq("").any():
            raise ValueError(f"Gate F metric {metric} requires a non-empty comparison basis")
        unique_basis = sorted(set(normalized))
        if len(unique_basis) != 1:
            raise ValueError(
                f"Gate F metric {metric} is not comparable across scenarios; comparison bases differ: {unique_basis}"
            )


def validate_gate_f_metric_contract(df: pd.DataFrame) -> None:
    validate_gate_f_metric_subset(df, METRIC_CONTRACT.keys())
