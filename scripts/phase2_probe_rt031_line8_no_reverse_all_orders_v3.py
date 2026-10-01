"""Distance minimum over interior stop orders, with local service boundary paths.

Frozen represented via-node semantics only. A single distance witness does not
certify the full Pareto frontier, boarding, fleet, calendar or physical legality.
"""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path

from scripts.phase2_probe_rt031_line8_calco_through_path_v3 import (
    OUTPUT as CALCO, refresh_events, local_access)
from scripts.phase2_probe_rt031_line8_manoeuvre_cycles_v3 import split_only_edges, reverse
from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import BASE, FS, inputs
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
from scripts.phase2_probe_rt031_line8_free_orders_v3 import EdgeStateClosure, terminal_tour, reversal_indices
from scripts.phase2_rebuild_rt031_uniform_complete_line_v3 import inputs as service_inputs
from scripts.phase2_probe_rt031_line8_variable_fs_hold_v3 import solve
from scripts.phase2_probe_rt031_line8_order_neighbourhood_v3 import access_vector
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter

OUTPUT = BASE/'no_reverse_all_orders.json.gz'
SHAPE = BASE/'no_reverse_all_orders.geojson'
MAP = BASE/'no_reverse_all_orders.png'
LOCAL = {'west_B': 'RT031::P2V2S_0031_PROJECTED_ROAD_POINT',
         'east_A': 'PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE'}


class NoReverseAdapter:
    def __init__(self, edges, adapter):
        self.edges, self.adapter = edges, adapter

    def decision(self, history, outgoing):
        decision = self.adapter.decision(history, outgoing)
        if history and reverse(self.edges[history[-1]], self.edges[outgoing]):
            return {**decision, 'allowed': False}
        return decision


def optimal_loop(closure, adapter, edges, old, wing, omitted=None):
    ordered = sorted(old['events'], key=lambda e: (e['path_node_index'], e['stop_place_id']))
    first, last = ordered[0], ordered[-1]
    if first['stop_place_id'] != LOCAL[wing] or last['stop_place_id'] != LOCAL[wing]:
        raise ValueError('local events must bound each wing service')
    prefix = old['edge_ids'][:first['path_node_index']]
    suffix = old['edge_ids'][last['path_node_index']-1:]
    by_node = {}
    for event in ordered[1:-1]:
        if event['stop_place_id'] != omitted:
            by_node.setdefault(edges[event['incoming_edge']]['v_node_id'], []).append(event)
    answer = terminal_tour(closure, set(by_node), prefix[-1],
                           edges[suffix[0]]['u_node_id'], suffix[0], adapter)
    path = prefix+answer['interior_edge_ids']+suffix
    if reversal_indices(path, edges):
        raise ValueError('reversal in reconstructed tour')
    checkpoints = [(prefix[-1], [first])]+[
        (eid, by_node[edges[eid]['v_node_id']]) for eid in answer['logical_terminal_incoming_edges']]+[(suffix[0], [last])]
    progress, events = 0, []
    for index, eid in enumerate(path, 1):
        if progress < len(checkpoints) and eid == checkpoints[progress][0]:
            for source in checkpoints[progress][1]:
                event = copy.deepcopy(source)
                event.update(path_node_index=index, physical_boarding_authorised=False,
                    parent_occurrence_id=source.get('parent_occurrence_id',source['occurrence_id']))
                events.append(event)
            progress += 1
    if progress != len(checkpoints):
        raise ValueError('service-event reconstruction failed')
    loop = {**old,'edge_ids':path,'events':events}
    refresh_events(loop,edges,wing)
    return loop, {k:v for k,v in answer.items() if k!='interior_edge_ids'}


