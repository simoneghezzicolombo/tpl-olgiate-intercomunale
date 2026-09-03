"""Deterministic Phase 2 building-level dasymetric population core.

Pure transformation functions only. Network acquisition, geometry I/O and walking
routing are handled by the production script. No randomisation is used.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import pandas as pd

RESIDENTIAL_USE_CODES = {"01", "0101"}
UNKNOWN_USE_CODES = {"", "95", "-99991", "-99992", "-99993", "-99994"}
CONSTRUCTED_STATUS = "03"
UNKNOWN_SENTINELS = {"", "-99991", "-99992", "-99993", "-99994"}
NONRESIDENTIAL_TYPE_CODES = {
    "06", "07", "08", "10", "11", "12", "13", "14", "15", "16", "18",
    "19", "20", "21", "22",
}


@dataclass(frozen=True)
class BuildingClassification:
    plausibility: str
    eligible_primary: bool
    eligible_fallback: bool
    residential_use_present: bool
    mixed_use: bool
    uncertainty_flags: tuple[str, ...]


def clean_code(value: object) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


def is_fictitious_section(section_code: object) -> bool:
    """Return True for ISTAT non-ordinary section suffixes 888888x/999999x."""
    code = clean_code(section_code)
    if len(code) < 6:
        return False
    tail7 = code[-7:]
    tail6 = code[-6:]
    return tail6 in {"888888", "999999"} or (
        len(tail7) == 7
        and tail7[:6] in {"888888", "999999"}
        and tail7[-1].isdigit()
    )


def classify_building(
    *, status_code: object, type_code: object, use_codes: Iterable[object]
) -> BuildingClassification:
    status = clean_code(status_code)
    btype = clean_code(type_code)
    uses = {clean_code(v) for v in use_codes if clean_code(v)}
    uncertainty: list[str] = []

    if status != CONSTRUCTED_STATUS:
        return BuildingClassification(
            plausibility="EXCLUDED_NOT_CONSTRUCTED",
            eligible_primary=False,
            eligible_fallback=False,
            residential_use_present=False,
            mixed_use=False,
            uncertainty_flags=(f"building_status={status or 'missing'}",),
        )

    residential = bool(uses & RESIDENTIAL_USE_CODES)
    known_nonresidential = {
        u for u in uses
        if u not in RESIDENTIAL_USE_CODES and u not in UNKNOWN_USE_CODES
    }
    unknown_only = not uses or all(u in UNKNOWN_USE_CODES for u in uses)

    if btype in UNKNOWN_SENTINELS:
        uncertainty.append("building_type_unknown")
    elif btype in NONRESIDENTIAL_TYPE_CODES and residential:
        uncertainty.append(f"residential_use_type_contradiction={btype}")

    if residential and known_nonresidential:
        uncertainty.append("mixed_use_no_residential_floor_area_share")
        return BuildingClassification(
            plausibility="MIXED_RESIDENTIAL",
            eligible_primary=True,
            eligible_fallback=False,
            residential_use_present=True,
            mixed_use=True,
            uncertainty_flags=tuple(sorted(uncertainty)),
        )
    if residential:
        return BuildingClassification(
            plausibility="EXPLICIT_RESIDENTIAL",
            eligible_primary=True,
            eligible_fallback=False,
            residential_use_present=True,
            mixed_use=False,
            uncertainty_flags=tuple(sorted(uncertainty)),
        )
    if unknown_only:
        uncertainty.append("building_use_unknown_or_other")
        return BuildingClassification(
            plausibility="UNKNOWN_OR_OTHER_USE",
            eligible_primary=False,
            eligible_fallback=True,
            residential_use_present=False,
            mixed_use=False,
            uncertainty_flags=tuple(sorted(uncertainty)),
        )
    return BuildingClassification(
        plausibility="EXPLICIT_NONRESIDENTIAL",
        eligible_primary=False,
        eligible_fallback=False,
        residential_use_present=False,
        mixed_use=False,
        uncertainty_flags=tuple(sorted(uncertainty)),
    )


def derive_section_targets(
    sections: pd.DataFrame,
    municipal_targets: pd.DataFrame,
    *,
    municipality_col: str = "municipality_code",
    section_population_col: str = "population_2023_fact",
    municipal_population_col: str = "population_2025_posas_fact",
) -> pd.DataFrame:
    """Scale official section counts within municipality to exact POSAS targets.

    The resulting section target is DERIVED, not an observed 2025 section count.
    """
    required_s = {municipality_col, section_population_col}
    required_m = {municipality_col, municipal_population_col}
    if not required_s.issubset(sections.columns):
        raise ValueError(f"section columns missing: {required_s - set(sections.columns)}")
    if not required_m.issubset(municipal_targets.columns):
        raise ValueError(f"municipal columns missing: {required_m - set(municipal_targets.columns)}")

    out = sections.copy()
    out[section_population_col] = pd.to_numeric(out[section_population_col], errors="raise")
    if (out[section_population_col] < 0).any():
        raise ValueError("negative official section population")
    muni = municipal_targets[[municipality_col, municipal_population_col]].copy()
    muni[municipal_population_col] = pd.to_numeric(muni[municipal_population_col], errors="raise")
    if muni[municipality_col].duplicated().any():
        raise ValueError("duplicate municipal calibration target")

    sums = (
        out.groupby(municipality_col, as_index=False)[section_population_col]
        .sum()
        .rename(columns={section_population_col: "section_population_2023_sum"})
    )
    factors = muni.merge(sums, on=municipality_col, how="left", validate="one_to_one")
    if factors["section_population_2023_sum"].isna().any():
        raise ValueError("municipality lacks section population")
    if (factors["section_population_2023_sum"] <= 0).any():
        raise ValueError("municipality has non-positive section population denominator")
    factors["municipal_scale_2023_to_2025"] = (
        factors[municipal_population_col] / factors["section_population_2023_sum"]
    )
    out = out.merge(
        factors[[municipality_col, municipal_population_col, "municipal_scale_2023_to_2025"]],
        on=municipality_col,
        how="left",
        validate="many_to_one",
    )
    if out["municipal_scale_2023_to_2025"].isna().any():
        missing = sorted(out.loc[out["municipal_scale_2023_to_2025"].isna(), municipality_col].astype(str).unique())
        raise ValueError(f"missing POSAS targets: {missing}")
    out["section_population_2025_derived"] = (
        out[section_population_col] * out["municipal_scale_2023_to_2025"]
    )
    out["section_target_epistemic_status"] = "DERIVED_SECTION_TARGET_2025_FROM_ISTAT2023_POSAS2025"
    return out


def allocate_section_population(
    pieces: pd.DataFrame,
    section_targets: pd.DataFrame,
    *,
    section_col: str = "section_id",
    building_col: str = "building_id",
    primary_col: str = "eligible_primary",
    fallback_col: str = "eligible_fallback",
    weight_col: str = "allocation_weight",
    target_col: str = "section_population_2025_derived",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Allocate each ordinary section target to plausible building-section pieces.

    Primary residential/mixed buildings are used whenever at least one exists.
    Unknown-use buildings are used only when a populated section has no primary
    candidate. Explicit non-residential and non-constructed buildings never receive
    residents. A section without any admissible building is retained as residual.
    """
    out_rows: list[dict] = []
    residual_rows: list[dict] = []
    targets = section_targets.set_index(section_col, drop=False)
    if targets.index.duplicated().any():
        raise ValueError("duplicate section target")

    for section_id, target_row in targets.iterrows():
        target = float(target_row[target_col])
        if target < 0 or not math.isfinite(target):
            raise ValueError(f"invalid section target {section_id}: {target}")
        subset = pieces.loc[pieces[section_col] == section_id].copy()
        primary = subset.loc[subset[primary_col].astype(bool)].copy()
        if len(primary):
            chosen = primary
            tier = "PRIMARY_EXPLICIT_OR_MIXED_RESIDENTIAL"
        else:
            chosen = subset.loc[subset[fallback_col].astype(bool)].copy()
            tier = "FALLBACK_UNKNOWN_USE_ONLY"

        if target == 0:
            residual_rows.append({
                section_col: section_id,
                "section_population_2025_derived": target,
                "allocated_population": 0.0,
                "unallocated_population": 0.0,
                "allocation_tier": "ZERO_POPULATION_SECTION",
            })
            continue
        if chosen.empty:
            residual_rows.append({
                section_col: section_id,
                "section_population_2025_derived": target,
                "allocated_population": 0.0,
                "unallocated_population": target,
                "allocation_tier": "UNALLOCATED_NO_PLAUSIBLE_BUILDING",
            })
            continue
        weights = pd.to_numeric(chosen[weight_col], errors="coerce")
        valid = weights.notna() & (weights > 0)
        chosen = chosen.loc[valid].copy()
        weights = weights.loc[valid]
        if chosen.empty or float(weights.sum()) <= 0:
            residual_rows.append({
                section_col: section_id,
                "section_population_2025_derived": target,
                "allocated_population": 0.0,
                "unallocated_population": target,
                "allocation_tier": "UNALLOCATED_NO_POSITIVE_WEIGHT",
            })
            continue
        total_weight = float(weights.sum())
        chosen["building_piece_population_model"] = target * weights / total_weight
        chosen["allocation_tier"] = tier
        chosen["resident_estimate_epistemic_status"] = "MODEL_OUTPUT_DASYMETRIC_BUILDING_POPULATION"
        out_rows.extend(chosen.to_dict("records"))
        residual_rows.append({
            section_col: section_id,
            "section_population_2025_derived": target,
            "allocated_population": target,
            "unallocated_population": 0.0,
            "allocation_tier": tier,
        })

    allocations = pd.DataFrame(out_rows)
    residuals = pd.DataFrame(residual_rows)
    return allocations, residuals


