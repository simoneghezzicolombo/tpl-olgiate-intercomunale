"""One hypothetical stop on an inherited bypass; no service or site approval."""
import argparse
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path

import numpy as np

from scripts.phase2_probe_rt031_line8_retention_tradeoffs_v3 import load_access, MUNICIPALITY_NAMES
from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import inputs, BASE, FLAGS, site_rides
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
from scripts.phase2_audit_rt031_south_road_probe_v3 import FS, VIRTUAL, digest
from scripts.phase2_export_rt031_line8_inclusive_shape_v3 import NORTH
from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops
from scripts.phase2_audit_rt031_unique_line_walk_access_v3 import pedestrian_time
from scripts.phase2_audit_rt031_conditional_new_stop_access_v3 import weighted_ratio

RETENTION = BASE / 'retention_tradeoffs.json'
OUTPUT = BASE / 'stop_relocation_screen.json'
LIMITS = (5, 8, 10)


def validate_paths(variants, edges, adapter, fs_node):
    """Recheck inherited edge/event witnesses, not full-history bus legality."""
    for group in variants.values():
        for variant in group:
            for pattern, loop in variant['loops'].items():
                path = loop['edge_ids']
                if not path or any(e not in edges for e in path):
                    raise ValueError('missing road edge')
                vertex = [edges[path[0]]['u_node_id']] + [edges[e]['v_node_id'] for e in path]
                if vertex[0] != fs_node or vertex[-1] != fs_node or fs_node in vertex[1:-1]:
                    raise ValueError('unexpected FS boundary or internal return')
                for a, b in zip(path, path[1:]):
                    if edges[a]['v_node_id'] != edges[b]['u_node_id'] or adapter.decision((a,), b)['allowed'] is not True:
                        raise ValueError('disconnected or forbidden represented turn')
                if abs(sum(float(edges[e]['length_m']) for e in path) - loop['distance_m']) > 1e-4:
                    raise ValueError('road distance mismatch')
                elapsed, offsets = 0., [0.]
                for eid in path:
                    elapsed += float(edges[eid]['running_minutes_model']); offsets.append(elapsed)
                if abs(elapsed - loop['road_minutes']) > 1e-5:
                    raise ValueError('road running-time mismatch')
                for event in loop['events']:
                    index = event['path_node_index']
                    if not 0 < index < len(vertex) - 1 or event['incoming_edge'] != path[index - 1]:
                        raise ValueError('event not bound to its actual road occurrence')
                    if abs(event['offset_from_wing_origin_min'] - offsets[index]) > 1e-5:
                        raise ValueError('event runtime offset mismatch')


def bypass_nodes(variants, edges):
    def nodes(loop):
        return {edges[e]['v_node_id'] for e in loop['edge_ids']}
    baseline = set.union(*(nodes(loop) for loop in variants[0]['loops'].values()))
    return {v['variant_id']: sorted(set.intersection(*(nodes(loop) for loop in v['loops'].values())) - baseline
            - {edges[e['incoming_edge']]['v_node_id'] for loop in v['loops'].values() for e in loop['events']})
            for v in variants[1:]}


def add_stop(loops, node, edges):
    """Preserve the actual path and every existing event; add real node visits."""
    result = {pattern: copy.deepcopy(loop) for pattern, loop in loops.items()}
    if node is None:
        return result
    sid = 'PROXY::RELOCATION_NODE_' + node
    for pattern, loop in result.items():
        elapsed = 0.
        found = []
        for index, eid in enumerate(loop['edge_ids'], 1):
            edge = edges[eid]
            elapsed += float(edge['running_minutes_model'])
            if edge['v_node_id'] == node:
                found.append({'stop_place_id': sid, 'name': 'Ipotesi fermata nodo ' + node,
                    'site_status': 'NEW_BYPASS_SITE_FIELD_CHECK_PENDING',
                    'path_node_index': index, 'occurrence_id': f'{pattern}:{index}:{sid}',
                    'incoming_edge': eid,
                    'outgoing_edge': loop['edge_ids'][index] if index < len(loop['edge_ids']) else None,
                    'offset_from_wing_origin_min': elapsed,
                    'boarding_authorised': False, 'passenger_continuity_certified': False})
        if not found:
            raise ValueError('new site absent from one directional path')
        loop['events'] = sorted(loop['events'] + found, key=lambda e: (e['path_node_index'], e['stop_place_id']))
    return result


def ratios(times, context):
    return {code: {str(t): str(weighted_ratio(times <= t, context['weights'],
                    context['core'] if code == 'TOTAL' else context['core'] & (context['codes'] == code)))
                  for t in LIMITS} for code in ('TOTAL', *MUNICIPALITY_NAMES)}


def lost_ratios(before, after, context):
    return {code: {str(t): str(weighted_ratio((before <= t) & (after > t), context['weights'],
                    context['core'] if code == 'TOTAL' else context['core'] & (context['codes'] == code)))
                  for t in LIMITS} for code in ('TOTAL', *MUNICIPALITY_NAMES)}


