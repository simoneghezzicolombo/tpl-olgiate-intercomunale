"""Local return cycles without geometric immediate reversals; not bus approval.

Original boarding events stay on their original visits, before inserted cycles.
Extra crossings are not silently promoted to passenger-service occurrences.
Only represented frozen via-node restrictions are evaluated.
"""
import argparse
import gzip
import heapq
import json
import math
import copy
from collections import defaultdict
from pathlib import Path

from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import BASE, FS, inputs
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
from scripts.phase2_rebuild_rt031_uniform_complete_line_v3 import inputs as service_inputs
from scripts.phase2_probe_rt031_line8_free_orders_v3 import reversal_indices
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter
from scripts.phase2_probe_rt031_line8_variable_fs_hold_v3 import (
    OUTPUT as TIMETABLE, original_target_compatibility, wing_offsets, windows)
from scripts.phase2_audit_rt031_line8_passenger_peaks_v3 import uncovered_intervals

OUTPUT = BASE / 'manoeuvre_return_cycles.json'
SHAPE = BASE / 'manoeuvre_return_cycles.geojson'
MAP = BASE / 'manoeuvre_return_cycles.png'


def render(cases, edges, coordinates):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 3, figsize=(12, 8))
    for ax, c in zip(axes.flat, cases):
        points = [coordinates[c['node_id']]]+[
            coordinates[edges[e]['v_node_id']] for e in c['cycle_edge_ids']]
        xs, ys = zip(*points)
        margin_x = max(max(xs)-min(xs), .002)*.2
        margin_y = max(max(ys)-min(ys), .002)*.2
        xlo, xhi = min(xs)-margin_x, max(xs)+margin_x
        ylo, yhi = min(ys)-margin_y, max(ys)+margin_y
        for e in edges.values():
            a, b = coordinates[e['u_node_id']], coordinates[e['v_node_id']]
            if (xlo <= a[0] <= xhi and ylo <= a[1] <= yhi
                    and xlo <= b[0] <= xhi and ylo <= b[1] <= yhi):
                ax.plot([a[0], b[0]], [a[1], b[1]], color='#dddddd', lw=.8)
        if c['reachable']:
            ax.plot(xs, ys, color='#176bb0', lw=2)
        ax.scatter(*coordinates[c['node_id']], color='#cc3322', zorder=5)
        suffix = f"+{c['added_distance_m']:.0f} m" if c['reachable'] else 'ritorno non trovato'
        ax.set_title(f"{c['id']} · {c['street_name_in_snapshot'] or 'Calco via Nazionale'}\n{suffix}", fontsize=10)
        ax.set_xlim(xlo, xhi); ax.set_ylim(ylo, yhi)
        ax.set_aspect(1/math.cos(math.radians(45.73)))
        ax.tick_params(labelsize=7)
    fig.suptitle('Alternative alle inversioni · grafo stradale, idoneità autobus non certificata')
    fig.tight_layout()
    fig.savefig(MAP, dpi=150)
    plt.close(fig)


def split_only_edges(edges):
    """A projected segment replaces its parent; never keep overlapping shortcuts."""
    return {eid: edge for eid, edge in edges.items()
            if not (eid+'::IN' in edges and eid+'::OUT' in edges)}


def reverse(a, b):
    return a['u_node_id'] == b['v_node_id'] and a['v_node_id'] == b['u_node_id']


def shortest_return_cycle(edges, adapter, incoming, outgoing, forbidden_nodes):
    """Distance minimum in the declared edge-state domain, including suffix turn."""
    starts = defaultdict(list)
    for eid, e in sorted(edges.items()):
        if any(not math.isfinite(float(e[k])) or float(e[k]) < 0
               for k in ('length_m', 'running_minutes_model')):
            raise ValueError('finite nonnegative edge costs required')
        starts[e['u_node_id']].append(eid)
    origin = edges[incoming]['v_node_id']
    if origin != edges[outgoing]['u_node_id']:
        raise ValueError('disconnected boundary')
    best = {incoming: (0., 0.)}
    previous = {}
    queue = [(0., 0., incoming)]
    while queue:
        distance, minutes, last = heapq.heappop(queue)
        if best[last] != (distance, minutes):
            continue
        if (last != incoming and edges[last]['v_node_id'] == origin
                and not reverse(edges[last], edges[outgoing])
                and adapter.decision((last,), outgoing)['allowed'] is True):
            path = []
            cursor = last
            while cursor != incoming:
                path.append(cursor)
                cursor = previous[cursor]
            path.reverse()
            if not path or reversal_indices([incoming, *path, outgoing], edges):
                raise ValueError('invalid cycle reconstruction')
            return {'reachable': True, 'cycle_edge_ids': path,
                    'added_distance_m': distance, 'added_running_minutes_model': minutes}
        for nxt in starts[edges[last]['v_node_id']]:
            e = edges[nxt]
            if (e['v_node_id'] in forbidden_nodes or reverse(edges[last], e)
                    or adapter.decision((last,), nxt)['allowed'] is not True):
                continue
            cost = (distance+float(e['length_m']), minutes+float(e['running_minutes_model']))
            if cost < best.get(nxt, (math.inf, math.inf)):
                best[nxt] = cost
                previous[nxt] = last
                heapq.heappush(queue, (*cost, nxt))
    return {'reachable': False, 'cycle_edge_ids': [],
            'status': 'NO_RETURN_CYCLE_IN_DECLARED_GRAPH_DOMAIN'}


