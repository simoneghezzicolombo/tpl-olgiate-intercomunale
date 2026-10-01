"""Replace local detours with explicit FS-rooted local services, not free extras.

Finite, non-decisional comparison: ordered outer service nodes are conserved.
Every FS return is an explicit trip boundary with recovery in the fleet model.
"""
import argparse
import itertools
import json
from pathlib import Path

from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import inputs, BASE, FLAGS, site_rides
from scripts.phase2_audit_rt031_south_road_probe_v3 import FS, VIRTUAL, digest, rows
from scripts.phase2_export_rt031_line8_inclusive_shape_v3 import NORTH
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
from scripts.phase2_rt031_ordered_via_node_path_v3 import ordered_path
from scripts.phase2_audit_rt031_line8_occurrence_service_v3 import occurrences
from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops
from scripts.phase2_audit_rt031_line8_independent_wings_v3 import minimum_blocks
from scripts.phase2_audit_rt031_line8_band_switch_v3 import largest_gap
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter


def route(name, waypoints, edges, rules, sites, fs):
    result=ordered_path(edges,rules,waypoints,allow_internal_origin=False)
    if not result['reachable']:
        raise ValueError('unreachable path: '+name)
    path=result['_path_edge_ids']
    events=[{**e,'offset_from_wing_origin_min':e['offset_road_minutes']}
            for e in occurrences(path,edges,sites,fs,name) if e['stop_place_id']!=FS]
    return {'edge_ids':path,'events':events,'ordered_required_nodes':waypoints,
        'distance_m':sum(float(edges[e]['length_m']) for e in path),
        'road_minutes':sum(float(edges[e]['running_minutes_model']) for e in path)}


def single_trip_pairs(loops, patterns):
    result=set()
    for pattern in patterns:
        seq=[FS]+[e['stop_place_id'] for e in sorted(loops[pattern]['events'],key=lambda e:e['path_node_index'])]+[FS]
        result.update((a,b) for i,a in enumerate(seq) for b in seq[i+1:] if a!=b)
    return result


def gaps(trips,loops):
    opportunities={}
    for i,t in enumerate(trips):
        for e in loops[t['loop']]['events']:
            sid=e['stop_place_id']
            for direction,minute in (('from_fs',t['departure_min']),('to_fs',t['departure_min']+e['offset_from_wing_origin_min'])):
                opportunities.setdefault((sid,direction),[]).append({'minute':minute,'event_id':f'{i}:{e["occurrence_id"]}'})
    return [{'site_id':sid,'direction':direction,'max_optimistic_identity_gap_min':largest_gap(values)['minutes']}
            for (sid,direction),values in sorted(opportunities.items())]


def evaluate(loops,trips,joins,baseline,source,patterns_by_phase,cap):
    own_nominal=adjusted_loops(loops,1.1,.5)
    old_nominal=adjusted_loops(baseline,1.1,.5)
    rides=[]; changes=[]; losses=[]
    for phase,patterns in patterns_by_phase.items():
        old_patterns=('west_A','east_B') if phase=='AM' else ('west_B','east_A')
        losses.append({'phase':phase,'lost_hypothetical_single_trip_pairs':[
            {'from':a,'to':b} for a,b in sorted(single_trip_pairs(baseline,old_patterns)-single_trip_pairs(loops,patterns))]})
        for sid in (VIRTUAL,NORTH):
            options=[{'pattern':p,**site_rides(own_nominal[p],sid,.5)} for p in patterns
                     if any(e['stop_place_id']==sid for e in own_nominal[p]['events'])]
            rides.append({'phase':phase,'site_id':sid,'single_trip_options':options,
                'best_from_fs_min':min(o['from_fs_min'] for o in options),
                'best_to_fs_min':min(o['to_fs_min'] for o in options)})
    for name,loop in old_nominal.items():
        for sid in sorted({e['stop_place_id'] for e in loop['events']}-{VIRTUAL,NORTH}):
            before=site_rides(loop,sid,.5); after=site_rides(own_nominal[name],sid,.5)
            changes.append({'pattern':name,'site_id':sid,
                'from_fs_delta_min':after['from_fs_min']-before['from_fs_min'],
                'to_fs_delta_min':after['to_fs_min']-before['to_fs_min']})
    scenarios=[]
    for m,d in itertools.product((.9,1,1.1),(0,.5,1)):
        adjusted=adjusted_loops(loops,m,d)
        gap_rows=gaps(trips,adjusted)
        margins=[]
        for p in patterns_by_phase['AM']:
            morning=sorted([t for t in trips if t['loop']==p and t['service_bank']=='AM'],key=lambda t:t['departure_min'])
            if len(morning)!=5:
                raise ValueError('five-trip AM bank required')
            margins.extend(target-t['departure_min']-adjusted[p]['road_minutes']-3
                           for target,t in zip(source['new_morning_train_targets_min'],morning))
        for recovery in (5,10,15):
            scenarios.append({'moving_multiplier':m,'dwell_min':d,
                'max_optimistic_identity_gap_min':max(r['max_optimistic_identity_gap_min'] for r in gap_rows),
                'sites_with_any_gap_above_60':sorted({r['site_id'] for r in gap_rows if r['max_optimistic_identity_gap_min']>60.000001}),
                'smallest_morning_target_margin_min':min(margins),
                'missed_deterministic_target_count':sum(v<0 for v in margins),
                **minimum_blocks(trips,adjusted,joins,recovery)})
    km=sum(loops[t['loop']]['distance_m'] for t in trips)/1000*260
    return {'annual_service_km':km,'delta_from_115800_reference_km':km-source['annual_service_km'],
        'excess_percent_vs_reference_cap':100*(km/cap-1),'trip_count':len(trips),
        'priority_rides_nominal':rides,'other_site_ride_changes_nominal':changes,
        'lost_direct_pair_diagnostics':losses,'nominal_gap_rows':gaps(trips,own_nominal),
        'scenarios':scenarios,
        'all_scenarios_optimistic_h60':all(r['max_optimistic_identity_gap_min']<=60.000001 for r in scenarios),
        'all_scenarios_same_morning_targets_retained':all(r['missed_deterministic_target_count']==0 for r in scenarios)}


