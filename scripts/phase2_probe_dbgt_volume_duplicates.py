#!/usr/bin/env python3
"""Audit DBGT volume-unit multiplicity for Phase 2 building references.

Checks whether active layer-0 rows are unique volume units or repeated delivery
records. The production dasymetric model may only sum rows as separate volume
units when the identifying relationship is not duplicated. No sampling or
randomisation is used.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path

import pandas as pd

import phase2_build_building_population as impl


def _chunks(values: list, size: int) -> list[list]:
    return [values[i:i + size] for i in range(0, len(values), size)]


def footprint_refs(selected_union_32632) -> tuple[list[str], dict]:
    union_7791 = impl.gpd.GeoSeries([selected_union_32632], crs=32632).to_crs(7791).iloc[0]
    minx, miny, maxx, maxy = union_7791.bounds
    ids_payload = impl.arc_post(3, {
        "where": "DATA_FIN IS NULL",
        "geometry": f"{minx},{miny},{maxx},{maxy}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "7791",
        "spatialRel": "esriSpatialRelIntersects",
        "returnIdsOnly": "true",
    })
    object_ids = sorted(ids_payload.get("objectIds") or [])
    if not object_ids:
        raise RuntimeError("no active layer-3 footprint object IDs")

    chunks = _chunks(object_ids, impl.DBGT_OBJECT_CHUNK)
    def one(chunk: list[int]) -> list[dict]:
        payload = impl.arc_post(3, {
            "where": f"OBJECTID IN ({','.join(map(str, chunk))})",
            "outFields": "OBJECTID,CLASSREF,DATA_FIN",
            "returnGeometry": "false",
        })
        return [f["attributes"] for f in payload.get("features", [])]
    results = {}
    with ThreadPoolExecutor(max_workers=impl.DBGT_WORKERS) as pool:
        futures = {pool.submit(one, chunk): i for i, chunk in enumerate(chunks)}
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    rows = []
    for i in range(len(chunks)):
        rows.extend(results[i])
    attrs = pd.DataFrame(rows)
    if len(attrs) != len(object_ids):
        raise RuntimeError("layer-3 footprint reference acquisition incomplete")
    refs = sorted({str(v).strip() for v in attrs["CLASSREF"].dropna() if str(v).strip()})
    return refs, {
        "layer3_candidate_object_ids": len(object_ids),
        "layer3_attribute_rows": len(attrs),
        "unique_nonblank_classref": len(refs),
    }


def _clean_values(series: pd.Series) -> list[str]:
    out = []
    for v in series:
        if pd.isna(v):
            out.append("<NULL>")
        else:
            out.append(str(v).strip())
    return sorted(set(out))


def main() -> None:
    source_dir = Path('/tmp/phase2_dbgt_volume_probe')
    source_dir.mkdir(parents=True, exist_ok=True)
    _, municipalities, geom_source = impl.load_istat_geography(source_dir)
    refs, footprint_counts = footprint_refs(municipalities.geometry.union_all())

    volumes = impl.query_dbgt_table(
        0,
        "CEDIUV",
        refs,
        "OBJECTID,CLASSID,CEDIUV,UN_VOL_AV,UN_VOL_EX,UN_VOL_QE,Shape_Area,COD_CONS,DATA_INI,DATA_FIN",
    )
    if volumes.empty:
        raise RuntimeError("active DBGT volume query returned no rows")
    for key in ("CLASSID", "CEDIUV"):
        volumes[key] = volumes[key].astype(str)

    pair_counts = volumes.groupby(["CEDIUV", "CLASSID"]).size()
    duplicate_pairs = pair_counts[pair_counts > 1]
    dup_keys = set(duplicate_pairs.index.tolist())
    duplicate_rows = volumes.loc[
        [(r.CEDIUV, r.CLASSID) in dup_keys for r in volumes.itertuples()]
    ].copy()

    details = []
    semantic_conflicts = 0
    for (cediuv, classid), group in duplicate_rows.groupby(["CEDIUV", "CLASSID"], sort=True):
        values = {
            field: _clean_values(group[field])
            for field in ("UN_VOL_AV", "UN_VOL_EX", "UN_VOL_QE", "Shape_Area")
        }
        numeric_identity = all(len(v) <= 1 for v in values.values())
        if not numeric_identity:
            semantic_conflicts += 1
        details.append({
            "CEDIUV": cediuv,
            "CLASSID": classid,
            "active_rows": len(group),
            **{f"{k}_values": v for k, v in values.items()},
            "COD_CONS_values": _clean_values(group["COD_CONS"]),
            "DATA_INI_values": _clean_values(group["DATA_INI"]),
            "numeric_fields_identical_across_repeated_unit": numeric_identity,
        })

    report = {
        "istat_geometry_source": geom_source,
        "selected_whole_municipalities": len(municipalities),
        **footprint_counts,
        "volume_layer": 0,
        "filter": "DATA_FIN IS NULL",
        "active_volume_rows": len(volumes),
        "unique_cediuv_building_refs_with_volume": int(volumes["CEDIUV"].nunique()),
        "unique_volume_classid": int(volumes["CLASSID"].nunique()),
        "duplicate_cediuv_classid_pair_count": len(duplicate_pairs),
        "duplicate_volume_rows": len(duplicate_rows),
        "max_active_rows_per_cediuv_classid": int(pair_counts.max()),
        "duplicate_pairs_with_numeric_field_conflict": semantic_conflicts,
        "classid_linked_to_multiple_cediuv": int((volumes.groupby("CLASSID")["CEDIUV"].nunique() > 1).sum()),
        "random_used": False,
        "sampling_used": False,
        "details": details,
    }
    Path('/tmp/dbgt-volume-duplicate-probe.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    duplicate_rows.sort_values(["CEDIUV", "CLASSID", "OBJECTID"]).to_csv(
        '/tmp/dbgt-volume-duplicate-rows.csv', index=False
    )
    print(json.dumps({k:v for k,v in report.items() if k != 'details'}, indent=2))
    if details:
        print('DUPLICATE_EXAMPLES')
        print(json.dumps(details[:20], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
