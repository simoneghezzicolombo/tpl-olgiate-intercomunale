"""Gate F: provenance-aware Pareto comparison for transit service scenarios.

This module intentionally contains no project scenario values and no default
preference weights. It can compare only upstream scenario metrics carrying
explicit epistemic status and source fields.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
import pandas as pd


ALLOWED_INPUT_STATUSES = {"FACT", "DERIVED", "ESTIMATE", "RECONSTRUCTED", "MODEL OUTPUT"}
REQUIRED_GATES = ("A", "B", "C", "D", "E")


@dataclass(frozen=True)
class Objective:
    column: str
    direction: str
    gate: str
    label: str

    def __post_init__(self) -> None:
        if self.direction not in {"max", "min"}:
            raise ValueError(f"Invalid objective direction: {self.direction}")


DEFAULT_OBJECTIVES: tuple[Objective, ...] = (
    Objective("population_covered_pct", "max", "B", "population accessibility"),
    Objective("headway_combined_min", "min", "E", "combined service headway"),
    Objective("annual_bus_km", "min", "E", "annual bus-km"),
    Objective("peak_buses_required", "min", "E", "peak buses required"),
    Objective("s8_useful_connection_pct", "max", "C", "useful S8 connections"),
    Objective("territories_served_count", "max", "B", "territories served"),
)


def blocker_labels(gate_status: Mapping[str, str]) -> list[str]:
    return [f"BLOCKED_BY_GATE_{gate}" for gate in REQUIRED_GATES if gate_status.get(gate) != "PASS"]


def _required_columns(objectives: Sequence[Objective]) -> set[str]:
    cols = {"scenario_id", "scenario_name", "scenario_epistemic_status", "scenario_source", "is_baseline"}
    for obj in objectives:
        cols.update({obj.column, f"{obj.column}__status", f"{obj.column}__source"})
    return cols


def validate_scenarios(df: pd.DataFrame, objectives: Sequence[Objective] = DEFAULT_OBJECTIVES) -> None:
    missing = sorted(_required_columns(objectives) - set(df.columns))
    if missing:
        raise ValueError(f"Missing Gate F input columns: {', '.join(missing)}")
    if df.empty:
        raise ValueError("Gate F scenario table is empty")
    if df["scenario_id"].isna().any() or df["scenario_id"].duplicated().any():
        raise ValueError("scenario_id must be non-null and unique")
    baseline_count = int(df["is_baseline"].astype(bool).sum())
    if baseline_count != 1:
        raise ValueError(f"Exactly one baseline scenario is required, found {baseline_count}")
    if (~df["scenario_epistemic_status"].isin(ALLOWED_INPUT_STATUSES)).any():
        bad = sorted(set(df.loc[~df["scenario_epistemic_status"].isin(ALLOWED_INPUT_STATUSES), "scenario_epistemic_status"].astype(str)))
        raise ValueError(f"Unsupported scenario epistemic status: {bad}")
    if df["scenario_source"].isna().any() or (df["scenario_source"].astype(str).str.strip() == "").any():
        raise ValueError("Every scenario requires a traceable scenario_source")

    for obj in objectives:
        values = pd.to_numeric(df[obj.column], errors="coerce")
        if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
            raise ValueError(f"Objective {obj.column} must contain only finite numeric values")
        if obj.column == "headway_combined_min" and (values <= 0).any():
            raise ValueError("headway_combined_min must be > 0")
        if obj.column in {"annual_bus_km", "peak_buses_required", "territories_served_count"} and (values < 0).any():
            raise ValueError(f"{obj.column} must be >= 0")
        status_col = f"{obj.column}__status"
        source_col = f"{obj.column}__source"
        if (~df[status_col].isin(ALLOWED_INPUT_STATUSES)).any():
            bad = sorted(set(df.loc[~df[status_col].isin(ALLOWED_INPUT_STATUSES), status_col].astype(str)))
            raise ValueError(f"Unsupported epistemic status for {obj.column}: {bad}")
        if df[source_col].isna().any() or (df[source_col].astype(str).str.strip() == "").any():
            raise ValueError(f"Every {obj.column} value requires a traceable source")


def identify_pareto_frontier(df: pd.DataFrame, objectives: Sequence[Objective] = DEFAULT_OBJECTIVES) -> pd.DataFrame:
    """Return scenarios with Pareto flags and the IDs that dominate each row."""
    validate_scenarios(df, objectives)
    out = df.copy().reset_index(drop=True)
    matrix = out[[o.column for o in objectives]].astype(float).to_numpy()
    signs = np.array([1.0 if o.direction == "max" else -1.0 for o in objectives])
    utility = matrix * signs
    dominated_by: list[list[str]] = [[] for _ in range(len(out))]

    for i in range(len(out)):
        for j in range(len(out)):
            if i == j:
                continue
            if np.all(utility[j] >= utility[i]) and np.any(utility[j] > utility[i]):
                dominated_by[i].append(str(out.loc[j, "scenario_id"]))

    out["pareto_optimal"] = [not ids for ids in dominated_by]
    out["dominated_by"] = [";".join(ids) for ids in dominated_by]
    return out


def leave_one_objective_out_robustness(
    df: pd.DataFrame, objectives: Sequence[Objective] = DEFAULT_OBJECTIVES
) -> pd.DataFrame:
    """Preference-free sensitivity: full frontier plus one frontier per omitted objective."""
    full = identify_pareto_frontier(df, objectives)
    counts = full.set_index("scenario_id")["pareto_optimal"].astype(int)
    runs = 1
    for omitted in objectives:
        reduced = tuple(obj for obj in objectives if obj != omitted)
        if not reduced:
            continue
        frontier = identify_pareto_frontier(df, reduced).set_index("scenario_id")["pareto_optimal"].astype(int)
        counts = counts.add(frontier, fill_value=0).astype(int)
        runs += 1
    result = full.copy()
    result["pareto_robustness_runs"] = runs
    result["pareto_robustness_count"] = result["scenario_id"].map(counts).astype(int)
    result["pareto_robustness_share"] = (result["pareto_robustness_count"] / runs).round(6)
    return result


def build_tradeoffs(df: pd.DataFrame, objectives: Sequence[Objective] = DEFAULT_OBJECTIVES) -> pd.DataFrame:
    """Add deltas versus the input baseline; no baseline value is hardcoded here."""
    validate_scenarios(df, objectives)
    baseline = df.loc[df["is_baseline"].astype(bool)].iloc[0]
    out = df.copy()
    for obj in objectives:
        out[f"delta_vs_baseline__{obj.column}"] = out[obj.column].astype(float) - float(baseline[obj.column])
    return out


def decision_summary(
    pareto_df: pd.DataFrame,
    gate_status: Mapping[str, str],
    objectives: Sequence[Objective] = DEFAULT_OBJECTIVES,
) -> dict:
    blockers = blocker_labels(gate_status)
    frontier_ids = pareto_df.loc[pareto_df["pareto_optimal"], "scenario_id"].astype(str).tolist()
    if blockers:
        return {
            "verdict": "PROVISIONAL",
            "dependency_status": blockers,
            "recommendation_status": "BLOCKED",
            "recommended_scenario_id": None,
            "pareto_scenario_ids": frontier_ids,
            "reason": "Upstream gates are not all PASS; no definitive recommendation is permitted.",
        }
    if len(frontier_ids) == 1:
        return {
            "verdict": "PASS",
            "dependency_status": [],
            "recommendation_status": "UNIQUE_PARETO_DOMINANT",
            "recommended_scenario_id": frontier_ids[0],
            "pareto_scenario_ids": frontier_ids,
            "reason": "Exactly one scenario remains non-dominated across the declared Gate F objectives.",
        }
    return {
        "verdict": "PASS",
        "dependency_status": [],
        "recommendation_status": "NO_SINGLE_WINNER_PARETO_TRADEOFF",
        "recommended_scenario_id": None,
        "pareto_scenario_ids": frontier_ids,
        "reason": "Multiple non-dominated scenarios remain; choosing one requires explicit decision preferences or constraints.",
    }