def build(paths):
    audit=json.loads(paths['counterflow'].read_text(encoding='utf-8'))
    if audit['contract']!='RT031_LINE8_LOCAL_COUNTERFLOW_ROAD_COMPARISON_V3' or any(audit[k] for k in ('network_selected','primary_selection_authorised','runner_up_selection_authorised')):
        raise ValueError('unsupported or decisional upstream source')
    for key,path in paths.items():
        if key=='counterflow':
            continue
        if audit['source_sha256'][key]!=digest(path,key not in ('edges','nodes','rules','attachments','successor')):
            raise ValueError('upstream source mismatch: '+key)
    wings=json.loads(paths['wings'].read_text(encoding='utf-8'))
    source=json.loads(paths['timetable'].read_text(encoding='utf-8'))
    if source['annual_service_days_assumption']!=260 or len(source['trips'])!=36:
        raise ValueError('source calendar or inventory drift')
    edges,nodes,rules,attachments=build_graph(paths)
    fs=attachments[FS]['graph_node_id']
    sites={FS:{'node':fs,'name':'Olgiate FS','status':'INVENTORY_NOT_APPROVED'}}
    for loop in wings['loops'].values():
        for e in loop['events']:
            sites[e['stop_place_id']]={'node':edges[e['incoming_edge']]['v_node_id'],'name':e['name'],'status':e['site_status']}
    outer={}
    for name,loop in wings['loops'].items():
        required=[]
        for e in sorted(loop['events'],key=lambda e:(e['path_node_index'],e['stop_place_id'])):
            if e['stop_place_id'] in (VIRTUAL,NORTH):
                continue
            point=(e['path_node_index'],sites[e['stop_place_id']]['node'])
            if not required or required[-1]!=point:
                required.append(point)
        outer[name]=route(name,[fs]+[node for _,node in required]+[fs],edges,rules,sites,fs)
        missing={e['stop_place_id'] for e in loop['events']}-{VIRTUAL,NORTH}-{e['stop_place_id'] for e in outer[name]['events']}
        if missing:
            raise ValueError('outer inventory lost')
    local={name:route(name,[fs]+[sites[s]['node'] for s in ids]+[fs],edges,rules,sites,fs)
           for name,ids in (('local_S',[VIRTUAL]),('local_N',[NORTH]),('local_SN',[VIRTUAL,NORTH]),('local_NS',[NORTH,VIRTUAL]))}
    loops={**outer,**local}
    adapter=FrozenRT017ViaNodeAdapter(edges.values(),rules,unresolved_external_via_way_count=2)
    joins={a+'>'+b:adapter.decision((ra['edge_ids'][-1],),rb['edge_ids'][0])['allowed'] is True for a,ra in loops.items() for b,rb in loops.items()}
    outer_trips=[{**t,'service_bank':'AM' if t['loop'] in ('west_A','east_B') else 'REST','role':'outer'} for t in source['trips']]
    specs=[('separate_local_services',None,None,None)]
    specs += [(f'combined_{am}_{rest}_{clock}',am,rest,clock)
              for am,rest,clock in itertools.product(('SN','NS'),('SN','NS'),('west','east'))]
    cases=[]
    for label,am,rest,clock in specs:
        trips=list(outer_trips)
        if am is None:
            trips += [{**t,'loop':'local_S' if t['loop'].startswith('west') else 'local_N','role':'local'} for t in outer_trips]
            phases={'AM':['west_A','east_B','local_S','local_N'],'REST':['west_B','east_A','local_S','local_N']}
        else:
            trips += [{**t,'loop':'local_'+(am if t['service_bank']=='AM' else rest),'role':'local'}
                      for t in outer_trips if t['loop'].startswith(clock)]
            phases={'AM':['west_A','east_B','local_'+am],'REST':['west_B','east_A','local_'+rest]}
        trips.sort(key=lambda t:(t['departure_min'],t['loop']))
        required=set(sites)-{FS}
        seen={e['stop_place_id'] for p in {t['loop'] for t in trips} for e in loops[p]['events']}
        if required-seen:
            raise ValueError('network site coverage lost')
        cases.append({'case_id':label,'trips':trips,'patterns_by_phase':phases,
            'lost_original_site_ids':sorted(required-seen),
            **evaluate(loops,trips,joins,wings['loops'],source,phases,source['reference_cap_unchanged'])})
    coords={nid:[float(n['lon']),float(n['lat'])] for nid,n in nodes.items()}
    cand=next(r for r in rows(paths['candidates_normalized_newlines']) if r['candidate_id']=='P2V2S_0031')
    coords[VIRTUAL]=[float(cand['lon']),float(cand['lat'])]
    features=[]
    for group,pool in (('baseline',wings['loops']),('split',loops)):
        for name,loop in pool.items():
            vertices=[edges[loop['edge_ids'][0]]['u_node_id']]+[edges[e]['v_node_id'] for e in loop['edge_ids']]
            features.append({'type':'Feature','properties':{'group':group,'pattern':name,'distance_m':loop['distance_m'],
                'boarding_authorised':False},'geometry':{'type':'LineString','coordinates':[coords[n] for n in vertices]}})
    for sid,s in sites.items():
        features.append({'type':'Feature','properties':{'site_id':sid,**s,'boarding_authorised':False},
            'geometry':{'type':'Point','coordinates':coords[s['node']]}})
    successor=json.loads(paths['successor'].read_text(encoding='utf-8'))
    via_ways={w for r in successor['successor_via_way_relations'] for w in r['via_way_ids']}
    result={'contract':'RT031_LINE8_EXPLICIT_LOCAL_SPLIT_COMPARISON_V3',
        'status':'NON_DECISIONAL_ROAD_AND_TIMETABLE_COMPARISON','loops':loops,'represented_via_node_joins':joins,
        'source_sha256':{k:digest(p,k not in ('edges','nodes','rules','attachments','successor')) for k,p in paths.items()},
        'cases':cases,'annual_service_days_assumption':260,'reference_cap_unchanged':source['reference_cap_unchanged'],
        'known_successor_via_way_overlap':sorted(via_ways & {edges[e]['osm_way_id'] for l in loops.values() for e in l['edge_ids']}),
        'full_history_legality_certified':False,'total_operating_km':None,'approved_uplift_percent':None,
        'domain':'Outer original ordered service-node sequences preserved except two local anchors assigned to explicit short services. Two separate local loops or one local loop in either order, independent AM/rest orders and two inherited clocks. Nine fixed timetable comparisons, no weighted selection or global optimum claim.',
        'frequency_semantics':'Five H30 departures per fixed pattern in each peak bank. Whole-network optimistic identity H60 checked in both to/from FS. Not common-window two-hour H30, authorised boarding or empirical reliability.',
        'transfer_semantics':'Local-to-outer journeys may now require an FS transfer. No vehicle or passenger through-continuity is assumed. Lost hypothetical one-trip OD pairs are explicitly reported, not demand counts. Every trip charges separate recovery in fleet checks.',
        'not_certified':['bus turning at local anchors','full-history restrictions','platform sides and boarding','actual railway timetable','driver duties and depot km','common-window H30','real passenger demand'],**FLAGS}
    return result,{'type':'FeatureCollection','properties':FLAGS,'features':features}


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--graph_dir',type=Path,required=True)
    p.add_argument('--output',type=Path,default=BASE/'local_split.json')
    p.add_argument('--geojson',type=Path,default=BASE/'local_split.geojson')
    a=p.parse_args(); paths=inputs(a.graph_dir); paths['counterflow']=BASE/'local_counterflow.json'
    result,shape=build(paths)
    for path,value in ((a.output,result),(a.geojson,shape)):
        path.write_text(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    for c in result['cases']:
        print(json.dumps({'case':c['case_id'],'km':c['annual_service_km'],'excess_percent':c['excess_percent_vs_reference_cap'],
            'trips':c['trip_count'],'local_max_ride_min':max(max(r['best_to_fs_min'],r['best_from_fs_min']) for r in c['priority_rides_nominal']),
            'h60':c['all_scenarios_optimistic_h60'],'rail':c['all_scenarios_same_morning_targets_retained'],
            'max_fleet':max(r['minimum_vehicle_count_conditional'] for r in c['scenarios'])}))
