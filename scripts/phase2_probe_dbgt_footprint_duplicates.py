#!/usr/bin/env python3
"""Exhaustive audit of active DBGT footprint rows sharing one CLASSREF.

This is a read-only diagnostic. It uses the same selected whole-municipality
10 km acquisition geography as the production building-population pipeline,
collects every active layer-3 footprint record in that envelope, identifies
repeated CLASSREF values and inspects geometry relationships for every repeated
record. No sampling or randomisation is used.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

import phase2_build_building_population as impl


def _chunks(values: list, size: int) -> list[list]:
    return [values[i:i + size] for i in range(0, len(values), size)]


def main() -> None:
    source_dir = Path('/tmp/phase2_dbgt_duplicate_probe')
    source_dir.mkdir(parents=True, exist_ok=True)
    _, municipalities, geom_source = impl.load_istat_geography(source_dir)
    selected_union = municipalities.geometry.union_all()
    union_7791 = gpd.GeoSeries([selected_union], crs=32632).to_crs(7791).iloc[0]
    minx, miny, maxx, maxy = union_7791.bounds

    ids_payload = impl.arc_post(3, {
        'where': 'DATA_FIN IS NULL',
        'geometry': f'{minx},{miny},{maxx},{maxy}',
        'geometryType': 'esriGeometryEnvelope',
        'inSR': '7791',
        'spatialRel': 'esriSpatialRelIntersects',
        'returnIdsOnly': 'true',
    })
    object_ids = sorted(ids_payload.get('objectIds') or [])
    if not object_ids:
        raise RuntimeError('DBGT duplicate probe returned no footprint object IDs')

    def fetch_attrs(chunk: list[int]) -> list[dict]:
        payload = impl.arc_post(3, {
            'objectIds': ','.join(map(str, chunk)),
            'outFields': 'OBJECTID,CLASSREF,COD_CONS,DATA_FIN',
            'returnGeometry': 'false',
        })
        return [f['attributes'] for f in payload.get('features', [])]

    results: dict[int, list[dict]] = {}
    chunks = _chunks(object_ids, impl.DBGT_OBJECT_CHUNK)
    with ThreadPoolExecutor(max_workers=impl.DBGT_WORKERS) as pool:
        futures = {pool.submit(fetch_attrs, chunk): i for i, chunk in enumerate(chunks)}
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    rows: list[dict] = []
    for i in range(len(chunks)):
        rows.extend(results[i])
    attrs = pd.DataFrame(rows)
    if attrs.empty or 'CLASSREF' not in attrs.columns:
        raise RuntimeError('DBGT duplicate probe returned no CLASSREF attributes')
    if attrs['OBJECTID'].duplicated().any():
        raise RuntimeError('duplicate OBJECTID returned by supposedly disjoint objectId chunks')

    counts = attrs.groupby('CLASSREF', dropna=False).size().rename('active_footprint_rows')
    duplicate_refs = sorted(str(x) for x in counts[counts > 1].index if pd.notna(x))
    duplicate_attrs = attrs.loc[attrs['CLASSREF'].astype(str).isin(duplicate_refs)].copy()
    duplicate_object_ids = sorted(int(x) for x in duplicate_attrs['OBJECTID'])

    geom_features: list[dict] = []
    if duplicate_object_ids:
        geom_chunks = _chunks(duplicate_object_ids, impl.DBGT_OBJECT_CHUNK)

        def fetch_geom(chunk: list[int]) -> dict:
            return impl._request_json(
                f'{impl.DBGT_BASE}/3/query',
                data={
                    'f': 'geojson',
                    'objectIds': ','.join(map(str, chunk)),
                    'outFields': 'OBJECTID,CLASSREF,COD_CONS,DATA_FIN',
                    'returnGeometry': 'true',
                    'outSR': '4326',
                },
            )

        geom_results: dict[int, dict] = {}
        with ThreadPoolExecutor(max_workers=impl.DBGT_WORKERS) as pool:
            futures = {pool.submit(fetch_geom, chunk): i for i, chunk in enumerate(geom_chunks)}
            for future in as_completed(futures):
                geom_results[futures[future]] = future.result()
        for i in range(len(geom_chunks)):
            geom_features.extend(geom_results[i].get('features', []))

    details: list[dict] = []
    if geom_features:
        gdf = gpd.GeoDataFrame.from_features(geom_features, crs=4326).to_crs(32632)
        gdf['geometry'] = gdf.geometry.make_valid()
        if gdf['OBJECTID'].duplicated().any():
            raise RuntimeError('duplicate geometry OBJECTID in duplicate audit')
        for ref, group in gdf.groupby('CLASSREF'):
            group = group.sort_values('OBJECTID').copy()
            geoms = list(group.geometry)
            sum_area = float(sum(g.area for g in geoms))
            union = group.geometry.union_all()
            union_area = float(union.area)
            exact_pairs = 0
            intersecting_pairs = 0
            positive_overlap_pairs = 0
            disjoint_pairs = 0
            for i in range(len(geoms)):
                for j in range(i + 1, len(geoms)):
                    a, b = geoms[i], geoms[j]
                    if a.equals(b):
                        exact_pairs += 1
                    if a.intersects(b):
                        intersecting_pairs += 1
                        if a.intersection(b).area > 1e-6:
                            positive_overlap_pairs += 1
                    else:
                        disjoint_pairs += 1
            details.append({
                'CLASSREF': str(ref),
                'active_footprint_rows': int(len(group)),
                'object_ids': [int(x) for x in group['OBJECTID']],
                'cod_cons_values': sorted(set(str(x) for x in group['COD_CONS'].dropna())),
                'sum_part_area_m2': sum_area,
                'union_area_m2': union_area,
                'sum_minus_union_area_m2': sum_area - union_area,
                'exact_geometry_pairs': exact_pairs,
                'intersecting_pairs': intersecting_pairs,
                'positive_overlap_pairs': positive_overlap_pairs,
                'disjoint_pairs': disjoint_pairs,
            })

    detail_df = pd.DataFrame(details)
    output = {
        'istat_geometry_source': geom_source,
        'selected_whole_municipalities': int(len(municipalities)),
        'dbgt_layer': 3,
        'dbgt_layer_name': 'EDIFC_CR_EDF_IS',
        'filter': 'DATA_FIN IS NULL',
        'bbox_candidate_object_ids': int(len(object_ids)),
        'returned_attribute_rows': int(len(attrs)),
        'unique_classref': int(attrs['CLASSREF'].nunique(dropna=True)),
        'duplicate_classref_count': int(len(duplicate_refs)),
        'duplicate_footprint_rows': int(len(duplicate_attrs)),
        'max_active_rows_per_classref': int(counts.max()),
        'duplicate_geometry_rows_fetched': int(len(geom_features)),
        'duplicate_refs_all_exact_copies': int(
            sum(
                1 for row in details
                if row['exact_geometry_pairs'] == row['active_footprint_rows'] * (row['active_footprint_rows'] - 1) // 2
            )
        ),
        'duplicate_refs_with_positive_overlap': int(sum(1 for row in details if row['positive_overlap_pairs'] > 0)),
        'duplicate_refs_with_disjoint_parts': int(sum(1 for row in details if row['disjoint_pairs'] > 0)),
        'duplicate_refs_with_multiple_cod_cons': int(sum(1 for row in details if len(row['cod_cons_values']) > 1)),
        'details': details,
        'random_used': False,
        'sampling_used': False,
    }
    Path('/tmp/dbgt-footprint-duplicate-probe.json').write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    duplicate_attrs.sort_values(['CLASSREF', 'OBJECTID']).to_csv(
        '/tmp/dbgt-footprint-duplicate-attributes.csv', index=False
    )
    print(json.dumps({k: v for k, v in output.items() if k != 'details'}, ensure_ascii=False, indent=2))
    if len(detail_df):
        print(detail_df.head(30).to_string(index=False))


if __name__ == '__main__':
    main()
