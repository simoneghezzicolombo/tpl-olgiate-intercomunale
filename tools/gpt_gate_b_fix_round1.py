from pathlib import Path

# 1) Correct Overpass recursion: first build the selector union, then recurse to
# child nodes from that result set. The prior placement of '>' inside the union
# did not recurse from the selected ways and produced almost no line geometry.
p = Path('scripts/audit_01_fetch_real_inputs.py')
s = p.read_text(encoding='utf-8')
old = '''    query = (\n        f"[out:xml][timeout:{timeout}];\\n"\n        "(\\n"\n        f'  way["highway"]({south},{west},{north},{east});\\n'\n        f'  node["highway"="bus_stop"]({south},{west},{north},{east});\\n'\n        f'  node["public_transport"]({south},{west},{north},{east});\\n'\n        f'  node["amenity"]({south},{west},{north},{east});\\n'\n        f'  node["shop"]({south},{west},{north},{east});\\n'\n        f'  node["leisure"]({south},{west},{north},{east});\\n'\n        "  >;\\n"\n        ");\\n"\n        "out meta;"\n    )\n'''
new = '''    query = (\n        f"[out:xml][timeout:{timeout}];\\n"\n        "(\\n"\n        f'  way["highway"]({south},{west},{north},{east});\\n'\n        f'  node["highway"="bus_stop"]({south},{west},{north},{east});\\n'\n        f'  node["public_transport"]({south},{west},{north},{east});\\n'\n        f'  node["amenity"]({south},{west},{north},{east});\\n'\n        f'  node["shop"]({south},{west},{north},{east});\\n'\n        f'  node["leisure"]({south},{west},{north},{east});\\n'\n        ");\\n"\n        "(._;>;);\\n"\n        "out meta;"\n    )\n'''
if s.count(old) != 1:
    raise RuntimeError(f'Overpass query block matches={s.count(old)}')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

# 2) Make the real-network smoke test parse line geometry, so a syntactically
# valid but semantically empty OSM XML response cannot pass Gate A again.
t = Path('tests/test_audit_provenance.py')
ts = t.read_text(encoding='utf-8')
old_test = '''    fetch_osm_xml((45.726, 9.388, 45.731, 9.396), str(out), timeout=60)\n    assert out.exists() and out.stat().st_size > 500\n    assert b"<osm" in out.read_bytes()[:1024]\n'''
new_test = '''    fetch_osm_xml((45.726, 9.388, 45.731, 9.396), str(out), timeout=60)\n    assert out.exists() and out.stat().st_size > 500\n    assert b"<osm" in out.read_bytes()[:1024]\n    parsed_lines = pyogrio.read_dataframe(out, layer="lines")\n    assert len(parsed_lines) > 5, "Overpass response contains no usable highway geometry"\n    assert parsed_lines["highway"].notna().sum() > 5\n'''
if ts.count(old_test) != 1:
    raise RuntimeError(f'OSM network test block matches={ts.count(old_test)}')
ts = ts.replace(old_test, new_test, 1)
t.write_text(ts, encoding='utf-8')

# 3) Include the GTFS stop-to-network snap connector in accessibility times.
b = Path('scripts/audit_02_real_spatial.py')
bs = b.read_text(encoding='utf-8')
old_access = '''    # Distances on the reversed directed graph represent travel from each network\n    # node to its nearest stop in the original slope-sensitive graph.\n    network_to_stop = nx.multi_source_dijkstra_path_length(\n        G.reverse(copy=False), source_nodes, weight="walk_min"\n    )\n\n'''
new_access = '''    # Distances on the reversed directed graph represent travel from each network\n    # node to its nearest stop in the original slope-sensitive graph. Stop snapping\n    # is not free: add a synthetic super-source with the metric connector time for\n    # each GTFS stop. If several stops share a graph node, keep the shortest snap.\n    reversed_graph = G.reverse(copy=True)\n    super_source = 0\n    while super_source in reversed_graph:\n        super_source -= 1\n    reversed_graph.add_node(super_source)\n    stop_connector_min = {}\n    for _, stop in usable_stops.iterrows():\n        node = int(stop["graph_node_id"])\n        connector = float(stop["snap_distance_m"]) / (WALK_CONNECTOR_KMH * 1000.0 / 60.0)\n        stop_connector_min[node] = min(stop_connector_min.get(node, float("inf")), connector)\n    for node, connector in stop_connector_min.items():\n        reversed_graph.add_edge(super_source, node, walk_min=connector)\n    distances = nx.single_source_dijkstra_path_length(\n        reversed_graph, super_source, weight="walk_min"\n    )\n    network_to_stop = {node: dist for node, dist in distances.items() if node != super_source}\n\n'''
if bs.count(old_access) != 1:
    raise RuntimeError(f'Gate B access block matches={bs.count(old_access)}')
bs = bs.replace(old_access, new_access, 1)
bs = bs.replace('"population_calibrated_2025": "DERIVED",', '"population_calibrated_2025": "ESTIMATE",', 1)
bs = bs.replace('"dem_node_elevation": "DERIVED_FROM_DSM",', '"dem_node_elevation": "DERIVED",', 1)
b.write_text(bs, encoding='utf-8')

# 4) Keep the tests aligned to the allowed epistemic-status vocabulary.
gbt = Path('tests/test_gate_b_spatial.py')
gs = gbt.read_text(encoding='utf-8')
if "assert status['population_calibrated_2025'] == 'DERIVED'" not in gs:
    raise RuntimeError('Gate B epistemic assertion not found')
gs = gs.replace(
    "assert status['population_calibrated_2025'] == 'DERIVED'",
    "assert status['population_calibrated_2025'] == 'ESTIMATE'",
    1,
)
gbt.write_text(gs, encoding='utf-8')

print('Applied Overpass recursion, semantic network-test, stop connector and epistemic-status fixes.')
