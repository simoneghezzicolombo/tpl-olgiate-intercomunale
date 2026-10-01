"""All-order distance comparison with incoming-edge terminal states.

Exact only for represented via-node turns, frozen local boundary paths and no
intermediate FS visit. Bus suitability and full-history restrictions unknown.
"""
import argparse
from collections import defaultdict
import heapq
import json
from pathlib import Path

import numpy as np

from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import inputs, BASE, FS, VIRTUAL, NORTH, digest
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
from scripts.phase2_audit_rt031_line8_occurrence_service_v3 import occurrences
from scripts.phase2_probe_rt031_line8_stop_relocation_v3 import validate_paths
from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import FLAGS, EXPECTED, load_sources
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import family_inputs
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter

OUTPUT = BASE / 'free_order_road_comparison.json'


class EdgeStateClosure:
    def __init__(self, edges, adapter, forbidden_nodes):
        self.edges = edges
        self.ids = sorted(edges)
        self.index = {eid: i for i, eid in enumerate(self.ids)}
        self.length = np.array([float(edges[e]['length_m']) for e in self.ids])
        self.minutes = np.array([float(edges[e]['running_minutes_model']) for e in self.ids])
        if (not np.all(np.isfinite(self.length)) or not np.all(np.isfinite(self.minutes))
                or np.any(self.length < 0) or np.any(self.minutes < 0)):
            raise ValueError('finite nonnegative road costs required')
        outgoing = defaultdict(list)
        self.incoming = defaultdict(list)
        for i, eid in enumerate(self.ids):
            outgoing[edges[eid]['u_node_id']].append(i)
            self.incoming[edges[eid]['v_node_id']].append(i)
        self.successors = []
        for eid in self.ids:
            self.successors.append([j for j in outgoing[edges[eid]['v_node_id']]
                                    if edges[self.ids[j]]['v_node_id'] not in forbidden_nodes
                                    and adapter.decision((eid,), self.ids[j])['allowed'] is True])
        self.trees = {}

    def tree(self, source):
        if source in self.trees:
            return self.trees[source]
        size = len(self.ids)
        meters, minutes = np.full(size, np.inf), np.full(size, np.inf)
        previous = np.full(size, -1, dtype=np.int32)
        meters[source] = minutes[source] = 0.
        heap = [(0., 0., source)]
        while heap:
            distance, runtime, last = heapq.heappop(heap)
            if (distance, runtime) != (meters[last], minutes[last]):
                continue
            for nxt in self.successors[last]:
                candidate = (distance + self.length[nxt], runtime + self.minutes[nxt])
                if candidate < (meters[nxt], minutes[nxt]):
                    meters[nxt], minutes[nxt] = candidate
                    previous[nxt] = last
                    heapq.heappush(heap, (*candidate, nxt))
        self.trees[source] = (meters, minutes, previous)
        return self.trees[source]

    def path(self, source, target):
        meters, _, previous = self.tree(source)
        if not np.isfinite(meters[target]):
            raise ValueError('unreachable reconstructed terminal state')
        path = []
        cursor = target
        while cursor != source:
            path.append(self.ids[cursor])
            cursor = int(previous[cursor])
            if cursor < 0:
                raise ValueError('broken shortest path predecessor')
        return path[::-1]


