"""Assemble Gate F v2 scenario metrics without inventing or imputing values."""
from __future__ import annotations

from pathlib import Path
from typing import Mapping
import pandas as pd

from src.gate_f_contract_v2 import validate_metric_contract_v2, validate_metric_subset_v2
from src.gate_f_inputs import strict_bool_series


ALLOWED_STATUSES = {"FACT", "DERIVED", "ESTIMATE", "RECONSTRUCTED", "MODEL OUTPUT", "FIELD CHECK"}

CATALOG_COLUMNS = (
    "scenario_id", "scenario_name", "topology_family", "is_baseline",
    "scenario_epistemic_status", "scenario_source",
)

B_METRICS = ("population_covered_pct", "territories_served_count")
C_METRICS = ("s8_useful_connection_pct",)
D_METRICS = ("road_feasible",)
E_METRICS = ("headway_combined_min", "annual_bus_km", "minimum_scheduled_vehicles")


def _metric_columns(metrics: tuple[str, ...]) -> tuple[str, ...]:
    columns: list[str] = ["scenario_id"]
    for metric in metrics:
        columns.extend(
            [
                metric,
                f"{metric}__status",
                f"{metric}__source",
                f"{metric}__unit",
                f"{metric}__semantics",
                f"{metric}__comparison_basis",
            ]
        )
        # uncertainty bounds are optional and are preserved if present.
    return tuple(columns)


def _read(path: str | Path, required: tuple[str, ...], name: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"{name}: missing columns: {missing}")
    if frame.empty:
        raise ValueError(f"{name}: empty fragment")
    ids = frame["scenario_id"].astype(str).str.strip()
    if frame["scenario_id"].isna().any() or ids.eq("").any() or ids.duplicated().any():
        raise ValueError(f"{name}: scenario_id must be non-empty and unique")
    return frame.copy()


def _validate_status_sources(frame: pd.DataFrame, metrics: tuple[str, ...], name: str) -> None:
    for metric in metrics:
        status_col = f"{metric}__status"
        source_col = f"{metric}__source"
        status = frame[status_col].astype(str).str.strip().str.upper()
        bad = sorted(set(status) - ALLOWED_STATUSES)
        if bad:
            raise ValueError(f"{name}: unsupported status for {metric}: {bad}")
        source = frame[source_col]
        if source.isna().any() or source.astype(str).str.strip().eq("").any():
            raise ValueError(f"{name}: {metric} requires traceable source")


def _catalog(path: str | Path) -> pd.DataFrame:
    frame = _read(path, CATALOG_COLUMNS, "catalog")
    frame["is_baseline"] = strict_bool_series(frame["is_baseline"], "is_baseline")
    if int(frame["is_baseline"].sum()) != 1:
        raise ValueError("catalog: exactly one baseline is required")
    status = frame["scenario_epistemic_status"].astype(str).str.strip().str.upper()
    bad = sorted(set(status) - ALLOWED_STATUSES)
    if bad:
        raise ValueError(f"catalog: unsupported scenario epistemic status: {bad}")
    for column in ("scenario_name", "topology_family", "scenario_source"):
        values = frame[column]
        if values.isna().any() or values.astype(str).str.strip().eq("").any():
            raise ValueError(f"catalog: {column} must be non-empty")
    return frame


def _fragment(path: str | Path, metrics: tuple[str, ...], name: str) -> pd.DataFrame:
    frame = _read(path, _metric_columns(metrics), name)
    _validate_status_sources(frame, metrics, name)
    validate_metric_subset_v2(frame, metrics)
    return frame


def _validate_scenario_set(frame: pd.DataFrame, name: str, catalog_ids: set[str], eligible_ids: set[str]) -> None:
    ids = set(frame["scenario_id"].astype(str))
    unknown = ids - catalog_ids
    missing = eligible_ids - ids
    if unknown:
        raise ValueError(f"{name}: unknown scenarios: {sorted(unknown)}")
    if missing:
        raise ValueError(f"{name}: missing eligible scenarios: {sorted(missing)}")


