"""Audit the confirmed path against its pinned road graph; prepare fieldwork.

Geometric adjacency and OSM tags are diagnostic evidence, never bus approval.
"""
import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import inputs
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph

BASE = ROOT / 'outputs/phase2/rt031_line8_local_shortcuts_v3'
DESIGN = BASE / 'calco_centre_adopted_design.json'
HANDOFF = BASE / 'caller_confirmed_design_handoff_20261001.json'
OUTPUT = BASE / 'caller_confirmed_route_fieldwork_20261001.json'


def audit_path(loops, edges, fs_node, nodes):
    """Exact graph adjacency and immediate edge-reversal check, including FS."""
    wing_results = {}
    combined = []
    for wing in ('east_A', 'west_B'):
        path = loops[wing]['edge_ids']
        if not path or any(eid not in edges for eid in path):
            raise ValueError('Confirmed path refers to an absent graph edge')
        if edges[path[0]]['u_node_id'] != fs_node or edges[path[-1]]['v_node_id'] != fs_node:
            raise ValueError('Confirmed wing does not begin and end at the FS node')
        for a, b in zip(path, path[1:]):
            if edges[a]['v_node_id'] != edges[b]['u_node_id']:
                raise ValueError(f'Disconnected directed path: {wing} {a} {b}')
        wing_results[wing] = dict(directed_edge_count=len(path), starts_and_ends_at_fs=True)
        combined.extend(path)
    pairs = [(combined[i-1], combined[i], i) for i in range(1, len(combined))]
    pairs.append((combined[-1], combined[0], len(combined)))  # next identical complete trip
    for a, b, _ in pairs:
        if edges[a]['v_node_id'] != edges[b]['u_node_id']:
            raise ValueError('FS interchange/next-trip graph boundary disconnected')
    reversals = [dict(previous_edge=a, next_edge=b, full_trip_boundary_after_edge=i)
                 for a, b, i in pairs
                 if edges[a]['u_node_id'] == edges[b]['v_node_id']
                 and edges[a]['v_node_id'] == edges[b]['u_node_id']]
    service_runs = []
    for wing in ('east_A', 'west_B'):
        path = loops[wing]['edge_ids']
        start = None
        for i in range(len(path)+1):
            service = i < len(path) and edges[path[i]]['highway'] == 'service'
            if service and start is None:
                start = i
            if not service and start is not None:
                run = path[start:i]
                first = nodes[edges[run[0]]['u_node_id']]
                last = nodes[edges[run[-1]]['v_node_id']]
                service_runs.append(dict(
                    wing=wing, first_edge_index_zero_based=start,
                    last_edge_index_zero_based=i-1,
                    edge_ids=run,
                    osm_way_ids=sorted({edges[e]['osm_way_id'] for e in run}),
                    length_m=sum(float(edges[e]['length_m']) for e in run),
                    start_lon_lat=[float(first['lon']), float(first['lat'])],
                    end_lon_lat=[float(last['lon']), float(last['lat'])],
                    service_events_within_run=[dict(site_id=e['stop_place_id'], name=e['name'],
                                                    occurrence_id=e['occurrence_id'],
                                                    path_node_index=e['path_node_index'])
                                               for e in loops[wing]['events']
                                               if start < e['path_node_index'] <= i],
                    bus_suitability_certified=False,
                ))
                start = None
    flags = Counter(flag for eid in combined
                    for flag in str(edges[eid]['uncertainty_flags']).split('|') if flag)
    node_sequence = [edges[combined[0]]['u_node_id']]+[edges[e]['v_node_id'] for e in combined]
    if node_sequence[0] != node_sequence[-1] or node_sequence[len(loops['east_A']['edge_ids'])] != fs_node:
        raise ValueError('Complete path does not return through and finish at FS')
    return dict(wing_graph=wing_results, full_trip_directed_edge_count=len(combined),
                full_trip_node_sequence_including_fs=node_sequence,
                checked_transition_count=len(pairs),
                immediate_edge_reversals=reversals,
                service_road_segments=service_runs,
                graph_highway_class_edge_counts=dict(sorted(Counter(edges[e]['highway'] for e in combined).items())),
                graph_access_basis_edge_counts=dict(sorted(Counter(edges[e]['access_basis'] for e in combined).items())),
                missing_osm_attribute_edge_counts=dict(sorted(flags.items())),
                represented_via_node_path_verified=all(loops[w]['represented_via_node_path_verified']
                                                      for w in ('east_A', 'west_B')),
                full_history_restrictions_certified=False,
                physical_bus_manoeuvres_certified=False,
                semantic_limit='No immediate reversal on this exact route does not establish turning radius, width, kerb clearance, full-history restriction legality, access permission, stop safety or an executable timetable.')