def build(graph_dir):
    paths = inputs(graph_dir)
    raw, nodes, rules, attachments = build_graph(paths)
    edges = split_only_edges(raw)
    adapter = NoReverseAdapter(edges, FrozenRT017ViaNodeAdapter(edges.values(), rules,
                                       unresolved_external_via_way_count=2))
    _, policy, _, _, _ = service_inputs()
    parent = json.loads(gzip.decompress(CALCO.read_bytes()))
    candidate = next(c for c in parent['cases'] if c['reachable'])
    baseline = candidate['whole_wing_fixed_order_without_reversals']['loops']
    fs = attachments[FS]['graph_node_id']
    closure = EdgeStateClosure(edges, adapter, {fs})
    loops, audits = {}, []
    for wing, old in baseline.items():
        ordered = sorted(old['events'], key=lambda e: (e['path_node_index'],e['stop_place_id']))
        first, last = ordered[0], ordered[-1]
        if first['stop_place_id'] != LOCAL[wing] or last['stop_place_id'] != LOCAL[wing]:
            raise ValueError('local events must bound each wing service')
        prefix = old['edge_ids'][:first['path_node_index']]
        suffix = old['edge_ids'][last['path_node_index']-1:]
        by_node = {}
        for event in ordered[1:-1]:
            node = edges[event['incoming_edge']]['v_node_id']
            by_node.setdefault(node, []).append(event)
        target = edges[suffix[0]]['u_node_id']
        answer = terminal_tour(closure, set(by_node), prefix[-1], target, suffix[0], adapter)
        path = prefix+answer['interior_edge_ids']+suffix
        if reversal_indices(path, edges) or any(edges[e]['v_node_id']==fs for e in path[:-1]):
            raise ValueError('all-order reconstruction violates road domain')
        checkpoints = [(prefix[-1], [first])]+[
            (eid, by_node[edges[eid]['v_node_id']]) for eid in answer['logical_terminal_incoming_edges']]+[
            (suffix[0], [last])]
        progress, events = 0, []
        for index, eid in enumerate(path, 1):
            if progress < len(checkpoints) and eid == checkpoints[progress][0]:
                for source in checkpoints[progress][1]:
                    event = copy.deepcopy(source)
                    event.update(path_node_index=index, physical_boarding_authorised=False,
                        parent_occurrence_id=source.get('parent_occurrence_id',source['occurrence_id']))
                    events.append(event)
                progress += 1
        if progress != len(checkpoints) or len(events) != len(ordered):
            raise ValueError('ordered service-event reconstruction failed')
        loop = {**old, 'edge_ids': path, 'events': events}
        refresh_events(loop, edges, wing)
        loops[wing] = loop
        audits.append({'wing': wing, **{k:v for k,v in answer.items() if k!='interior_edge_ids'},
            'fixed_prefix_edge_ids': prefix, 'fixed_suffix_edge_ids': suffix,
            'distance_m': loop['distance_m'], 'road_minutes_model': loop['road_minutes'],
            'served_site_ids': sorted({e['stop_place_id'] for e in events}),
            'distance_minimum_in_declared_interior_order_domain': True})
        print(wing, loop['distance_m'], answer['terminal_node_count'], flush=True)
    total = sum(l['distance_m'] for l in loops.values())
    omissions = []
    for wing, old in baseline.items():
        protected = {LOCAL[wing], 'PROXY::RT031_ADDITIONAL::n:534398.29:5063851.64'}
        for sid in sorted({e['stop_place_id'] for e in old['events']}-protected):
            revised_loop, proof = optimal_loop(closure, adapter, edges, old, wing, sid)
            revised = {**loops, wing: revised_loop}
            distance = sum(l['distance_m'] for l in revised.values())
            omissions.append({'omitted_stop_identity':sid, 'wing':wing,
                'omitted_name':next(e['name'] for e in old['events'] if e['stop_place_id']==sid),
                'distance_m':distance,'annual_service_km_16_trips_260_days':distance*16*260/1000,
                'distance_saved_m':total-distance,'all_order_distance_proof':proof,
                'calco_19m_hypothesis_required':sid!='FROZEN::300634',
                'coverage_loss_certified':False,'stop_omission_adopted':False,'loops':revised})
            print('omit',sid,distance*16*260/1000,flush=True)
    shortest_omission = min(omissions,key=lambda c:c['distance_m'])
    shortest_omission['timetable_comparison_not_adopted'] = solve(policy,
        shortest_omission['loops'],'west_B',False,70,60,max_mid=55,
        anchor_policy='flexible_real_trains')
    timetable = solve(policy, loops, 'west_B', False, 70, 60, max_mid=60,
                      anchor_policy='flexible_real_trains')
    # This comparison changes only the admitted road orders; all caller inputs
    # (16 complete trips, and non-adopted H70 engineering profile) remain explicit.
    result = {'contract': 'RT031_LINE8_NO_REVERSE_ALL_INTERIOR_ORDERS_DIAGNOSTIC_V3',
        'parent_source_sha256': hashlib.sha256(CALCO.read_bytes()).hexdigest(),
        'graph_inputs_sha256': {k: hashlib.sha256(paths[k].read_bytes()).hexdigest()
                               for k in ('edges','nodes','rules','attachments')},
        'audits': audits, 'loops': loops, 'distance_m': total,
        'annual_service_km_16_trips_260_days': total*16*260/1000,
        'local_fast_passages_nominal': local_access(loops),
        'access_nominal_by_site': access_vector(loops),
        'baseline_access_nominal_by_site': access_vector(baseline),
        'single_inventory_omission_comparisons_not_adopted':omissions,
        'shortest_omission_identity_not_selection':shortest_omission['omitted_stop_identity'],
        'timetable_comparison_not_adopted': timetable,
        'semantics': 'Exact distance minimum over all interior terminal visit orders in each wing, '
            'fixed first-local arrival prefix and last-local arrival+FS suffix from the Calco '
            '19m hypothesis reference; all 29 design identities including FS. Directed incoming '
            'edge states retain represented via-node restrictions, with no immediate reversals '
            'inside wings and no internal FS visit. One designated service event per interior '
            'identity, and two distinct ordered local events. Incidental geometric crossings '
            'are not extra service events. Local boundary road paths are fixed, not all roads '
            'or boundary choices. Only one minimum-distance witness; not the full Pareto frontier. '
            'Stop approach sides may change and are not physically certified. Nominal engineering '
            'access is not OD, passengers, walking coverage or empirical missed-connection probability.',
        'interior_event_order_adopted': False, 'fs_manoeuvre_certified': False,
        'physical_boarding_authorised': False, 'coverage_preservation_certified': False,
        'full_history_legality_certified': False, 'candidate_domain_complete': False,
        'network_selected': False, 'primary_selection_authorised': False,
        'runner_up_selection_authorised': False, 'decision_budget_km': None,
        'uncertainty_band_min': None}
    # Publish both wings of the single complete road itinerary.
    manoeuvres = json.loads(gzip.decompress((BASE/'stop_plan_and_additions.json.gz').read_bytes()))['manoeuvres']
    coordinates = {n:[float(v['lon']),float(v['lat'])] for n,v in nodes.items()}
    coordinates.update({m['node_id']:m['coordinates'] for m in manoeuvres})
    features = []
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10,6))
    for wing, loop in loops.items():
        path = loop['edge_ids']
        xy = [coordinates[edges[path[0]]['u_node_id']]]+[
            coordinates[edges[e]['v_node_id']] for e in path]
        ax.plot(*zip(*xy), lw=2, color='#2586d8' if wing.startswith('west') else '#ee8128',
                label='Ala ovest' if wing.startswith('west') else 'Ala est')
        pts = [coordinates[edges[e['incoming_edge']]['v_node_id']] for e in loop['events']]
        ax.scatter(*zip(*pts), s=12, color='#303030',zorder=4)
        features.append({'type':'Feature','properties':{'wing':wing,'adopted':False},
                         'geometry':{'type':'LineString','coordinates':xy}})
    for label, sid in [('Olgiate sud',LOCAL['west_B']),('San Zeno',LOCAL['east_A']),
                       ('Brivio · Via Bergamo','FROZEN::300063'),
                       ('Calco: accosto ipotizzato','FROZEN::300634')]:
        event = next(e for l in loops.values() for e in l['events'] if e['stop_place_id']==sid)
        ax.annotate(label, coordinates[edges[event['incoming_edge']]['v_node_id']],
                    xytext=(5,7),textcoords='offset points',fontsize=8)
    ax.annotate('Olgiate FS',coordinates[fs],xytext=(5,7),textcoords='offset points')
    ax.scatter(*coordinates[fs],color='red',zorder=5)
    import math
    ax.set_aspect(1/math.cos(math.radians(45.73)));ax.legend()
    ax.set_title('Linea 8 · tutti i siti di progetto · ordini interni esplorati\nNessuna inversione nelle ali; accosto Calco e idoneità autobus da verificare')
    fig.tight_layout();fig.savefig(MAP,dpi=150);plt.close(fig)
    # Also show exactly what the low-km omission comparison leaves out.
    fig, ax = plt.subplots(figsize=(10,6))
    for wing, loop in loops.items():
        path=loop['edge_ids']
        xy=[coordinates[edges[path[0]]['u_node_id']]]+[
            coordinates[edges[e]['v_node_id']] for e in path]
        ax.plot(*zip(*xy),color='#bbbbbb',lw=1,ls='--')
    for wing, loop in shortest_omission['loops'].items():
        path=loop['edge_ids']
        xy=[coordinates[edges[path[0]]['u_node_id']]]+[
            coordinates[edges[e]['v_node_id']] for e in path]
        ax.plot(*zip(*xy),lw=2,color='#2586d8' if wing.startswith('west') else '#ee8128',
                label='Ala ovest' if wing.startswith('west') else 'Ala est')
        pts=[coordinates[edges[e['incoming_edge']]['v_node_id']] for e in loop['events']]
        ax.scatter(*zip(*pts),s=12,color='#303030',zorder=4)
    omitted=next(e for l in loops.values() for e in l['events']
                 if e['stop_place_id']==shortest_omission['omitted_stop_identity'])
    xy=coordinates[edges[omitted['incoming_edge']]['v_node_id']]
    ax.scatter(*xy,marker='x',s=75,color='red',zorder=5)
    ax.annotate("Hoè: fermata esclusa in questo confronto",xy,xytext=(7,7),textcoords='offset points',fontsize=8)
    for label,sid in [('Olgiate sud',LOCAL['west_B']),('San Zeno',LOCAL['east_A']),
                      ('Brivio · Via Bergamo','FROZEN::300063'),('Calco: accosto ipotizzato','FROZEN::300634')]:
        event=next(e for l in shortest_omission['loops'].values() for e in l['events'] if e['stop_place_id']==sid)
        ax.annotate(label,coordinates[edges[event['incoming_edge']]['v_node_id']],xytext=(5,7),textcoords='offset points',fontsize=8)
    ax.scatter(*coordinates[fs],color='red',zorder=5)
    ax.annotate('Olgiate FS',coordinates[fs],xytext=(5,7),textcoords='offset points')
    ax.set_aspect(1/math.cos(math.radians(45.73)));ax.legend()
    ax.set_title('Linea 8 · confronto con la sola fermata Hoè esclusa\n28 siti di progetto inclusa FS; tracciato precedente tratteggiato')
    fig.tight_layout();fig.savefig(BASE/'no_reverse_hoe_omission.png',dpi=150);plt.close(fig)
    for wing,loop in shortest_omission['loops'].items():
        path=loop['edge_ids']
        xy=[coordinates[edges[path[0]]['u_node_id']]]+[
            coordinates[edges[e]['v_node_id']] for e in path]
        features.append({'type':'Feature','properties':{'wing':wing,
            'omitted_stop_identity':shortest_omission['omitted_stop_identity'],'adopted':False},
            'geometry':{'type':'LineString','coordinates':xy}})
    return result, {'type':'FeatureCollection','features':features}


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--graph_dir',type=Path,required=True)
    a=p.parse_args();result,shape=build(a.graph_dir)
    OUTPUT.write_bytes(gzip.compress((json.dumps(result,sort_keys=True,ensure_ascii=False,
        separators=(',',':'))+'\n').encode('utf-8'),mtime=0))
    SHAPE.write_text(json.dumps(shape,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf-8')
