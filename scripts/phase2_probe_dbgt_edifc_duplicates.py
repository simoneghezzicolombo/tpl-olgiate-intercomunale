#!/usr/bin/env python3
"""Exhaustively audit repeated active DBGT EDIFC rows per CLASSID.

The production pipeline currently assumes one active EDIFC attribute row per
building identifier. This read-only probe checks that assumption over the exact
Phase 2 selected geography and reports whether repeated rows agree on the
semantic fields used for residential classification.

No sampling or randomisation is used.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path

import pandas as pd

import phase2_build_building_population as impl


def _chunks(values: list, size: int) -> list[list]:
    return [values[i:i + size] for i in range(0, len(values), size)]


def _layer3_refs(selected_union_32632) -> tuple[list[str], dict]:
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
        raise RuntimeError("DBGT layer 3 footprint query returned no object IDs")

    chunks = _chunks(object_ids, impl.DBGT_OBJECT_CHUNK)

    def one(chunk: list[int]) -> list[dict]:
        payload = impl.arc_post(3, {
            "where": f"OBJECTID IN ({','.join(map(str, chunk))})",
            "outFields": "OBJECTID,CLASSREF,COD_CONS,DATA_FIN",
            "returnGeometry": "false",
        })
        return [f["attributes"] for f in payload.get("features", [])]

    results: dict[int, list[dict]] = {}
    with ThreadPoolExecutor(max_workers=impl.DBGT_WORKERS) as pool:
        futures = {pool.submit(one, chunk): i for i, chunk in enumerate(chunks)}
        for future in as_completed(futures):
            results[futures[future]] = future.result()

    rows: list[dict] = []
    for i in range(len(chunks)):
        rows.extend(results[i])
    attrs = pd.DataFrame(rows)
    if len(attrs) != len(object_ids):
        raise RuntimeError(f"layer 3 attribute row count mismatch {len(attrs)} != {len(object_ids)}")
    refs = sorted({str(v).strip() for v in attrs["CLASSREF"].dropna() if str(v).strip()})
    return refs, {
        "layer3_candidate_object_ids": len(object_ids),
        "layer3_attribute_rows": len(attrs),
        "unique_nonblank_classref": len(refs),
    }


def _values(group: pd.DataFrame, field: str) -> list[str]:
    if field not in group.columns:
        return []
    vals = []
    for value in group[field]:
        if pd.isna(value):
            vals.append("<NULL>")
        else:
            vals.append(str(value).strip())
    return sorted(set(vals))


def main() -> None:
    source_dir = Path("/tmp/phase2_dbgt_edifc_duplicate_probe")
    source_dir.mkdir(parents=True, exist_ok=True)
    _, municipalities, geom_source = impl.load_istat_geography(source_dir)
    selected_union = municipalities.geometry.union_all()
    refs, footprint_counts = _layer3_refs(selected_union)

    edifc = impl.query_dbgt_table(
        22,
        "CLASSID",
        refs,
        "OBJECTID,CLASSID,EDIFC_STAT,EDIFC_TY,FONTE,SCALA,COD_CONS,DATA_INI,DATA_FIN",
    )
    if edifc.empty:
        raise RuntimeError("active EDIFC query returned no rows")
    edifc["CLASSID"] = edifc["CLASSID"].astype(str)
    counts = edifc.groupby("CLASSID").size()
    duplicate_refs = sorted(counts[counts > 1].index.tolist())
    duplicate_rows = edifc.loc[edifc["CLASSID"].isin(duplicate_refs)].copy()

    details = []
    semantic_conflicts = []
    for classid, group in duplicate_rows.groupby("CLASSID", sort=True):
        status_values = _values(group, "EDIFC_STAT")
        type_values = _values(group, "EDIFC_TY")
        cod_cons_values = _values(group, "COD_CONS")
        fonte_values = _values(group, "FONTE")
        scala_values = _values(group, "SCALA")
        data_ini_values = _values(group, "DATA_INI")
        semantic_consensus = len(status_values) <= 1 and len(type_values) <= 1
        record = {
            "CLASSID": classid,
            "active_edifc_rows": len(group),
            "object_ids": sorted(pd.to_numeric(group["OBJECTID"], errors="coerce").dropna().astype(int).tolist()),
            "EDIFC_STAT_values": status_values,
            "EDIFC_TY_values": type_values,
            "COD_CONS_values": cod_cons_values,
            "FONTE_values": fonte_values,
            "SCALA_values": scala_values,
            "DATA_INI_values": data_ini_values,
            "semantic_status_type_consensus": semantic_consensus,
        }
        details.append(record)
        if not semantic_consensus:
            semantic_conflicts.append(record)

    report = {
        "istat_geometry_source": geom_source,
        "selected_whole_municipalities": len(municipalities),
        **footprint_counts,
        "edifc_layer": 22,
        "edifc_filter": "DATA_FIN IS NULL",
        "active_edifc_rows": len(edifc),
        "unique_active_classid": int(edifc["CLASSID"].nunique()),
        "classid_with_no_active_edifc": len(set(refs) - set(edifc["CLASSID"])),
        "duplicate_classid_count": len(duplicate_refs),
        "duplicate_edifc_rows": len(duplicate_rows),
        "max_active_edifc_rows_per_classid": int(counts.max()),
        "duplicate_classid_with_semantic_status_type_conflict": len(semantic_conflicts),
        "duplicate_classid_with_status_conflict": sum(len(r["EDIFC_STAT_values"]) > 1 for r in details),
        "duplicate_classid_with_type_conflict": sum(len(r["EDIFC_TY_values"]) > 1 for r in details),
        "duplicate_classid_with_multiple_cod_cons": sum(len(r["COD_CONS_values"]) > 1 for r in details),
        "duplicate_classid_with_multiple_fonte": sum(len(r["FONTE_values"]) > 1 for r in details),
        "duplicate_classid_with_multiple_scala": sum(len(r["SCALA_values"]) > 1 for r in details),
        "random_used": False,
        "sampling_used": False,
        "details": details,
    }
    Path("/tmp/dbgt-edifc-duplicate-probe.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    duplicate_rows.sort_values(["CLASSID", "OBJECTID"]).to_csv(
        "/tmp/dbgt-edifc-duplicate-rows.csv", index=False
    )
    pd.DataFrame(semantic_conflicts).to_json(
        "/tmp/dbgt-edifc-semantic-conflicts.json", orient="records", indent=2
    )
    print(json.dumps({k: v for k, v in report.items() if k != "details"}, ensure_ascii=False, indent=2))
    if semantic_conflicts:
        print("SEMANTIC_CONFLICT_EXAMPLES")
        print(json.dumps(semantic_conflicts[:20], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