def _preserve_optional_bounds(frame: pd.DataFrame, metrics: tuple[str, ...]) -> pd.DataFrame:
    keep = list(_metric_columns(metrics))
    for metric in metrics:
        lower, upper = f"{metric}__lower", f"{metric}__upper"
        if (lower in frame.columns) != (upper in frame.columns):
            raise ValueError(f"{metric}: uncertainty requires both lower and upper columns")
        if lower in frame.columns:
            keep.extend([lower, upper])
    return frame[keep].copy()


def assemble_gate_f_inputs_v2(
    catalog_path: str | Path,
    gate_b_path: str | Path,
    gate_c_path: str | Path,
    gate_d_path: str | Path,
    gate_e_path: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    catalog = _catalog(catalog_path)
    catalog_ids = set(catalog["scenario_id"].astype(str))

    d_required = _metric_columns(D_METRICS) + ("road_uncertainty_status", "road_uncertainty_source")
    gate_d = _read(gate_d_path, d_required, "gate_d")
    _validate_status_sources(gate_d, D_METRICS, "gate_d")
    validate_metric_subset_v2(gate_d, D_METRICS)
    if set(gate_d["scenario_id"].astype(str)) != catalog_ids:
        raise ValueError("gate_d: structural routing eligibility must cover the entire scenario catalog")
    gate_d["road_feasible"] = strict_bool_series(gate_d["road_feasible"], "road_feasible")
    uncertainty = gate_d["road_uncertainty_status"].astype(str).str.strip().str.upper()
    if (~uncertainty.isin({"RESOLVED", "QUANTIFIED", "UNKNOWN"})).any():
        raise ValueError("gate_d: invalid road_uncertainty_status")
    if gate_d["road_uncertainty_source"].isna().any() or gate_d["road_uncertainty_source"].astype(str).str.strip().eq("").any():
        raise ValueError("gate_d: road uncertainty requires traceable source")

    eligible_ids = set(gate_d.loc[gate_d["road_feasible"], "scenario_id"].astype(str))
    if len(eligible_ids) < 2:
        raise ValueError("gate_d: Gate F v2 requires at least two structurally route-eligible scenarios")
    baseline_id = str(catalog.loc[catalog["is_baseline"], "scenario_id"].iloc[0])
    if baseline_id not in eligible_ids:
        raise ValueError("gate_d: current-service baseline cannot be structurally route-ineligible")

    fragments: Mapping[str, tuple[pd.DataFrame, tuple[str, ...]]] = {
        "gate_b": (_fragment(gate_b_path, B_METRICS, "gate_b"), B_METRICS),
        "gate_c": (_fragment(gate_c_path, C_METRICS, "gate_c"), C_METRICS),
        "gate_e": (_fragment(gate_e_path, E_METRICS, "gate_e"), E_METRICS),
    }
    for name, (frame, _) in fragments.items():
        _validate_scenario_set(frame, name, catalog_ids, eligible_ids)

    result = catalog.loc[catalog["scenario_id"].astype(str).isin(eligible_ids)].copy()
    eligible_d = gate_d.loc[gate_d["scenario_id"].astype(str).isin(eligible_ids), list(d_required)].copy()
    result = result.merge(eligible_d, on="scenario_id", validate="one_to_one")
    for name in ("gate_b", "gate_c", "gate_e"):
        frame, metrics = fragments[name]
        frame = _preserve_optional_bounds(frame, metrics)
        frame = frame.loc[frame["scenario_id"].astype(str).isin(eligible_ids)].copy()
        result = result.merge(frame, on="scenario_id", validate="one_to_one")

    if result.isna().any().any():
        nulls = sorted(result.columns[result.isna().any()].tolist())
        raise ValueError(f"Gate F v2 assembled input contains nulls: {nulls}")
    validate_metric_contract_v2(result)

    excluded = catalog.loc[~catalog["scenario_id"].astype(str).isin(eligible_ids)].copy()
    if not excluded.empty:
        excluded = excluded.merge(
            gate_d[
                [
                    "scenario_id", "road_feasible", "road_feasible__status", "road_feasible__source",
                    "road_uncertainty_status", "road_uncertainty_source",
                ]
            ],
            on="scenario_id",
            validate="one_to_one",
        )
        excluded["gate_f_exclusion_reason"] = "STRUCTURAL_ROUTING_INELIGIBLE_GATE_D"
    return result.sort_values("scenario_id").reset_index(drop=True), excluded.sort_values("scenario_id").reset_index(drop=True)
