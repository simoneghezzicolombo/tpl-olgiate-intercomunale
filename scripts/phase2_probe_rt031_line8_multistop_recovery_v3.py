"""Multiple hypothetical stops on the cheapest previously checked road geometry.

Maximum recoverable baseline units is a spatial diagnostic, not a service
guarantee or policy selection. Minimise added count only for that explicit target.
"""
import argparse
import copy
import heapq
import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csc_matrix

from scripts.phase2_probe_rt031_line8_stop_relocation_v3 import (
    BASE, RETENTION, inputs, build_graph, FS, VIRTUAL, NORTH, digest,
    load_access, inventory_times, ratios, lost_ratios, add_stop, validate_paths)
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import FLAGS, family_inputs, load_sources
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter

OUTPUT = BASE / 'multistop_recovery.json'


def seeded_distances(reverse, seeds):
    """Reverse multi-source Dijkstra includes each stop's connector cost."""
    distance = {}
    for node, cost in seeds:
        if not math.isfinite(cost) or cost < 0:
            raise ValueError('invalid connector distance')
        distance[node] = min(distance.get(node, math.inf), cost)
    queue = [(cost, node) for node, cost in distance.items()]
    heapq.heapify(queue)
    while queue:
        cost, node = heapq.heappop(queue)
        if cost != distance[node]:
            continue
        for nxt, weight in reverse.get(node, []):
            if not math.isfinite(weight) or weight < 0:
                raise ValueError('invalid pedestrian edge')
            proposal = cost + weight
            if proposal < distance.get(nxt, math.inf):
                distance[nxt] = proposal
                heapq.heappush(queue, (proposal, nxt))
    return distance


def minimum_cover(matrix):
    """Exact cardinality witness for covering every declared recoverable row."""
    if not len(matrix):
        return [], True, 0.
    if np.any(~matrix.any(axis=1)):
        raise ValueError('uncoverable target must be reported, not silently removed')
    # Equivalent coverage vectors are interchangeable only in this spatial
    # count problem. Keep original node identities for reconstructing the witness.
    unique, indices = np.unique(matrix.T, axis=0, return_index=True)
    useful = unique.any(axis=1)
    unique, indices = unique[useful], indices[useful]
    answer = milp(np.ones(len(indices)), integrality=np.ones(len(indices)), bounds=Bounds(0, 1),
                  constraints=LinearConstraint(csc_matrix(unique.T.astype(float)), 1, np.inf),
                  options={'time_limit': 60, 'mip_rel_gap': 0})
    if answer.x is None:
        raise ValueError('no spatial cover witness; do not manufacture a stop set')
    if np.max(np.abs(answer.x - np.rint(answer.x))) > 1e-5:
        raise ValueError('fractional stop selection')
    selected = sorted(int(i) for i, value in zip(indices, answer.x) if value > .5)
    if not matrix[:, selected].any(axis=1).all():
        raise ValueError('cover reconstruction failed')
    bound = getattr(answer, 'mip_dual_bound', None)
    return selected, bool(answer.success), None if bound is None else float(bound)


