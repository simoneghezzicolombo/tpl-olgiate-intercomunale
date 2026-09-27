"""Prefix/suffix partial circuits on pinned roads; no site or service selection."""
import argparse
import copy
import json
from pathlib import Path

from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import inputs, BASE, FS, VIRTUAL, NORTH, digest
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
from scripts.phase2_rt031_ordered_via_node_path_v3 import ordered_path
from scripts.phase2_audit_rt031_line8_occurrence_service_v3 import occurrences
from scripts.phase2_probe_rt031_line8_stop_relocation_v3 import validate_paths
from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import FLAGS, EXPECTED, load_sources
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import family_inputs
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter

OUTPUT = BASE / 'partial_services_pool.json'


def subsets(loop, local):
    ids = list(dict.fromkeys(e['stop_place_id'] for e in sorted(loop['events'], key=lambda e: e['path_node_index'])
                            if e['stop_place_id'] not in (FS, local)))
    # Every prefix and suffix, including the local-only option; no chosen town
    # or normative exclusion. Full patterns already retained separately.
    return sorted({(), *(tuple(ids[:i]) for i in range(1, len(ids))),
                   *(tuple(ids[i:]) for i in range(1, len(ids)))})


def build(graph_dir):
    sources = load_sources()
    reference = next(f for f in family_inputs(sources) if f['name'] == 'fast_local_both_directions')
    paths = inputs(graph_dir)
    edges, nodes, rules, attachments = build_graph(paths)
    fs = attachments[FS]['graph_node_id']
    sites = {FS: {'node': fs, 'name': 'Olgiate FS', 'status': 'INVENTORY_NOT_APPROVED'}}
    for loop in reference['loops'].values():
        for event in loop['events']:
            sites[event['stop_place_id']] = {'node': edges[event['incoming_edge']]['v_node_id'],
                                            'name': event['name'], 'status': event['site_status']}
    adapter = FrozenRT017ViaNodeAdapter(edges.values(), rules, unresolved_external_via_way_count=2)
    loops = copy.deepcopy(reference['loops'])
    seen = {tuple(l['edge_ids']): p for p, l in loops.items()}
    records = []
    for pattern, original in sorted(sources['wings']['loops'].items()):
        wing = pattern.split('_')[0]
        local = VIRTUAL if wing == 'west' else NORTH
        for index, ids in enumerate(subsets(original, local)):
            name = f'{pattern}_partial_{index:02d}'
            waypoints = [fs, sites[local]['node'], *(sites[sid]['node'] for sid in ids), sites[local]['node'], fs]
            waypoints = [node for i, node in enumerate(waypoints) if i == 0 or node != waypoints[i-1]]
            answer = ordered_path(edges, rules, waypoints, allow_internal_origin=False)
            record = {'requested_pattern_id': name, 'source_pattern': pattern,
                      'required_nonlocal_site_sequence': list(ids), 'required_local_site_id': local,
                      'reachable': answer['reachable']}
            if not answer['reachable']:
                records.append(record)
                continue
            path = answer['_path_edge_ids']
            if tuple(path) in seen:
                record.update(pattern_id=seen[tuple(path)], duplicate_geometry=True)
                records.append(record)
                continue
            events = [{**e, 'offset_from_wing_origin_min': e['offset_road_minutes']}
                      for e in occurrences(path, edges, sites, fs, name) if e['stop_place_id'] != FS]
            if not set(ids) | {local} <= {e['stop_place_id'] for e in events}:
                raise ValueError('ordered site lost')
            loop = {'edge_ids': path, 'events': events,
                    'distance_m': sum(float(edges[e]['length_m']) for e in path),
                    'road_minutes': sum(float(edges[e]['running_minutes_model']) for e in path),
                    'ordered_required_nodes': waypoints,
                    'represented_via_node_path_verified': True, 'full_history_legality_certified': False}
            loops[name] = loop
            seen[tuple(path)] = name
            record.update(pattern_id=name, duplicate_geometry=False)
            records.append(record)
        print(json.dumps({'source_pattern': pattern, 'requests_so_far': len(records), 'unique_patterns_so_far': len(loops)}), flush=True)
    validate_paths({'all': [{'loops': loops}]}, edges, adapter, fs)
    joins = {a + '>' + b: adapter.decision((left['edge_ids'][-1],), right['edge_ids'][0])['allowed'] is True
             for a, left in loops.items() for b, right in loops.items()}
    if not all(joins.values()):
        raise ValueError('partial-pattern FS joins incompatible; fleet occupation cannot certify this pool')
    family = {**reference, 'name': 'full_retention_with_prefix_suffix_partials', 'loops': loops, 'joins': joins,
              'rail_anchor_scope': 'each_declared_site'}
    result = {'contract': 'RT031_LINE8_PREFIX_SUFFIX_PARTIAL_POOL_V3', 'family': family, 'requests': records,
              'source_sha256_normalized_newlines': EXPECTED,
              'road_source_sha256': {k: digest(paths[k], k.endswith('normalized_newlines')) for k in paths},
              'reference_site_ids': sorted(sites),
              'semantics': 'Four full corrected wing paths plus shortest represented-via-node circuits for every proper prefix/suffix of nonlocal site order in each original direction, with own local site at both ends (one visit for local-only). Encountered reference sites counted as hypothetical events. No internal FS return. Not all road orders or all partial services; all 28 sites must retain service in the timetable, not on every trip. Full-history restrictions, platforms, vehicle suitability and passenger continuity remain uncertified.',
              **{k: False for k in FLAGS}, 'actual_timetable_certified': False,
              'decision_budget_km': None, 'uncertainty_band_min': None}
    coordinates = {n: [float(row['lon']), float(row['lat'])] for n, row in nodes.items()}
    # Virtual coordinates are already pinned by the source GeoJSON.
    prior_shape = json.loads((BASE / 'local_counterflow.geojson').read_text(encoding='utf-8'))
    local_point = next(f for f in prior_shape['features'] if f['geometry']['type'] == 'Point' and f['properties']['site_id'] == VIRTUAL)
    coordinates[VIRTUAL] = local_point['geometry']['coordinates']
    features = []
    for pattern, loop in loops.items():
        vertex = [edges[loop['edge_ids'][0]]['u_node_id']] + [edges[e]['v_node_id'] for e in loop['edge_ids']]
        features.append({'type': 'Feature', 'properties': {'pattern': pattern, 'boarding_authorised': False},
                         'geometry': {'type': 'LineString', 'coordinates': [coordinates[n] for n in vertex]}})
    features.extend(f for f in prior_shape['features'] if f['geometry']['type'] == 'Point')
    return result, {'type': 'FeatureCollection', 'properties': {k: False for k in FLAGS}, 'features': features}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--graph_dir', type=Path, required=True)
    args = parser.parse_args()
    result, shape = build(args.graph_dir)
    for path, value in ((OUTPUT, result), (BASE / 'partial_services_pool.geojson', shape)):
        path.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps({'requests': len(result['requests']), 'unique_patterns': len(result['family']['loops'])}), flush=True)
