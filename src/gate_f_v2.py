"""Gate F v2 objectives and verdict guardrails for validated upstream contracts."""
from __future__ import annotations

from typing import Mapping
import numpy as np
import pandas as pd

from src.gate_f_contract_v2 import ROAD_UNCERTAINTY, validate_metric_contract_v2
from src.gate_f_pareto import (
    Objective,
    decision_summary,
    identify_pareto_frontier,
    identify_robust_pareto_frontier,
    validate_scenarios,
)


V2_OBJECTIVES: tuple[Objective, ...] = (
    Objective("population_covered_pct", "max", "B", "population accessibility", "%"),
    Objective("headway_combined_min", "min", "E", "combined service headway", "min"),
    Objective("annual_bus_km", "min", "E", "annual bus-km", "bus-km/year"),
    Objective(
        "minimum_scheduled_vehicles",
        "min",
        "E",
        "minimum scheduled in-service vehicles",
        "vehicles",
    ),
    Objective("s8_useful_connection_pct", "max", "C+E", "useful S8 connections", "%"),
    Objective("territories_served_count", "max", "B", "territories served", "count"),
)


def validate_v2_scenarios(df: pd.DataFrame) -> None:
    validate_metric_contract_v2(df)
    validate_scenarios(df, V2_OBJECTIVES)
    vehicles = pd.to_numeric(df["minimum_scheduled_vehicles"], errors="coerce")
    if vehicles.isna().any() or (vehicles < 1).any() or not np.equal(vehicles, np.floor(vehicles)).all():
        raise ValueError("minimum_scheduled_vehicles must be an integer >= 1")
    uncertainty = df["road_uncertainty_status"].astype(str).str.strip().str.upper()
    if (~uncertainty.isin(ROAD_UNCERTAINTY)).any():
        bad = sorted(set(uncertainty) - ROAD_UNCERTAINTY)
        raise ValueError(f"Unsupported road_uncertainty_status: {bad}")


def point_frontier_v2(df: pd.DataFrame) -> pd.DataFrame:
    validate_v2_scenarios(df)
    return identify_pareto_frontier(df, V2_OBJECTIVES)


def robust_frontier_v2(df: pd.DataFrame) -> pd.DataFrame:
    validate_v2_scenarios(df)
    return identify_robust_pareto_frontier(df, V2_OBJECTIVES)


def decision_summary_v2(pareto_df: pd.DataFrame, gate_status: Mapping[str, str]) -> dict:
    """Apply the normal robust Pareto verdict, then preserve Gate D uncertainty.

    Gate D PASS establishes structural routing integrity but explicitly leaves
    some vehicle-specific/field conditions unresolved. If a robustly non-dominated
    scenario still has QUANTIFIED or UNKNOWN road uncertainty, Gate F may report
    the frontier but cannot issue a definitive recommendation for that scenario.
    """
    summary = decision_summary(pareto_df, gate_status, V2_OBJECTIVES)
    robust_ids = summary.get("robust_pareto_scenario_ids")
    if not robust_ids:
        return summary
    lookup = pareto_df.set_index("scenario_id")
    conditional = sorted(
        sid
        for sid in robust_ids
        if str(lookup.loc[sid, "road_uncertainty_status"]).strip().upper() != "RESOLVED"
    )
    if not conditional:
        return summary
    evidence = list(summary.get("evidence_status") or [])
    if "CONDITIONAL_ROAD_UNCERTAINTY" not in evidence:
        evidence.append("CONDITIONAL_ROAD_UNCERTAINTY")
    summary.update(
        {
            "verdict": "PROVISIONAL",
            "evidence_status": evidence,
            "recommendation_status": "NO_DEFINITIVE_RECOMMENDATION_ROAD_UNCERTAINTY",
            "recommended_scenario_id": None,
            "conditional_road_scenario_ids": conditional,
            "reason": (
                "At least one robustly non-dominated scenario retains quantified or unknown Gate D road uncertainty; "
                "the Pareto frontier is reportable but a definitive recommendation is not."
            ),
        }
    )
    return summary
