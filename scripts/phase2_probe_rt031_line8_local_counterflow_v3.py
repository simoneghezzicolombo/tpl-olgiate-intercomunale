"""Bounded repeated-locality road comparison; no automatic service selection."""
import argparse
from collections import Counter
import itertools
import json
from pathlib import Path

from scripts.phase2_audit_rt031_south_road_probe_v3 import EXPECTED, FS, VIRTUAL, digest, rows
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
from scripts.phase2_export_rt031_line8_inclusive_shape_v3 import NORTH
from scripts.phase2_rt031_ordered_via_node_path_v3 import ordered_path
from scripts.phase2_audit_rt031_line8_occurrence_service_v3 import occurrences
from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops
from scripts.phase2_audit_rt031_line8_independent_wings_v3 import minimum_blocks
from scripts.phase2_audit_rt031_line8_joint_phases_v3 import metrics
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'outputs/phase2/rt031_line8_local_shortcuts_v3'
FLAGS = dict(network_selected=False, primary_selection_authorised=False,
             runner_up_selection_authorised=False, decision_budget_km=None, uncertainty_band_min=None)


def inputs(graph_dir):
    return dict(edges=graph_dir/'rt017/frozen_graph_edges.csv.gz',
        nodes=graph_dir/'rt017/frozen_graph_nodes.csv.gz', rules=graph_dir/'rt017/frozen_turn_rules.csv.gz',
        attachments=graph_dir/'rt022/stop_attachments.csv',
        successor=graph_dir/'successor/rt031-successor-via-way-relevance.json',
        candidates_normalized_newlines=ROOT/'outputs/phase2/stop_universe_v2/proposed_stop_candidates.csv',
        wings=BASE/'independent_wings.json', timetable=BASE/'peak_direction_retimed.json')


def site_rides(loop, sid, dwell):
    events=[e for e in loop['events'] if e['stop_place_id']==sid]
    if not events:
        raise ValueError('missing required site')
    return {'from_fs_min':min(e['offset_from_wing_origin_min']-dwell for e in events),
            'to_fs_min':min(loop['road_minutes']-e['offset_from_wing_origin_min'] for e in events)}


def endpoint_variant(name, loop, edges, rules, sites, fs_node, added_sites=None):
    """Preserve ordered original service-node visits, add local visit at other end.

    Internal geometric FS returns are excluded: no hidden station stop, recovery,
    transfer, or vehicle/passenger continuity is assumed at an intermediate FS.
    """
    added_sites=added_sites or [VIRTUAL if name.startswith('west') else NORTH]
    ordered=sorted(loop['events'],key=lambda e:(e['path_node_index'],e['stop_place_id']))
    stops=[]
    for e in ordered:
        value=(e['path_node_index'],sites[e['stop_place_id']]['node'])
        if not stops or value!=stops[-1]:
            stops.append(value)
    waypoints=[fs_node]+[node for _,node in stops]+[fs_node]
    if name in ('west_A','east_B'):
        waypoints[1:1]=[sites[sid]['node'] for sid in added_sites]
    else:
        waypoints[-1:-1]=[sites[sid]['node'] for sid in added_sites]
    answer=ordered_path(edges,rules,waypoints,allow_internal_origin=False)
    if not answer['reachable']:
        raise ValueError('ordered repeated-locality path unreachable: '+name)
    path=answer['_path_edge_ids']
    actual=occurrences(path,edges,sites,fs_node,name)
    events=[{**e,'offset_from_wing_origin_min':e['offset_road_minutes']} for e in actual if e['stop_place_id']!=FS]
    for sid in added_sites:
        required_count=Counter(e['stop_place_id'] for e in loop['events'])[sid]+1
        if Counter(e['stop_place_id'] for e in events)[sid]<required_count:
            raise ValueError('locality did not receive the additional occurrence')
    if any(edges[e]['v_node_id']==fs_node for e in path[:-1]):
        raise ValueError('hidden intermediate station return')
    return {'edge_ids':path,'events':events,
        'distance_m':sum(float(edges[e]['length_m']) for e in path),
        'road_minutes':sum(float(edges[e]['running_minutes_model']) for e in path),
        'ordered_required_nodes':waypoints,
        'represented_via_node_path_verified':True,'full_history_legality_certified':False}


