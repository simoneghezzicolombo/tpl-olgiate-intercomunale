"""Assemble provenance-complete Gate F scenario metrics from upstream gate fragments.

The assembler contains no project scenario values. It enforces a lossless scenario
catalog, Gate D road eligibility, exact provenance fields, units/semantics and
one-to-one joins. Ineligible scenarios may be absent from B/C/E metric fragments,
but every eligible scenario must be present and no unknown scenario may appear.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pandas as pd

from src.gate_f_contract import validate_gate_f_metric_contract


ALLOWED_STATUSES = {"FACT", "DERIVED", "ESTIMATE", "RECONSTRUCTED", "MODEL OUTPUT", "FIELD CHECK"}


@dataclass(frozen=True)
class FragmentSpec:
    name: str
    required_columns: tuple[str, ...]


CATALOG_SPEC = FragmentSpec(
    "catalog",
    (
        "scenario_id",
        "scenario_name",
        "topology_family",
        "is_baseline",
        "scenario_epistemic_status",
        "scenario_source",
    ),
)
GATE_B_SPEC = FragmentSpec(
    "gate_b",
    (
        "scenario_id",
        "population_covered_pct",
        "population_covered_pct__status",
        "population_covered_pct__source",
        "population_covered_pct__unit",
        "population_covered_pct__semantics",
        "territories_served_count",
        "territories_served_count__status",
        "territories_served_count__source",
        "territories_served_count__unit",
        "territories_served_count__semantics",
    ),
)
GATE_C_SPEC = FragmentSpec(
    "gate_c",
    (
        "scenario_id",
        "s8_useful_connection_pct",
        "s8_useful_connection_pct__status",
        "s8_useful_connection_pct__source",
        "s8_useful_connection_pct__unit",
        "s8_useful_connection_pct__semantics",
    ),
)
GATE_D_SPEC = FragmentSpec(
    "gate_d",
    (
        "scenario_id",
        "road_feasible",
        "road_feasible__status",
        "road_feasible__source",
        "road_feasible__unit",
        "road_feasible__semantics",
    ),
)
GATE_E_SPEC = FragmentSpec(
    "gate_e",
    (
        "scenario_id",
        "headway_combined_min",
        "headway_combined_min__status",
        "headway_combined_min__source",
        "headway_combined_min__unit",
        "headway_combined_min__semantics",
        "annual_bus_km",
        "annual_bus_km__status",
        "annual_bus_km__source",
        "annual_bus_km__unit",
        "annual_bus_km__semantics",
        "peak_buses_required",
        "peak_buses_required__status",
        "peak_buses_required__source",
        "peak_buses_required__unit",
        "peak_buses_required__semantics",
    ),
)


def strict_bool_series(series: pd.Series, field: str) -> pd.Series:
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


def _read_fragment(path: str | Path, spec: FragmentSpec) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(set(spec.required_columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{spec.name}: missing columns: {missing}")
    if frame.empty:
        raise ValueError(f"{spec.name}: fragment is empty")
    ids = frame["scenario_id"]
    if ids.isna().any() or (ids.astype(str).str.strip() == "").any():
        raise ValueError(f"{spec.name}: scenario_id must be non-empty")
    if ids.duplicated().any():
        duplicates = sorted(set(ids.loc[ids.duplicated(keep=False)].astype(str)))
        raise ValueError(f"{spec.name}: duplicate scenario_id: {duplicates}")
    return frame.copy()


def _validate_status_source_pairs(frame: pd.DataFrame, spec: FragmentSpec) -> None:
    for column in frame.columns:
        if not column.endswith("__status"):
            continue
        status = frame[column].astype(str).str.strip().str.upper()
        invalid = ~status.isin(ALLOWED_STATUSES)
        if invalid.any():
            bad = sorted(set(frame.loc[invalid, column].astype(str)))
            raise ValueError(f"{spec.name}: unsupported status in {column}: {bad}")
        source_col = column[:-8] + "__source"
        if source_col not in frame.columns:
            raise ValueError(f"{spec.name}: {column} has no matching {source_col}")
        source = frame[source_col]
        if source.isna().any() or (source.astype(str).str.strip() == "").any():
            raise ValueError(f"{spec.name}: every {source_col} must be traceable")


def _validate_catalog(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["is_baseline"] = strict_bool_series(out["is_baseline"], "is_baseline")
    baseline_count = int(out["is_baseline"].sum())
    if baseline_count != 1:
        raise ValueError(f"catalog: exactly one baseline is required, found {baseline_count}")
    status = out["scenario_epistemic_status"].astype(str).str.strip().str.upper()
    if (~status.isin(ALLOWED_STATUSES)).any():
        bad = sorted(set(out.loc[~status.isin(ALLOWED_STATUSES), "scenario_epistemic_status"].astype(str)))
        raise ValueError(f"catalog: unsupported scenario epistemic status: {bad}")
    for col in ("scenario_name", "topology_family", "scenario_source"):
        values = out[col]
        if values.isna().any() or (values.astype(str).str.strip() == "").any():
            raise ValueError(f"catalog: {col} must be non-empty")
    return out


def _validate_fragment_scenario_set(
    fragment: pd.DataFrame,
    name: str,
    catalog_ids: set[str],
    eligible_ids: set[str],
) -> None:
    ids = set(fragment["scenario_id"].astype(str))
    unknown = ids - catalog_ids
    if unknown:
        raise ValueError(f"{name}: unknown scenario IDs not present in catalog: {sorted(unknown)}")
    missing_eligible = eligible_ids - ids
    if missing_eligible:
        raise ValueError(f"{name}: missing eligible scenarios: {sorted(missing_eligible)}")


def assemble_gate_f_inputs(
    catalog_path: str | Path,
    gate_b_path: str | Path,
    gate_c_path: str | Path,
    gate_d_path: str | Path,
    gate_e_path: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (eligible_metrics, exclusions) without inventing missing values."""
    catalog = _validate_catalog(_read_fragment(catalog_path, CATALOG_SPEC))
    gate_d = _read_fragment(gate_d_path, GATE_D_SPEC)
    _validate_status_source_pairs(gate_d, GATE_D_SPEC)

    catalog_ids = set(catalog["scenario_id"].astype(str))
    gate_d_ids = set(gate_d["scenario_id"].astype(str))
    if gate_d_ids != catalog_ids:
        raise ValueError(
            "gate_d: road eligibility must cover the entire scenario catalog; "
            f"missing={sorted(catalog_ids - gate_d_ids)}, unknown={sorted(gate_d_ids - catalog_ids)}"
        )

    gate_d = gate_d.copy()
    gate_d["road_feasible"] = strict_bool_series(gate_d["road_feasible"], "road_feasible")
    eligible_ids = set(gate_d.loc[gate_d["road_feasible"], "scenario_id"].astype(str))
    if not eligible_ids:
        raise ValueError("gate_d: no road-feasible scenarios remain")
    baseline_id = str(catalog.loc[catalog["is_baseline"], "scenario_id"].iloc[0])
    if baseline_id not in eligible_ids:
        raise ValueError(f"gate_d: baseline scenario {baseline_id} is marked road-infeasible")

    fragments: Mapping[str, tuple[pd.DataFrame, FragmentSpec]] = {
        "gate_b": (_read_fragment(gate_b_path, GATE_B_SPEC), GATE_B_SPEC),
        "gate_c": (_read_fragment(gate_c_path, GATE_C_SPEC), GATE_C_SPEC),
        "gate_e": (_read_fragment(gate_e_path, GATE_E_SPEC), GATE_E_SPEC),
    }
    for name, (frame, spec) in fragments.items():
        _validate_status_source_pairs(frame, spec)
        _validate_fragment_scenario_set(frame, name, catalog_ids, eligible_ids)

    eligible_catalog = catalog.loc[catalog["scenario_id"].astype(str).isin(eligible_ids)].copy()
    eligible_d = gate_d.loc[gate_d["scenario_id"].astype(str).isin(eligible_ids)].copy()
    result = eligible_catalog.merge(eligible_d, on="scenario_id", how="left", validate="one_to_one")
    for name in ("gate_b", "gate_c", "gate_e"):
        frame = fragments[name][0]
        eligible_fragment = frame.loc[frame["scenario_id"].astype(str).isin(eligible_ids)].copy()
        result = result.merge(eligible_fragment, on="scenario_id", how="left", validate="one_to_one")

    if result.isna().any().any():
        null_columns = sorted(result.columns[result.isna().any()].tolist())
        raise ValueError(f"assembled Gate F input contains nulls: {null_columns}")
    validate_gate_f_metric_contract(result)

    exclusions = catalog.loc[
        ~catalog["scenario_id"].astype(str).isin(eligible_ids),
        ["scenario_id", "scenario_name", "topology_family", "is_baseline", "scenario_epistemic_status", "scenario_source"],
    ].copy()
    if not exclusions.empty:
        exclusions = exclusions.merge(
            gate_d[
                [
                    "scenario_id",
                    "road_feasible",
                    "road_feasible__status",
                    "road_feasible__source",
                    "road_feasible__unit",
                    "road_feasible__semantics",
                ]
            ],
            on="scenario_id",
            how="left",
            validate="one_to_one",
        )
        exclusions["gate_f_exclusion_reason"] = "ROAD_INFEASIBLE_GATE_D"
    return result.sort_values("scenario_id").reset_index(drop=True), exclusions.sort_values("scenario_id").reset_index(drop=True)