def terminal_tour(closure, required_nodes, start_edge, end_node, suffix_edge, adapter):
    nodes = sorted(set(required_nodes))
    if not nodes or end_node in nodes:
        raise ValueError('nonempty nonlocal terminal set required')
    ports = [p for node in nodes for p in closure.incoming[node]]
    group = [nodes.index(closure.edges[closure.ids[p]]['v_node_id']) for p in ports]
    if len(set(group)) != len(nodes):
        raise ValueError('terminal without incoming road state')
    start = closure.index[start_edge]
    ends = [p for p in closure.incoming[end_node]
            if adapter.decision((closure.ids[p],), suffix_edge)['allowed'] is True]
    if not ends:
        raise ValueError('no terminal state compatible with fixed suffix')
    start_m, start_t, _ = closure.tree(start)
    distance = np.array([closure.tree(p)[0][ports] for p in ports])
    runtime = np.array([closure.tree(p)[1][ports] for p in ports])
    size = 1 << len(nodes)
    dp = np.full((size, len(ports)), np.inf)
    dt = np.full_like(dp, np.inf)
    parent = np.full(dp.shape, -1, dtype=np.int16)
    by_group = [[j for j, g in enumerate(group) if g == i] for i in range(len(nodes))]
    for j, port in enumerate(ports):
        dp[1 << group[j], j] = start_m[port]
        dt[1 << group[j], j] = start_t[port]
    for mask in range(1, size):
        remaining = [g for g in range(len(nodes)) if not mask & (1 << g)]
        for last in np.flatnonzero(np.isfinite(dp[mask])):
            for g in remaining:
                nxt_mask = mask | (1 << g)
                for nxt in by_group[g]:
                    cost = (dp[mask, last] + distance[last, nxt], dt[mask, last] + runtime[last, nxt])
                    if cost < (dp[nxt_mask, nxt], dt[nxt_mask, nxt]):
                        dp[nxt_mask, nxt], dt[nxt_mask, nxt] = cost
                        parent[nxt_mask, nxt] = last
    candidates = []
    for j, port in enumerate(ports):
        m, t, _ = closure.tree(port)
        for end in ends:
            candidates.append((dp[-1, j] + m[end], dt[-1, j] + t[end], j, end))
    total_m, total_t, last, end = min(candidates)
    if not np.isfinite(total_m):
        raise ValueError('all-order terminal tour unreachable')
    visits = []
    mask = size - 1
    while mask:
        visits.append(ports[last])
        previous = int(parent[mask, last])
        mask ^= 1 << group[last]
        last = previous
        if mask and last < 0:
            raise ValueError('incomplete subset predecessor')
    visits.reverse()
    path = []
    current = start
    for port in [*visits, end]:
        path.extend(closure.path(current, port))
        current = port
    return {'interior_distance_m': float(total_m), 'interior_road_minutes': float(total_t),
            'logical_terminal_incoming_edges': [closure.ids[p] for p in visits],
            'logical_terminal_node_order': [closure.edges[closure.ids[p]]['v_node_id'] for p in visits],
            'interior_edge_ids': path, 'terminal_node_count': len(nodes), 'terminal_state_count': len(ports),
            'subset_state_count': int(size * len(ports))}


def reversal_indices(path, edges):
    return [i for i in range(1, len(path))
            if edges[path[i-1]]['u_node_id'] == edges[path[i]]['v_node_id']
            and edges[path[i-1]]['v_node_id'] == edges[path[i]]['u_node_id']]