def reconcile_municipal_population(
    *,
    building_allocations: pd.DataFrame,
    section_targets: pd.DataFrame,
    section_residuals: pd.DataFrame,
    municipal_targets: pd.DataFrame,
    municipality_col: str = "municipality_code",
    section_col: str = "section_id",
    target_col: str = "population_2025_posas_fact",
) -> pd.DataFrame:
    """Prove exact accounting: buildings + section residuals = POSAS municipal target."""
    section_to_muni = section_targets[[section_col, municipality_col]].drop_duplicates()
    if section_to_muni[section_col].duplicated().any():
        raise ValueError("section maps to multiple municipalities")

    if building_allocations.empty:
        alloc = pd.DataFrame(columns=[municipality_col, "building_population_model"])
    else:
        # Production building-section pieces already carry municipality_code. Drop it
        # before the authoritative section->municipality join so pandas cannot create
        # municipality_code_x/municipality_code_y and silently break accounting.
        alloc_input = building_allocations.drop(columns=[municipality_col], errors="ignore")
        alloc = alloc_input.merge(section_to_muni, on=section_col, how="left", validate="many_to_one")
        if alloc[municipality_col].isna().any():
            raise ValueError("building allocation section lacks municipality mapping")
        alloc = (
            alloc.groupby(municipality_col, as_index=False)["building_piece_population_model"]
            .sum()
            .rename(columns={"building_piece_population_model": "building_population_model"})
        )

    residual_input = section_residuals.drop(columns=[municipality_col], errors="ignore")
    res = residual_input.merge(section_to_muni, on=section_col, how="left", validate="one_to_one")
    if res[municipality_col].isna().any():
        raise ValueError("section residual lacks municipality mapping")
    res = (
        res.groupby(municipality_col, as_index=False)["unallocated_population"]
        .sum()
        .rename(columns={"unallocated_population": "section_residual_population"})
    )
    result = municipal_targets[[municipality_col, target_col]].merge(alloc, on=municipality_col, how="left")
    result = result.merge(res, on=municipality_col, how="left")
    result[["building_population_model", "section_residual_population"]] = result[
        ["building_population_model", "section_residual_population"]
    ].fillna(0.0)
    result["accounted_population"] = result["building_population_model"] + result["section_residual_population"]
    result["reconciliation_error"] = result["accounted_population"] - result[target_col]
    result["reconciliation_pass"] = result["reconciliation_error"].abs() <= 1e-7
    if not result["reconciliation_pass"].all():
        raise ValueError("municipal population reconciliation failed")
    return result
