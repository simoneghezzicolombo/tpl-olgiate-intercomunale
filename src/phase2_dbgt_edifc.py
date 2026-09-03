"""Fail-closed normalization for repeated active DBGT EDIFC attribute rows.

Multiple active source rows may exist for one CLASSID because DBGT data are
published through multiple construction/delivery records. The fields used for
residential classification may only be collapsed when all non-null semantic
values agree. Conflicting EDIFC_STAT or EDIFC_TY values are never resolved by
row order, OBJECTID, COD_CONS or arbitrary preference.
"""
from __future__ import annotations

import math

import pandas as pd

SEMANTIC_FIELDS = ("EDIFC_STAT", "EDIFC_TY")
PROVENANCE_FIELDS = ("OBJECTID", "FONTE", "SCALA", "COD_CONS", "DATA_INI")
CONSENSUS_STATUS = "DERIVED_CONSENSUS_FROM_ACTIVE_DBGT_EDIFC_ROWS"
RAW_STATUS = "FACT_DBGT_ACTIVE_EDIFC_SOURCE_ROW"


def _clean(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


def _unique_non_null(series: pd.Series) -> list[str]:
    return sorted({v for v in (_clean(x) for x in series) if v is not None})


def consolidate_active_edifc(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Return one consensus record per CLASSID and explicit audit metrics.

    Null/missing values do not conflict with one observed value. Two different
    non-null values in either EDIFC_STAT or EDIFC_TY are a semantic conflict and
    raise RuntimeError. This is intentionally fail closed.
    """
    required = {"CLASSID", *SEMANTIC_FIELDS}
    if not required.issubset(raw.columns):
        raise ValueError(f"EDIFC columns missing: {required - set(raw.columns)}")
    if raw.empty:
        return raw.copy(), {
            "raw_active_edifc_rows": 0,
            "unique_active_edifc_classid": 0,
            "classid_with_multiple_active_edifc_rows": 0,
            "extra_active_edifc_rows_collapsed": 0,
            "max_active_edifc_rows_per_classid": 0,
            "semantic_conflict_classid": 0,
        }

    work = raw.copy()
    work["CLASSID"] = work["CLASSID"].map(_clean)
    blank = int(work["CLASSID"].isna().sum())
    if blank:
        raise RuntimeError(f"active EDIFC rows with blank CLASSID: {blank}")

    rows: list[dict] = []
    conflict_examples: list[dict] = []
    duplicate_groups = 0
    max_rows = 0
    for classid, group in work.groupby("CLASSID", sort=True, dropna=False):
        max_rows = max(max_rows, len(group))
        if len(group) > 1:
            duplicate_groups += 1
        semantic: dict[str, str | None] = {}
        conflict = False
        for field in SEMANTIC_FIELDS:
            values = _unique_non_null(group[field])
            if len(values) > 1:
                conflict = True
            semantic[field] = values[0] if len(values) == 1 else None
        if conflict:
            conflict_examples.append({
                "CLASSID": classid,
                "active_rows": len(group),
                "EDIFC_STAT_values": _unique_non_null(group["EDIFC_STAT"]),
                "EDIFC_TY_values": _unique_non_null(group["EDIFC_TY"]),
                "COD_CONS_values": _unique_non_null(group["COD_CONS"]) if "COD_CONS" in group else [],
                "OBJECTID_values": _unique_non_null(group["OBJECTID"]) if "OBJECTID" in group else [],
            })
            continue
        row = {
            "CLASSID": classid,
            **semantic,
            "active_edifc_source_row_count": len(group),
            "edifc_consensus_epistemic_status": CONSENSUS_STATUS,
        }
        for field in PROVENANCE_FIELDS:
            if field in group.columns:
                row[f"{field}_source_values"] = "|".join(_unique_non_null(group[field]))
        rows.append(row)

    if conflict_examples:
        raise RuntimeError(
            "active EDIFC semantic conflicts for CLASSID; no arbitrary resolution allowed: "
            f"count={len(conflict_examples)} examples={conflict_examples[:20]}"
        )

    out = pd.DataFrame(rows)
    if out["CLASSID"].duplicated().any():
        raise RuntimeError("EDIFC consensus normalization did not produce one row per CLASSID")
    metrics = {
        "raw_active_edifc_rows": len(work),
        "unique_active_edifc_classid": int(work["CLASSID"].nunique()),
        "classid_with_multiple_active_edifc_rows": duplicate_groups,
        "extra_active_edifc_rows_collapsed": int(len(work) - work["CLASSID"].nunique()),
        "max_active_edifc_rows_per_classid": max_rows,
        "semantic_conflict_classid": 0,
        "raw_edifc_epistemic_status": RAW_STATUS,
        "consensus_edifc_epistemic_status": CONSENSUS_STATUS,
    }
    return out.sort_values("CLASSID").reset_index(drop=True), metrics
