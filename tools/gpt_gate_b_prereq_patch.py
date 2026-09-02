from pathlib import Path

p = Path('scripts/audit_01_fetch_real_inputs.py')
s = p.read_text(encoding='utf-8')

old_def = 'def step_7_osm_real_data() -> None:\n'
new_def = 'def step_7_osm_real_data(boundaries: gpd.GeoDataFrame) -> None:\n'
if s.count(old_def) != 1:
    raise RuntimeError(f'step_7 definition matches={s.count(old_def)}')
s = s.replace(old_def, new_def, 1)

old_block = '''    stops_file = out_dir / "osm_bus_stops_core.json"\n    pois_file = out_dir / "osm_pois_core.json"\n    bbox = (\n        BBOX_CORE["south"],\n        BBOX_CORE["west"],\n        BBOX_CORE["north"],\n        BBOX_CORE["east"],\n    )\n\n    if not raw.exists() or raw.stat().st_size == 0:\n        fetch_osm_xml(bbox, str(raw))\n\n    ogr_bbox = (\n        BBOX_CORE["west"],\n        BBOX_CORE["south"],\n        BBOX_CORE["east"],\n        BBOX_CORE["north"],\n    )\n'''
new_block = '''    stops_file = out_dir / "osm_bus_stops_core.json"\n    pois_file = out_dir / "osm_pois_core.json"\n    bbox_meta_file = out_dir / "osm_core_bbox.meta.json"\n\n    # Gate B spatial-integrity prerequisite: derive the acquisition extent from the\n    # full official municipal geometry rather than from a hand-written bbox. A\n    # small buffer preserves road-network continuity just outside administrative\n    # borders. This matters especially for northern Brivio, which extended beyond\n    # the earlier 45.760 N cutoff.\n    minx, miny, maxx, maxy = boundaries.to_crs(4326).total_bounds\n    bbox_pad_deg = 0.002\n    bbox = (\n        float(miny - bbox_pad_deg),\n        float(minx - bbox_pad_deg),\n        float(maxy + bbox_pad_deg),\n        float(maxx + bbox_pad_deg),\n    )\n    bbox_meta = {\n        "bbox_south_west_north_east": [round(x, 8) for x in bbox],\n        "derived_from": "ISTAT 2026 five-core-municipality total_bounds + 0.002 degree buffer",\n    }\n\n    cached_bbox_matches = False\n    if bbox_meta_file.exists():\n        try:\n            cached_bbox_matches = json.loads(\n                bbox_meta_file.read_text(encoding="utf-8")\n            ) == bbox_meta\n        except (json.JSONDecodeError, OSError):\n            cached_bbox_matches = False\n\n    if (\n        not raw.exists()\n        or raw.stat().st_size == 0\n        or not cached_bbox_matches\n    ):\n        # Invalidate derivatives tied to the former/manual extent before fetching.\n        for stale in (raw, lines_file, points_file, stops_file, pois_file):\n            stale.unlink(missing_ok=True)\n        fetch_osm_xml(bbox, str(raw))\n        bbox_meta_file.write_text(\n            json.dumps(bbox_meta, indent=2, ensure_ascii=False) + "\\n",\n            encoding="utf-8",\n        )\n\n    ogr_bbox = (bbox[1], bbox[0], bbox[3], bbox[2])\n'''
if s.count(old_block) != 1:
    raise RuntimeError(f'OSM bbox block matches={s.count(old_block)}')
s = s.replace(old_block, new_block, 1)

old_main = '    step_7_osm_real_data()\n'
new_main = '    step_7_osm_real_data(boundaries)\n'
if s.count(old_main) != 1:
    raise RuntimeError(f'main call matches={s.count(old_main)}')
s = s.replace(old_main, new_main, 1)

old_note = '        note=f"Access date 2026-09-03; bbox={bbox}; raw snapshot checksum recorded here.",\n'
new_note = '''        note=(\n            f"Access date 2026-09-03; bbox={bbox}; extent derived from the full "\n            "ISTAT core-municipality geometry with 0.002 degree buffer; raw snapshot "\n            "checksum recorded here."\n        ),\n'''
if s.count(old_note) != 1:
    raise RuntimeError(f'OSM note matches={s.count(old_note)}')
s = s.replace(old_note, new_note, 1)

p.write_text(s, encoding='utf-8')

# Strengthen Gate A test: the OSM snapshot acquisition extent must cover all five
# municipalities. Network-quality checks remain Gate B.
t = Path('tests/test_audit_provenance.py')
ts = t.read_text(encoding='utf-8')
anchor = '''def test_osm_repo_snapshot_and_layers():\n'''
insert = '''def test_osm_acquisition_extent_covers_core_boundaries():\n    meta = Path("data/raw/osm/osm_core_bbox.meta.json")\n    assert meta.exists(), "OSM bbox metadata missing"\n    import json\n    payload = json.loads(meta.read_text(encoding="utf-8"))\n    south, west, north, east = payload["bbox_south_west_north_east"]\n    bounds = gpd.read_file("data/raw/boundaries/comuni_core_istat_2026.geojson").to_crs(4326)\n    minx, miny, maxx, maxy = bounds.total_bounds\n    assert west <= minx and south <= miny\n    assert east >= maxx and north >= maxy\n\n\n'''
if insert not in ts:
    if ts.count(anchor) != 1:
        raise RuntimeError(f'OSM test anchor matches={ts.count(anchor)}')
    ts = ts.replace(anchor, insert + anchor, 1)
t.write_text(ts, encoding='utf-8')

print('Patched Gate A OSM extent to full official five-municipality geometry.')
