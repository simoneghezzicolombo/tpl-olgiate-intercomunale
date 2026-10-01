"""Diagnostic all-stop road minimum with unfrozen wing boundary legs.

The only protected road boundary is Olgiate FS itself. This is an exact
distance minimum in the frozen RT017 graph under represented via-node turns,
not proof of full-history road legality or an operable bus service.
"""

import argparse
import json
from pathlib import Path

from scripts.phase2_probe_rt031_line8_free_orders_v3 import (
    EdgeStateClosure, reversal_indices, terminal_tour,
)
from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import BASE, FS, NORTH, VIRTUAL, digest, inputs
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
from scripts.phase2_audit_rt031_line8_occurrence_service_v3 import occurrences
from scripts.phase2_probe_rt031_line8_stop_relocation_v3 import validate_paths
from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import load_sources
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import family_inputs
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter

OUTPUT = BASE / 'free_boundary_road_comparison.json'
SHAPE = BASE / 'free_boundary_road_comparison.geojson'
ARLATE_NEW = 'PROXY::RT031_ADDITIONAL::n:534398.29:5063851.64'
ARLATE_NODE = 'n:534398.29:5063851.64'


def directional_access(events, site_id):
    hits = [event for event in events if event['stop_place_id'] == site_id]
    if not hits:
        raise ValueError('required directional service site absent')
    return {'occurrence_count': len(hits),
            'best_fs_to_site_road_min': min(e['road_minutes_from_previous_fs'] for e in hits),
            'best_site_to_fs_road_min': min(e['road_minutes_to_next_fs'] for e in hits)}