def evaluate(loops, baseline, trips, joins, targets, reference_cap):
    nominal=adjusted_loops(loops,1.1,.5)
    original=adjusted_loops(baseline,1.1,.5)
    rides=[]; impacts=[]; network_rides=[]
    for name,loop in nominal.items():
        sid=VIRTUAL if name.startswith('west') else NORTH
        rides.append({'pattern':name,'site_id':sid,**site_rides(loop,sid,.5)})
        for site in sorted({e['stop_place_id'] for e in original[name]['events']}):
            before=site_rides(original[name],site,.5); after=site_rides(loop,site,.5)
            impacts.append({'pattern':name,'site_id':site,
                'from_fs_delta_min':after['from_fs_min']-before['from_fs_min'],
                'to_fs_delta_min':after['to_fs_min']-before['to_fs_min']})
    for phase,patterns in (('AM',('west_A','east_B')),('REST',('west_B','east_A'))):
        for sid in (VIRTUAL,NORTH):
            options=[{'pattern':name,**site_rides(nominal[name],sid,.5)} for name in patterns
                     if any(e['stop_place_id']==sid for e in nominal[name]['events'])]
            network_rides.append({'phase':phase,'site_id':sid,'single_trip_options':options,
                'best_from_fs_min':min(r['from_fs_min'] for r in options),
                'best_to_fs_min':min(r['to_fs_min'] for r in options)})
    scenarios=[]
    for m,d in itertools.product((.9,1,1.1),(0,.5,1)):
        adjusted=adjusted_loops(loops,m,d)
        gap=max(metrics([t for t in trips if t['loop'].startswith(w)],adjusted)['max_optimistic_identity_gap_min'] for w in ('west','east'))
        margins=[]
        for am in ('west_A','east_B'):
            own=sorted((t for t in trips if t['loop']==am),key=lambda t:t['departure_min'])
            if len(own)!=len(targets):
                raise ValueError('morning bank inventory drift')
            margins.extend(target-(trip['departure_min']+adjusted[am]['road_minutes'])-3 for target,trip in zip(targets,own))
        for recovery in (5,10,15):
            scenarios.append({'moving_multiplier':m,'dwell_min':d,
                'max_optimistic_identity_gap_min':gap,
                'missed_deterministic_target_count':sum(margin<0 for margin in margins),
                'smallest_morning_train_margin_min':min(margins),
                **minimum_blocks(trips,adjusted,joins,recovery)})
    annual=sum(loops[t['loop']]['distance_m'] for t in trips)/1000*260
    old=sum(baseline[t['loop']]['distance_m'] for t in trips)/1000*260
    return {'annual_service_km':annual,'added_annual_service_km':annual-old,
        'excess_percent_vs_reference':100*(annual/reference_cap-1),
        'priority_rides_nominal':rides,'network_priority_rides_nominal':network_rides,
        'all_original_site_ride_changes_nominal':impacts,
        'maximum_other_site_ride_increase_min':max(max(r['from_fs_delta_min'],r['to_fs_delta_min']) for r in impacts if r['site_id'] not in (VIRTUAL,NORTH)),
        'scenarios':scenarios,
        'all_scenarios_optimistic_h60':all(r['max_optimistic_identity_gap_min']<=60.000001 for r in scenarios),
        'all_scenarios_same_morning_targets_retained':all(r['missed_deterministic_target_count']==0 for r in scenarios)}


