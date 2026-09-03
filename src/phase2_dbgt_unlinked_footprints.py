"""Fail-closed handling of active DBGT footprint rows without relational CLASSREF.

Rows with official COD_CONS but blank CLASSREF are retained in raw provenance but
cannot be treated as buildings because they cannot be joined to EDIFC/use/volume
records. They are excluded from allocation and their count/area are reported.
A missing COD_CONS remains a hard failure because delivery scope is unknown.
"""
from __future__ import annotations

import math

import geopandas as gpd
from shapely import make_valid as shapely_make_valid

from src.phase2_dbgt_composite import (
    BUILDING_ID_STATUS,
    NORMALIZED_FOOTPRINT_STATUS,
    RAW_FOOTPRINT_STATUS,
    clean_key,
    make_composite_id,
    split_composite_id,
)

UNLINKED_STATUS = "FACT_DBGT_ACTIVE_FOOTPRINT_WITHOUT_CLASSREF_EXCLUDED_FROM_BUILDING_ALLOCATION"


def normalize_footprints(raw: gpd.GeoDataFrame, selected_union_32632):
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
    missing_delivery = work["dbgt_cod_cons_fact"].eq("")
    if missing_delivery.any():
        examples = work.loc[missing_delivery, [c for c in ("OBJECTID", "COD_CONS", "CLASSREF") if c in work.columns]].head(20)
        raise RuntimeError(f"active selected DBGT footprint lacks COD_CONS delivery scope: {examples.to_dict('records')}")

    unlinked = work["dbgt_local_classref_fact"].eq("")
    unlinked_rows = work.loc[unlinked].copy()
    linked = work.loc[~unlinked].copy()
    if linked.empty:
        raise RuntimeError("all selected active DBGT footprint rows lack CLASSREF; no auditable building universe")

    linked["building_id"] = [
        make_composite_id(c, r)
        for c, r in zip(linked["dbgt_cod_cons_fact"], linked["dbgt_local_classref_fact"])
    ]
    counts = linked.groupby("building_id").size()

    rows = []
    for building_id, group in linked.groupby("building_id", sort=True):
        delivery, local = split_composite_id(building_id)
        union = shapely_make_valid(group.geometry.union_all())
        if union.is_empty:
            raise RuntimeError(f"empty normalized DBGT building geometry: {building_id}")
        area = float(union.area)
        if not math.isfinite(area) or area <= 0:
            raise RuntimeError(f"invalid normalized DBGT building area: {building_id} area={area}")
        rows.append({
            "building_id": building_id,
            "CLASSREF": building_id,
            "dbgt_cod_cons_fact": delivery,
            "dbgt_local_classref_fact": local,
            "active_footprint_source_part_count": len(group),
            "footprint_area_m2": area,
            "building_id_epistemic_status": BUILDING_ID_STATUS,
            "geometry_epistemic_status": NORMALIZED_FOOTPRINT_STATUS,
            "raw_footprint_source_epistemic_status": RAW_FOOTPRINT_STATUS,
            "geometry": union,
        })
    out = gpd.GeoDataFrame(rows, geometry="geometry", crs=32632)
    if out["building_id"].duplicated().any():
        raise RuntimeError("composite DBGT building identity is not one-to-one after normalization")

    unlinked_area = float(unlinked_rows.geometry.area.sum()) if len(unlinked_rows) else 0.0
    metrics = {
        "raw_selected_active_footprint_rows": len(work),
        "raw_linked_active_footprint_rows": len(linked),
        "raw_active_footprints_without_classref_excluded": len(unlinked_rows),
        "raw_active_footprints_without_classref_excluded_area_m2": unlinked_area,
        "unlinked_footprint_epistemic_status": UNLINKED_STATUS,
        "unlinked_footprints_population_assigned": False,
        "raw_unique_global_classref": int(linked["dbgt_local_classref_fact"].nunique()),
        "normalized_composite_building_count": len(out),
        "composite_buildings_with_multiple_active_footprint_parts": int((counts > 1).sum()),
        "extra_active_footprint_rows_collapsed_by_composite_union": int(len(linked) - len(out)),
        "max_active_footprint_parts_per_composite_building": int(counts.max()),
        "building_identity_status": BUILDING_ID_STATUS,
        "raw_geometry_status": RAW_FOOTPRINT_STATUS,
        "normalized_geometry_status": NORMALIZED_FOOTPRINT_STATUS,
        "random_used": False,
        "sampling_used": False,
    }
    return out.sort_values("building_id").reset_index(drop=True), metrics
