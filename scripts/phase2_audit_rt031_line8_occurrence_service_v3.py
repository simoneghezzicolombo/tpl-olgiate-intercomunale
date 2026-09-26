"""Conditional occurrence-level service diagnostics; never authorised boarding."""
import argparse
import csv
import json
import math
from pathlib import Path

from scripts.phase2_audit_rt031_south_road_probe_v3 import EXPECTED, FS, VIRTUAL, digest
from scripts.phase2_export_rt031_line8_inclusive_shape_v3 import NORTH
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter


def occurrences(path, edges, sites, fs_node, direction):
    nodes = [edges[path[0]]['u_node_id']]
    times = [0.0]
    for eid in path:
        edge = edges[eid]
        if edge['u_node_id'] != nodes[-1]:
            raise ValueError('discontinuous path')
        nodes.append(edge['v_node_id'])
        times.append(times[-1] + float(edge['running_minutes_model']))
    if nodes[0] != fs_node or nodes[-1] != fs_node:
        raise ValueError('path must start and finish at FS')
    result = []
    for index, node in enumerate(nodes):
        following = next((i for i in range(index + 1, len(nodes)) if nodes[i] == fs_node), None)
        previous = max((i for i in range(index + 1) if nodes[i] == fs_node), default=None)
        for sid, site in sorted(sites.items()):
            if site['node'] != node:
                continue
            result.append({'occurrence_id': f'{direction}:{index}:{sid}',
                'direction': direction, 'path_node_index': index, 'stop_place_id': sid,
                'name': site['name'], 'site_status': site['status'],
                'incoming_edge': path[index-1] if index else None,
                'outgoing_edge': path[index] if index < len(path) else None,
                'offset_road_minutes': round(times[index], 6),
                'next_fs_node_index': following,
                'road_minutes_to_next_fs': round(times[following]-times[index], 6) if following is not None else None,
                'previous_fs_node_index': previous,
                'road_minutes_from_previous_fs': round(times[index]-times[previous], 6) if previous is not None else None,
                'boarding_authorised': False, 'passenger_continuity_certified': False})
    return result


