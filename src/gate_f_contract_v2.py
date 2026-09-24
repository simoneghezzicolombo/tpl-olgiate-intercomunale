"""Gate F v2 metric contract aligned with the validated upstream workstreams.

V2 deliberately distinguishes scheduled in-service fleet evidence from an exact
procurement fleet count and carries unresolved Gate D road uncertainty outside
the optimization objectives.
"""
from __future__ import annotations

from collections.abc import Iterable
import pandas as pd


METRIC_CONTRACT_V2: dict[str, dict[str, str]] = {
    "road_feasible": {"unit": "boolean", "semantics": "STRUCTURAL_ROUTING_ELIGIBILITY_CONSTRAINT"},
    "population_covered_pct": {"unit": "%", "semantics": "PERCENT_OF_DEFINED_POPULATION_DENOMINATOR"},
    "territories_served_count": {"unit": "count", "semantics": "COUNT_OF_DEFINED_TERRITORIAL_UNITS"},
    "s8_useful_connection_pct": {"unit": "%", "semantics": "PERCENT_OF_DEFINED_S8_CONNECTION_DENOMINATOR"},
    "headway_combined_min": {"unit": "min", "semantics": "RATE_EQUIVALENT_NOT_MAX_GAP"},
    "annual_bus_km": {"unit": "bus-km/year", "semantics": "ANNUAL_SCHEDULED_BUS_DISTANCE"},
    "minimum_scheduled_vehicles": {
        "unit": "vehicles",
        "semantics": "THEORETICAL_IN_SERVICE_SCHEDULED_MINIMUM_EXCLUDES_DEADHEAD_RELIEFS_MAINTENANCE_SPARES",
    },
}

ROAD_UNCERTAINTY = {"RESOLVED", "QUANTIFIED", "UNKNOWN"}


def metric_contract_manifest_v2() -> dict[str, dict[str, str]]:
    return {
        metric: {**spec, "comparison_basis_rule": "NONEMPTY_AND_IDENTICAL_ACROSS_COMPARED_SCENARIOS"}
        for metric, spec in METRIC_CONTRACT_V2.items()
    }


def validate_metric_subset_v2(df: pd.DataFrame, metrics: Iterable[str]) -> None:
    for metric in metrics:
        if metric not in METRIC_CONTRACT_V2:
            raise ValueError(f"Unknown Gate F v2 metric: {metric}")
        spec = METRIC_CONTRACT_V2[metric]
        for suffix in ("unit", "semantics", "comparison_basis"):
            column = f"{metric}__{suffix}"
            if column not in df.columns:
                raise ValueError(f"Gate F v2 missing {column}")
        units = df[f"{metric}__unit"].astype(str).str.strip()
        if not units.eq(spec["unit"]).all():
            raise ValueError(f"Gate F v2 {metric} requires unit {spec['unit']!r}")
        semantics = df[f"{metric}__semantics"].astype(str).str.strip()
        if not semantics.eq(spec["semantics"]).all():
            raise ValueError(f"Gate F v2 {metric} requires semantics {spec['semantics']!r}")
        basis = df[f"{metric}__comparison_basis"].astype(str).str.strip()
        if basis.eq("").any() or len(set(basis)) != 1:
            raise ValueError(f"Gate F v2 {metric} comparison basis must be non-empty and identical")


def validate_metric_contract_v2(df: pd.DataFrame) -> None:
    validate_metric_subset_v2(df, METRIC_CONTRACT_V2)
    if "road_uncertainty_status" not in df.columns or "road_uncertainty_source" not in df.columns:
        raise ValueError("Gate F v2 requires road_uncertainty_status and road_uncertainty_source")
    uncertainty = df["road_uncertainty_status"].astype(str).str.strip().str.upper()
    bad = sorted(set(uncertainty) - ROAD_UNCERTAINTY)
    if bad:
        raise ValueError(f"Gate F v2 invalid road uncertainty status: {bad}")
    source = df["road_uncertainty_source"]
    if source.isna().any() or source.astype(str).str.strip().eq("").any():
        raise ValueError("Gate F v2 road uncertainty requires a traceable source")
    vehicles = pd.to_numeric(df["minimum_scheduled_vehicles"], errors="coerce")
    if vehicles.isna().any() or (vehicles < 1).any() or not (vehicles == vehicles.astype(int)).all():
        raise ValueError("minimum_scheduled_vehicles must be an integer >= 1")