def build(paths):
    wings=json.loads(paths['wings'].read_text(encoding='utf-8'))
    timetable=json.loads(paths['timetable'].read_text(encoding='utf-8'))
    for item,contract in ((wings,'RT031_LINE8_INDEPENDENT_WINGS_DIAGNOSTIC_V3'),
                          (timetable,'RT031_LINE8_SAME_KM_CONDITIONAL_RETIMING_V3')):
        if item['contract']!=contract or any(item[k] for k in ('network_selected','primary_selection_authorised','runner_up_selection_authorised')):
            raise ValueError('wrong or decisional upstream contract')
    if timetable['source_sha256']['wings']!=digest(paths['wings'],True):
        raise ValueError('timetable source mismatch')
    for k in EXPECTED:
        if wings['source_sha256'][k]!=digest(paths[k],k.endswith('normalized_newlines')):
            raise ValueError('wings road source mismatch: '+k)
    if timetable['annual_service_days_assumption']!=260:
        raise ValueError('annual calendar drift')
    edges,nodes,rules,attachments=build_graph(paths)
    fs_node=attachments[FS]['graph_node_id']
    sites={FS:{'node':fs_node,'name':'Olgiate FS','status':'INVENTORY_NOT_BOARDING_APPROVED'}}
    for loop in wings['loops'].values():
        for event in loop['events']:
            node=edges[event['incoming_edge']]['v_node_id']
            value={'node':node,'name':event['name'],'status':event['site_status']}
            if event['stop_place_id'] in sites and sites[event['stop_place_id']]!=value:
                raise ValueError('ambiguous site node')
            sites[event['stop_place_id']]=value
    patched={name:endpoint_variant(name,loop,edges,rules,sites,fs_node) for name,loop in wings['loops'].items()}
    crossed={name:endpoint_variant(name,loop,edges,rules,sites,fs_node,
             added_sites=[NORTH if name.startswith('west') else VIRTUAL]) for name,loop in wings['loops'].items()}
    joint={order:{name:endpoint_variant(name,loop,edges,rules,sites,fs_node,added_sites=ids)
                  for name,loop in wings['loops'].items()}
           for order,ids in (('SN',[VIRTUAL,NORTH]),('NS',[NORTH,VIRTUAL]))}
    adapter=FrozenRT017ViaNodeAdapter(edges.values(),rules,unresolved_external_via_way_count=2)
    successor=json.loads(paths['successor'].read_text(encoding='utf-8'))
    via_ways={way for r in successor['successor_via_way_relations'] for way in r['via_way_ids']}
    cases=[]
    specifications=[('baseline',(),patched),('south_only',('west',),patched),
            ('north_only',('east',),patched),('both',('west','east'),patched),
            ('cross_south_only',('east',),crossed),('cross_north_only',('west',),crossed),
            ('cross_both',('west','east'),crossed)]
    for wing,am,rest in (('west','west_A','west_B'),('east','east_B','east_A')):
        for am_order,rest_order in itertools.product(('SN','NS'),repeat=2):
            specifications.append((f'joint_{wing}_{am_order}_{rest_order}',(wing,),
                                   {am:joint[am_order][am],rest:joint[rest_order][rest]}))
    for label,replace,pool in specifications:
        loops={name:pool[name] if name.split('_')[0] in replace else loop for name,loop in wings['loops'].items()}
        joins={a+'>'+b:adapter.decision((la['edge_ids'][-1],),lb['edge_ids'][0])['allowed'] is True for a,la in loops.items() for b,lb in loops.items()}
        lost={name:sorted({e['stop_place_id'] for e in wings['loops'][name]['events']}-{e['stop_place_id'] for e in loop['events']}) for name,loop in loops.items()}
        if any(lost.values()):
            raise ValueError('original site lost')
        cap=timetable['reference_cap_unchanged']
        cases.append({'case_id':label,'changed_wings':list(replace),'lost_original_site_ids':lost,
            'represented_via_node_joins':joins,
            'known_successor_via_way_overlap':sorted(via_ways & {edges[e]['osm_way_id'] for l in loops.values() for e in l['edge_ids']}),
            **evaluate(loops,wings['loops'],timetable['trips'],joins,timetable['new_morning_train_targets_min'],cap)})
    coordinates={nid:[float(r['lon']),float(r['lat'])] for nid,r in nodes.items()}
    candidate=next(r for r in rows(paths['candidates_normalized_newlines']) if r['candidate_id']=='P2V2S_0031')
    coordinates[VIRTUAL]=[float(candidate['lon']),float(candidate['lat'])]
    features=[]
    for label,replace,pool in specifications:
        if label not in ('baseline','both','cross_both') and not label.startswith('joint_'):
            continue
        loops={name:pool[name] if name.split('_')[0] in replace else loop for name,loop in wings['loops'].items()}
        for name,loop in loops.items():
            vertex=[edges[loop['edge_ids'][0]]['u_node_id']]+[edges[e]['v_node_id'] for e in loop['edge_ids']]
            features.append({'type':'Feature','properties':{'case':label,'pattern':name,'distance_m':loop['distance_m'],
                'boarding_authorised':False},'geometry':{'type':'LineString','coordinates':[coordinates[n] for n in vertex]}})
    for sid,site in sites.items():
        features.append({'type':'Feature','properties':{'site_id':sid,**site,'boarding_authorised':False},
            'geometry':{'type':'Point','coordinates':coordinates[site['node']]}})
    # Explicit witness, not a minimum-fleet or optimal-phasing claim. Keep the
    # same frozen train targets; a pure clock shift cannot change service km.
    repair_trips=sorted([{**t,'departure_min':t['departure_min']-(1 if t['loop']=='west_A' else 0)}
                         for t in timetable['trips']],key=lambda t:(t['departure_min'],t['loop']))
    full_case=next(c for c in cases if c['case_id']=='both')
    repair={'case_id':'both_west_am_one_minute_earlier','trips':repair_trips,
        'semantics':'Constructed clock-shift witness only. Same routes, 36 trips and frozen train targets; no optimal-phase or operational approval claim.',
        **evaluate(patched,wings['loops'],repair_trips,full_case['represented_via_node_joins'],
                   timetable['new_morning_train_targets_min'],timetable['reference_cap_unchanged'])}
    result={'contract':'RT031_LINE8_LOCAL_COUNTERFLOW_ROAD_COMPARISON_V3',
        'status':'BOUNDED_ROAD_AND_FIXED_TIMETABLE_COMPARISON_NOT_SELECTED',
        'source_sha256':{k:digest(v,k not in ('edges','nodes','rules','attachments','successor')) for k,v in paths.items()},
        'candidate_loops':patched,'cross_candidate_loops':crossed,'joint_candidate_loops':joint,
        'cases':cases,'trips_unchanged':timetable['trips'],
        'full_correction_one_minute_retiming':repair,
        'per_modified_trip_cost':{name:{
            'additional_km':loop['distance_m']/1000-wings['loops'][name]['distance_m']/1000,
            'annual_km_if_one_such_trip_per_day':(loop['distance_m']-wings['loops'][name]['distance_m'])/1000*260}
            for name,loop in patched.items()},
        'annual_service_days_assumption':260,'reference_cap_unchanged':timetable['reference_cap_unchanged'],
        'total_operating_km':None,'approved_uplift_percent':None,
        'domain':'Shortest distance paths for each fixed ordered original service-node sequence, adding priority localities at the opposite endpoint on their own, crossed, or jointly on one wing (both orders independently for AM/rest). No internal FS return. Only represented via-node restrictions. Fifteen comparisons, no weights or selected winner.',
        'service_semantics':'Each encountered occurrence at the original 28 sites hypothetically served. Earliest from-FS and latest to-FS occurrences are distinct ordered events, not interchangeable platforms. No certified boarding or passenger continuity. Timetable unchanged; failures are not repaired silently.',
        'not_certified':['full-history restrictions','bus suitability and turnarounds','physical directional platforms','current train timetable','actual passenger continuity','observed travel times','driver/depot duties','all-day common-window H30'],
        **FLAGS}
    shape={'type':'FeatureCollection','properties':FLAGS,'features':features}
    return result,shape


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--graph_dir',type=Path,required=True)
    p.add_argument('--output',type=Path,default=BASE/'local_counterflow.json')
    p.add_argument('--geojson',type=Path,default=BASE/'local_counterflow.geojson')
    a=p.parse_args(); result,shape=build(inputs(a.graph_dir))
    for path,data in ((a.output,result),(a.geojson,shape)):
        path.write_text(json.dumps(data,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    for c in result['cases']:
        print(json.dumps({k:c[k] for k in ('case_id','annual_service_km','added_annual_service_km','excess_percent_vs_reference','priority_rides_nominal','maximum_other_site_ride_increase_min','all_scenarios_optimistic_h60','all_scenarios_same_morning_targets_retained')}))
