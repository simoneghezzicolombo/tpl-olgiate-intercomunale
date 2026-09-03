import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

from scripts.audit_02_real_spatial import (
    ACCESS_CELLS,
    CORE_CODES,
    CORE_STOPS,
    COVERAGE,
    GRAPH_EDGES,
    GRAPH_NODES,
    MAX_CELL_CONNECTOR_M,
    POP_CELLS,
    POSAS,
    SPOT_CHECKS,
    SUMMARY,
    THRESHOLDS_MIN,
    _dem_bilinear,
    load_posas_totals,
    tobler_walk_minutes,
)


def _posas_totals():
    df = pd.read_csv(
        POSAS,
        sep=';',
        skiprows=1,
        dtype={'Codice comune': str},
        encoding='utf-8-sig',
        low_memory=False,
    )
    df['Codice comune'] = (
        df['Codice comune'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(6)
    )
    df['Età_num'] = pd.to_numeric(df['Età'], errors='coerce')
    df['Totale'] = pd.to_numeric(df['Totale'], errors='coerce')
    agg = df[df['Codice comune'].isin(CORE_CODES) & (df['Età_num'] == 999)].copy()
    return agg.set_index('Codice comune')['Totale']


def test_posas_aggregate_row_is_not_double_counted():
    parsed = load_posas_totals().set_index('Codice comune')['istat_2025'].sort_index()
    official = _posas_totals().sort_index()
    assert np.allclose(parsed.to_numpy(), official.to_numpy(), atol=1e-6)

    raw = pd.read_csv(
        POSAS, sep=';', skiprows=1, dtype={'Codice comune': str},
        encoding='utf-8-sig', low_memory=False,
    )
    raw['Codice comune'] = raw['Codice comune'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(6)
    raw['Età_num'] = pd.to_numeric(raw['Età'], errors='coerce')
    raw['Totale'] = pd.to_numeric(raw['Totale'], errors='coerce')
    core = raw[raw['Codice comune'].isin(CORE_CODES)]
    naive = core.groupby('Codice comune')['Totale'].sum().sort_index()
    # The old bug summed detailed ages plus the already-aggregated 999 row.
    assert np.allclose(naive.to_numpy(), 2.0 * official.to_numpy(), atol=1e-6)
    assert float(parsed.sum()) == 22914.0


def test_gate_b_source_contains_no_legacy_random_or_manual_nuclei():
    text = Path('scripts/audit_02_real_spatial.py').read_text(encoding='utf-8')
    assert 'np.random' not in text
    assert 'NUCLEI =' not in text
    assert 'STOPS_DATABASE' not in text
    assert 'STOP_ELEVATIONS' not in text
    assert 'Euclidean*' not in text


def test_dem_bilinear_sampler_is_continuous_on_planar_surface():
    # 4x4 raster whose centre values lie on z = 10*col + 5*row.
    arr = np.fromfunction(lambda r, c: 10.0 * c + 5.0 * r, (4, 4), dtype=float).astype('float32')
    profile = {
        'driver': 'GTiff', 'height': 4, 'width': 4, 'count': 1,
        'dtype': 'float32', 'crs': 'EPSG:4326',
        'transform': from_origin(0.0, 4.0, 1.0, 1.0),
    }
    with MemoryFile() as mem:
        with mem.open(**profile) as ds:
            ds.write(arr, 1)
            # Pixel centres (1.5, 2.5) and (2.5, 2.5) have z=15 and z=25.
            # Midway between them must interpolate to 20, not jump to either cell.
            z = _dem_bilinear(ds, arr, 2.0, 2.5)
            assert abs(z - 20.0) < 1e-6


def test_directional_tobler_behaviour():
    flat = tobler_walk_minutes(1000, 0)
    uphill = tobler_walk_minutes(1000, 100)
    downhill = tobler_walk_minutes(1000, -100)
    assert flat > 0
    assert uphill > flat
    assert downhill < uphill


def test_population_cells_are_real_worldpop_and_quadrate_to_posas():
    df = pd.read_csv(POP_CELLS, dtype={'PRO_COM_T': str})
    df['PRO_COM_T'] = df['PRO_COM_T'].str.zfill(6)
    assert len(df) > 1000
    assert set(df['PRO_COM_T']) == CORE_CODES
    assert (df['worldpop_2020_raw'] > 0).all()
    assert (df['pop_calibrated_2025'] > 0).all()
    assert np.isfinite(df['calibration_factor_2025']).all()
    assert not np.allclose(df['worldpop_2020_raw'], df['pop_calibrated_2025'])

    got = df.groupby('PRO_COM_T')['pop_calibrated_2025'].sum().sort_index()
    expected = _posas_totals().sort_index()
    assert list(got.index) == list(expected.index)
    assert np.allclose(got.to_numpy(), expected.to_numpy(), atol=1e-5)


def test_osm_acquisition_extent_covers_full_municipal_geometry():
    meta = json.loads(Path('data/raw/osm/osm_core_bbox.meta.json').read_text(encoding='utf-8'))
    south, west, north, east = meta['bbox_south_west_north_east']
    b = gpd.read_file('data/raw/boundaries/comuni_core_istat_2026.geojson').to_crs(4326)
    minx, miny, maxx, maxy = b.total_bounds
    assert west <= minx and south <= miny
    assert east >= maxx and north >= maxy
    assert north > 45.77


def test_walk_graph_is_real_connected_and_slope_aware():
    nodes = pd.read_csv(GRAPH_NODES)
    edges = pd.read_csv(GRAPH_EDGES)
    summary = json.loads(SUMMARY.read_text(encoding='utf-8'))
    assert len(nodes) > 1500
    assert len(edges) > 1500
    assert nodes['in_giant_component'].sum() > 1000
    assert edges['in_giant_component'].sum() > 1000
    assert summary['graph']['giant_component_ratio'] >= 0.75
    assert nodes['elevation_m'].notna().all()
    assert nodes['elevation_m'].max() > nodes['elevation_m'].min()
    assert (edges['length_m'] > 0).all()
    assert (edges['walk_min_uv'] > 0).all()
    assert (edges['walk_min_vu'] > 0).all()
    assert ((edges['walk_min_uv'] - edges['walk_min_vu']).abs() > 1e-5).sum() > 100

    # Regression guard against the former nearest-pixel DSM artifact. These are
    # distribution-level sanity limits, not claims that every walkable path must
    # be below a given natural grade. They deliberately allow a steep tail for
    # paths/steps while rejecting a network where raster cell boundaries create
    # implausible grades across a large share of ordinary segments.
    assert 'bilinear interpolation' in summary['graph']['dem_sampling']
    assert summary['graph']['edge_abs_slope_p95'] < 0.30
    assert summary['graph']['edge_abs_slope_p99'] < 0.50
    giant_edge_count = int(edges['in_giant_component'].sum())
    steep_share = summary['graph']['edges_abs_slope_gt_030'] / giant_edge_count
    assert steep_share < 0.05


def test_gtfs_is_primary_stop_source_and_spot_checks_pass():
    stops = pd.read_csv(CORE_STOPS, dtype={'stop_id': str})
    spots = pd.read_csv(SPOT_CHECKS, dtype={'stop_id': str})
    assert len(stops) >= 10
    assert stops['stop_id'].notna().all()
    assert stops['stop_name'].notna().all()
    assert stops['snap_ok'].sum() >= 5
    assert set(spots['stop_id']) == {'300407', '300063', '300089', '300782', '300804'}
    assert spots['present_in_official_gtfs'].all()
    assert spots['name_match'].all()
    assert spots['pass'].all()
    assert (spots['coordinate_error_m'] <= 5).all()


def test_accessibility_outputs_are_complete_and_monotonic():
    pop = pd.read_csv(POP_CELLS)
    acc = pd.read_csv(ACCESS_CELLS)
    cov = pd.read_csv(COVERAGE)
    summary = json.loads(SUMMARY.read_text(encoding='utf-8'))
    assert len(acc) == len(pop)
    assert acc['cell_id'].is_unique
    assert (acc['connector_distance_m'] >= 0).all()
    assert summary['access']['max_cell_connector_m'] == MAX_CELL_CONNECTOR_M
    assert summary['access']['population_with_graph_access_pct'] >= 85.0

    total = float(acc['pop_calibrated_2025'].sum())
    covered = []
    for t in THRESHOLDS_MIN:
        col = f'covered_{t}min'
        assert col in acc.columns
        pop_t = float(acc.loc[acc[col], 'pop_calibrated_2025'].sum())
        assert 0 <= pop_t <= total + 1e-6
        covered.append(pop_t)
    assert covered == sorted(covered)

    core = cov[cov['scope'] == 'core_total'].sort_values('threshold_min')
    assert list(core['threshold_min']) == list(THRESHOLDS_MIN)
    assert core['population_covered_2025'].tolist() == sorted(core['population_covered_2025'].tolist())
    assert core['coverage_pct'].between(0, 100).all()


def test_gate_b_summary_keeps_epistemic_statuses_separate():
    summary = json.loads(SUMMARY.read_text(encoding='utf-8'))
    status = summary['epistemic_status']
    assert status['worldpop_2020_raw'] == 'FACT'
    assert status['population_calibrated_2025'] == 'ESTIMATE'
    assert status['gtfs_stop_coordinates'] == 'FACT'
    assert status['accessibility'] == 'MODEL_OUTPUT'
    assert summary['status'] == 'PENDING_EXTERNAL_REVIEW'
