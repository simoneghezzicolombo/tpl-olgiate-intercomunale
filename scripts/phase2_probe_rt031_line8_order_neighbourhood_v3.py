"""Declared local order/arrival neighbourhood; no stop loss or route selection."""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path

from scripts.phase2_probe_rt031_line8_calco_through_path_v3 import (
    OUTPUT as CALCO, through_path, refresh_events, local_access)
from scripts.phase2_probe_rt031_line8_manoeuvre_cycles_v3 import split_only_edges
from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import BASE, FS, inputs
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
from scripts.phase2_rebuild_rt031_uniform_complete_line_v3 import inputs as service_inputs
from scripts.phase2_probe_rt031_line8_free_orders_v3 import reversal_indices
from scripts.phase2_probe_rt031_line8_variable_fs_hold_v3 import solve
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter

OUTPUT = BASE/'order_neighbourhood.json.gz'
LOCAL = {'west_B': 'RT031::P2V2S_0031_PROJECTED_ROAD_POINT',
         'east_A': 'PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE'}


def reconstruct(old, ordered, edges, adapter, fs, calco_node, protect_local, wing):
    checkpoints = []
    for event in ordered:
        node = edges[event['incoming_edge']]['v_node_id']
        if event['stop_place_id'] == 'FROZEN::300634':
            node = calco_node
        required = event['incoming_edge'] if protect_local and event['stop_place_id'] == LOCAL[wing] else None
        checkpoints.append((node, required))
    answer = through_path(edges, adapter, old['edge_ids'][0], old['edge_ids'][-1], checkpoints, {fs})
    if not answer['reachable']:
        return None
    path = [old['edge_ids'][0], *answer['edge_ids'], old['edge_ids'][-1]]
    progress, events = 0, []
    for index, eid in enumerate(path, 1):
        while progress < len(checkpoints):
            node, required = checkpoints[progress]
            if edges[eid]['v_node_id'] != node or (required is not None and eid != required):
                break
            event = copy.deepcopy(ordered[progress])
            event.update(path_node_index=index, parent_occurrence_id=event['occurrence_id'],
                         service_node_hypothesis=node, physical_boarding_authorised=False)
            events.append(event); progress += 1
    if progress != len(checkpoints) or reversal_indices(path, edges):
        raise ValueError('ordered event reconstruction failed')
    result = {**old, 'edge_ids': path, 'events': events}
    refresh_events(result, edges, wing)
    local = [e for e in events if e['stop_place_id'] == LOCAL[wing]]
    if len(local) != 2 or local[0]['path_node_index'] >= local[1]['path_node_index']:
        raise ValueError('two distinct ordered local service events required')
    return result


def access_vector(loops):
    from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops
    adjusted = adjusted_loops(loops, 1.1, .5)
    result = {}
    for wing, loop in adjusted.items():
        for sid in sorted({e['stop_place_id'] for e in loop['events']}):
            events = [e for e in loop['events'] if e['stop_place_id'] == sid]
            result[sid] = {'from_fs_min': min(e['offset_from_wing_origin_min']-.5 for e in events),
                           'to_fs_min': min(loop['road_minutes']-e['offset_from_wing_origin_min'] for e in events)}
    return result