def build(graph_dir, walk_dir):
    retention = json.loads(RETENTION.read_text(encoding='utf-8'))
    diagnostic_path = BASE / 'combined_edits_joint_diagnostics.json'
    diagnostics = json.loads(diagnostic_path.read_text(encoding='utf-8'))
    if any(diagnostics[k] or retention[k] for k in FLAGS):
        raise ValueError('decisional upstream evidence')
    # Deterministic diagnostic: cheapest verified no-new-stop case, not PRIMARY.
    cases = [c for c in diagnostics['cases'] if c['west_choice_id'].endswith('__no_new_stop')
             and c['east_choice_id'].endswith('__no_new_stop')]
    case = min(cases, key=lambda c: (c['annual_service_km'], c['west_choice_id'], c['east_choice_id']))
    variants = {v['variant_id']: v for values in retention['variants'].values() for v in values}
    selected_variants = {wing: variants[case[wing + '_choice_id'].split('__')[0]] for wing in ('west', 'east')}
    loops = copy.deepcopy({p: l for v in selected_variants.values() for p, l in v['loops'].items()})
    paths = inputs(graph_dir)
    paths.update(counterflow=BASE/'local_counterflow.json',
                 matrix=walk_dir/'output/rt028_population_unit_stop_walk_matrix_v3.csv',
                 pedestrian_osm=walk_dir/'input/rt028_osm_pedestrian_snapshot_v3.osm',
                 candidates_normalized=paths['candidates_normalized_newlines'],
                 road_screen=BASE.parent/'rt031_unique_line_road_screen_v3/screen.json',
                 access_reference=BASE/'brivio_existing_sites_walk.json')
    for key, path in paths.items():
        normalized = key not in ('edges','nodes','rules','attachments','successor','matrix','pedestrian_osm')
        if digest(path, normalized) != retention['source_sha256'][key]:
            raise ValueError('source drift: ' + key)
    if diagnostics['source_sha256_normalized_newlines']['retention'] != digest(RETENTION, True):
        raise ValueError('diagnostic road source drift')
    edges, nodes, rules, attachments = build_graph(paths)
    fs = attachments[FS]['graph_node_id']
    adapter = FrozenRT017ViaNodeAdapter(edges.values(), rules, unresolved_external_via_way_count=2)
    validate_paths({'base': [{'loops': loops}]}, edges, adapter, fs)
    reference = family_inputs(load_sources())[1]
    sites = {FS: {'node': fs, 'name': 'Olgiate FS'}}
    for loop in reference['loops'].values():
        for e in loop['events']:
            sites[e['stop_place_id']] = {'node': edges[e['incoming_edge']]['v_node_id'], 'name': e['name']}
    _, baseline, _, context = load_access(paths, sites, include_context=True)
    before = inventory_times(sites, context)
    retained = {e['stop_place_id'] for l in loops.values() for e in l['events']} | {FS}
    without = inventory_times(retained, context)
    existing_nodes = {edges[e['incoming_edge']]['v_node_id'] for l in loops.values() for e in l['events']} | {fs}
    domains = {wing: sorted(set.intersection(*({edges[e]['v_node_id'] for e in l['edge_ids']}
                                            for p, l in loops.items() if p.startswith(wing))) - existing_nodes)
               for wing in ('west', 'east')}
    all_nodes = sorted(set.union(*(set(ns) for ns in domains.values())))
    details, snaps, vectors = {}, {}, []
    for node in all_nodes:
        lat, lon = float(nodes[node]['lat']), float(nodes[node]['lon'])
        snap = context['graph'].snap(lat, lon)
        details[node] = {'lat': lat, 'lon': lon, 'pedestrian_status': snap.status,
                         'pedestrian_node_id': snap.node_id, 'connector_m': snap.connector_distance_m,
                         'boarding_authorised': False, 'physical_suitability_certified': False}
        if snap.status == 'REACHABLE' and snap.node_id:
            snaps[node] = (snap.node_id, float(snap.connector_distance_m))
    units = context['units']
    unit_nodes = [str(context['snap_map'][u]['population_snap_node_id']) for u in units]
    connectors = np.array([float(context['snap_map'][u]['population_connector_distance_m']) for u in units])
    def times(seeds):
        d = seeded_distances(context['graph'].reverse_adjacency, seeds)
        return (connectors + np.array([d.get(n, math.inf) for n in unit_nodes])) / 80
    upper = np.minimum(without, times(snaps.values()))
    # Target is every previously covered population unit / threshold that this
    # finite road-node domain can recover; irrecoverable rows remain explicit.
    targets = [(i, t) for t in (5, 8, 10) for i in np.flatnonzero(context['core'] & (before <= t) & (without > t) & (upper <= t))]
    eligible_nodes = sorted(snaps)
    cache = {}
    for index, node in enumerate(eligible_nodes):
        key = snaps[node]
        if key not in cache:
            cache[key] = times([key])
        vectors.append(cache[key])
        if index % 200 == 0:
            print(json.dumps({'walking_nodes_done': index, 'total': len(eligible_nodes)}), flush=True)
    matrix = np.array([[vector[i] <= t for vector in vectors] for i, t in targets], dtype=bool)
    chosen, exact, bound = minimum_cover(matrix)
    chosen_nodes = [eligible_nodes[i] for i in chosen]
    after = np.minimum(without, np.min([vectors[i] for i in chosen], axis=0)) if chosen else without
    for threshold in (5, 8, 10):
        if not np.array_equal(context['core'] & (before <= threshold) & (after > threshold),
                              context['core'] & (before <= threshold) & (upper > threshold)):
            raise ValueError('selected stops fail to recover all recoverable baseline units')
    for wing in ('west', 'east'):
        pair = {p: l for p, l in loops.items() if p.startswith(wing)}
        for node in chosen_nodes:
            if node in domains[wing]:
                pair = add_stop(pair, node, edges)
        loops.update(pair)
    validate_paths({'new': [{'loops': loops}]}, edges, adapter, fs)
    result = {'contract': 'RT031_LINE8_MULTISTOP_RECOVERY_V3',
              'source_sha256': {**retention['source_sha256'], 'retention': digest(RETENTION, True),
                                'operating_diagnostics': digest(diagnostic_path, True)},
              'diagnostic_reference_case': {k: case[k] for k in ('west_choice_id','east_choice_id','annual_service_km')},
              'candidate_nodes_by_wing': domains, 'candidate_nodes': details,
              'candidate_node_count': len(all_nodes), 'walk_attachable_node_count': len(snaps),
              'baseline_potential_access_fraction': baseline,
              'without_new_stops_potential_access_fraction': ratios(without, context),
              'all_candidate_stops_upper_potential_access_fraction': ratios(upper, context),
              'all_candidate_stops_irrecoverable_loss_fraction': lost_ratios(before, upper, context),
              'no_loss_possible_in_finite_node_domain': all(not np.any(context['core'] & (before <= t) & (upper > t)) for t in (5,8,10)),
              'recoverable_target_count': len(targets),
              'recoverable_population_unit_threshold_targets': [{'population_unit_id': units[i], 'walk_limit_min': t} for i,t in targets],
              'minimum_added_stop_count_proven_for_recoverable_target': exact,
              'added_stop_count_lower_bound': bound, 'added_stop_count': len(chosen_nodes),
              'added_road_nodes': chosen_nodes, 'loops': loops,
              'witness_potential_access_fraction': ratios(after, context),
              'witness_previously_covered_population_fraction_lost': lost_ratios(before, after, context),
              'municipality_names': {k: v for k,v in json.loads((BASE/'stop_relocation_screen.json').read_text())['municipality_names'].items()},
              'semantics': 'Cheapest previously timetable-checked no-new-stop geometry only. Every unserved road vertex common to both directions of either wing is tested, including old-road sections, not only new bypass nodes. Unlimited added stops gives an exact potential-access ceiling for this finite vertex domain with pinned walking graph/connectors. It is not a bound on continuous positions or other roads. Minimum added count covers all recoverable baseline unit/5-8-10-minute requirements, not a weighted population score or a policy-selected compromise. Stops remain hypothetical; additional dwell and rail/frequency/vehicle checks are required before any operating claim. Baseline loss impossibility is spatial only.',
              'annual_service_km': None, 'timetable_validated': False,
              'decision_budget_km': None, 'uncertainty_band_min': None, 'total_operating_km': None,
              **{k: False for k in FLAGS}}
    prior = json.loads((BASE/'local_counterflow.geojson').read_text())
    coordinates = {n: [float(row['lon']),float(row['lat'])] for n,row in nodes.items()}
    coordinates[VIRTUAL] = next(f['geometry']['coordinates'] for f in prior['features'] if f['geometry']['type']=='Point' and f['properties']['site_id']==VIRTUAL)
    features=[]
    for p,l in loops.items():
        vertices=[edges[l['edge_ids'][0]]['u_node_id']]+[edges[e]['v_node_id'] for e in l['edge_ids']]
        features.append({'type':'Feature','properties':{'pattern':p,'boarding_authorised':False},'geometry':{'type':'LineString','coordinates':[coordinates[n] for n in vertices]}})
    for f in prior['features']:
        if f['geometry']['type']=='Point':
            f=copy.deepcopy(f);f['properties']['retained']=f['properties']['site_id'] in retained;features.append(f)
    for node in chosen_nodes:
        features.append({'type':'Feature','properties':{'new_road_node':node,'boarding_authorised':False},'geometry':{'type':'Point','coordinates':coordinates[node]}})
    return result,{'type':'FeatureCollection','properties':{k:False for k in FLAGS},'features':features}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--graph_dir',type=Path,required=True)
    parser.add_argument('--walk_dir',type=Path,required=True)
    args=parser.parse_args()
    result,shape=build(args.graph_dir,args.walk_dir)
    for path,data in ((OUTPUT,result),(OUTPUT.with_suffix('.geojson'),shape)):
        path.write_text(json.dumps(data,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('candidate_node_count','added_stop_count','minimum_added_stop_count_proven_for_recoverable_target','no_loss_possible_in_finite_node_domain','witness_potential_access_fraction')}),flush=True)