def build(graph_dir):
    paths = inputs(graph_dir)
    original_edges, nodes, rules, attachments = build_graph(paths)
    edges = split_only_edges(original_edges)
    adapter = FrozenRT017ViaNodeAdapter(edges.values(), rules,
                                       unresolved_external_via_way_count=2)
    source = BASE / 'stop_plan_and_additions.json.gz'
    register = json.loads(gzip.decompress(source.read_bytes()))
    _, policy, _, _, loops = service_inputs()
    fs_node = attachments[FS]['graph_node_id']
    coordinates = {n: [float(v['lon']), float(v['lat'])] for n, v in nodes.items()}
    coordinates.update({m['node_id']: m['coordinates'] for m in register['manoeuvres']})
    cases, features = [], []
    for m in register['manoeuvres']:
        path = loops[m['pattern']]['edge_ids']
        index = m['path_node_index']
        if path[index-1:index+1] != [m['incoming_edge'], m['outgoing_edge']]:
            raise ValueError('manoeuvre no longer matches confirmed geometry')
        answer = shortest_return_cycle(edges, adapter, m['incoming_edge'],
                                       m['outgoing_edge'], {fs_node})
        case = {**m, **answer, 'full_history_legality_certified': False,
                'cycle_bus_suitability_certified': False,
                'original_ordered_boarding_events_preserved_by_construction': True,
                'extra_cycle_crossings_are_public_stops': False,
                'replacement_adopted': False}
        if answer['reachable']:
            revised = path[:index]+answer['cycle_edge_ids']+path[index:]
            remaining = reversal_indices(revised, edges)
            if len(remaining) != len(reversal_indices(path, edges))-1:
                raise ValueError('replacement must eliminate exactly its own reversal')
            case.update(remaining_immediate_reversal_count_in_wing=len(remaining),
                        annual_added_service_km_16_trips_260_days=
                            answer['added_distance_m']*16*260/1000,
                        shifted_original_events=[
                            {'site_id': e['stop_place_id'], 'occurrence_id': e['occurrence_id'],
                             'additional_running_minutes_model': answer['added_running_minutes_model']}
                            for e in loops[m['pattern']]['events']
                            if e['path_node_index'] > index])
            pts = [coordinates[m['node_id']]]+[
                coordinates[edges[e]['v_node_id']] for e in answer['cycle_edge_ids']]
            features.append({'type': 'Feature', 'properties': {
                'manoeuvre_id': m['id'], 'added_distance_m': answer['added_distance_m'],
                'bus_suitability_certified': False},
                'geometry': {'type': 'LineString', 'coordinates': pts}})
        cases.append(case)
        print(m['id'], answer['reachable'], answer.get('added_distance_m'), flush=True)
    # Cost/time of all available insertions, while M5 remains unresolved.
    revised = copy.deepcopy(loops)
    for wing, loop in revised.items():
        additions = [c for c in cases if c['pattern'] == wing and c['reachable']]
        loop['road_minutes'] += sum(c['added_running_minutes_model'] for c in additions)
        for event in loop['events']:
            event['offset_from_wing_origin_min'] += sum(
                c['added_running_minutes_model'] for c in additions
                if c['path_node_index'] < event['path_node_index'])
    tt = json.loads(gzip.decompress(TIMETABLE.read_bytes()))
    witness = next(c for c in tt['cases'] if c['case_id'] == tt['engineering_validation_priority_case_id'])
    offsets = wing_offsets(revised)
    incompatible_holds = [
        {'first_fs_min': q['first_fs_min'], 'moving_multiplier': moving, 'dwell_min': dwell}
        for (moving, dwell), scenario in offsets.items() for q in witness['full_trips']
        if scenario[witness['first_wing']]['road_minutes']+1 > q['intermediate_offset_min']+1e-8]
    original_compatibility = original_target_compatibility(policy, offsets, {
        witness['first_wing']: [q['first_fs_min'] for q in witness['full_trips']],
        witness['second_wing']: [q['second_fs_min'] for q in witness['full_trips']]})
    readiness_violations = []
    for (moving, dwell), scenario in offsets.items():
        for wing, key in ((witness['first_wing'], 'first_fs_min'),
                          (witness['second_wing'], 'second_fs_min')):
            for sid, site in scenario[wing]['sites'].items():
                for direction in ('to_fs', 'from_fs'):
                    events = [q[key]+site[direction] for q in witness['full_trips']]
                    for lo, hi, cap in windows(witness['ready_start_min'], 70):
                        gaps = uncovered_intervals(events, lo, hi, cap)
                        if gaps:
                            readiness_violations.append({'wing': wing, 'site_id': sid,
                                'direction': direction, 'moving_multiplier': moving,
                                'dwell_min': dwell, 'window': [lo, hi], 'uncovered': gaps})
    rail_violations = []
    for a in witness['rail_assignments']:
        if a['kind'] == 'bus_to_rail':
            waits = [a['rail_min']-a['wing_fs_departure_min']-g[a['wing']]['road_minutes']-3
                     for g in offsets.values()]
            if min(waits) < -1e-8 or max(waits) > policy['wait_ceiling']+1e-8:
                rail_violations.append(a)
    vehicle_counts = []
    for (moving, dwell), scenario in offsets.items():
        for recovery in (5, 10, 15):
            ongoing, maximum = [], 0
            for q in witness['full_trips']:
                while ongoing and ongoing[0] <= q['first_fs_min']+1e-8:
                    heapq.heappop(ongoing)
                heapq.heappush(ongoing, q['second_fs_min']+
                              scenario[witness['second_wing']]['road_minutes']+recovery)
                maximum = max(maximum, len(ongoing))
            vehicle_counts.append({'moving_multiplier': moving, 'dwell_min': dwell,
                                   'recovery_min': recovery, 'vehicle_count_conditional': maximum})
    total_extra_m = sum(c.get('added_distance_m', 0) for c in cases)
    import hashlib
    result = {'contract': 'RT031_LINE8_LOCAL_MANOEUVRE_RETURN_CYCLES_DIAGNOSTIC_V3',
              'manoeuvre_source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'timetable_source_sha256': hashlib.sha256(TIMETABLE.read_bytes()).hexdigest(),
              'source_timetable_case_id': witness['case_id'],
              'cases': cases,
              'available_five_cycles_comparison_not_adopted': {
                  'unresolved_manoeuvre_ids': [c['id'] for c in cases if not c['reachable']],
                  'added_distance_m_per_full_trip': total_extra_m,
                  'annual_service_km_16_trips_260_days':
                      witness['annual_service_km_260_day_comparison']+total_extra_m*16*260/1000,
                  'fixed_timetable_intermediate_hold_violations': incompatible_holds,
                  'fixed_timetable_readiness_violations': readiness_violations,
                  'selected_real_train_binding_violations': rail_violations,
                  'vehicle_cases_conditional': vehicle_counts,
                  'original_rail_target_compatibility_at_unchanged_departures': original_compatibility,
                  'retimed_solution_explored': False,
                  'physically_executable': False},
              'graph_inputs_sha256': {k: hashlib.sha256(paths[k].read_bytes()).hexdigest()
                                      for k in ('edges', 'nodes', 'rules', 'attachments')},
              'semantics': 'Shortest-distance local cycle in frozen directed split-only graph, '
                  'retaining incoming-edge memory for represented via-node rules. No immediate '
                  'edge reversal, no internal FS visit; original passenger events retained on '
                  'original visits before inserted cycles. Extra geometric crossings are not '
                  'new guaranteed boarding events. Road time excludes new acceleration/braking '
                  'or stop dwell. This does not certify path-history restrictions, bus swept '
                  'paths, kerbs, platforms, passenger continuity or a revised timetable.',
              'all_six_replacements_available_in_declared_domain': all(c['reachable'] for c in cases),
              'original_timetable_certified_for_replacements': False,
              'physical_bus_operation_authorised': False,
              'network_selected': False, 'primary_selection_authorised': False,
              'runner_up_selection_authorised': False,
              'decision_budget_km': None, 'uncertainty_band_min': None}
    render(cases, edges, coordinates)
    return result, {'type': 'FeatureCollection', 'features': features}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--graph_dir', type=Path, required=True)
    args = parser.parse_args()
    result, shape = build(args.graph_dir)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)+'\n', encoding='utf-8')
    SHAPE.write_text(json.dumps(shape, ensure_ascii=False, sort_keys=True)+'\n', encoding='utf-8')
