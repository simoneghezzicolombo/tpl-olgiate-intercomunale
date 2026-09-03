#!/usr/bin/env python3
"""Authoritative Phase 2 building-population runner using DBGT composite identity.

Regione Lombardia's merged DBGT service reuses local CLASSREF / CLASSID values
across COD_CONS deliveries. This runner scopes every footprint, EDIFC, use and
volume relation by `(COD_CONS, local id)` and exposes a stable derived building
identifier `COD_CONS::CLASSREF` downstream.

No cross-delivery row is accepted. No semantic conflict is resolved by row
order. No randomisation or synthetic population is used.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import json
import math
from pathlib import Path
import shutil
import sys

import geopandas as gpd
import pandas as pd

import phase2_run_building_population_v2 as v2
from src.phase2_dbgt_composite import (
    BUILDING_ID_STATUS,
    NORMALIZED_EDIFC_STATUS,
    NORMALIZED_FOOTPRINT_STATUS,
    NORMALIZED_VOLUME_STATUS,
    RAW_EDIFC_STATUS,
    RAW_FOOTPRINT_STATUS,
    RAW_VOLUME_STATUS,
    clean_key,
    make_composite_id,
    normalize_edifc,
    normalize_footprints,
    normalize_volume_units,
    split_composite_id,
)

impl = v2.previous.impl


def _sql_string(value: object) -> str:
    return clean_key(value).replace("'", "''")


def query_dbgt_composite(
    layer: int,
    key: str,
    pairs: list[tuple[str, str]],
    fields: str,
) -> pd.DataFrame:
    """Query DBGT rows without allowing local identifiers to cross deliveries."""
    normalized = sorted({(clean_key(c), clean_key(r)) for c, r in pairs})
    if any(not c or not r for c, r in normalized):
        raise ValueError("blank DBGT composite query key")
    if not normalized:
        return pd.DataFrame()

    by_delivery: dict[str, list[str]] = {}
    for delivery, local in normalized:
        by_delivery.setdefault(delivery, []).append(local)

    tasks: list[tuple[str, list[str]]] = []
    for delivery in sorted(by_delivery):
        refs = sorted(set(by_delivery[delivery]))
        for chunk in impl._chunks(refs, impl.DBGT_REF_CHUNK):
            tasks.append((delivery, chunk))

    def one(delivery: str, chunk: list[str]) -> list[dict]:
        where = (
            f"COD_CONS = '{_sql_string(delivery)}' AND "
            f"{key} IN ({impl._quoted(chunk)}) AND DATA_FIN IS NULL"
        )
        payload = impl.arc_post(layer, {
            "where": where,
            "outFields": fields,
            "returnGeometry": "false",
        })
        rows = [f["attributes"] for f in payload.get("features", [])]
        expected = {(delivery, clean_key(x)) for x in chunk}
        for row in rows:
            actual = (clean_key(row.get("COD_CONS")), clean_key(row.get(key)))
            if actual not in expected:
                raise RuntimeError(
                    f"DBGT composite query leaked cross-delivery/unrequested row: "
                    f"layer={layer} key={key} actual={actual}"
                )
        return rows

    results: dict[int, list[dict]] = {}
    with ThreadPoolExecutor(max_workers=impl.DBGT_WORKERS) as pool:
        futures = {
            pool.submit(one, delivery, chunk): i
            for i, (delivery, chunk) in enumerate(tasks)
        }
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    rows: list[dict] = []
    for i in range(len(tasks)):
        rows.extend(results[i])
    return pd.DataFrame(rows)


def fetch_dbgt_footprints(selected_union_32632, source_dir: Path):
    union_7791 = gpd.GeoSeries([selected_union_32632], crs=32632).to_crs(7791).iloc[0]
    minx, miny, maxx, maxy = union_7791.bounds
    ids_payload = impl.arc_post(3, {
        "where": "DATA_FIN IS NULL",
        "geometry": f"{minx},{miny},{maxx},{maxy}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "7791",
        "spatialRel": "esriSpatialRelIntersects",
        "returnIdsOnly": "true",
    })
    ids = sorted(ids_payload.get("objectIds") or [])
    if not ids:
        raise RuntimeError("DBGT footprint query returned no IDs")

    def one(chunk: list[int]) -> dict:
        return impl._request_json(
            f"{impl.DBGT_BASE}/3/query",
            data={
                "f": "geojson",
                "objectIds": ",".join(map(str, chunk)),
                "outFields": "OBJECTID,CLASSREF,COD_CONS,DATA_FIN",
                "returnGeometry": "true",
                "outSR": "4326",
            },
        )

    chunks = impl._chunks(ids, impl.DBGT_OBJECT_CHUNK)
    payloads: dict[int, dict] = {}
    with ThreadPoolExecutor(max_workers=impl.DBGT_WORKERS) as pool:
        futures = {pool.submit(one, chunk): i for i, chunk in enumerate(chunks)}
        for future in as_completed(futures):
            payloads[futures[future]] = future.result()
    features: list[dict] = []
    for i in range(len(chunks)):
        features.extend(payloads[i].get("features", []))
    if len(features) != len(ids):
        raise RuntimeError(
            f"DBGT footprint feature acquisition incomplete: {len(features)} != {len(ids)}"
        )

    raw = gpd.GeoDataFrame.from_features(features, crs=4326).to_crs(32632)
    normalized, metrics = normalize_footprints(raw, selected_union_32632)

    raw_snap = source_dir / "dbgt_footprint_source_rows_selected.geojson"
    selected_raw = raw.loc[raw.geometry.notna() & ~raw.geometry.is_empty].copy()
    selected_raw["geometry"] = selected_raw.geometry.make_valid()
    selected_raw = selected_raw.loc[selected_raw.intersects(selected_union_32632)].copy()
    selected_raw.to_crs(4326).to_file(raw_snap, driver="GeoJSON")
    raw_gz = source_dir / "dbgt_footprint_source_rows_selected.geojson.gz"
    with raw_snap.open("rb") as src, gzip.open(raw_gz, "wb") as dst:
        shutil.copyfileobj(src, dst)
    raw_snap.unlink()

    norm_snap = source_dir / "dbgt_footprints_composite_normalized.geojson"
    normalized.to_crs(4326).to_file(norm_snap, driver="GeoJSON")
    norm_gz = source_dir / "dbgt_footprints_composite_normalized.geojson.gz"
    with norm_snap.open("rb") as src, gzip.open(norm_gz, "wb") as dst:
        shutil.copyfileobj(src, dst)
    norm_snap.unlink()

    info = {
        "url": f"{impl.DBGT_BASE}/3",
        "epistemic_status": "FACT_SOURCE_ROWS_AND_DERIVED_DELIVERY_SCOPED_BUILDING_GEOMETRY",
        "query": "DATA_FIN IS NULL; bbox of selected whole-municipality geography; exact union clip",
        "bbox_candidate_object_ids": len(ids),
        **metrics,
        "raw_snapshot_path": str(raw_gz),
        "raw_snapshot_sha256": impl.sha256_file(raw_gz),
        "normalized_snapshot_path": str(norm_gz),
        "normalized_snapshot_sha256": impl.sha256_file(norm_gz),
    }
    return normalized, info


def enrich_dbgt(footprints: gpd.GeoDataFrame, source_dir: Path):
    pairs = list(zip(
        footprints["dbgt_cod_cons_fact"].astype(str),
        footprints["dbgt_local_classref_fact"].astype(str),
    ))
    expected_buildings = set(footprints["building_id"].astype(str))

    raw_edifc = query_dbgt_composite(
        22,
        "CLASSID",
        pairs,
        "OBJECTID,CLASSID,EDIFC_STAT,EDIFC_TY,FONTE,SCALA,COD_CONS,DATA_INI,DATA_FIN",
    )
    edifc, edifc_metrics = normalize_edifc(raw_edifc)
    edifc_ids = set(edifc["building_id"].astype(str))
    missing_edifc = expected_buildings - edifc_ids
    unexpected_edifc = edifc_ids - expected_buildings
    if missing_edifc or unexpected_edifc:
        raise RuntimeError(
            "delivery-scoped DBGT footprint/EDIFC relationship mismatch: "
            f"missing={sorted(missing_edifc)[:20]} unexpected={sorted(unexpected_edifc)[:20]}"
        )

    uses = query_dbgt_composite(
        24,
        "CLASSREF",
        pairs,
        "OBJECTID,CLASSREF,EDIFC_USO,COD_CONS,DATA_FIN",
    )
    use_map: dict[str, list[str]] = {}
    if len(uses):
        uses = uses.copy()
        uses["building_id"] = [
            make_composite_id(c, r)
            for c, r in zip(uses["COD_CONS"], uses["CLASSREF"])
        ]
        use_map = (
            uses.groupby("building_id")["EDIFC_USO"]
            .apply(lambda s: sorted({clean_key(v) for v in s if clean_key(v)}))
            .to_dict()
        )

    metadata = edifc.set_index("building_id").to_dict("index")
    rows = []
    for building_id in footprints["building_id"].astype(str):
        meta = metadata[building_id]
        cls = impl.classify_building(
            status_code=meta.get("EDIFC_STAT"),
            type_code=meta.get("EDIFC_TY"),
            use_codes=use_map.get(building_id, []),
        )
        uncertainty = list(cls.uncertainty_flags)
        source_count = int(meta.get("active_edifc_source_row_count", 1))
        if source_count > 1:
            uncertainty.append(f"duplicate_active_edifc_source_rows_same_composite_identity={source_count}")
        rows.append({
            "CLASSREF": building_id,
            "dbgt_status_fact": meta.get("EDIFC_STAT"),
            "dbgt_type_fact": meta.get("EDIFC_TY"),
            "dbgt_use_codes_fact": "|".join(use_map.get(building_id, [])),
            "residential_plausibility": cls.plausibility,
            "eligible_primary": cls.eligible_primary,
            "eligible_fallback": cls.eligible_fallback,
            "residential_use_present": cls.residential_use_present,
            "mixed_use": cls.mixed_use,
            "classification_uncertainty_flags": "|".join(sorted(set(uncertainty))),
            "classification_epistemic_status": "DERIVED_FROM_DELIVERY_SCOPED_DBGT_STATUS_USAGE_TYPE",
        })
    classification = pd.DataFrame(rows)
    gdf = footprints.merge(classification, on="CLASSREF", how="left", validate="one_to_one")

    eligible = gdf.loc[gdf["eligible_primary"] | gdf["eligible_fallback"]].copy()
    volume_pairs = list(zip(
        eligible["dbgt_cod_cons_fact"].astype(str),
        eligible["dbgt_local_classref_fact"].astype(str),
    ))
    raw_volumes = query_dbgt_composite(
        0,
        "CEDIUV",
        volume_pairs,
        "OBJECTID,CLASSID,CEDIUV,UN_VOL_AV,UN_VOL_EX,UN_VOL_QE,Shape_Area,COD_CONS,DATA_INI,DATA_FIN",
    ) if volume_pairs else pd.DataFrame()
    volumes, volume_metrics = normalize_volume_units(raw_volumes)

    volume_summary: dict[str, tuple[bool, float, int]] = {}
    if len(volumes):
        for building_id, group in volumes.groupby("building_id"):
            heights = pd.to_numeric(group["UN_VOL_AV"], errors="coerce")
            areas = pd.to_numeric(group["Shape_Area"], errors="coerce")
            complete = (
                len(group) > 0
                and heights.notna().all()
                and areas.notna().all()
                and (heights > 0).all()
                and (areas > 0).all()
            )
            proxy = float((heights * areas).sum()) if complete else math.nan
            volume_summary[str(building_id)] = (complete, proxy, len(group))

    gdf["dbgt_volume_units_count"] = gdf["building_id"].map(
        lambda r: volume_summary.get(str(r), (False, math.nan, 0))[2]
    )
    gdf["dbgt_volume_complete"] = gdf["building_id"].map(
        lambda r: volume_summary.get(str(r), (False, math.nan, 0))[0]
    )
    gdf["dbgt_volume_proxy_m3"] = gdf["building_id"].map(
        lambda r: volume_summary.get(str(r), (False, math.nan, 0))[1]
    )
    gdf["allocation_weight_basis"] = gdf["dbgt_volume_complete"].map(
        lambda complete: "DBGT_VOLUME_PROXY_COMPLETE_DELIVERY_SCOPED" if complete else "DBGT_FOOTPRINT_AREA"
    )

    raw_edifc_path = source_dir / "dbgt_edifc_source_rows_composite_scoped.csv.gz"
    edifc_path = source_dir / "dbgt_edifc_composite_normalized.csv.gz"
    uses_path = source_dir / "dbgt_uses_composite_scoped.csv.gz"
    raw_volume_path = source_dir / "dbgt_volume_source_rows_composite_scoped.csv.gz"
    volume_path = source_dir / "dbgt_volume_units_composite_normalized.csv.gz"
    raw_edifc.sort_values(["COD_CONS", "CLASSID", "OBJECTID"]).to_csv(raw_edifc_path, index=False, compression="gzip")
    edifc.sort_values("building_id").to_csv(edifc_path, index=False, compression="gzip")
    uses.sort_values(["COD_CONS", "CLASSREF", "EDIFC_USO"]).to_csv(uses_path, index=False, compression="gzip") if len(uses) else pd.DataFrame().to_csv(uses_path, index=False, compression="gzip")
    raw_volumes.sort_values(["COD_CONS", "CEDIUV", "CLASSID", "OBJECTID"]).to_csv(raw_volume_path, index=False, compression="gzip") if len(raw_volumes) else pd.DataFrame().to_csv(raw_volume_path, index=False, compression="gzip")
    volumes.sort_values(["building_id", "volume_unit_id"]).to_csv(volume_path, index=False, compression="gzip") if len(volumes) else pd.DataFrame().to_csv(volume_path, index=False, compression="gzip")

    info = {
        "edifc_url": f"{impl.DBGT_BASE}/22",
        "uses_url": f"{impl.DBGT_BASE}/24",
        "volume_url": f"{impl.DBGT_BASE}/0",
        "epistemic_status": "FACT_SOURCE_ROWS_PLUS_DERIVED_DELIVERY_SCOPED_RELATIONAL_NORMALIZATION",
        "relational_identity": "COD_CONS_PLUS_LOCAL_RELATION_ID",
        "building_identity_status": BUILDING_ID_STATUS,
        **edifc_metrics,
        **volume_metrics,
        "active_use_rows": len(uses),
        "buildings_missing_delivery_scoped_edifc": 0,
        "volume_complete_buildings": int(gdf["dbgt_volume_complete"].sum()),
        "raw_edifc_snapshot_sha256": impl.sha256_file(raw_edifc_path),
        "normalized_edifc_snapshot_sha256": impl.sha256_file(edifc_path),
        "uses_snapshot_sha256": impl.sha256_file(uses_path),
        "raw_volume_snapshot_sha256": impl.sha256_file(raw_volume_path),
        "normalized_volume_snapshot_sha256": impl.sha256_file(volume_path),
    }
    return gdf, info


def _postprocess_outputs(output_dir: Path) -> None:
    manifest_path = output_dir / "building_population_source_manifest.json"
    validation_path = output_dir / "building_population_validation.json"
    building_csv = output_dir / "building_population_buildings.csv"
    building_geojson = output_dir / "building_population_buildings_core.geojson"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    fp = manifest["sources"]["lombardia_dbgt_footprints"]
    attr = manifest["sources"]["lombardia_dbgt_attributes"]

    manifest["dbgt_relational_identity"] = {
        "status": BUILDING_ID_STATUS,
        "method": "Every local CLASSREF/CLASSID/CEDIUV is scoped by official COD_CONS delivery id before joins.",
        "cross_delivery_local_id_join_allowed": False,
    }
    manifest["source_hierarchy"] = [
        x.replace(
            "FACT Regione Lombardia DBGT building footprints/status/use/available volumetric units",
            "FACT Regione Lombardia DBGT source rows; DERIVED delivery-scoped identities, footprint unions, EDIFC consensus and unique volume units",
        )
        for x in manifest["source_hierarchy"]
    ]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    validation.update({
        "dbgt_relational_identity_status": BUILDING_ID_STATUS,
        "dbgt_cross_delivery_local_id_join_allowed": False,
        "dbgt_raw_footprint_source_status": RAW_FOOTPRINT_STATUS,
        "dbgt_building_geometry_status": NORMALIZED_FOOTPRINT_STATUS,
        "dbgt_raw_edifc_status": RAW_EDIFC_STATUS,
        "dbgt_normalized_edifc_status": NORMALIZED_EDIFC_STATUS,
        "dbgt_raw_volume_status": RAW_VOLUME_STATUS,
        "dbgt_normalized_volume_status": NORMALIZED_VOLUME_STATUS,
        "dbgt_raw_selected_active_footprint_rows": fp["raw_selected_active_footprint_rows"],
        "dbgt_raw_unique_global_classref": fp["raw_unique_global_classref"],
        "dbgt_normalized_composite_building_count": fp["normalized_composite_building_count"],
        "dbgt_composite_buildings_with_multiple_active_footprint_parts": fp["composite_buildings_with_multiple_active_footprint_parts"],
        "dbgt_extra_active_footprint_rows_collapsed_by_composite_union": fp["extra_active_footprint_rows_collapsed_by_composite_union"],
        "dbgt_composite_edifc_semantic_conflicts": attr["composite_edifc_semantic_conflicts"],
        "dbgt_composite_volume_numeric_conflicts": attr["composite_volume_numeric_conflicts"],
        "dbgt_buildings_missing_delivery_scoped_edifc": attr["buildings_missing_delivery_scoped_edifc"],
        "dbgt_raw_active_edifc_rows": attr["raw_active_edifc_rows"],
        "dbgt_normalized_composite_edifc_records": attr["normalized_composite_edifc_records"],
        "dbgt_raw_active_volume_rows": attr["raw_active_volume_rows"],
        "dbgt_normalized_composite_volume_units": attr["normalized_composite_volume_units"],
        "dbgt_composite_random_used": False,
        "dbgt_composite_sampling_used": False,
    })
    validation["limitations"].append(
        "DBGT local relation identifiers are not global across the merged regional service. Phase 2 therefore scopes every CLASSREF/CLASSID/CEDIUV by COD_CONS before relational joins; cross-delivery local-id joins are forbidden."
    )
    validation_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")

    buildings = pd.read_csv(building_csv)
    parsed = buildings["building_id"].map(split_composite_id)
    buildings.insert(1, "dbgt_cod_cons_fact", parsed.map(lambda x: x[0]))
    buildings.insert(2, "dbgt_local_classref_fact", parsed.map(lambda x: x[1]))
    buildings.insert(3, "building_id_epistemic_status", BUILDING_ID_STATUS)
    buildings["geometry_epistemic_status"] = NORMALIZED_FOOTPRINT_STATUS
    buildings.to_csv(building_csv, index=False)

    if building_geojson.is_file():
        core = gpd.read_file(building_geojson)
        parsed_core = core["building_id"].map(split_composite_id)
        core["dbgt_cod_cons_fact"] = parsed_core.map(lambda x: x[0])
        core["dbgt_local_classref_fact"] = parsed_core.map(lambda x: x[1])
        core["building_id_epistemic_status"] = BUILDING_ID_STATUS
        core["geometry_epistemic_status"] = NORMALIZED_FOOTPRINT_STATUS
        core.to_file(building_geojson, driver="GeoJSON")

    impl.write_checksums(output_dir)
    print(json.dumps(validation, ensure_ascii=False, indent=2))


impl.fetch_dbgt_footprints = fetch_dbgt_footprints
impl.enrich_dbgt = enrich_dbgt


if __name__ == "__main__":
    result = impl.main()
    output_dir = Path("outputs/phase2")
    if "--output-dir" in sys.argv:
        output_dir = Path(sys.argv[sys.argv.index("--output-dir") + 1])
    _postprocess_outputs(output_dir)
    sys.exit(result)
