#!/usr/bin/env python3
"""Phase 2 building-population runner with DBGT footprint normalization.

Source layer 3 rows are retained as FACT source parts, while the geometry used
for a linked EDIFC building is a DERIVED topological union by CLASSREF. This
prevents duplicate/overlapping source rows from double-counting footprint area
and preserves disjoint components belonging to the same building identifier.
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

import phase2_run_building_population_v2 as v2
from src.phase2_dbgt_footprints import (
    NORMALIZED_GEOMETRY_STATUS,
    RAW_GEOMETRY_STATUS,
    normalize_active_building_footprints,
)

impl = v2.previous.impl


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
    if not features:
        raise RuntimeError("DBGT footprint features empty")

    raw = gpd.GeoDataFrame.from_features(features, crs=4326).to_crs(32632)
    normalized, metrics = normalize_active_building_footprints(raw, selected_union_32632)

    snap = source_dir / "dbgt_footprints_selected_normalized.geojson"
    normalized.to_crs(4326).to_file(snap, driver="GeoJSON")
    gz = source_dir / "dbgt_footprints_selected_normalized.geojson.gz"
    with snap.open("rb") as src, gzip.open(gz, "wb") as dst:
        shutil.copyfileobj(src, dst)
    snap.unlink()

    info = {
        "url": f"{impl.DBGT_BASE}/3",
        "epistemic_status": "FACT_SOURCE_ROWS_AND_DERIVED_NORMALIZED_BUILDING_GEOMETRY",
        "query": "DATA_FIN IS NULL; bbox of selected whole-municipality acquisition geography; intersect selected union",
        "bbox_candidate_object_ids": len(ids),
        **metrics,
        "snapshot_path": str(gz),
        "snapshot_sha256": impl.sha256_file(gz),
        "snapshot_bytes": gz.stat().st_size,
    }
    return normalized, info


def _postprocess_epistemic_outputs(output_dir: Path) -> None:
    manifest_path = output_dir / "building_population_source_manifest.json"
    validation_path = output_dir / "building_population_validation.json"
    building_csv = output_dir / "building_population_buildings.csv"
    building_geojson = output_dir / "building_population_buildings_core.geojson"

    if not manifest_path.is_file() or not validation_path.is_file() or not building_csv.is_file():
        raise RuntimeError("building-population outputs missing before DBGT epistemic postprocess")

    import pandas as pd

    buildings = pd.read_csv(building_csv)
    buildings["geometry_epistemic_status"] = NORMALIZED_GEOMETRY_STATUS
    buildings["raw_footprint_source_epistemic_status"] = RAW_GEOMETRY_STATUS
    buildings.to_csv(building_csv, index=False)

    if building_geojson.is_file():
        core = gpd.read_file(building_geojson)
        core["geometry_epistemic_status"] = NORMALIZED_GEOMETRY_STATUS
        core["raw_footprint_source_epistemic_status"] = RAW_GEOMETRY_STATUS
        core.to_file(building_geojson, driver="GeoJSON")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    fp = manifest["sources"]["lombardia_dbgt_footprints"]
    fp["raw_geometry_epistemic_status"] = RAW_GEOMETRY_STATUS
    fp["normalized_geometry_epistemic_status"] = NORMALIZED_GEOMETRY_STATUS
    manifest["source_hierarchy"] = [
        x.replace(
            "FACT Regione Lombardia DBGT building footprints/status/use/available volumetric units",
            "FACT Regione Lombardia DBGT active footprint parts/status/use/available volumetric units; DERIVED building geometry union by CLASSREF",
        )
        for x in manifest["source_hierarchy"]
    ]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    validation.update({
        "dbgt_raw_footprint_source_status": RAW_GEOMETRY_STATUS,
        "dbgt_building_geometry_status": NORMALIZED_GEOMETRY_STATUS,
        "dbgt_raw_selected_active_footprint_rows": fp["raw_selected_active_footprint_rows"],
        "dbgt_active_footprints_without_classref_excluded": fp["raw_active_footprints_without_classref_excluded"],
        "dbgt_normalized_building_classref_count": fp["normalized_building_classref_count"],
        "dbgt_classref_with_multiple_active_footprint_parts": fp["classref_with_multiple_active_footprint_parts"],
        "dbgt_extra_active_footprint_rows_collapsed_by_union": fp["extra_active_footprint_rows_collapsed_by_union"],
        "dbgt_max_active_footprint_parts_per_classref": fp["max_active_footprint_parts_per_classref"],
        "dbgt_footprint_random_used": False,
        "dbgt_footprint_sampling_used": False,
    })
    validation["limitations"].append(
        "Regione Lombardia DBGT may expose multiple active ground-footprint source rows for one EDIFC CLASSREF; Phase 2 uses their topological union as a DERIVED building geometry and records the source multiplicity explicitly."
    )
    validation_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")

    impl.write_checksums(output_dir)
    corrected = json.loads(validation_path.read_text(encoding="utf-8"))
    print(json.dumps(corrected, ensure_ascii=False, indent=2))


impl.fetch_dbgt_footprints = fetch_dbgt_footprints


if __name__ == "__main__":
    result = impl.main()
    # argparse in impl.main() already resolved the default or requested output
    # directory. Read it again from argv without inventing any alternative path.
    output_dir = Path("outputs/phase2")
    if "--output-dir" in sys.argv:
        output_dir = Path(sys.argv[sys.argv.index("--output-dir") + 1])
    _postprocess_epistemic_outputs(output_dir)
    sys.exit(result)
