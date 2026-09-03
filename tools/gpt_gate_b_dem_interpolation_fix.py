from pathlib import Path

p = Path('scripts/audit_02_real_spatial.py')
s = p.read_text(encoding='utf-8')

old_import = 'from scipy.spatial import cKDTree\n'
new_import = 'from scipy.ndimage import median_filter\nfrom scipy.spatial import cKDTree\n'
if s.count(old_import) != 1:
    raise RuntimeError(f'scipy import matcher count={s.count(old_import)}')
s = s.replace(old_import, new_import, 1)

old_dem = '''def _load_dem_array():\n    src = rasterio.open(DEM_RAW)\n    arr = src.read(1, masked=True)\n    return src, arr\n\n\ndef _dem_median(src, arr, lon: float, lat: float) -> float:\n    try:\n        row, col = src.index(lon, lat)\n    except Exception:\n        return float("nan")\n    r0, r1 = max(0, row - 1), min(arr.shape[0], row + 2)\n    c0, c1 = max(0, col - 1), min(arr.shape[1], col + 2)\n    window = arr[r0:r1, c0:c1]\n    values = np.asarray(window.compressed(), dtype=float)\n    values = values[np.isfinite(values)]\n    if len(values) == 0:\n        return float("nan")\n    return float(np.median(values))\n'''
new_dem = '''def _load_dem_array():\n    src = rasterio.open(DEM_RAW)\n    masked = src.read(1, masked=True)\n    data = np.asarray(masked.filled(np.nan), dtype=float)\n    finite = np.isfinite(data)\n    if finite.mean() < 0.95:\n        src.close()\n        raise ValueError(f"Copernicus DSM contains too many missing cells: {finite.mean():.3f} finite")\n    # Median-filter the DSM before interpolation. The source is a 30 m DSM, not\n    # bare-earth DTM; the local robust filter suppresses isolated building/tree\n    # returns. Missing values, if any, are neutral-filled before the filter and\n    # are still guarded by the node-level finite-coverage test downstream.\n    fill = float(np.nanmedian(data))\n    prepared = np.where(finite, data, fill)\n    prepared = median_filter(prepared, size=3, mode="nearest")\n    return src, prepared\n\n\ndef _dem_bilinear(src, arr: np.ndarray, lon: float, lat: float) -> float:\n    """Sample the prepared DSM continuously at lon/lat using bilinear interpolation.\n\n    Nearest-pixel sampling creates artificial elevation steps at 30 m raster cell\n    boundaries. Those steps become impossible grades on short OSM segments.\n    Bilinear interpolation turns the filtered raster into a continuous local\n    surface while preserving the underlying DEM scale.\n    """\n    try:\n        col_corner, row_corner = (~src.transform) * (lon, lat)\n    except Exception:\n        return float("nan")\n\n    # Raster values represent pixel centres at integer corner coordinate + 0.5.\n    x = float(col_corner) - 0.5\n    y = float(row_corner) - 0.5\n    c0 = math.floor(x)\n    r0 = math.floor(y)\n    dx = x - c0\n    dy = y - r0\n    c1 = c0 + 1\n    r1 = r0 + 1\n    if r0 < 0 or c0 < 0 or r1 >= arr.shape[0] or c1 >= arr.shape[1]:\n        return float("nan")\n\n    z00 = float(arr[r0, c0])\n    z10 = float(arr[r0, c1])\n    z01 = float(arr[r1, c0])\n    z11 = float(arr[r1, c1])\n    if not np.isfinite([z00, z10, z01, z11]).all():\n        return float("nan")\n    return float(\n        z00 * (1.0 - dx) * (1.0 - dy)\n        + z10 * dx * (1.0 - dy)\n        + z01 * (1.0 - dx) * dy\n        + z11 * dx * dy\n    )\n'''
if s.count(old_dem) != 1:
    raise RuntimeError(f'DEM sampler block matcher count={s.count(old_dem)}')
s = s.replace(old_dem, new_dem, 1)

old_elev = '    elevations = {node: _dem_median(dem_src, dem_arr, node[0], node[1]) for node in node_xy}\n'
new_elev = '    elevations = {node: _dem_bilinear(dem_src, dem_arr, node[0], node[1]) for node in node_xy}\n'
if s.count(old_elev) != 1:
    raise RuntimeError(f'elevation call matcher count={s.count(old_elev)}')
