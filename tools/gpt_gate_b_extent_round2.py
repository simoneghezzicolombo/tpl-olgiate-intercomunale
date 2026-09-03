from pathlib import Path

p = Path('scripts/audit_01_fetch_real_inputs.py')
s = p.read_text(encoding='utf-8')
old = '''    # Gate B spatial-integrity prerequisite: derive the acquisition extent from the\n    # full official municipal geometry rather than from a hand-written bbox. A\n    # small buffer preserves road-network continuity just outside administrative\n    # borders. This matters especially for northern Brivio, which extended beyond\n    # the earlier 45.760 N cutoff.\n    minx, miny, maxx, maxy = boundaries.to_crs(4326).total_bounds\n    bbox_pad_deg = 0.002\n    bbox = (\n        float(miny - bbox_pad_deg),\n        float(minx - bbox_pad_deg),\n        float(maxy + bbox_pad_deg),\n        float(maxx + bbox_pad_deg),\n    )\n    bbox_meta = {\n        "bbox_south_west_north_east": [round(x, 8) for x in bbox],\n        "derived_from": "ISTAT 2026 five-core-municipality total_bounds + 0.002 degree buffer",\n    }\n'''
new = '''    # Gate B spatial-integrity prerequisite: derive the acquisition extent from the\n    # full official municipal geometry rather than from a hand-written bbox. Use a\n    # metric buffer, not angular-degree padding, so east-west and north-south margins\n    # have a defensible physical meaning. 500 m exceeds Gate B's 350 m road-context\n    # buffer and avoids artificially truncating the pedestrian graph at borders.\n    buffered_core_utm = boundaries.to_crs(32632).geometry.union_all().buffer(500.0)\n    buffered_wgs84 = gpd.GeoSeries([buffered_core_utm], crs=32632).to_crs(4326)\n    minx, miny, maxx, maxy = buffered_wgs84.total_bounds\n    bbox = (float(miny), float(minx), float(maxy), float(maxx))\n    bbox_meta = {\n        "bbox_south_west_north_east": [round(x, 8) for x in bbox],\n        "derived_from": "ISTAT 2026 five-core-municipality geometry + 500 m UTM32N buffer",\n        "buffer_m": 500.0,\n    }\n'''
if s.count(old) != 1:
    raise RuntimeError(f'metric OSM extent matcher count={s.count(old)}')
s = s.replace(old, new, 1)
old_note = '''            f"Access date 2026-09-03; bbox={bbox}; extent derived from the full "\n            "ISTAT core-municipality geometry with 0.002 degree buffer; raw snapshot "\n            "checksum recorded here."\n'''
new_note = '''            f"Access date 2026-09-03; bbox={bbox}; extent derived from the full "\n            "ISTAT core-municipality geometry with a 500 m UTM32N buffer; raw snapshot "\n            "checksum recorded here."\n'''
if s.count(old_note) != 1:
    raise RuntimeError(f'OSM provenance note matcher count={s.count(old_note)}')
s = s.replace(old_note, new_note, 1)
p.write_text(s, encoding='utf-8')

# Gate A coverage test must also ensure the physical buffer is recorded.
t = Path('tests/test_audit_provenance.py')
ts = t.read_text(encoding='utf-8')
needle = '''    payload = json.loads(meta.read_text(encoding="utf-8"))\n    south, west, north, east = payload["bbox_south_west_north_east"]\n'''
replacement = '''    payload = json.loads(meta.read_text(encoding="utf-8"))\n    assert payload.get("buffer_m") == 500.0\n    south, west, north, east = payload["bbox_south_west_north_east"]\n'''
if ts.count(needle) != 1:
    raise RuntimeError(f'bbox metadata test matcher count={ts.count(needle)}')
ts = ts.replace(needle, replacement, 1)
t.write_text(ts, encoding='utf-8')

# Gate B method should name the audited relation between acquisition and graph buffer.
d = Path('docs/GATE_B_METHOD.md')
ds = d.read_text(encoding='utf-8')
old_doc = '- OpenStreetMap acquisito via Overpass con estensione derivata dall\'intera geometria ufficiale dei cinque comuni e buffer di continuità;\n'
new_doc = '- OpenStreetMap acquisito via Overpass con estensione derivata dall\'intera geometria ufficiale dei cinque comuni e buffer metrico UTM di 500 m, maggiore del contesto stradale Gate B di 350 m;\n'
if ds.count(old_doc) != 1:
    raise RuntimeError(f'Gate B method buffer matcher count={ds.count(old_doc)}')
ds = ds.replace(old_doc, new_doc, 1)
d.write_text(ds, encoding='utf-8')

print('Replaced angular OSM padding with audited 500 m UTM buffer.')

# trigger after workflow installation
