"""Ordered Calco through-path comparison, avoiding reversal rather than returning.

Preserve the neighbouring stop arrival/departure edges and the Calco site.
The strict case also preserves Calco's incoming edge. Neither certifies bus use.
"""
import argparse
import copy
import gzip
import heapq
import json
import math
from collections import defaultdict
from pathlib import Path

from scripts.phase2_probe_rt031_line8_manoeuvre_cycles_v3 import split_only_edges, reverse
from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import BASE, FS, inputs
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
from scripts.phase2_rebuild_rt031_uniform_complete_line_v3 import inputs as service_inputs
from scripts.phase2_probe_rt031_line8_free_orders_v3 import reversal_indices
from scripts.phase2_probe_rt031_line8_variable_fs_hold_v3 import solve
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter

OUTPUT = BASE / 'calco_through_path.json.gz'
SHAPE = BASE / 'calco_through_path.geojson'
MAP = BASE / 'calco_through_path.png'


def refresh_events(loop, edges, wing):
    offsets = [0.]
    for eid in loop['edge_ids']:
        offsets.append(offsets[-1]+float(edges[eid]['running_minutes_model']))
    loop['road_minutes'] = offsets[-1]
    loop['distance_m'] = sum(float(edges[e]['length_m']) for e in loop['edge_ids'])
    for event in loop['events']:
        index = event['path_node_index']
        updated_id = f"{wing}:{index}:{event['stop_place_id']}"
        if event['occurrence_id'] != updated_id:
            event.setdefault('parent_occurrence_id', event['occurrence_id'])
            event['occurrence_id'] = updated_id
        event.update(offset_road_minutes=offsets[index],
                     offset_from_wing_origin_min=offsets[index],
                     road_minutes_from_previous_fs=offsets[index],
                     road_minutes_to_next_fs=offsets[-1]-offsets[index],
                     previous_fs_node_index=0, next_fs_node_index=len(loop['edge_ids']),
                     incoming_edge=loop['edge_ids'][index-1],
                     outgoing_edge=loop['edge_ids'][index] if index < len(loop['edge_ids']) else None)


def local_access(loops):
    from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops
    adjusted = adjusted_loops(loops, 1.1, .5)
    result = {}
    for wing, sid in [('west_B', 'RT031::P2V2S_0031_PROJECTED_ROAD_POINT'),
                      ('east_A', 'PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE')]:
        hits = [e for e in adjusted[wing]['events'] if e['stop_place_id'] == sid]
        result[sid] = {'served_occurrence_count': len(hits),
            'outbound_min_nominal': min(e['offset_from_wing_origin_min']-.5 for e in hits),
            'inbound_min_nominal': min(adjusted[wing]['road_minutes']-e['offset_from_wing_origin_min'] for e in hits)}
    return result


def through_path(edges, adapter, incoming, outgoing, via, forbidden_nodes,
                 required_via_incoming=None, objective='distance'):
    """Lexicographic distance/time minimum within represented via-node rules.

    ``minutes`` swaps the two optimisation coordinates, never their physical
    units in the result. Neither objective certifies full-history legality.
    """
    if objective not in ('distance', 'minutes'):
        raise ValueError('Unsupported through-path objective')
    adjacency = defaultdict(list)
    for eid, edge in sorted(edges.items()):
        if any(not math.isfinite(float(edge[k])) or float(edge[k]) < 0
               for k in ('length_m', 'running_minutes_model')):
            raise ValueError('finite nonnegative costs required')
        adjacency[edge['u_node_id']].append(eid)
    target = edges[outgoing]['u_node_id']
    checkpoints = [(via, required_via_incoming)] if isinstance(via, str) else via
    start = (0, incoming)
    best, previous = {start: (0., 0.)}, {}
    queue = [(0., 0., *start)]
    while queue:
        primary, secondary, served, last = heapq.heappop(queue)
        state = (served, last)
        if best[state] != (primary, secondary):
            continue
        if (served == len(checkpoints) and edges[last]['v_node_id'] == target
                and not reverse(edges[last], edges[outgoing])
                and adapter.decision((last,), outgoing)['allowed'] is True):
            path, cursor = [], state
            while cursor != start:
                path.append(cursor[1]); cursor = previous[cursor]
            path.reverse()
            distance, minutes = ((primary, secondary) if objective == 'distance'
                                 else (secondary, primary))
            return {'reachable': True, 'edge_ids': path, 'distance_m': distance,
                    'running_minutes_model': minutes}
        for nxt in adjacency[edges[last]['v_node_id']]:
            e = edges[nxt]
            if (e['v_node_id'] in forbidden_nodes or reverse(edges[last], e)
                    or adapter.decision((last,), nxt)['allowed'] is not True):
                continue
            progress = served
            while progress < len(checkpoints):
                node, required = checkpoints[progress]
                if e['v_node_id'] != node or (required is not None and nxt != required):
                    break
                progress += 1
            new = (progress, nxt)
            distance, minutes = float(e['length_m']), float(e['running_minutes_model'])
            costs = (distance, minutes) if objective == 'distance' else (minutes, distance)
            cost = (primary+costs[0], secondary+costs[1])
            if cost < best.get(new, (math.inf, math.inf)):
                best[new], previous[new] = cost, state
                heapq.heappush(queue, (*cost, *new))
    return {'reachable': False, 'edge_ids': []}


