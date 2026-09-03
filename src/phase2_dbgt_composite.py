"""Composite-key normalization for Regione Lombardia DBGT Tema 0201.

The ArcGIS service merges many DBGT deliveries. Local CLASSREF / CLASSID values
are not globally unique across those deliveries, so every relational identity
used by Phase 2 is scoped by COD_CONS (id consegna).

Source rows remain FACT. Composite identifiers, footprint unions and consensus
records are DERIVED transformations. All semantic conflicts fail closed.
"""
from __future__ import annotations

import math
from typing import Iterable

import geopandas as gpd
import pandas as pd

BUILDING_ID_STATUS = "DERIVED_COMPOSITE_DBGT_KEY_COD_CONS_PLUS_LOCAL_ID"
RAW_FOOTPRINT_STATUS = "FACT_DBGT_ACTIVE_FOOTPRINT_SOURCE_PART"
NORMALIZED_FOOTPRINT_STATUS = "DERIVED_UNION_OF_ACTIVE_DBGT_FOOTPRINT_PARTS_BY_DELIVERY_AND_CLASSREF"
RAW_EDIFC_STATUS = "FACT_DBGT_ACTIVE_EDIFC_SOURCE_ROW"
NORMALIZED_EDIFC_STATUS = "DERIVED_CONSENSUS_BY_DELIVERY_AND_CLASSID"
RAW_VOLUME_STATUS = "FACT_DBGT_ACTIVE_VOLUME_UNIT_SOURCE_ROW"
NORMALIZED_VOLUME_STATUS = "DERIVED_UNIQUE_VOLUME_UNIT_BY_DELIVERY_AND_CLASSID"