def build(graph_dir):
    sources = load_sources()
    reference = next(f for f in family_inputs(sources) if f['name'] == 'fast_local_both_directions')
    paths = inputs(graph_dir)
    edges, nodes, rules, attachments = build_graph(paths)
    fs = attachments[FS]['graph_node_id']
    sites = {FS: {'node': fs, 'name': 'Olgiate FS', 'status': 'INVENTORY_NOT_APPROVED'}}
    for loop in reference['loops'].values():
        for e in loop['events']:
            sites[e['stop_place_id']] = {'node': edges[e['incoming_edge']]['v_node_id'], 'name': e['name'], 'status': e['site_status']}
    adapter = FrozenRT017ViaNodeAdapter(edges.values(), rules, unresolved_external_via_way_count=2)
    closure = EdgeStateClosure(edges, adapter, {fs})
    loops, audits = {}, []
    for pattern, old in sorted(reference['loops'].items()):
        local = VIRTUAL if pattern.startswith('west') else NORTH
        local_events = [e for e in old['events'] if e['stop_place_id'] == local]
        first = min(e['path_node_index'] for e in local_events)
        last = max(e['path_node_index'] for e in local_events)
        prefix, suffix = old['edge_ids'][:first], old['edge_ids'][last:]
        if not prefix or not suffix or first == last:
            raise ValueError('missing distinct fixed local boundary visits')
        boundary_ids = {e['stop_place_id'] for e in old['events'] if e['path_node_index'] <= first or e['path_node_index'] >= last}
        required = {sites[e['stop_place_id']]['node'] for e in old['events'] if e['stop_place_id'] not in boundary_ids}
        answer = terminal_tour(closure, required, prefix[-1], sites[local]['node'], suffix[0], adapter)
        path = prefix + answer['interior_edge_ids'] + suffix
        name = pattern + '_free_order'
        actual = occurrences(path, edges, sites, fs, name)
        events = [{**e, 'offset_from_wing_origin_min': e['offset_road_minutes']} for e in actual if e['stop_place_id'] != FS]
        if not {e['stop_place_id'] for e in old['events']} <= {e['stop_place_id'] for e in events}:
            raise ValueError('reference site lost after road reconstruction')
        loop = {'edge_ids': path, 'events': events,
                'distance_m': sum(float(edges[e]['length_m']) for e in path),
                'road_minutes': sum(float(edges[e]['running_minutes_model']) for e in path),
                'represented_via_node_path_verified': True, 'full_history_legality_certified': False}
        if abs(loop['distance_m'] - answer['interior_distance_m'] - sum(float(edges[e]['length_m']) for e in prefix + suffix)) > 1e-4:
            raise ValueError('terminal DP and reconstructed distance disagree')
        if loop['distance_m'] > old['distance_m'] + 1e-4:
            raise ValueError('all-order domain lost its own feasible reference')
        loops[name] = loop
        audits.append({'pattern': name, 'reference_pattern': pattern, 'frozen_prefix_edge_ids': prefix,
                       'frozen_suffix_edge_ids': suffix, 'boundary_served_site_ids': sorted(boundary_ids),
                       'required_interior_nodes': sorted(required), 'reference_distance_m': old['distance_m'],
                       'distance_m': loop['distance_m'], 'distance_saved_m': old['distance_m'] - loop['distance_m'],
                       'identical_reference_patterns': sorted(k for k, v in reference['loops'].items()
                                                              if v['edge_ids'] == path),
                       'reference_immediate_reversal_count': len(reversal_indices(old['edge_ids'], edges)),
                       'new_immediate_reversal_indices': reversal_indices(path, edges),
                       'minimum_distance_proven_in_represented_fixed_boundary_domain': True, **answer})
        print(json.dumps({k: audits[-1][k] for k in ('pattern', 'distance_m', 'distance_saved_m', 'terminal_node_count', 'terminal_state_count', 'new_immediate_reversal_indices')}), flush=True)
    validate_paths({'all': [{'loops': loops}]}, edges, adapter, fs)
    combined = {**reference['loops'], **loops}
    joins = {a + '>' + b: adapter.decision((left['edge_ids'][-1],), right['edge_ids'][0])['allowed'] is True
             for a, left in combined.items() for b, right in combined.items()}
    if not all(joins.values()):
        raise ValueError('reordered paths do not preserve represented FS joins')
    result = {'contract': 'RT031_LINE8_FREE_ORDER_ROAD_COMPARISON_V3', 'loops': loops, 'audits': audits,
              'represented_via_node_joins_with_reference': joins,
              'source_sha256_normalized_newlines': EXPECTED,
              'road_source_sha256': {k: digest(paths[k], k.endswith('normalized_newlines')) for k in paths},
              'reference_site_ids': sorted(sites),
              'semantics': 'Exact minimum road distance under represented via-node rules, each fixed FS-to-first-local prefix and last-local-to-FS suffix, and no internal FS return. Every own-wing original site retained, all interior visit orders admitted. Incoming directed edge is preserved in Dijkstra terminal closure and subset DP, not reset at sites. Incidental encounters and repeated visits are reconstructed as actual events. A represented rule not rejecting a U-turn is NOT bus turnaround approval. Full-history restrictions, boarding, operating timetable and route selection remain uncertified. A distance-minimum path is only one diagnostic witness, not the complete time/access frontier.',
              **{k: False for k in FLAGS}, 'actual_timetable_certified': False,
              'decision_budget_km': None, 'uncertainty_band_min': None, 'total_operating_km': None}
    prior_shape = json.loads((BASE / 'local_counterflow.geojson').read_text(encoding='utf-8'))
    coords = {nid: [float(row['lon']), float(row['lat'])] for nid, row in nodes.items()}
    coords[VIRTUAL] = next(f['geometry']['coordinates'] for f in prior_shape['features']
                          if f['geometry']['type'] == 'Point' and f['properties']['site_id'] == VIRTUAL)
    features = []
    for pattern, loop in loops.items():
        vertex = [edges[loop['edge_ids'][0]]['u_node_id']] + [edges[e]['v_node_id'] for e in loop['edge_ids']]
        features.append({'type': 'Feature', 'properties': {'pattern': pattern, 'boarding_authorised': False},
                         'geometry': {'type': 'LineString', 'coordinates': [coords[n] for n in vertex]}})
        for index in reversal_indices(loop['edge_ids'], edges):
            node = edges[loop['edge_ids'][index]]['u_node_id']
            features.append({'type': 'Feature', 'properties': {'pattern': pattern, 'immediate_reversal': True,
                                                               'path_node_index': index, 'graph_node_id': node,
                                                               'site_ids_at_node': sorted(s for s, v in sites.items() if v['node'] == node),
                                                               'incoming_edge': loop['edge_ids'][index - 1],
                                                               'outgoing_edge': loop['edge_ids'][index],
                                                               'bus_manoeuvre_authorised': False},
                             'geometry': {'type': 'Point', 'coordinates': coords[node]}})
    features.extend(f for f in prior_shape['features'] if f['geometry']['type'] == 'Point')
    return result, {'type': 'FeatureCollection', 'properties': {k: False for k in FLAGS}, 'features': features}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--graph_dir', type=Path, required=True)
    args = parser.parse_args()
    result, shape = build(args.graph_dir)
    for path, data in ((OUTPUT, result), (BASE / 'free_order_road_comparison.geojson', shape)):
        path.write_text(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
