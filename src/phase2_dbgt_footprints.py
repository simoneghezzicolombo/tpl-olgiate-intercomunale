"""Deterministic normalization of DBGT building-footprint source rows.

The Regione Lombardia layer EDIFC_CR_EDF_IS exposes the ground-footprint
spatial component linked to EDIFC through CLASSREF. Live source data can contain
more than one active polygon row for the same CLASSREF. The building geometry
used by Phase 2 is therefore the topological union of all active, non-empty
source footprint parts linked to that CLASSREF.

Raw source polygons remain FACT. The normalized one-row-per-building geometry
is DERIVED from those source polygons. No randomisation or sampling is used.
"""
from __future__ import annotations

import geopandas as gpd


NORMALIZED_GEOMETRY_STATUS = "DERIVED_UNION_OF_ACTIVE_DBGT_FOOTPRINT_PARTS_BY_CLASSREF"
RAW_GEOMETRY_STATUS = "FACT_DBGT_ACTIVE_FOOTPRINT_SOURCE_PART"


def normalize_active_building_footprints(
    footprints: gpd.GeoDataFrame,
    selected_union,
) -> tuple[gpd.GeoDataFrame, dict]:
    required = {"CLASSREF", "geometry"}
    if not required.issubset(footprints.columns):
        raise ValueError(f"DBGT footprint columns missing: {required - set(footprints.columns)}")
    if footprints.crs is None:
        raise ValueError("DBGT footprint CRS is required")

    gdf = footprints.loc[footprints.geometry.notna() & ~footprints.geometry.is_empty].copy()
    gdf["geometry"] = gdf.geometry.make_valid()
    gdf = gdf.loc[gdf.intersects(selected_union)].copy()
    if gdf.empty:
        raise ValueError("no active DBGT footprints intersect selected geography")

    classref = gdf["CLASSREF"].astype("string").str.strip()
    missing_key = classref.isna() | classref.eq("")
    unlinked_count = int(missing_key.sum())
    linked = gdf.loc[~missing_key].copy()
    linked["CLASSREF"] = classref.loc[~missing_key].astype(str)
    if linked.empty:
        raise ValueError("all selected active DBGT footprints lack CLASSREF")

    counts = linked.groupby("CLASSREF").size()
    duplicate_refs = counts[counts > 1]

    # Dissolve is a topological union, so exact duplicate/overlapping source rows
    # cannot double-count area while disjoint components remain represented as a
    # MultiPolygon for the same linked EDIFC building.
    normalized = linked[["CLASSREF", "geometry"]].dissolve(
        by="CLASSREF", as_index=False, method="unary"
    )
    normalized["geometry"] = normalized.geometry.make_valid()
    normalized = normalized.loc[
        normalized.geometry.notna() & ~normalized.geometry.is_empty
    ].copy()
    if normalized["CLASSREF"].duplicated().any():
        raise ValueError("DBGT normalization failed one-row-per-CLASSREF invariant")

    normalized["footprint_area_m2"] = normalized.geometry.area
    if (normalized["footprint_area_m2"] <= 0).any():
        raise ValueError("non-positive normalized DBGT building footprint area")
    normalized = normalized.sort_values("CLASSREF").reset_index(drop=True)

    metrics = {
        "raw_selected_active_footprint_rows": int(len(gdf)),
        "raw_active_footprints_without_classref_excluded": unlinked_count,
        "raw_linked_active_footprint_rows": int(len(linked)),
        "normalized_building_classref_count": int(len(normalized)),
        "classref_with_multiple_active_footprint_parts": int(len(duplicate_refs)),
        "extra_active_footprint_rows_collapsed_by_union": int((counts - 1).clip(lower=0).sum()),
        "max_active_footprint_parts_per_classref": int(counts.max()),
        "raw_geometry_epistemic_status": RAW_GEOMETRY_STATUS,
        "normalized_geometry_epistemic_status": NORMALIZED_GEOMETRY_STATUS,
        "normalization_method": "TOPOLOGICAL_UNION_ALL_ACTIVE_NONEMPTY_SOURCE_PARTS_BY_CLASSREF",
        "random_used": False,
        "sampling_used": False,
    }
    if metrics["raw_linked_active_footprint_rows"] - metrics["extra_active_footprint_rows_collapsed_by_union"] != metrics["normalized_building_classref_count"]:
        raise ValueError("DBGT footprint normalization accounting mismatch")
    return normalized, metrics