def build(graph_dir):
    design = json.loads(DESIGN.read_text(encoding='utf-8'))
    handoff = json.loads(HANDOFF.read_text(encoding='utf-8'))
    if not handoff['caller_confirmed_design_timetable_basis'] or not handoff['all_trips_same_complete_path']:
        raise ValueError('A single caller-confirmed complete path is required')
    if handoff['complete_path_distance_m'] != design['complete_path_distance_m']:
        raise ValueError('Confirmed distance differs from route input')
    if hashlib.sha256(DESIGN.read_bytes()).hexdigest() != handoff['source_sha256'][DESIGN.name]:
        raise ValueError('Handoff design source differs from pinned content')
    graph_paths = inputs(graph_dir)
    for key in ('edges', 'nodes', 'rules', 'attachments'):
        actual = hashlib.sha256(graph_paths[key].read_bytes()).hexdigest()
        if actual != design['road_graph_inputs_sha256'][key]:
            raise ValueError(f'Frozen road graph source drift: {key}')
    raw_edges, nodes, _, attachments = build_graph(graph_paths)
    edges = {eid: edge for eid, edge in raw_edges.items()
             if not (eid+'::IN' in raw_edges and eid+'::OUT' in raw_edges)}
    fs_node = attachments['FROZEN::L00407']['graph_node_id']
    audit = audit_path(design['loops'], edges, fs_node, nodes)
    if audit['full_trip_directed_edge_count'] != 1435 or audit['immediate_edge_reversals']:
        raise ValueError('Current route does not match the expected no-reversal fieldwork basis')
    register = handoff['design_stop_register']
    if len(register) != 27 or sum(len(s['ordered_occurrences']) for s in register) != 28:
        raise ValueError('Stop register differs from confirmed 27 sites / 28 events')
    fields = [dict(
        site_id=s['site_id'], name=s['name'], coordinates_lon_lat=s['coordinates_lon_lat'],
        proposed_new_site=s['proposed_new_site'],
        service_occurrences=[dict(occurrence_id=o['occurrence_id'], wing=o['wing'],
                                  full_path_edge_index=o['full_path_edge_index'],
                                  incoming_edge=o['incoming_edge'], outgoing_edge=o['outgoing_edge'])
                             for o in s['ordered_occurrences']],
        fs_roles=s['hub_service_roles'],
        observed_boarding_side=None, bus_kerb_access_confirmed=None,
        accessible_waiting_and_crossing_confirmed=None,
        directional_boarding_alighting_permission_confirmed=None,
        physical_platform_count_confirmed=None,
        operator_fieldwork_outcome='PENDING',
    ) for s in register]
    return dict(contract='RT031_CALLER_CONFIRMED_ROUTE_FIELDWORK_V3',
                status='ROAD_GRAPH_AUDITED_FIELDWORK_PENDING',
                source_sha256={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in (DESIGN,HANDOFF)},
                frozen_road_graph_sha256=design['road_graph_inputs_sha256'],
                current_route_audit=audit,
                historical_six_immediate_reversals_still_present=False,
                old_manoeuvre_ids_applicable_to_current_path=False,
                stop_fieldwork_register=fields,
                highest_priority_field_checks=[
                    'Service-road segment around Scarpone: bus width, access and swept path',
                    'Four proposed stop sites: physical kerb, side, crossing and accessibility',
                    'FS intermediate stay-onboard operation and vehicle movement',
                    'Remaining directed junctions, turning radii and full-history restrictions',
                ],
                physical_bus_operation_authorised=False,
                all_stops_authorised=False,
                full_history_legality_certified=False,
                network_selected=False,
                primary_selection_authorised=False,
                runner_up_selection_authorised=False,
                decision_budget_km=None,
                uncertainty_band_min=None)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--graph_dir', type=Path, required=True)
    args = parser.parse_args()
    result = build(args.graph_dir)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)+'\n',
                      encoding='utf-8')
    audit = result['current_route_audit']
    print(json.dumps(dict(immediate_reversals=len(audit['immediate_edge_reversals']),
                          service_segments=len(audit['service_road_segments']),
                          stop_sites=len(result['stop_fieldwork_register'])), ensure_ascii=False))