def build(paths):
    witness = json.loads(paths['witness'].read_text(encoding='utf-8'))
    screen = json.loads(paths['road_screen'].read_text(encoding='utf-8'))
    policy = json.loads(paths['policy'].read_text(encoding='utf-8'))
    sensitivity = json.loads(paths['sensitivity'].read_text(encoding='utf-8'))
    if witness['contract'] != 'RT031_LINE8_ALL_REFERENCE_CONTEXTUAL_ROAD_WITNESS_V3' or witness['network_selected']:
        raise ValueError('wrong witness contract')
    if policy['contract'] != 'PHASE2_HUMAN_APPROVED_FINAL_POLICY_V3':
        raise ValueError('wrong policy contract')
    if sensitivity['recovery_status'] != 'ASSUMPTION_SENSITIVITY':
        raise ValueError('recovery not a declared sensitivity')
    for key in (*EXPECTED, 'road_screen', 'policy'):
        if witness['source_sha256'][key] != digest(paths[key], key in ('road_screen', 'policy', 'candidates_normalized_newlines')):
            raise ValueError('source mismatch: ' + key)
    edges, _, rules, attachments = build_graph(paths)
    adapter = FrozenRT017ViaNodeAdapter(edges.values(), rules, unresolved_external_via_way_count=2)
    sites = {sid: {'node': attachments[sid]['graph_node_id'], 'name': attachments[sid]['stop_name'],
                  'status': 'INVENTORY_ATTACHMENT_NOT_BOARDING_CERTIFIED'}
             for sid in witness['both_direction_encountered_stop_ids_not_boarding_guaranteed']}
    sites[VIRTUAL] = {'node': VIRTUAL, 'name': 'Olgiate sud', 'status': 'NEW_SITE_NOT_APPROVED'}
    sites[NORTH] = {'node': screen['north_proxy']['graph_node_id'], 'name': 'San Zeno/Via Cantu', 'status': 'NEW_SITE_NOT_APPROVED'}
    base = witness['directions']
    splits = {}
    for direction, route in base.items():
        path = route['edge_ids']
        returns = [i+1 for i,eid in enumerate(path) if edges[eid]['v_node_id'] == sites[FS]['node']]
        if len(returns) != 2 or returns[-1] != len(path):
            raise ValueError('ambiguous geometric wing split')
        splits[direction] = (path[:returns[0]], path[returns[0]:])
    routes = dict(base)
    for name, path in (
        ('west_forward_east_reverse', splits['forward'][0] + splits['reverse'][0]),
        ('west_reverse_east_forward', splits['reverse'][1] + splits['forward'][1])):
        routes[name] = {'edge_ids': path,
            'distance_m': round(sum(float(edges[e]['length_m']) for e in path), 3),
            'running_minutes_excluding_dwell': round(sum(float(edges[e]['running_minutes_model']) for e in path), 6)}
    events = []
    rejected = []
    for direction, route in list(routes.items()):
        path = route['edge_ids']
        if any(adapter.decision((a,), b)['allowed'] is not True for a, b in zip(path, path[1:])):
            rejected.append(direction)
            del routes[direction]
            continue
        events.extend(occurrences(path, edges, sites, sites[FS]['node'], direction))
    joins = {a + '_then_' + b: adapter.decision((pa['edge_ids'][-1],), pb['edge_ids'][0])['allowed'] is True
             for a, pa in routes.items() for b, pb in routes.items()}
    cap = policy['human_policy_decisions']['annual_bus_km_cap']
    scenarios = []
    for span in (13, 14, 16):
        count = span + 4
        for direction, route in routes.items():
            annual = route['distance_m'] / 1000 * count * 260
            scenarios.append({'span_hours': span, 'pattern': 'REPEAT_' + direction,
                'full_traversals_per_day': count, 'annual_km_before_extras': round(annual, 3),
                'remaining_annual_km_before_extras': round(cap-annual, 3),
                'remaining_daily_extra_km_ceiling': round((cap-annual)/260, 6),
                'conditional_same_occurrence_peak_headway_min': 30,
                'conditional_same_occurrence_offpeak_headway_min': 60,
                'headway_scope': 'Interior of a stationary departure band, same authorised event hypothetically repeated; not timetable boundaries or certified stop service'})
    runtime = []
    for direction, route in routes.items():
        for recovery in sensitivity['recovery_min']:
            runtime.append({'direction': direction, 'recovery_min_assumption': recovery,
                'road_minutes_excluding_dwell': route['running_minutes_excluding_dwell'],
                'total_dwell_and_traffic_allowance_for_60min_cycle_min': round(60-route['running_minutes_excluding_dwell']-recovery, 6),
                'peak_fleet_lower_bound_before_dwell': math.ceil((route['running_minutes_excluding_dwell']+recovery)/30),
                'offpeak_fleet_lower_bound_before_dwell': math.ceil((route['running_minutes_excluding_dwell']+recovery)/60)})
    return {'contract': 'RT031_LINE8_OCCURRENCE_SERVICE_DIAGNOSTIC_V3',
        'source_sha256': {k: digest(v, k not in ('edges','nodes','rules','attachments','successor')) for k,v in paths.items()},
        'status': 'CONDITIONAL_NOT_AN_OPERATING_TIMETABLE', 'events': events,
        'road_patterns': routes, 'rejected_patterns_for_represented_turns': rejected,
        'represented_via_node_cycle_joins_allowed': joins,
        'repeat_direction_scenarios': scenarios,
        'alternating_directions': {'aggregate_peak_dispatch_interval_min': 30,
            'aggregate_offpeak_dispatch_interval_min': 60,
            'same_direction_same_occurrence_peak_headway_min': 60,
            'same_direction_same_occurrence_offpeak_headway_min': 120,
            'combined_opposite_occurrences_headway_certified': False},
        'runtime_sensitivities': runtime,
        'assumptions': ['260 days, four peak hours; no clock windows selected',
            'offsets are road-only, not scheduled times; FS occurrences are geometric',
            'repeat-direction alternative is a comparison, not permission to withdraw the other direction'],
        'missing': ['safe directional platforms and boarding events', 'full-history and bus-suitability approval',
            'passenger continuity and FS dwell', 'dwell/traffic measurements', 'train-event phasing',
            'peak transitions and first/last useful trips', 'vehicle blocks', 'depot location and empty km'],
        'network_selected': False, 'primary_selection_authorised': False,
        'runner_up_selection_authorised': False, 'decision_budget_km': None, 'uncertainty_band_min': None}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for key in (*EXPECTED, 'road_screen', 'policy', 'sensitivity', 'witness', 'output', 'events_csv'):
        p.add_argument('--'+key, required=True, type=Path)
    a = p.parse_args()
    result = build({k:v for k,v in vars(a).items() if k not in ('output','events_csv')})
    a.output.write_text(json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(',',':'))+'\n', encoding='utf-8')
    with a.events_csv.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(result['events'][0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(result['events'])
