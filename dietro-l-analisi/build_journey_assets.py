#!/usr/bin/env python3
"""Build static source-closed assets for the Dietro l'analisi scrollytelling.

This script does not recompute Phase 2 decisions. It only transforms pinned,
already validated evidence into deterministic web-friendly visual layers.
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
import math
from pathlib import Path
import shutil
import zipfile

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parent
BUILDING_ZIP = Path('/tmp/journey-building-population.zip')
STOP_ZIP = Path('/tmp/journey-stop-universe-v2.zip')
BOUNDARY_SOURCE = Path('/tmp/journey-boundaries.geojson')
ROAD_SOURCE = Path('/tmp/journey-road-structural.geojson.gz')

BUILDING_ARTIFACT_ID = 9910900017
BUILDING_ZIP_SHA256 = '4f5f0123ced2b763c2a063258ad724c43ac7f57ede707db3fa76e6a8977688b1'
STOP_ARTIFACT_ID = 9911651930
STOP_ZIP_SHA256 = '25d3dbf52cb428d54a46569b7dbbf9e78dcee6fcf5ee69b9c6e928a367e0a2f9'

FROZEN_RUNTIME_SOURCE_COMMIT = '29203ad64c3e32e6164ef6997933eb5c5ff2d5b1'
BOUNDARY_SOURCE_REPO_PATH = 'data/raw/boundaries/comuni_core_istat_2026.geojson'
BOUNDARY_SOURCE_SIZE = 79275
BOUNDARY_SOURCE_GIT_BLOB_SHA1 = '1d5dcb825b21631f824f53aa5a76cfaf669ce744'
ROAD_SOURCE_REPO_PATH = 'data/phase2/frozen_gate_d/source/osm_gate_d_structural.geojson.gz'
ROAD_SOURCE_SIZE = 2270082
ROAD_SOURCE_GIT_BLOB_SHA1 = '54594215060b6cbe1cb15cf2d45f994ec85439ab'
ROAD_SOURCE_GZIP_SHA256 = '001ca3fd752a8fb378d1769e6ec6d9cb49203ee38dbe812106d7cc8aca752620'
ROAD_SOURCE_GEOJSON_SHA256 = '9032fa1fa2f8a22fd5cfcf81ad7366269d062cb7c27ffbfd57bfba754a1b51ce'
ROAD_VISUAL_BBOX = [9.32, 45.695, 9.47, 45.765]

CORE = {'097010','097012','097058','097074','097092'}
CHUNK = 220_000


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(f'blob {len(data)}\0'.encode('ascii') + data).hexdigest()


def verify_zip(path: Path, expected: str) -> None:
    actual = sha256(path)
    if actual != expected:
        raise RuntimeError(f'{path.name} SHA256 {actual} != {expected}')


def verify_frozen_source(path: Path, expected_size: int, expected_blob: str, expected_sha256: str | None = None) -> bytes:
    data = path.read_bytes()
    if len(data) != expected_size:
        raise RuntimeError(f'{path.name} size {len(data)} != {expected_size}')
    blob = git_blob_sha1(data)
    if blob != expected_blob:
        raise RuntimeError(f'{path.name} Git blob {blob} != {expected_blob}')
    if expected_sha256 is not None:
        actual = sha256_bytes(data)
        if actual != expected_sha256:
            raise RuntimeError(f'{path.name} SHA256 {actual} != {expected_sha256}')
    return data


def extract_member(z: zipfile.ZipFile, name: str, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with z.open(name) as src, dst.open('wb') as out:
        shutil.copyfileobj(src, out)
    return dst


def compact_geojson(gdf: gpd.GeoDataFrame, props: list[str]) -> bytes:
    fc = json.loads(gdf[props + ['geometry']].to_json(drop_id=True))
    return json.dumps(fc, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def gzip_b64_chunks(stem: str, raw: bytes) -> list[Path]:
    for old in ROOT.glob(f'{stem}.gz.*.b64'):
        old.unlink()
    gz_path = ROOT / f'{stem}.gz'
    with gz_path.open('wb') as raw_out:
        with gzip.GzipFile(filename='', fileobj=raw_out, mode='wb', compresslevel=9, mtime=0) as gz:
            gz.write(raw)
    b64 = base64.b64encode(gz_path.read_bytes()).decode('ascii')
    gz_path.unlink()
    outs = []
    for i in range(math.ceil(len(b64) / CHUNK)):
        p = ROOT / f'{stem}.gz.{i}.b64'
        p.write_text(b64[i * CHUNK:(i + 1) * CHUNK], encoding='ascii')
        outs.append(p)
    return outs


def coords_inside_visual_box(coords) -> bool:
    if not coords:
        return False
    if isinstance(coords[0], (int, float)):
        return (
            ROAD_VISUAL_BBOX[0] <= coords[0] <= ROAD_VISUAL_BBOX[2]
            and ROAD_VISUAL_BBOX[1] <= coords[1] <= ROAD_VISUAL_BBOX[3]
        )
    return any(coords_inside_visual_box(part) for part in coords)


def main() -> None:
    verify_zip(BUILDING_ZIP, BUILDING_ZIP_SHA256)
    verify_zip(STOP_ZIP, STOP_ZIP_SHA256)
    boundary_source_bytes = verify_frozen_source(
        BOUNDARY_SOURCE,
        BOUNDARY_SOURCE_SIZE,
        BOUNDARY_SOURCE_GIT_BLOB_SHA1,
    )
    road_source_gzip = verify_frozen_source(
        ROAD_SOURCE,
        ROAD_SOURCE_SIZE,
        ROAD_SOURCE_GIT_BLOB_SHA1,
        ROAD_SOURCE_GZIP_SHA256,
    )
    road_source_raw = gzip.decompress(road_source_gzip)
    if sha256_bytes(road_source_raw) != ROAD_SOURCE_GEOJSON_SHA256:
        raise RuntimeError('Gate D structural GeoJSON uncompressed SHA256 mismatch')

    boundaries_geo = json.loads(boundary_source_bytes)
    if len(boundaries_geo.get('features', [])) != 5:
        raise RuntimeError(f'boundary feature contract failed: {len(boundaries_geo.get("features", []))}')

    road_geo = json.loads(road_source_raw)
    source_road_features = len(road_geo.get('features', []))
    if source_road_features != 24384:
        raise RuntimeError(f'Gate D structural feature contract failed: {source_road_features}')
    visual_road_features = [
        f for f in road_geo['features']
        if f.get('geometry') and coords_inside_visual_box(f['geometry'].get('coordinates'))
    ]
    if not visual_road_features:
        raise RuntimeError('visual Gate D road subset is empty')
    road_visual_geo = dict(road_geo)
    road_visual_geo['features'] = visual_road_features
    road_visual_raw = json.dumps(road_visual_geo, separators=(',', ':'), ensure_ascii=False).encode('utf-8')

    work = Path('/tmp/journey-assets')
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir()
    with zipfile.ZipFile(BUILDING_ZIP) as z:
        needed = [
            'building_population_allocations.csv',
            'building_population_sections.csv',
            'building_population_worldpop_heterogeneity.csv',
            'building_population_source_istat_R03_21.zip',
            'source-snapshots/dbgt_footprints_composite_normalized.geojson.gz',
        ]
        for n in needed:
            extract_member(z, n, work / n)
    with zipfile.ZipFile(STOP_ZIP) as z:
        for n in [
            'accessibility_gap_building_pieces.geojson',
            'proposed_stop_candidates.geojson',
            'existing_official_stops.geojson',
            'stop_universe_v2_validation.json',
        ]:
            extract_member(z, n, work / n)

    wp = pd.read_csv(work / 'building_population_worldpop_heterogeneity.csv')
    wp_features = []
    for r in wp.itertuples():
        hw = float(r.cell_width_deg) / 2
        hh = float(r.cell_height_deg) / 2
        wp_features.append({
            'type': 'Feature',
            'properties': {
                'id': r.cell_id,
                'pop': round(float(r.pop_calibrated_2025), 4),
                'raw': round(float(r.worldpop_2020_raw), 4),
                'muni': str(r.PRO_COM_T).split('.')[0].zfill(6),
            },
            'geometry': {
                'type': 'Polygon',
                'coordinates': [[
                    [r.lon - hw, r.lat - hh], [r.lon + hw, r.lat - hh],
                    [r.lon + hw, r.lat + hh], [r.lon - hw, r.lat + hh],
                    [r.lon - hw, r.lat - hh],
                ]],
            },
        })
    worldpop_raw = json.dumps({'type': 'FeatureCollection', 'features': wp_features}, separators=(',', ':')).encode()

    sec_zip = work / 'building_population_source_istat_R03_21.zip'
    sec_geo = gpd.read_file(f'/vsizip/{sec_zip}/SHP/R03_21_WGS84.shp')
    sec_geo['PRO_COM_N'] = sec_geo['PRO_COM'].astype(int)
    sec_geo = sec_geo[sec_geo.PRO_COM_N.isin({97010, 97012, 97058, 97074, 97092})].copy()
    secs = pd.read_csv(work / 'building_population_sections.csv', dtype={'section_id': str, 'municipality_code': str})
    secs['section_id'] = secs['section_id'].str.replace('.0', '', regex=False).str.zfill(12)
    sec_geo['section_id'] = sec_geo['SEZ21_ID'].astype(str).str.replace('.0', '', regex=False).str.zfill(12)
    pop_lookup = secs.set_index('section_id')['section_population_2025_derived'].to_dict()
    sec_geo['pop2025'] = sec_geo['section_id'].map(pop_lookup).fillna(0.0)
    sec_geo['muni'] = sec_geo['PRO_COM_N'].map(lambda x: str(x).zfill(6))
    sec_geo = sec_geo.to_crs(32632)
    sec_geo['geometry'] = sec_geo.geometry.simplify(2.0, preserve_topology=True)
    sec_geo = sec_geo.to_crs(4326)
    sections_raw = compact_geojson(sec_geo, ['section_id', 'muni', 'pop2025'])

    alloc = pd.read_csv(work / 'building_population_allocations.csv', dtype={'municipality_code': str})
    alloc['municipality_code'] = alloc['municipality_code'].str.zfill(6)
    a = alloc[alloc.municipality_code.isin(CORE)]
    agg = a.groupby('building_id', as_index=False).agg(
        pop=('building_piece_population_model', 'sum'),
        muni=('municipality_code', 'first'),
        pieces=('section_id', 'nunique'),
    )
    footprints = gpd.read_file(f'/vsigzip/{work / "source-snapshots/dbgt_footprints_composite_normalized.geojson.gz"}')
    buildings = footprints[footprints.building_id.isin(set(agg.building_id))].merge(agg, on='building_id', how='inner')
    buildings = buildings.to_crs(32632)
    buildings['geometry'] = buildings.geometry.simplify(0.5, preserve_topology=True)
    buildings = buildings.to_crs(4326)
    buildings_raw = compact_geojson(buildings, ['building_id', 'pop', 'muni', 'pieces'])

    pieces = json.loads((work / 'accessibility_gap_building_pieces.geojson').read_text())
    brows = []
    for f in pieces['features']:
        p = f['properties']
        lon, lat = f['geometry']['coordinates']
        walk = p.get('walk_min_to_nearest_existing_stop_v2')
        brows.append([
            round(lon, 6), round(lat, 6), round(float(p['building_piece_population_model']), 3),
            None if walk is None else round(float(walk), 2), str(p['PRO_COM_T']).zfill(6),
        ])
    cand = json.loads((work / 'proposed_stop_candidates.geojson').read_text())
    crows = []
    for f in cand['features']:
        p = f['properties']
        lon, lat = f['geometry']['coordinates']
        crows.append([
            p['candidate_id'], round(lon, 6), round(lat, 6), str(p['PRO_COM_T']).zfill(6),
            round(float(p['population_additional_10min']), 2), p.get('highway', ''),
            p.get('road_uncertainty_flags', ''),
        ])
    ex = json.loads((work / 'existing_official_stops.geojson').read_text())
    erows = []
    for f in ex['features']:
        p = f['properties']
        lon, lat = f['geometry']['coordinates']
        erows.append([
            p['physical_cluster_id'], p['stop_name'], round(lon, 6), round(lat, 6),
            str(p.get('PRO_COM_T', '')).zfill(6), p.get('official_routes_reference_gtfs', ''),
        ])
    v = json.loads((work / 'stop_universe_v2_validation.json').read_text())

    worldpop_files = gzip_b64_chunks('data-worldpop.geojson', worldpop_raw)
    sections_files = gzip_b64_chunks('data-sections.geojson', sections_raw)
    buildings_files = gzip_b64_chunks('data-buildings.geojson', buildings_raw)
    boundary_files = gzip_b64_chunks('data-boundaries.geojson', boundary_source_bytes)
    road_files = gzip_b64_chunks('data-roads.geojson', road_visual_raw)

    meta = {
        'populationTotal': 22914.0,
        'populationLocated': 22820.839937434386,
        'populationResidual': 93.16006256561045,
        'populationUnits': 4348,
        'worldpopCells': len(wp),
        'sections': len(sec_geo),
        'buildings': len(buildings),
        'candidateStops': len(crows),
        'officialStopRecords': len(erows),
        'physicalClusters': 43,
        'discoverySamples': 3858,
        'gapSeeds8': 1686,
        'rawSeededBeforeThin': 1074,
        'rawSeeded': 320,
        'preprune': 292,
        'finalCandidates': 155,
        'roadWays': 24384,
        'roadEligibleWays': 15872,
        'roadDeniedWays': 8512,
        'graphNodes': 104071,
        'graphEdges': 199217,
        'coverage': {
            '5': 46.97958635342723,
            '8': 68.46684292749644,
            '10': 77.55600347715396,
            '12': 84.8663356191682,
        },
        'lineage': {
            'building': FROZEN_RUNTIME_SOURCE_COMMIT,
            'finalists': 'aa16a9934a78be9a3ee1230996fcaf72c5657f92',
            'gateD': '7c220f7586d0f6e5cccd14a2d518be52eb1c4a55',
            'stopUniverseV2Building': v.get('source_building_population_head', ''),
        },
        'localAssets': {
            'boundaries': [p.name for p in boundary_files],
            'roads': [p.name for p in road_files],
        },
    }
    (ROOT / 'journey-data.js').write_text(
        'window.ANALYSIS_JOURNEY_DATA=' + json.dumps(
            {'meta': meta, 'pieces': brows, 'candidates': crows, 'existingStops': erows},
            ensure_ascii=False, separators=(',', ':'),
        ) + ';\n',
        encoding='utf-8',
    )

    generated = worldpop_files + sections_files + buildings_files + boundary_files + road_files
    generated.append(ROOT / 'journey-data.js')

    if len(wp) != 4283 or len(sec_geo) != 229 or len(buildings) != 4226 or len(brows) != 4348 or len(crows) != 155 or len(erows) != 67:
        raise RuntimeError(
            'journey cardinality contract failed: '
            f'wp={len(wp)} sections={len(sec_geo)} buildings={len(buildings)} '
            f'pieces={len(brows)} candidates={len(crows)} stops={len(erows)}'
        )

    manifest = {
        'contract': 'PHASE2_ANALYSIS_JOURNEY_VISUAL_ASSETS_V2_SOURCE_CLOSED_RUNTIME',
        'decision_output': False,
        'runtime_external_evidence_fetches': 0,
        'building_artifact_id': BUILDING_ARTIFACT_ID,
        'building_artifact_sha256': BUILDING_ZIP_SHA256,
        'stop_universe_artifact_id': STOP_ARTIFACT_ID,
        'stop_universe_artifact_sha256': STOP_ZIP_SHA256,
        'frozen_runtime_source_commit': FROZEN_RUNTIME_SOURCE_COMMIT,
        'frozen_runtime_sources': {
            'boundaries': {
                'repo_path': BOUNDARY_SOURCE_REPO_PATH,
                'size_bytes': len(boundary_source_bytes),
                'git_blob_sha1': BOUNDARY_SOURCE_GIT_BLOB_SHA1,
                'sha256': sha256_bytes(boundary_source_bytes),
                'feature_count': len(boundaries_geo['features']),
                'used_in_numeric_decision': False,
            },
            'gate_d_structural_roads': {
                'repo_path': ROAD_SOURCE_REPO_PATH,
                'size_bytes': len(road_source_gzip),
                'git_blob_sha1': ROAD_SOURCE_GIT_BLOB_SHA1,
                'gzip_sha256': ROAD_SOURCE_GZIP_SHA256,
                'geojson_sha256': ROAD_SOURCE_GEOJSON_SHA256,
                'source_feature_count': source_road_features,
                'visual_feature_count': len(visual_road_features),
                'visual_bbox_west_south_east_north': ROAD_VISUAL_BBOX,
                'used_in_numeric_decision': False,
                'epistemic_status': 'FROZEN_DERIVATIVE_OF_GATE_D_PASS_VISUAL_SUBSET_ONLY',
            },
        },
        'counts': {
            'worldpop_cells': len(wp),
            'sections': len(sec_geo),
            'dbgt_buildings_with_core_population': len(buildings),
            'building_section_pieces': len(brows),
            'proposed_candidates_v2': len(crows),
            'official_stop_records_v2': len(erows),
            'municipality_boundaries': len(boundaries_geo['features']),
            'gate_d_structural_source_features': source_road_features,
            'gate_d_visual_features': len(visual_road_features),
        },
        'local_asset_chunks': {
            'boundaries': [p.name for p in boundary_files],
            'roads': [p.name for p in road_files],
        },
        'files': {p.name: sha256(p) for p in sorted(generated)},
    }
    (ROOT / 'data-manifest.json').write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8'
    )
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