def build(graph_dir):
    paths = inputs(graph_dir)
    pinned = json.loads((BASE / 'free_order_road_comparison.json').read_text(encoding='utf-8'))
    normalized_keys = {'candidates_normalized_newlines', 'wings', 'timetable'}
    actual_hashes = {k: digest(p, k in normalized_keys) for k, p in paths.items()}
    expected_hashes = {**pinned['road_source_sha256'],
                       **{k: pinned['source_sha256_normalized_newlines'][k]
                          for k in ('wings', 'timetable')}}
    if actual_hashes != expected_hashes:
        raise ValueError('road evidence differs from pinned free-order audit')
    edges, nodes, rules, attachments = build_graph(paths)
    fs = attachments[FS]['graph_node_id']
    starts = [e for e in sorted(edges) if edges[e]['u_node_id'] == fs]
    finishes = [e for e in sorted(edges) if edges[e]['v_node_id'] == fs]
    if len(starts) != 1 or len(finishes) != 1:
        raise ValueError('this diagnostic requires exactly one FS outgoing and incoming edge')
    start, finish = starts[0], finishes[0]
    sources = load_sources()
    reference = next(f for f in family_inputs(sources) if f['name'] == 'fast_local_both_directions')
    sites = {FS: {'node': fs, 'name': 'Olgiate FS', 'status': 'INVENTORY_NOT_APPROVED'}}
    for loop in reference['loops'].values():
        for event in loop['events']:
            sid = event['stop_place_id']
            node = edges[event['incoming_edge']]['v_node_id']
            if sid in sites and sites[sid]['node'] != node:
                raise ValueError('one site identity maps to multiple graph nodes')
            sites[sid] = {
                'node': node,
                'name': event['name'], 'status': event['site_status'],
            }
    if ARLATE_NODE not in nodes or ARLATE_NEW in sites:
        raise ValueError('Arlate additional site inconsistent with road graph')
    sites[ARLATE_NEW] = {'node': ARLATE_NODE, 'name': 'Arlate N1212 (proposta)',
                         'status': 'NEW_ON_PATH_SITE_NOT_APPROVED'}
    if len(sites) != 29:
        raise ValueError('expected exactly 29 project stop identities including FS')
    adapter = FrozenRT017ViaNodeAdapter(edges.values(), rules, unresolved_external_via_way_count=2)
    closure = EdgeStateClosure(edges, adapter, {fs})
    loops, audits = {}, []
    for wing, ref_name in [('west', 'west_B'), ('east', 'east_A')]:
        old = reference['loops'][ref_name]
        required_ids = {event['stop_place_id'] for event in old['events']}
        if wing == 'east':
            required_ids.add(ARLATE_NEW)
        required_nodes = {sites[sid]['node'] for sid in required_ids}
        answer = terminal_tour(closure, required_nodes, start,
                               edges[finish]['u_node_id'], finish, adapter)
        path = [start, *answer['interior_edge_ids'], finish]
        actual = occurrences(path, edges, sites, fs, wing + '_free_boundary')
        events = [{**e, 'offset_from_wing_origin_min': e['offset_road_minutes']}
                  for e in actual if e['stop_place_id'] != FS]
        found = {e['stop_place_id'] for e in events}
        if not required_ids <= found:
            raise ValueError('required stop occurrence lost')
        distance = sum(float(edges[e]['length_m']) for e in path)
        road_minutes = sum(float(edges[e]['running_minutes_model']) for e in path)
        if abs(distance - answer['interior_distance_m'] -
               float(edges[start]['length_m']) - float(edges[finish]['length_m'])) > 1e-4:
            raise ValueError('distance reconstruction inconsistent')
        loops[wing] = {'edge_ids': path, 'events': events, 'distance_m': distance,
                       'road_minutes': road_minutes,
                       'represented_via_node_path_verified': True,
                       'full_history_legality_certified': False}
        audits.append({'wing': wing, 'reference_pattern': ref_name,
                       'reference_distance_m': old['distance_m'], 'distance_m': distance,
                       'distance_saved_m': old['distance_m'] - distance,
                       'required_site_ids': sorted(required_ids),
                       'required_site_count': len(required_ids),
                       'all_required_sites_observed': True,
                       'immediate_reversal_indices': reversal_indices(path, edges), **answer})
        print(json.dumps({k: audits[-1][k] for k in
                          ('wing', 'distance_m', 'distance_saved_m', 'required_site_count',
                           'terminal_state_count', 'immediate_reversal_indices')}), flush=True)
    validate_paths({'all': [{'loops': loops}]}, edges, adapter, fs)
    prior = json.loads((BASE / 'independent_wings.json').read_text(encoding='utf-8'))
    if prior['contract'] != 'RT031_LINE8_INDEPENDENT_WINGS_DIAGNOSTIC_V3':
        raise ValueError('prior wing comparison contract changed')
    for wing, prior_name in [('west', 'west_A'), ('east', 'east_A')]:
        if loops[wing]['edge_ids'] != prior['loops'][prior_name]['edge_ids']:
            raise ValueError('relaxed minimum differs from existing recorded road witness')
    join = adapter.decision((loops['west']['edge_ids'][-1],),
                            loops['east']['edge_ids'][0])['allowed'] is True
    if not join:
        raise ValueError('represented FS turn from west to east forbidden')
    total = sum(a['distance_m'] for a in audits)
    reference_total = sum(reference['loops'][n]['distance_m'] for n in ('west_B', 'east_A'))
    target_loop_m = reference_total * 16 / 18
    local_service_comparison = {}
    for wing, ref_name, local_id in [('west', 'west_B', VIRTUAL), ('east', 'east_A', NORTH)]:
        before = directional_access(reference['loops'][ref_name]['events'], local_id)
        after = directional_access(loops[wing]['events'], local_id)
        local_service_comparison[wing] = {
            'stop_place_id': local_id, 'reference': before, 'road_minimum': after,
            'same_or_better_road_minutes_both_directions':
                after['best_fs_to_site_road_min'] <= before['best_fs_to_site_road_min'] + 1e-5
                and after['best_site_to_fs_road_min'] <= before['best_site_to_fs_road_min'] + 1e-5,
            'reference_occurrence_count_preserved':
                after['occurrence_count'] >= before['occurrence_count'],
        }
    result = {'contract': 'RT031_LINE8_FREE_BOUNDARY_ROAD_COMPARISON_V3',
              'semantics': 'Exact independent wing road-distance minima retaining all 29 site identities, '
                           'with FS as the sole fixed boundary and no internal FS return, in the frozen RT017 '
                           'directed graph under represented via-node restrictions. Shortest-path terminal '
                           'states retain the incoming directed edge. Full-history restrictions, bus manoeuvres, '
                           'physical boarding, passenger continuity, timetable, access and selection are not certified.',
              'loops': loops, 'audits': audits, 'reference_total_distance_m': reference_total,
              'minimum_total_distance_m': total,
              'prior_recorded_wing_geometry_reproduced': True,
              'prior_recorded_wing_source_sha256_normalized_newlines':
                  digest(BASE / 'independent_wings.json', True),
              'target_loop_distance_m_for_18_trips_at_reference_16_trip_production': target_loop_m,
              'distance_margin_to_target_m': target_loop_m - total,
              'annual_service_km_if_18_trips_260_days': total * 18 * 260 / 1000,
              'local_service_comparison': local_service_comparison,
              'both_local_directional_occurrence_guarantees_preserved': all(
                  row['same_or_better_road_minutes_both_directions']
                  and row['reference_occurrence_count_preserved']
                  for row in local_service_comparison.values()),
              'represented_via_node_join_verified': join,
              'full_history_legality_certified': False,
              'bus_manoeuvres_authorised': False,
              'actual_timetable_certified': False,
              'candidate_domain_complete': False,
              'network_selected': False,
              'primary_selection_authorised': False,
              'runner_up_selection_authorised': False,
              'decision_budget_km': None, 'uncertainty_band_min': None,
              'road_source_sha256': actual_hashes}
    coords = {nid: [float(row['lon']), float(row['lat'])] for nid, row in nodes.items()}
    prior_shape = json.loads((BASE / 'local_counterflow.geojson').read_text(encoding='utf-8'))
    for feature in prior_shape['features']:
        if feature['geometry']['type'] == 'Point' and feature['properties'].get('site_id') in sites:
            coords[sites[feature['properties']['site_id']]['node']] = feature['geometry']['coordinates']
    features = []
    for wing, loop in loops.items():
        vertex = [edges[loop['edge_ids'][0]]['u_node_id']] + [edges[e]['v_node_id'] for e in loop['edge_ids']]
        features.append({'type': 'Feature',
                         'properties': {'wing': wing, 'boarding_authorised': False,
                                        'route_selected': False},
                         'geometry': {'type': 'LineString',
                                      'coordinates': [coords[n] for n in vertex]}})
        for index in reversal_indices(loop['edge_ids'], edges):
            node = vertex[index]
            features.append({'type': 'Feature',
                             'properties': {'wing': wing, 'immediate_reversal': True,
                                            'graph_node_id': node, 'bus_manoeuvre_authorised': False},
                             'geometry': {'type': 'Point', 'coordinates': coords[node]}})
    for sid, site in sorted(sites.items()):
        loc = coords.get(site['node'])
        if loc is None:
            raise ValueError('site node lacks coordinates')
        features.append({'type': 'Feature', 'properties': {'site_id': sid,
                         'name': site['name'], 'boarding_authorised': False},
                         'geometry': {'type': 'Point', 'coordinates': loc}})
    shape = {'type': 'FeatureCollection',
             'properties': {'contract': result['contract'], 'network_selected': False},
             'features': features}
    return result, shape


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--graph_dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--geojson', type=Path, default=SHAPE)
    args = parser.parse_args()
    result, shape = build(args.graph_dir)
    for path, data in ((args.output, result), (args.geojson, shape)):
        path.write_text(json.dumps(data, sort_keys=True, ensure_ascii=False,
                                   separators=(',', ':')) + '\n', encoding='utf-8')