def build(graph_dir):
    paths = inputs(graph_dir)
    raw, _, rules, attachments = build_graph(paths)
    edges = split_only_edges(raw)
    adapter = FrozenRT017ViaNodeAdapter(edges.values(), rules, unresolved_external_via_way_count=2)
    _, policy, _, _, original = service_inputs()
    parent = json.loads(gzip.decompress(CALCO.read_bytes()))
    calco = next(c for c in parent['cases'] if c['reachable'])
    reference = calco['whole_wing_fixed_order_without_reversals']['loops']
    baseline_access = access_vector(reference)
    fs = attachments[FS]['graph_node_id']
    cases = []
    # Each wing independently: unchanged order under protected/free arrival,
    # then every single adjacent swap of nonlocal service events under free arrival.
    pools = {}
    for wing, old in original.items():
        ordered = sorted(old['events'], key=lambda e: (e['path_node_index'], e['stop_place_id']))
        variants = [('protected_original_order', ordered, True), ('free_original_order', ordered, False)]
        for i in range(len(ordered)-1):
            if any(e['stop_place_id'] == LOCAL[wing] for e in ordered[i:i+2]):
                continue
            swapped = ordered.copy()
            swapped[i:i+2] = reversed(swapped[i:i+2])
            variants.append((f'free_adjacent_swap_{i}', swapped, False))
        pools[wing] = []
        for name, events, protect in variants:
            loop = reconstruct(old, events, edges, adapter, fs, calco['candidate_service_node'], protect, wing)
            case = {'wing': wing, 'variant': name, 'reachable': loop is not None,
                    'original_local_incoming_edges_required': protect,
                    'service_event_order_changed': 'swap' in name,
                    'physical_platform_approval': False, 'full_history_legality_certified': False}
            if loop:
                case.update(loop=loop, distance_m=loop['distance_m'])
                pools[wing].append(case)
            cases.append(case)
            print(wing, name, case['reachable'], case.get('distance_m'), flush=True)
    # Product is an explicit diagnostic domain. Keep all nondominated points
    # across distance AND every site's two nominal engineering access metrics.
    networks = []
    for west in pools['west_B']:
        for east in pools['east_A']:
            loops = {'west_B': west['loop'], 'east_A': east['loop']}
            access = access_vector(loops)
            distance = sum(l['distance_m'] for l in loops.values())
            local = local_access(loops)
            metric_vector = [distance]+[access[sid][direction] for sid in sorted(access)
                for direction in ('from_fs_min', 'to_fs_min')]
            networks.append({'variants': [west['variant'], east['variant']], 'distance_m': distance,
                'annual_service_km_16_trips_260_days': distance*16*260/1000,
                'access_nominal_by_site': access, 'local_fast_passages_nominal': local,
                'metric_vector': metric_vector,
                'all_sites_no_worse_than_reference_nominal': all(
                    access[sid][d] <= baseline_access[sid][d]+1e-8
                    for sid in access for d in ('from_fs_min', 'to_fs_min')),
                'loops': loops})
    # Deduplicate identical reconstructed paths before Pareto evaluation.
    unique = {}
    for n in networks:
        key = tuple(tuple(n['loops'][wing]['edge_ids']) for wing in ('west_B', 'east_A'))
        unique.setdefault(key, n)
    networks = list(unique.values())
    frontier = [n for n in networks if not any(
        all(a <= b+1e-8 for a,b in zip(other['metric_vector'], n['metric_vector'])) and
        any(a < b-1e-8 for a,b in zip(other['metric_vector'], n['metric_vector']))
        for other in networks)]
    # The shortest supported witness is a distance diagnostic, not utility selection.
    shortest = min(networks, key=lambda n: n['distance_m'])
    shortest['timetable_comparison_not_adopted'] = solve(policy, shortest['loops'], 'west_B', False,
        70, 60, max_mid=60, anchor_policy='flexible_real_trains')
    return {'contract': 'RT031_LINE8_ADJACENT_ORDER_ARRIVAL_NEIGHBOURHOOD_DIAGNOSTIC_V3',
        'parent_source_sha256': hashlib.sha256(CALCO.read_bytes()).hexdigest(),
        'wing_cases': cases, 'distinct_network_count': len(networks),
        'frontier': [{k:v for k,v in n.items() if k!='loops'} for n in frontier],
        'shortest_distance_diagnostic_not_selection': shortest,
        'reference_access_nominal_by_site': baseline_access,
        'semantics': 'Same 29 design identities including FS and explicit ordered passenger events; '
            'same Calco 19m hypothesis. Same FS boundary edges, no immediate reversals inside wings '
            'or internal FS visits. Per wing: inherited order with original/free local arrival edges, '
            'and every single adjacent swap of nonlocal events with free arrival. Cartesian product '
            'of these finite pools only, not all orders or all streets. Local sites retain two distinct '
            'ordered events; actual arrival/departure edges and both local travel times are exposed. '
            'Pareto dimensions: road distance and every site two nominal engineering access times; '
            'no demand weights, OD downscale, inferred platforms or empirical reliability.',
        'physical_boarding_authorised': False, 'coverage_preservation_certified': False,
        'network_selected': False, 'primary_selection_authorised': False,
        'runner_up_selection_authorised': False, 'decision_budget_km': None,
        'uncertainty_band_min': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--graph_dir', type=Path, required=True)
    args = parser.parse_args()
    result = build(args.graph_dir)
    OUTPUT.write_bytes(gzip.compress((json.dumps(result, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'))+'\n').encode('utf-8'), mtime=0))