def clean_key(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none"}:
        return ""
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


def make_composite_id(cod_cons: object, local_id: object) -> str:
    delivery = clean_key(cod_cons)
    local = clean_key(local_id)
    if not delivery or not local:
        raise ValueError(f"blank DBGT composite-key component COD_CONS={cod_cons!r} local_id={local_id!r}")
    if "::" in delivery or "::" in local:
        raise ValueError("DBGT key component contains reserved delimiter '::'")
    return f"{delivery}::{local}"


def split_composite_id(value: object) -> tuple[str, str]:
    text = clean_key(value)
    parts = text.split("::")
    if len(parts) != 2 or not all(parts):
        raise ValueError(f"invalid DBGT composite id: {value!r}")
    return parts[0], parts[1]


def _unique_non_null(values: Iterable[object]) -> list[str]:
    return sorted({x for x in (clean_key(v) for v in values) if x})


def normalize_footprints(
    raw: gpd.GeoDataFrame,
    selected_union_32632,
) -> tuple[gpd.GeoDataFrame, dict]:
    required = {"CLASSREF", "COD_CONS", "geometry"}
    if not required.issubset(raw.columns):
        raise ValueError(f"footprint columns missing: {required - set(raw.columns)}")
    if raw.crs is None:
        raise ValueError("DBGT footprints lack CRS")

    work = raw.to_crs(32632).copy()
    work = work.loc[work.geometry.notna() & ~work.geometry.is_empty].copy()
    work["geometry"] = work.geometry.make_valid()
    work = work.loc[work.intersects(selected_union_32632)].copy()
    if work.empty:
        raise RuntimeError("no active DBGT footprint source rows intersect selected geography")

    work["dbgt_cod_cons_fact"] = work["COD_CONS"].map(clean_key)
    work["dbgt_local_classref_fact"] = work["CLASSREF"].map(clean_key)
    missing = work["dbgt_cod_cons_fact"].eq("") | work["dbgt_local_classref_fact"].eq("")
    if missing.any():
        examples = work.loc[missing, [c for c in ("OBJECTID", "COD_CONS", "CLASSREF") if c in work.columns]].head(20)
        raise RuntimeError(f"active selected DBGT footprints lack composite identity: {examples.to_dict('records')}")

    work["building_id"] = [
        make_composite_id(c, r)
        for c, r in zip(work["dbgt_cod_cons_fact"], work["dbgt_local_classref_fact"])
    ]
    counts = work.groupby("building_id").size()

    rows = []
    for building_id, group in work.groupby("building_id", sort=True):
        delivery, local = split_composite_id(building_id)
        union = group.geometry.union_all().make_valid()
        if union.is_empty:
            raise RuntimeError(f"empty normalized DBGT building geometry: {building_id}")
        rows.append({
            "building_id": building_id,
            "CLASSREF": building_id,
            "dbgt_cod_cons_fact": delivery,
            "dbgt_local_classref_fact": local,
            "active_footprint_source_part_count": len(group),
            "footprint_area_m2": float(union.area),
            "building_id_epistemic_status": BUILDING_ID_STATUS,
            "geometry_epistemic_status": NORMALIZED_FOOTPRINT_STATUS,
            "raw_footprint_source_epistemic_status": RAW_FOOTPRINT_STATUS,
            "geometry": union,
        })
    out = gpd.GeoDataFrame(rows, geometry="geometry", crs=32632)
    if out["building_id"].duplicated().any():
        raise RuntimeError("composite DBGT building identity is not one-to-one after normalization")
    metrics = {
        "raw_selected_active_footprint_rows": len(work),
        "raw_unique_global_classref": int(work["dbgt_local_classref_fact"].nunique()),
        "normalized_composite_building_count": len(out),
        "composite_buildings_with_multiple_active_footprint_parts": int((counts > 1).sum()),
        "extra_active_footprint_rows_collapsed_by_composite_union": int(len(work) - len(out)),
        "max_active_footprint_parts_per_composite_building": int(counts.max()),
        "building_identity_status": BUILDING_ID_STATUS,
        "raw_geometry_status": RAW_FOOTPRINT_STATUS,
        "normalized_geometry_status": NORMALIZED_FOOTPRINT_STATUS,
        "random_used": False,
        "sampling_used": False,
    }
    return out.sort_values("building_id").reset_index(drop=True), metrics


def normalize_edifc(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    required = {"COD_CONS", "CLASSID", "EDIFC_STAT", "EDIFC_TY"}
    if not required.issubset(raw.columns):
        raise ValueError(f"EDIFC columns missing: {required - set(raw.columns)}")
    if raw.empty:
        raise RuntimeError("active composite-scoped EDIFC query returned no rows")
    work = raw.copy()
    work["dbgt_cod_cons_fact"] = work["COD_CONS"].map(clean_key)
    work["dbgt_local_classid_fact"] = work["CLASSID"].map(clean_key)
    missing = work["dbgt_cod_cons_fact"].eq("") | work["dbgt_local_classid_fact"].eq("")
    if missing.any():
        raise RuntimeError("active EDIFC row lacks COD_CONS or CLASSID")
    work["building_id"] = [
        make_composite_id(c, r)
        for c, r in zip(work["dbgt_cod_cons_fact"], work["dbgt_local_classid_fact"])
    ]
    counts = work.groupby("building_id").size()
    rows = []
    conflicts = []
    for building_id, group in work.groupby("building_id", sort=True):
        status = _unique_non_null(group["EDIFC_STAT"])
        btype = _unique_non_null(group["EDIFC_TY"])
        if len(status) > 1 or len(btype) > 1:
            conflicts.append({
                "building_id": building_id,
                "EDIFC_STAT_values": status,
                "EDIFC_TY_values": btype,
                "source_rows": len(group),
            })
            continue
        delivery, local = split_composite_id(building_id)
        rows.append({
            "building_id": building_id,
            "dbgt_cod_cons_fact": delivery,
            "dbgt_local_classid_fact": local,
            "EDIFC_STAT": status[0] if status else None,
            "EDIFC_TY": btype[0] if btype else None,
            "active_edifc_source_row_count": len(group),
            "edifc_epistemic_status": NORMALIZED_EDIFC_STATUS,
        })
    if conflicts:
        raise RuntimeError(
            "semantic conflict within DBGT composite EDIFC identity; no arbitrary resolution: "
            f"count={len(conflicts)} examples={conflicts[:20]}"
        )
    out = pd.DataFrame(rows)
    if out["building_id"].duplicated().any():
        raise RuntimeError("EDIFC composite normalization did not produce one row per building")
    metrics = {
        "raw_active_edifc_rows": len(work),
        "normalized_composite_edifc_records": len(out),
        "composite_buildings_with_multiple_active_edifc_rows": int((counts > 1).sum()),
        "extra_active_edifc_rows_collapsed": int(len(work) - len(out)),
        "max_active_edifc_rows_per_composite_building": int(counts.max()),
        "composite_edifc_semantic_conflicts": 0,
        "raw_edifc_status": RAW_EDIFC_STATUS,
        "normalized_edifc_status": NORMALIZED_EDIFC_STATUS,
    }
    return out.sort_values("building_id").reset_index(drop=True), metrics


def normalize_volume_units(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    required = {"COD_CONS", "CEDIUV", "CLASSID", "UN_VOL_AV", "Shape_Area"}
    if not required.issubset(raw.columns):
        raise ValueError(f"volume columns missing: {required - set(raw.columns)}")
    if raw.empty:
        return raw.copy(), {
            "raw_active_volume_rows": 0,
            "normalized_composite_volume_units": 0,
            "composite_volume_units_with_multiple_source_rows": 0,
            "extra_active_volume_rows_collapsed": 0,
            "composite_volume_numeric_conflicts": 0,
        }
    work = raw.copy()
    work["dbgt_cod_cons_fact"] = work["COD_CONS"].map(clean_key)
    work["dbgt_local_cediuv_fact"] = work["CEDIUV"].map(clean_key)
    work["dbgt_local_volume_classid_fact"] = work["CLASSID"].map(clean_key)
    missing = (
        work["dbgt_cod_cons_fact"].eq("")
        | work["dbgt_local_cediuv_fact"].eq("")
        | work["dbgt_local_volume_classid_fact"].eq("")
    )
    if missing.any():
        raise RuntimeError("active DBGT volume row lacks delivery, building or volume-unit id")
    work["building_id"] = [
        make_composite_id(c, r)
        for c, r in zip(work["dbgt_cod_cons_fact"], work["dbgt_local_cediuv_fact"])
    ]
    work["volume_unit_id"] = [
        make_composite_id(c, r)
        for c, r in zip(work["dbgt_cod_cons_fact"], work["dbgt_local_volume_classid_fact"])
    ]
    counts = work.groupby("volume_unit_id").size()
    numeric_fields = ("UN_VOL_AV", "UN_VOL_EX", "UN_VOL_QE", "Shape_Area")
    rows = []
    conflicts = []
    for unit_id, group in work.groupby("volume_unit_id", sort=True):
        vals = {}
        for field in numeric_fields:
            if field not in group.columns:
                continue
            numeric = pd.to_numeric(group[field], errors="coerce")
            unique = sorted({float(x) for x in numeric.dropna() if math.isfinite(float(x))})
            vals[field] = unique
        if any(len(v) > 1 for v in vals.values()):
            conflicts.append({"volume_unit_id": unit_id, "values": vals, "source_rows": len(group)})
            continue
        building_ids = sorted(set(group["building_id"]))
        if len(building_ids) != 1:
            raise RuntimeError(f"one composite volume unit links multiple buildings: {unit_id} -> {building_ids}")
        first = group.iloc[0].to_dict()
        first["building_id"] = building_ids[0]
        first["volume_unit_id"] = unit_id
        first["active_volume_source_row_count"] = len(group)
        first["volume_unit_epistemic_status"] = NORMALIZED_VOLUME_STATUS
        for field, unique in vals.items():
            first[field] = unique[0] if unique else math.nan
        rows.append(first)
    if conflicts:
        raise RuntimeError(
            "numeric conflict within DBGT composite volume-unit identity; no arbitrary resolution: "
            f"count={len(conflicts)} examples={conflicts[:20]}"
        )
    out = pd.DataFrame(rows)
    if out["volume_unit_id"].duplicated().any():
        raise RuntimeError("volume-unit composite normalization is not one-to-one")
    metrics = {
        "raw_active_volume_rows": len(work),
        "normalized_composite_volume_units": len(out),
        "composite_volume_units_with_multiple_source_rows": int((counts > 1).sum()),
        "extra_active_volume_rows_collapsed": int(len(work) - len(out)),
        "max_active_volume_source_rows_per_unit": int(counts.max()),
        "composite_volume_numeric_conflicts": 0,
        "raw_volume_status": RAW_VOLUME_STATUS,
        "normalized_volume_status": NORMALIZED_VOLUME_STATUS,
    }
    return out.sort_values("volume_unit_id").reset_index(drop=True), metrics