def build(graph_dir):
    paths = inputs(graph_dir)
    raw, nodes, rules, attachments = build_graph(paths)
    edges = split_only_edges(raw)
    adapter = FrozenRT017ViaNodeAdapter(edges.values(), rules, unresolved_external_via_way_count=2)
    _, policy, _, _, loops = service_inputs()
    loop = loops['east_A']
    msource = BASE/'stop_plan_and_additions.json.gz'
    m = next(m for m in json.loads(gzip.decompress(msource.read_bytes()))['manoeuvres']
             if m['id'] == 'M5')
    events = sorted(loop['events'], key=lambda e: e['path_node_index'])
    before = max((e for e in events if e['path_node_index'] < 489), key=lambda e: e['path_node_index'])
    after = min((e for e in events if e['path_node_index'] > m['path_node_index']), key=lambda e: e['path_node_index'])
    lo, hi = before['path_node_index']+1, after['path_node_index']-1
    oldpath = loop['edge_ids']
    incoming, outgoing = oldpath[lo-1], oldpath[hi]
    old_distance = sum(float(edges[e]['length_m']) for e in oldpath[lo:hi])
    old_minutes = sum(float(edges[e]['running_minutes_model']) for e in oldpath[lo:hi])
    cases, features = [], []
    # Entire service-edge component of the current point, including junction
    # endpoints; no hand-picked distance radius or automatic relocation choice.
    service_neighbors = defaultdict(set)
    for e in edges.values():
        if e['highway'] == 'service':
            service_neighbors[e['u_node_id']].add(e['v_node_id'])
            service_neighbors[e['v_node_id']].add(e['u_node_id'])
    component, pending = {m['node_id']}, [m['node_id']]
    while pending:
        node = pending.pop()
        for nxt in sorted(service_neighbors[node]-component):
            component.add(nxt); pending.append(nxt)
    candidates = [(m['node_id'], True), (m['node_id'], False)]+[
        (node, False) for node in sorted(component-{m['node_id']})]
    for candidate_node, strict in candidates:
        relocated = candidate_node != m['node_id']
        answer = through_path(edges, adapter, incoming, outgoing, candidate_node,
                              {attachments[FS]['graph_node_id']},
                              m['incoming_edge'] if strict else None)
        c = {**answer, 'original_calco_incoming_edge_required': strict,
             'candidate_service_node': candidate_node,
             'original_calco_service_point_retained': not relocated,
             'graph_service_point_displacement_m': math.hypot(
                 float(nodes[candidate_node]['x'])-float(nodes[m['node_id']]['x']),
                 float(nodes[candidate_node]['y'])-float(nodes[m['node_id']]['y'])),
             'physical_relocation_adopted': False,
             'pedestrian_coverage_preservation_certified': False,
             'full_history_legality_certified': False, 'bus_suitability_certified': False,
             'geometry_adopted': False, 'new_stop_identity_added': False,
             'physical_platform_side_certified': False}
        if answer['reachable']:
            path = answer['edge_ids']
            revised_path = oldpath[:lo]+path+oldpath[hi:]
            cumulative, visit_index = 0., None
            for i, eid in enumerate(path):
                cumulative += float(edges[eid]['running_minutes_model'])
                if (edges[eid]['v_node_id'] == candidate_node and
                        (not strict or eid == m['incoming_edge'])):
                    visit_index = i+1; visit_minutes = cumulative; break
            if visit_index is None:
                raise ValueError('missing ordered Calco service visit')
            revised = copy.deepcopy(loops)
            target_loop = revised['east_A']
            delta = answer['running_minutes_model']-old_minutes
            target_loop['edge_ids'] = revised_path
            target_loop['distance_m'] += answer['distance_m']-old_distance
            target_loop['road_minutes'] += delta
            prefix_minutes = sum(float(edges[e]['running_minutes_model']) for e in oldpath[:lo])
            for event in target_loop['events']:
                index = event['path_node_index']
                if lo <= index <= hi:
                    if event['stop_place_id'] != 'FROZEN::300634':
                        raise ValueError('unrepresented interior service event')
                    event.update(path_node_index=lo+visit_index,
                                 service_node_hypothesis=candidate_node,
                                 original_graph_service_point_retained=not relocated,
                                 offset_from_wing_origin_min=prefix_minutes+visit_minutes,
                                 incoming_edge=path[visit_index-1],
                                 outgoing_edge=(path[visit_index] if visit_index < len(path) else outgoing))
                elif index > hi:
                    event['path_node_index'] += len(path)-(hi-lo)
                    event['offset_from_wing_origin_min'] += delta
            refresh_events(target_loop, edges, 'east_A')
            c.update(distance_delta_m=answer['distance_m']-old_distance,
                     running_minutes_delta_model=delta,
                     full_trip_distance_m=sum(l['distance_m'] for l in revised.values()),
                     annual_service_km_16_trips_260_days=sum(l['distance_m'] for l in revised.values())*16*260/1000,
                     remaining_immediate_reversal_indices=reversal_indices(revised_path, edges),
                     calco_service_event=next(e for e in target_loop['events'] if e['stop_place_id']=='FROZEN::300634'),
                     ordered_original_site_ids_preserved=[e['stop_place_id'] for e in target_loop['events']]
                         == [e['stop_place_id'] for e in loop['events']],
                     revised_loops=revised)
            coordinates = [[float(nodes[edges[incoming]['v_node_id']]['lon']), float(nodes[edges[incoming]['v_node_id']]['lat'])]]
            coordinates += [[float(nodes[edges[e]['v_node_id']]['lon']), float(nodes[edges[e]['v_node_id']]['lat'])] for e in path]
            features.append({'type': 'Feature', 'properties': {
                'strict_original_calco_incoming': strict, 'distance_delta_m': c['distance_delta_m'],
                'candidate_service_node': candidate_node, 'original_point_retained': not relocated,
                'adopted': False}, 'geometry': {'type': 'LineString', 'coordinates': coordinates}})
        cases.append(c)
        print(candidate_node, 'strict' if strict else 'arrival_free', c['reachable'], c.get('distance_delta_m'), flush=True)
    feasible = [c for c in cases if c['reachable']]
    frontier = [c for c in feasible if not any(
        other['distance_delta_m'] <= c['distance_delta_m'] and
        other['graph_service_point_displacement_m'] <= c['graph_service_point_displacement_m'] and
        (other['distance_delta_m'] < c['distance_delta_m'] or
         other['graph_service_point_displacement_m'] < c['graph_service_point_displacement_m'])
        for other in feasible)]
    for c in frontier:
        c['timetable_comparison'] = solve(policy, c['revised_loops'], 'west_B', False, 70, 60,
            max_mid=60, anchor_policy='flexible_real_trains')
        # Whole-wing fixed public event order, with the same FS boundary edges.
        # Protect BOTH original incoming directions at the two local sites.
        complete = copy.deepcopy(loops)
        found = True
        for wing, old in loops.items():
            ordered = sorted(old['events'], key=lambda e: (e['path_node_index'], e['stop_place_id']))
            checkpoints = []
            for event in ordered:
                node = edges[event['incoming_edge']]['v_node_id']
                if event['stop_place_id'] == 'FROZEN::300634':
                    node = c['candidate_service_node']
                required = event['incoming_edge'] if event['stop_place_id'] in (
                    'RT031::P2V2S_0031_PROJECTED_ROAD_POINT',
                    'PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE') else None
                checkpoints.append((node, required))
            answer = through_path(edges, adapter, old['edge_ids'][0], old['edge_ids'][-1],
                                  checkpoints, {attachments[FS]['graph_node_id']})
            if not answer['reachable']:
                found = False; break
            full = [old['edge_ids'][0], *answer['edge_ids'], old['edge_ids'][-1]]
            elapsed, progress, new_events = 0., 0, []
            for index, eid in enumerate(full, 1):
                elapsed += float(edges[eid]['running_minutes_model'])
                while progress < len(checkpoints):
                    node, required = checkpoints[progress]
                    if edges[eid]['v_node_id'] != node or (required is not None and required != eid):
                        break
                    old_event = ordered[progress]
                    new_events.append({**old_event, 'path_node_index': index,
                        'parent_occurrence_id': old_event['occurrence_id'],
                        'occurrence_id': f"{wing}:{index}:{old_event['stop_place_id']}",
                        'offset_from_wing_origin_min': elapsed,
                        'incoming_edge': eid, 'outgoing_edge': full[index] if index < len(full) else None,
                        'physical_boarding_authorised': False,
                        'service_node_hypothesis': node})
                    progress += 1
            if progress != len(checkpoints) or reversal_indices(full, edges):
                raise ValueError('whole-wing ordered-event reconstruction failed')
            complete[wing] = {**old, 'edge_ids': full, 'events': new_events,
                'distance_m': sum(float(edges[e]['length_m']) for e in full), 'road_minutes': elapsed}
            refresh_events(complete[wing], edges, wing)
        c['whole_wing_fixed_order_without_reversals'] = {'reachable': found,
            'protected_local_incoming_directions': True,
            'physical_bus_operation_authorised': False}
        if found:
            total = sum(l['distance_m'] for l in complete.values())
            c['whole_wing_fixed_order_without_reversals'].update(loops=complete,
                local_fast_passages_nominal=local_access(complete),
                distance_m=total, annual_service_km_16_trips_260_days=total*16*260/1000,
                timetable_comparison=solve(policy, complete, 'west_B', False, 70, 60,
                    max_mid=60, anchor_policy='flexible_real_trains'))
            # Explicit comparisons, never override the caller's adopted 16 trips.
            reduced = []
            for shoulder in (70, 75, 80):
                comparison = solve(policy, complete, 'west_B', False, shoulder, 60,
                    max_mid=60, full_trip_count=15, anchor_policy='flexible_real_trains')
                comparison['comparison_trip_count_not_adopted'] = True
                reduced.append(comparison)
                print('15-trip comparison', shoulder, comparison['solver_status'], flush=True)
            c['whole_wing_fixed_order_without_reversals']['reduced_trip_count_comparisons_not_adopted'] = reduced
            # Publish the complete road shape, not just a connector sketch.
            register = json.loads(gzip.decompress(msource.read_bytes()))
            coords = {n: [float(v['lon']), float(v['lat'])] for n, v in nodes.items()}
            coords.update({m['node_id']: m['coordinates'] for m in register['manoeuvres']})
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(10, 6))
            for wing, colour in [('west_B', '#2586d8'), ('east_A', '#ee8128')]:
                path = complete[wing]['edge_ids']
                xy = [coords[edges[path[0]]['u_node_id']]]+[
                    coords[edges[e]['v_node_id']] for e in path]
                ax.plot(*zip(*xy), color=colour, lw=2,
                        label='Ala ovest' if wing.startswith('west') else 'Ala est')
                features.append({'type': 'Feature', 'properties': {
                    'kind': 'whole_wing_without_reversals', 'wing': wing,
                    'bus_suitability_certified': False, 'adopted': False},
                    'geometry': {'type': 'LineString', 'coordinates': xy}})
                points = [coords[edges[e['incoming_edge']]['v_node_id']] for e in complete[wing]['events']]
                ax.scatter(*zip(*points), s=12, color='#303030', zorder=4)
            for label, sid in [('Olgiate sud', 'RT031::P2V2S_0031_PROJECTED_ROAD_POINT'),
                               ('San Zeno', 'PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE'),
                               ('Calco: ipotesi di accosto', 'FROZEN::300634')]:
                event = next(e for l in complete.values() for e in l['events'] if e['stop_place_id'] == sid)
                xy = coords[edges[event['incoming_edge']]['v_node_id']]
                ax.annotate(label, xy, xytext=(7, 7), textcoords='offset points', fontsize=9)
            fs_xy = coords[attachments[FS]['graph_node_id']]
            ax.scatter(*fs_xy, s=40, color='red', zorder=5)
            ax.annotate('Olgiate FS', fs_xy, xytext=(7, 7), textcoords='offset points')
            for label, fragment in [('Perego', 'Perego'), ('Santa Maria Hoè', 'Santa Maria'),
                                    ('Brivio', 'Brivio -'), ('Arlate', 'Arlate -')]:
                event = next((e for l in complete.values() for e in l['events']
                              if fragment in e['name']), None)
                if event:
                    point = coords[edges[event['incoming_edge']]['v_node_id']]
                    ax.annotate(label, point, xytext=(5, 8), textcoords='offset points', fontsize=8)
            ax.set_title('Linea 8 · 29 siti di progetto · sei inversioni intermedie eliminate\nIpotesi Calco a 19 m; manovre a FS e idoneità autobus da verificare')
            ax.set_aspect(1/math.cos(math.radians(45.73))); ax.legend()
            fig.tight_layout(); fig.savefig(MAP, dpi=150); plt.close(fig)
    import hashlib
    result = {'contract': 'RT031_LINE8_CALCO_THROUGH_PATH_DIAGNOSTIC_V3', 'cases': cases,
              'unweighted_distance_displacement_frontier_nodes': [c['candidate_service_node'] for c in frontier],
              'relocation_domain': 'All nodes of the undirected highway=service edge component '
                  'containing the original stop attachment, including boundary junction nodes. '
                  'A graph-node displacement is not a pedestrian distance or coverage result.',
              'manoeuvre_source_sha256': hashlib.sha256(msource.read_bytes()).hexdigest(),
              'graph_inputs_sha256': {k: hashlib.sha256(paths[k].read_bytes()).hexdigest()
                                      for k in ('edges', 'nodes', 'rules', 'attachments')},
              'baseline_service_loops_sha256': hashlib.sha256(json.dumps(loops,
                  sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest(),
              'whole_wing_search_semantics': 'Fixed original ordered passenger events and FS '
                  'boundary directed edges, Calco node hypothesis as disclosed, incoming edge '
                  'protected for both occurrences at Olgiate south and San Zeno. Extra geometric '
                  'crossings are not new passenger events. Distance minimum only in this domain; '
                  'not an all-order network optimum or physical approval.',
              'semantics': 'Distance-minimum through path from after Arlate Madonnina departure '
                  'to before Calco Via Virgilio arrival, retaining these boundary directed edges '
                  'and an explicit Calco Via Nazionale service event. No immediate reversals or '
                  'internal FS visits. Strict case also keeps original Calco incoming edge; '
                  'outgoing edge may change. Extra crossings are not additional public stops. '
                  'Incoming-edge state is sufficient only for frozen represented via-node rules. '
                  'No global legality, bus/platform approval, OD downscale or normative selection.',
              'network_selected': False, 'primary_selection_authorised': False,
              'fs_terminal_manoeuvre_certified': False,
              'runner_up_selection_authorised': False, 'decision_budget_km': None,
              'uncertainty_band_min': None}
    return result, {'type': 'FeatureCollection', 'features': features}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--graph_dir', required=True, type=Path)
    parser.add_argument('--output', default=OUTPUT, type=Path)
    parser.add_argument('--geojson', default=SHAPE, type=Path)
    args = parser.parse_args()
    result, shape = build(args.graph_dir)
    payload = (json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(',', ':'))+'\n').encode('utf-8')
    args.output.write_bytes(gzip.compress(payload, mtime=0))
    args.geojson.write_text(json.dumps(shape, ensure_ascii=False, sort_keys=True)+'\n', encoding='utf-8')
