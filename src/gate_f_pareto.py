"""Gate F: provenance-aware and uncertainty-aware Pareto comparison.

This module intentionally contains no project scenario values and no default
preference weights. It compares only upstream scenario metrics carrying
explicit epistemic status and source fields. Gate D road feasibility is an
eligibility constraint and must already be true for every row entering Pareto.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
import pandas as pd


ALLOWED_INPUT_STATUSES = {
    "FACT",
    "DERIVED",
    "ESTIMATE",
    "RECONSTRUCTED",
    "MODEL OUTPUT",
    "FIELD CHECK",
}
REQUIRED_GATES = ("A", "B", "C", "D", "E")


@dataclass(frozen=True)
class Objective:
    column: str
    direction: str
    gate: str
    label: str
    unit: str = ""

    def __post_init__(self) -> None:
        if self.direction not in {"max", "min"}:
            raise ValueError(f"Invalid objective direction: {self.direction}")


DEFAULT_OBJECTIVES: tuple[Objective, ...] = (
    Objective("population_covered_pct", "max", "B", "population accessibility", "%"),
    Objective("headway_combined_min", "min", "E", "combined service headway", "min"),
    Objective("annual_bus_km", "min", "E", "annual bus-km", "bus-km/year"),
    Objective("peak_buses_required", "min", "E", "peak buses required", "vehicles"),
    Objective("s8_useful_connection_pct", "max", "C", "useful S8 connections", "%"),
    Objective("territories_served_count", "max", "B", "territories served", "count"),
)


def blocker_labels(gate_status: Mapping[str, str]) -> list[str]:
    return [f"BLOCKED_BY_GATE_{gate}" for gate in REQUIRED_GATES if gate_status.get(gate) != "PASS"]


def objective_manifest(objectives: Sequence[Objective] = DEFAULT_OBJECTIVES) -> list[dict[str, str]]:
    return [
        {
            "column": obj.column,
            "direction": obj.direction,
            "gate": obj.gate,
            "label": obj.label,
            "unit": obj.unit,
        }
        for obj in objectives
    ]


def _required_columns(objectives: Sequence[Objective]) -> set[str]:
    cols = {
        "scenario_id",
        "scenario_name",
        "topology_family",
        "scenario_epistemic_status",
        "scenario_source",
        "is_baseline",
        "road_feasible",
        "road_feasible__status",
        "road_feasible__source",
    }
    for obj in objectives:
        cols.update({obj.column, f"{obj.column}__status", f"{obj.column}__source"})
    return cols


def _strict_bool_series(series: pd.Series, field: str) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        if series.isna().any():
            raise ValueError(f"{field} contains null values")
        return series.astype(bool)
    normalized = series.astype(str).str.strip().str.lower()
    mapping = {"true": True, "false": False, "1": True, "0": False}
    invalid = ~normalized.isin(mapping)
    if invalid.any():
        bad = sorted(set(series.loc[invalid].astype(str)))
        raise ValueError(f"{field} must be boolean-like, found: {bad}")
    return normalized.map(mapping).astype(bool)


def _baseline_mask(series: pd.Series) -> pd.Series:
    return _strict_bool_series(series, "is_baseline")


def _validate_status_source(frame: pd.DataFrame, status_col: str, source_col: str, label: str) -> None:
    status = frame[status_col].astype(str).str.strip().str.upper()
    invalid = ~status.isin(ALLOWED_INPUT_STATUSES)
    if invalid.any():
        bad = sorted(set(frame.loc[invalid, status_col].astype(str)))
        raise ValueError(f"Unsupported epistemic status for {label}: {bad}")
    source = frame[source_col]
    if source.isna().any() or (source.astype(str).str.strip() == "").any():
        raise ValueError(f"Every {label} value requires a traceable source")


def _validate_uncertainty_columns(df: pd.DataFrame, obj: Objective, values: pd.Series) -> None:
    lower_col = f"{obj.column}__lower"
    upper_col = f"{obj.column}__upper"
    present = {col for col in (lower_col, upper_col) if col in df.columns}
    if present and len(present) != 2:
        raise ValueError(f"{obj.column}: uncertainty requires both {lower_col} and {upper_col}")
    if not present:
        return
    lower = pd.to_numeric(df[lower_col], errors="coerce")
    upper = pd.to_numeric(df[upper_col], errors="coerce")
    finite = np.isfinite(lower.to_numpy(dtype=float)) & np.isfinite(upper.to_numpy(dtype=float))
    estimate = df[f"{obj.column}__status"].astype(str).str.strip().str.upper().eq("ESTIMATE")
    if estimate.any() and not finite[estimate.to_numpy()].all():
        raise ValueError(f"{obj.column}: ESTIMATE rows require finite uncertainty bounds")
    bounded = lower.notna() & upper.notna()
    if (lower[bounded] > upper[bounded]).any():
        raise ValueError(f"{obj.column}: lower bound exceeds upper bound")
    if ((values[bounded] < lower[bounded]) | (values[bounded] > upper[bounded])).any():
        raise ValueError(f"{obj.column}: point value must lie inside uncertainty bounds")


def validate_scenarios(df: pd.DataFrame, objectives: Sequence[Objective] = DEFAULT_OBJECTIVES) -> None:
    missing = sorted(_required_columns(objectives) - set(df.columns))
    if missing:
        raise ValueError(f"Missing Gate F input columns: {', '.join(missing)}")
    if len(df) < 2:
        raise ValueError("Gate F requires at least two scenarios for comparison")
    ids = df["scenario_id"]
    if ids.isna().any() or (ids.astype(str).str.strip() == "").any() or ids.duplicated().any():
        raise ValueError("scenario_id must be non-null, non-empty and unique")
    baseline_count = int(_baseline_mask(df["is_baseline"]).sum())
    if baseline_count != 1:
        raise ValueError(f"Exactly one baseline scenario is required, found {baseline_count}")

    feasible = _strict_bool_series(df["road_feasible"], "road_feasible")
    if (~feasible).any():
        bad = sorted(df.loc[~feasible, "scenario_id"].astype(str).tolist())
        raise ValueError(
            "Road-infeasible scenarios must be excluded before Pareto analysis; "
            f"found: {bad}"
        )
    _validate_status_source(df, "road_feasible__status", "road_feasible__source", "road_feasible")

    scenario_status = df["scenario_epistemic_status"].astype(str).str.strip().str.upper()
    if (~scenario_status.isin(ALLOWED_INPUT_STATUSES)).any():
        bad = sorted(set(df.loc[~scenario_status.isin(ALLOWED_INPUT_STATUSES), "scenario_epistemic_status"].astype(str)))
        raise ValueError(f"Unsupported scenario epistemic status: {bad}")
    for col in ("scenario_name", "topology_family", "scenario_source"):
        values = df[col]
        if values.isna().any() or (values.astype(str).str.strip() == "").any():
            raise ValueError(f"{col} must be non-empty")

    for obj in objectives:
        values = pd.to_numeric(df[obj.column], errors="coerce")
        if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
            raise ValueError(f"Objective {obj.column} must contain only finite numeric values")
        if obj.column == "headway_combined_min" and (values <= 0).any():
            raise ValueError("headway_combined_min must be > 0")
        if obj.column in {"population_covered_pct", "s8_useful_connection_pct"} and (~values.between(0, 100)).any():
            raise ValueError(f"{obj.column} must be between 0 and 100")
        if obj.column == "annual_bus_km" and (values <= 0).any():
            raise ValueError("annual_bus_km must be > 0")
        if obj.column == "peak_buses_required":
            if (values < 1).any() or not np.equal(values, np.floor(values)).all():
                raise ValueError("peak_buses_required must be an integer >= 1")
        if obj.column == "territories_served_count":
            if (values < 0).any() or not np.equal(values, np.floor(values)).all():
                raise ValueError("territories_served_count must be a non-negative integer")
        _validate_status_source(
            df,
            f"{obj.column}__status",
            f"{obj.column}__source",
            obj.column,
        )
        _validate_uncertainty_columns(df, obj, values)


def _utility_matrix(df: pd.DataFrame, objectives: Sequence[Objective]) -> np.ndarray:
    matrix = df[[o.column for o in objectives]].astype(float).to_numpy()
    signs = np.array([1.0 if o.direction == "max" else -1.0 for o in objectives])
    return matrix * signs


def identify_pareto_frontier(df: pd.DataFrame, objectives: Sequence[Objective] = DEFAULT_OBJECTIVES) -> pd.DataFrame:
    """Return point-estimate Pareto flags and IDs that dominate each scenario."""
    validate_scenarios(df, objectives)
    out = df.copy().reset_index(drop=True)
    utility = _utility_matrix(out, objectives)
    dominated_by: list[list[str]] = [[] for _ in range(len(out))]

    for i in range(len(out)):
        for j in range(len(out)):
            if i == j:
                continue
            if np.all(utility[j] >= utility[i]) and np.any(utility[j] > utility[i]):
                dominated_by[i].append(str(out.loc[j, "scenario_id"]))

    out["pareto_optimal"] = [not ids for ids in dominated_by]
    out["dominated_by"] = [";".join(sorted(ids)) for ids in dominated_by]
    return out


def dominance_pairs(df: pd.DataFrame, objectives: Sequence[Objective] = DEFAULT_OBJECTIVES) -> pd.DataFrame:
    """Return an auditable table of point-estimate dominance relations."""
    out = identify_pareto_frontier(df, objectives)
    lookup = out.set_index("scenario_id")
    rows: list[dict[str, object]] = []
    for dominated_id, raw in out.set_index("scenario_id")["dominated_by"].items():
        if not raw:
            continue
        for dominator_id in raw.split(";"):
            strict = []
            equal = []
            for obj in objectives:
                a = float(lookup.loc[dominator_id, obj.column])
                b = float(lookup.loc[dominated_id, obj.column])
                (equal if a == b else strict).append(obj.column)
            rows.append(
                {
                    "dominator_scenario_id": dominator_id,
                    "dominated_scenario_id": dominated_id,
                    "strictly_better_objectives": ";".join(strict),
                    "equal_objectives": ";".join(equal),
                }
            )
    return pd.DataFrame(
        rows,
        columns=[
            "dominator_scenario_id",
            "dominated_scenario_id",
            "strictly_better_objectives",
            "equal_objectives",
        ],
    )


def leave_one_objective_out_robustness(
    df: pd.DataFrame, objectives: Sequence[Objective] = DEFAULT_OBJECTIVES
) -> pd.DataFrame:
    """Preference-free sensitivity: full frontier plus one run per omitted objective."""
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


def unbounded_estimate_metrics(df: pd.DataFrame, objectives: Sequence[Objective] = DEFAULT_OBJECTIVES) -> list[str]:
    """Return scenario:metric labels for ESTIMATE values without finite lower/upper bounds."""
    issues: list[str] = []
    for obj in objectives:
        status = df[f"{obj.column}__status"].astype(str).str.strip().str.upper()
        estimate_rows = status.eq("ESTIMATE")
        if not estimate_rows.any():
            continue
        lower_col = f"{obj.column}__lower"
        upper_col = f"{obj.column}__upper"
        if lower_col not in df.columns or upper_col not in df.columns:
            issues.extend(f"{sid}:{obj.column}" for sid in df.loc[estimate_rows, "scenario_id"].astype(str))
            continue
        lower = pd.to_numeric(df[lower_col], errors="coerce")
        upper = pd.to_numeric(df[upper_col], errors="coerce")
        bounded = np.isfinite(lower.to_numpy(dtype=float)) & np.isfinite(upper.to_numpy(dtype=float))
        bad_mask = estimate_rows.to_numpy() & ~bounded
        issues.extend(f"{sid}:{obj.column}" for sid in df.loc[bad_mask, "scenario_id"].astype(str))
    return sorted(issues)


def _utility_bounds(df: pd.DataFrame, obj: Objective) -> tuple[np.ndarray, np.ndarray]:
    point = pd.to_numeric(df[obj.column], errors="raise").to_numpy(dtype=float)
    lower_col = f"{obj.column}__lower"
    upper_col = f"{obj.column}__upper"
    if lower_col in df.columns and upper_col in df.columns:
        lower = pd.to_numeric(df[lower_col], errors="coerce").to_numpy(dtype=float)
        upper = pd.to_numeric(df[upper_col], errors="coerce").to_numpy(dtype=float)
        lower = np.where(np.isfinite(lower), lower, point)
        upper = np.where(np.isfinite(upper), upper, point)
    else:
        lower = point.copy()
        upper = point.copy()
    if obj.direction == "max":
        return lower, upper
    return -upper, -lower


def identify_robust_pareto_frontier(
    df: pd.DataFrame, objectives: Sequence[Objective] = DEFAULT_OBJECTIVES
) -> pd.DataFrame:
    """Interval-robust Pareto frontier.

    Scenario j robustly dominates i only when j's worst-case utility is at least
    i's best-case utility for every objective and strictly better for at least one.
    ESTIMATE values without finite bounds are refused rather than treated as exact.
    """
    validate_scenarios(df, objectives)
    unbounded = unbounded_estimate_metrics(df, objectives)
    if unbounded:
        raise ValueError(f"Unbounded ESTIMATE metrics prevent robust Pareto: {unbounded}")
    out = df.copy().reset_index(drop=True)
    worst = np.column_stack([_utility_bounds(out, obj)[0] for obj in objectives])
    best = np.column_stack([_utility_bounds(out, obj)[1] for obj in objectives])
    dominated_by: list[list[str]] = [[] for _ in range(len(out))]
    for i in range(len(out)):
        for j in range(len(out)):
            if i == j:
                continue
            if np.all(worst[j] >= best[i]) and np.any(worst[j] > best[i]):
                dominated_by[i].append(str(out.loc[j, "scenario_id"]))
    out["robust_pareto_optimal"] = [not ids for ids in dominated_by]
    out["robustly_dominated_by"] = [";".join(sorted(ids)) for ids in dominated_by]
    return out


def build_tradeoffs(df: pd.DataFrame, objectives: Sequence[Objective] = DEFAULT_OBJECTIVES) -> pd.DataFrame:
    """Add deltas versus the input baseline; no baseline value is hardcoded here."""
    validate_scenarios(df, objectives)
    baseline = df.loc[_baseline_mask(df["is_baseline"])].iloc[0]
    out = df.copy()
    for obj in objectives:
        out[f"delta_vs_baseline__{obj.column}"] = out[obj.column].astype(float) - float(baseline[obj.column])
    return out


def build_epistemic_audit(df: pd.DataFrame, objectives: Sequence[Objective] = DEFAULT_OBJECTIVES) -> pd.DataFrame:
    """Return one row per scenario/objective with status, source and uncertainty."""
    validate_scenarios(df, objectives)
    rows: list[dict[str, object]] = []
    for _, scenario in df.iterrows():
        for obj in objectives:
            lower_col = f"{obj.column}__lower"
            upper_col = f"{obj.column}__upper"
            rows.append(
                {
                    "scenario_id": scenario["scenario_id"],
                    "objective": obj.column,
                    "objective_gate": obj.gate,
                    "direction": obj.direction,
                    "unit": obj.unit,
                    "value": float(scenario[obj.column]),
                    "lower": scenario[lower_col] if lower_col in df.columns else np.nan,
                    "upper": scenario[upper_col] if upper_col in df.columns else np.nan,
                    "epistemic_status": scenario[f"{obj.column}__status"],
                    "source": scenario[f"{obj.column}__source"],
                }
            )
    return pd.DataFrame(rows)


def decision_summary(
    pareto_df: pd.DataFrame,
    gate_status: Mapping[str, str],
    objectives: Sequence[Objective] = DEFAULT_OBJECTIVES,
) -> dict:
    blockers = blocker_labels(gate_status)
    point_frontier_ids = sorted(
        pareto_df.loc[pareto_df["pareto_optimal"], "scenario_id"].astype(str).tolist()
    )
    if blockers:
        return {
            "verdict": "PROVISIONAL",
            "dependency_status": blockers,
            "evidence_status": [],
            "recommendation_status": "BLOCKED",
            "recommended_scenario_id": None,
            "pareto_scenario_ids": point_frontier_ids,
            "robust_pareto_scenario_ids": None,
            "reason": "Upstream gates are not all PASS; no definitive recommendation is permitted.",
        }

    unbounded = unbounded_estimate_metrics(pareto_df, objectives)
    if unbounded:
        return {
            "verdict": "PROVISIONAL",
            "dependency_status": [],
            "evidence_status": ["UNBOUNDED_ESTIMATE_UNCERTAINTY"],
            "recommendation_status": "NO_DEFINITIVE_RECOMMENDATION_UNCERTAINTY",
            "recommended_scenario_id": None,
            "pareto_scenario_ids": point_frontier_ids,
            "robust_pareto_scenario_ids": None,
            "unbounded_estimates": unbounded,
            "reason": "At least one ESTIMATE objective lacks finite uncertainty bounds.",
        }

    robust = identify_robust_pareto_frontier(pareto_df, objectives)
    robust_ids = sorted(
        robust.loc[robust["robust_pareto_optimal"], "scenario_id"].astype(str).tolist()
    )
    if len(robust_ids) == 1:
        return {
            "verdict": "PASS",
            "dependency_status": [],
            "evidence_status": [],
            "recommendation_status": "UNIQUE_ROBUST_PARETO_DOMINANT",
            "recommended_scenario_id": robust_ids[0],
            "pareto_scenario_ids": point_frontier_ids,
            "robust_pareto_scenario_ids": robust_ids,
            "reason": "Exactly one scenario remains non-dominated under worst-vs-best uncertainty bounds.",
        }
    return {
        "verdict": "PASS",
        "dependency_status": [],
        "evidence_status": [],
        "recommendation_status": "NO_SINGLE_WINNER_ROBUST_PARETO_TRADEOFF",
        "recommended_scenario_id": None,
        "pareto_scenario_ids": point_frontier_ids,
        "robust_pareto_scenario_ids": robust_ids,
        "reason": "Multiple robustly non-dominated scenarios remain; choosing one requires explicit decision preferences or constraints.",
    }