s = s.replace(old_elev, new_elev, 1)

old_info = '''    info = {\n        "walkable_source_features": int(len(lines)),\n        "graph_nodes_all": int(len(node_rows)),\n        "graph_edges_undirected_all": int(len(edge_rows)),\n        "giant_component_nodes": int(G.number_of_nodes()),\n        "giant_component_directed_edges": int(G.number_of_edges()),\n        "giant_component_ratio": float(giant_ratio),\n        "dem_missing_nodes_filled": int(len(elevations) - len(finite)),\n    }\n'''
new_info = '''    giant_edges = edge_df[edge_df["in_giant_component"]].copy()\n    abs_slope = giant_edges["slope_uv"].abs().replace([np.inf, -np.inf], np.nan).dropna()\n    info = {\n        "walkable_source_features": int(len(lines)),\n        "graph_nodes_all": int(len(node_rows)),\n        "graph_edges_undirected_all": int(len(edge_rows)),\n        "giant_component_nodes": int(G.number_of_nodes()),\n        "giant_component_directed_edges": int(G.number_of_edges()),\n        "giant_component_ratio": float(giant_ratio),\n        "dem_missing_nodes_filled": int(len(elevations) - len(finite)),\n        "dem_sampling": "3x3 median-filtered Copernicus DSM + bilinear interpolation",\n        "edge_abs_slope_p95": float(abs_slope.quantile(0.95)),\n        "edge_abs_slope_p99": float(abs_slope.quantile(0.99)),\n        "edges_abs_slope_gt_030": int((abs_slope > 0.30).sum()),\n    }\n'''
if s.count(old_info) != 1:
    raise RuntimeError(f'graph info matcher count={s.count(old_info)}')
s = s.replace(old_info, new_info, 1)

old_note = '            "Copernicus GLO-30 is a DSM; node elevations use a 3x3 median to reduce local building/tree artifacts but are not treated as bare-earth truth.",\n'
new_note = '            "Copernicus GLO-30 is a DSM; a 3x3 median-filtered surface with bilinear interpolation reduces local building/tree artifacts and avoids nearest-pixel elevation steps on short OSM segments, but is not treated as bare-earth truth.",\n'
if s.count(old_note) != 1:
    raise RuntimeError(f'DSM method-note matcher count={s.count(old_note)}')
s = s.replace(old_note, new_note, 1)
p.write_text(s, encoding='utf-8')

# Add a regression test for continuous bilinear sampling on a synthetic plane.
t = Path('tests/test_gate_b_spatial.py')
ts = t.read_text(encoding='utf-8')
ts = ts.replace(
    '    THRESHOLDS_MIN,\n    load_posas_totals,\n',
    '    THRESHOLDS_MIN,\n    _dem_bilinear,\n    load_posas_totals,\n',
    1,
)
ts = ts.replace('import pandas as pd\n', 'import pandas as pd\nimport rasterio\nfrom rasterio.io import MemoryFile\nfrom rasterio.transform import from_origin\n', 1)
anchor = '''def test_directional_tobler_behaviour():\n'''
regression = '''def test_dem_bilinear_sampler_is_continuous_on_planar_surface():\n    # 4x4 raster whose centre values lie on z = 10*col + 5*row.\n    arr = np.fromfunction(lambda r, c: 10.0 * c + 5.0 * r, (4, 4), dtype=float).astype('float32')\n    profile = {\n        'driver': 'GTiff', 'height': 4, 'width': 4, 'count': 1,\n        'dtype': 'float32', 'crs': 'EPSG:4326',\n        'transform': from_origin(0.0, 4.0, 1.0, 1.0),\n    }\n    with MemoryFile() as mem:\n        with mem.open(**profile) as ds:\n            ds.write(arr, 1)\n            # Pixel centres (1.5, 2.5) and (2.5, 2.5) have z=15 and z=25.\n            # Midway between them must interpolate to 20, not jump to either cell.\n            z = _dem_bilinear(ds, arr, 2.0, 2.5)\n            assert abs(z - 20.0) < 1e-6\n\n\n'''
if ts.count(anchor) != 1:
    raise RuntimeError(f'DEM regression insertion anchor count={ts.count(anchor)}')
ts = ts.replace(anchor, regression + anchor, 1)
t.write_text(ts, encoding='utf-8')

print('Applied continuous filtered DSM sampling and regression test.')