def inventory_times(ids, context):
    substrate = context['substrate']
    ids = sorted(set(ids) - {VIRTUAL, NORTH})
    if not ids or any(sid not in substrate.stop_index for sid in ids):
        raise ValueError('inventory IDs outside pinned pedestrian matrix')
    return np.minimum(context['local'], substrate.walk_time_matrix[:, [substrate.stop_index[s] for s in ids]].min(axis=1))


def ride_changes(loops, original):
    now, old = adjusted_loops(loops, 1.1, .5), adjusted_loops(original, 1.1, .5)
    changes = []
    for pattern, loop in now.items():
        common = {e['stop_place_id'] for e in loop['events']} & {e['stop_place_id'] for e in old[pattern]['events']}
        for sid in sorted(common):
            before, after = site_rides(old[pattern], sid, .5), site_rides(loop, sid, .5)
            changes.append({'pattern': pattern, 'site_id': sid,
                            'from_fs_delta_min': after['from_fs_min'] - before['from_fs_min'],
                            'to_fs_delta_min': after['to_fs_min'] - before['to_fs_min']})
    return changes


def shortlist(cases):
    """Diagnostic sets, not selection: retain all cases; no municipal loss cutoff."""
    saving = [c for c in cases if c['direction_pair_m_saved'] > 1e-6]
    access = [c for c in saving if c['all_15_municipal_access_metrics_nonworse']]
    units = [c for c in saving if c['no_previously_covered_units_lost']]
    def minima(rows):
        if not rows:
            return []
        best = max(c['direction_pair_m_saved'] for c in rows)
        return [c['case_id'] for c in rows if abs(c['direction_pair_m_saved'] - best) < 1e-6]
    return {'saving_case_count': len(saving), 'nonworse_15_metrics_case_count': len(access),
            'no_covered_units_lost_case_count': len(units),
            'maximum_distance_saving_all_15_metrics_nonworse_ids': minima(access),
            'maximum_distance_saving_no_units_lost_ids': minima(units)}


def build(paths):
    raw = RETENTION.read_bytes().replace(b'\r\n', b'\n')
    source = json.loads(raw)
    if source['contract'] != 'RT031_LINE8_SMALL_RETENTION_RELAXATIONS_V3' or any(source[k] for k in ('network_selected', 'primary_selection_authorised', 'runner_up_selection_authorised')):
        raise ValueError('unsupported retention evidence')
    for key, path in paths.items():
        normalized = key not in ('edges', 'nodes', 'rules', 'attachments', 'successor', 'matrix', 'pedestrian_osm')
        if source['source_sha256'][key] != digest(path, normalized):
            raise ValueError('retention upstream drift: ' + key)
    edges, nodes, rules, attachments = build_graph(paths)
    from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter
    adapter = FrozenRT017ViaNodeAdapter(edges.values(), rules, unresolved_external_via_way_count=2)
    validate_paths(source['variants'], edges, adapter, attachments[FS]['graph_node_id'])
    wings = json.loads(paths['wings'].read_text(encoding='utf-8'))
    sites = {FS: {'node': attachments[FS]['graph_node_id'], 'name': 'Olgiate FS'}}
    for loop in wings['loops'].values():
        for e in loop['events']:
            sites[e['stop_place_id']] = {'node': edges[e['incoming_edge']]['v_node_id'], 'name': e['name']}
    access, baseline_ratios, _, context = load_access(paths, sites, include_context=True)
    baseline_times = inventory_times(sites, context)
    if ratios(baseline_times, context) != baseline_ratios:
        raise ValueError('baseline access not reproduced')
    original = set(sites)
    domains = {wing: bypass_nodes(values, edges) for wing, values in source['variants'].items()}
    candidate_nodes = sorted(set(n for values in domains.values() for ns in values.values() for n in ns))
    walk, node_details = {}, {}
    for index, node in enumerate(candidate_nodes):
        lat, lon = float(nodes[node]['lat']), float(nodes[node]['lon'])
        times, snap = pedestrian_time(context['graph'], context['snap_map'], context['units'], lat, lon)
        walk[node] = times
        node_details[node] = {'lat': lat, 'lon': lon, 'pedestrian_snap': snap,
                              'boarding_authorised': False, 'physical_suitability_certified': False}
        if (index + 1) % 50 == 0:
            print(f'Pedestrian candidates: {index + 1}/{len(candidate_nodes)}', flush=True)
    cases = []
    for wing, variants in source['variants'].items():
        other = source['variants']['west' if wing == 'east' else 'east'][0]
        baseline_pair = variants[0]['loops']
        for variant in variants[1:]:
            seen = set(variant['both_patterns_seen_ids']) | set(other['both_patterns_seen_ids'])
            no_new_times = inventory_times(seen, context)
            for node in [None, *domains[wing][variant['variant_id']]]:
                times = no_new_times if node is None else np.minimum(no_new_times, walk[node])
                coverage = ratios(times, context)
                losses = lost_ratios(baseline_times, times, context)
                loops = add_stop(variant['loops'], node, edges)
                changes = ride_changes(loops, baseline_pair)
                saved = sum(l['distance_m'] for l in baseline_pair.values()) - sum(l['distance_m'] for l in loops.values())
                case = {'case_id': variant['variant_id'] + ('__no_new_stop' if node is None else '__node_' + node),
                        'wing': wing, 'variant_id': variant['variant_id'], 'new_road_node': node,
                        'omitted_required_ids': variant['omitted_required_ids'],
                        'lost_original_site_ids': sorted(original - seen),
                        'gained_inventory_site_ids': sorted(seen - original),
                        'site_count_including_fs': len(seen) + (node is not None),
                        'direction_pair_m_saved': saved,
                        'pattern_distance_m': {p: l['distance_m'] for p, l in loops.items()},
                        'potential_access_fraction': coverage,
                        'potential_access_change_pp': {c: {t: 100 * float(Fraction(coverage[c][t]) - Fraction(baseline_ratios[c][t])) for t in ('5', '8', '10')} for c in baseline_ratios},
                        'previously_covered_population_fraction_lost': losses,
                        'all_15_municipal_access_metrics_nonworse': all(Fraction(coverage[c][str(t)]) >= Fraction(baseline_ratios[c][str(t)]) for c in MUNICIPALITY_NAMES for t in LIMITS),
                        'no_previously_covered_units_lost': all(not np.any(context['core'] & (baseline_times <= t) & (times > t)) for t in LIMITS),
                        'retained_site_ride_changes_nominal': changes,
                        'maximum_retained_site_from_fs_increase_min': max(r['from_fs_delta_min'] for r in changes),
                        'maximum_retained_site_to_fs_increase_min': max(r['to_fs_delta_min'] for r in changes),
                        'new_site_occurrences': {p: [e for e in l['events'] if e['stop_place_id'].startswith('PROXY::RELOCATION_NODE_')] for p, l in loops.items()},
                        'annual_service_km': None, 'timetable_validated': False,
                        'boarding_authorised': False, 'full_history_legality_certified': False}
                cases.append(case)
        print(f'{wing}: road/access cases complete', flush=True)
    return {'contract': 'RT031_LINE8_BYPASS_STOP_RELOCATION_SCREEN_V3',
            'status': 'CONDITIONAL_ROAD_WALK_AND_RIDE_COMPARISON_NOT_OPERATING_PROPOSAL',
            'source_sha256_normalized_retention': hashlib.sha256(raw).hexdigest(),
            'source_sha256': source['source_sha256'],
            'candidate_nodes': node_details, 'candidate_nodes_by_variant': domains,
            'candidate_node_count': len(candidate_nodes), 'case_count': len(cases),
            'cases': cases, 'diagnostic_summary': shortlist(cases),
            'baseline_potential_access_fraction': baseline_ratios,
            'municipality_names': MUNICIPALITY_NAMES,
            'domain': 'One wing changed at a time; inherited zero/one/two-adjacent required-ID omission shortest-path witnesses. Add at most one hypothetical stop at each node common to both direction paths and absent from both original full-retention direction paths and already-served candidate inventory nodes. All such nodes enumerated, no radius or popularity threshold. Other wing unchanged. Does not search all roads, stop positions or multi-edit combinations.',
            'access_semantics': 'Pinned pedestrian graph and population weights, including assumed connectors for new road-node sites. Potential spatial access only, not passenger demand or authorised boarding. Each municipal 5/8/10-minute metric and gross loss of previously covered population reported. Aggregate nonworsening is distinct from no previously covered unit lost.',
            'ride_semantics': 'Nominal +10% moving time and 0.5-minute dwell per distinct service node. New occurrences added on actual unchanged paths. Retained-site best within-trip rides compared separately in both directions; no per-site mix presented as one trip. Lost sites have no remaining identity-level ride guarantee.',
            'distance_semantics': 'Sum of two directional wing lengths, metres saved per one traversal of each pattern. Not daily or annual km; route-dependent timetable, H30/H60 boundaries, train connections and fleet have not yet been revalidated.',
            'selection_semantics': 'All cases retained. Diagnostic maxima conditional on exact nonworsening tests are not PRIMARY or a weighted ranking. Stop identity retention is not a hard constraint. No acceptable loss, normative travel-time ceiling or budget uplift chosen.',
            'reference_cap_unchanged': 111419, 'total_operating_km': None, **FLAGS}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--graph_dir', type=Path, required=True)
    parser.add_argument('--walk_dir', type=Path, required=True)
    args = parser.parse_args()
    paths = inputs(args.graph_dir)
    paths.update(counterflow=BASE / 'local_counterflow.json',
                 matrix=args.walk_dir / 'output/rt028_population_unit_stop_walk_matrix_v3.csv',
                 pedestrian_osm=args.walk_dir / 'input/rt028_osm_pedestrian_snapshot_v3.osm',
                 candidates_normalized=paths['candidates_normalized_newlines'],
                 road_screen=BASE.parent / 'rt031_unique_line_road_screen_v3/screen.json',
                 access_reference=BASE / 'brivio_existing_sites_walk.json')
    result = build(paths)
    OUTPUT.write_text(json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps({'nodes': result['candidate_node_count'], 'cases': result['case_count'], **result['diagnostic_summary']}), flush=True)
