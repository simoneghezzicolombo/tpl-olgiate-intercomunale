"""Numbered stop/occurrence register and on-path additional-stop screening.

No route changes, accepted additions, platform approvals or invented demand.
Every unserved road vertex of the two approved paths is a point hypothesis.
"""
import argparse
from collections import Counter, defaultdict
import copy
from fractions import Fraction
import gzip
import json
import heapq
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

from scripts.phase2_close_rt031_line8_31_trips_v3 import sources, PATTERNS, PEAKS, AUTH, OUTPUT as TIMETABLE, digest
from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import inputs, BASE, FS, VIRTUAL, NORTH
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
from scripts.phase2_probe_rt031_line8_free_orders_v3 import reversal_indices
from scripts.phase2_probe_rt031_line8_retention_tradeoffs_v3 import load_access, MUNICIPALITY_NAMES
from scripts.phase2_probe_rt031_line8_stop_relocation_v3 import inventory_times, ratios
from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import events_by_site, uncovered_intervals, minimum_blocks, FLAGS
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter

OUTPUT=BASE/'stop_plan_and_additions.json.gz'
SHAPE=BASE/'stop_plan_and_additions.geojson'
EXAMPLES=BASE/'stop_addition_examples.json'


def read_result():
    return json.loads(gzip.decompress(OUTPUT.read_bytes()))


def write_result(result):
    payload=(json.dumps(result,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')
    OUTPUT.write_bytes(gzip.compress(payload,mtime=0))


def example_proofs(result,loops,edges,p,timetable,ids):
    """Portable, independently replayable ordered events and full vehicle grid.

    Explicit example IDs are presentation choices, not automatic stop adoption.
    """
    rows={c['candidate_id']:c for c in result['single_additions']}
    selections=[[i] for i in ids]+([ids] if len(ids)>1 else [])
    proofs=[]
    for selected in selections:
        revised=loops
        for cid in selected:revised=add_site(revised,rows[cid]['node_id'],edges)
        scenarios=[]
        for moving,dwell in p['adjusted']:
            adjusted=adjusted_loops(revised,moving,dwell)
            for recovery in (5,10,15):
                scenarios.append({'moving_multiplier':moving,'dwell_min':dwell,'recovery_min':recovery,
                    **minimum_blocks(timetable['trips'],adjusted,p['family']['joins'],recovery)})
        proofs.append({'candidate_ids':selected,'added_events_by_pattern':{
            pat:[e for e in loop['events'] if e['stop_place_id'].startswith('PROXY::RT031_ADDITIONAL::')]
            for pat,loop in revised.items()},'timing':timing_check(revised,p,timetable),
            'conditional_scenarios':scenarios,'boarding_authorised':False})
    return {'source_sha256_normalized_newlines':result['source_sha256_normalized_newlines'],
            'road_and_walk_source_sha256':result['road_and_walk_source_sha256'],
            'examples':proofs,'selected_stop_additions':[],
            'scope':'Illustrative points only. Replay against pinned base loops; no new service selection or physical approval.'}


def coordinate(node,nodes):
    return [float(nodes[node]['lon']),float(nodes[node]['lat'])]


def hub_boundaries(loops):
    return [{'pattern':pat,'path_node_index':index,'service_role':role,
             'occurrence_id':f'{pat}:{index}:{FS}:{role}',
             'physical_platform_side':None,'boarding_authorised':False,
             'cross_wing_passenger_continuity_certified':False}
            for pat,loop in loops.items()
            for index,role in ((0,'BOARD_DEPARTURE'),(len(loop['edge_ids']),'ALIGHT_ARRIVAL'))]


def road_context(path):
    """Observed snapshot tags only, not current kerb/road legality."""
    ways={};points={}
    for _,el in ET.iterparse(path,events=('end',)):
        if el.tag=='node':
            points[el.attrib['id']]=[float(el.attrib['lon']),float(el.attrib['lat'])];el.clear()
        elif el.tag=='way':
            tags={t.attrib['k']:t.attrib['v'] for t in el.findall('tag')}
            if 'highway' in tags:
                ways[el.attrib['id']]={'tags':tags,'nodes':[x.attrib['ref'] for x in el.findall('nd')]}
            el.clear()
        elif el.tag=='relation':el.clear()
    return ways,points


def bounded_walk(context,lat,lon):
    """Exact at the declared <=10-minute thresholds; farther distances unknown.

    All connectors are nonnegative. A road-network distance >800m cannot yield
    a <=10-minute total journey at the inherited 80m/min walking speed.
    """
    graph=context['graph'];snap=graph.snap(lat,lon)
    if snap.status!='REACHABLE' or not snap.node_id: raise ValueError('unreachable walk attachment')
    distances={snap.node_id:0.};queue=[(0.,snap.node_id)]
    while queue:
        distance,node=heapq.heappop(queue)
        if distance!=distances[node]:continue
        for other,length in graph.reverse_adjacency.get(node,[]):
            if length<0:raise ValueError('negative walking edge')
            value=distance+length
            if value<=800 and value<distances.get(other,math.inf):
                distances[other]=value;heapq.heappush(queue,(value,other))
    times=[]
    for unit in context['units']:
        row=context['snap_map'][unit];connector=float(row['population_connector_distance_m'])
        if connector<0 or snap.connector_distance_m<0:raise ValueError('negative connector')
        times.append((connector+distances.get(str(row['population_snap_node_id']),math.inf)+snap.connector_distance_m)/80)
    return np.array(times),{'status':snap.status,'graph_node_id':snap.node_id,
                            'connector_distance_m':round(float(snap.connector_distance_m),3),
                            'distance_domain':'Exact <=10-minute threshold screen, not full walking-time matrix'}


def add_site(loops,node,edges):
    if any(edges[e['incoming_edge']]['v_node_id']==node for loop in loops.values() for e in loop['events']):
        raise ValueError('road node already has a service event; cannot count it as an additional site')
    out=copy.deepcopy(loops);sid='PROXY::RT031_ADDITIONAL::'+node
    for pattern,loop in out.items():
        elapsed=0
        for index,eid in enumerate(loop['edge_ids'],1):
            edge=edges[eid];elapsed+=float(edge['running_minutes_model'])
            if edge['v_node_id']==node and index<len(loop['edge_ids']):
                loop['events'].append({'stop_place_id':sid,'name':'Ipotesi aggiuntiva '+node,
                    'site_status':'NEW_ON_PATH_SITE_NOT_APPROVED','path_node_index':index,
                    'incoming_edge':eid,'outgoing_edge':loop['edge_ids'][index],
                    'occurrence_id':f'{pattern}:{index}:{sid}','offset_from_wing_origin_min':elapsed,
                    'boarding_authorised':False,'passenger_continuity_certified':False})
        loop['events'].sort(key=lambda e:(e['path_node_index'],e['stop_place_id']))
    if not any(e['stop_place_id']==sid for loop in out.values() for e in loop['events']):
        raise ValueError('hypothesis not on operated path')
    return out


def timing_check(loops,p,timetable):
    """Rebuild timing and rail eligibility; never reuse pre-addition anchors."""
    failures=Counter();margins=[];grids={};targets={}
    for a in p['anchors']: targets[a['wing'],a['kind'],a['rail_min']]=None
    for moving,dwell in p['adjusted']:
        adjusted=adjusted_loops(loops,moving,dwell);grids[moving,dwell]=adjusted
        service=copy.deepcopy(adjusted)
        for loop in service.values():
            latest={e['stop_place_id']:max(x['path_node_index'] for x in loop['events'] if x['stop_place_id']==e['stop_place_id'])
                    for e in loop['events'] if e['stop_place_id'].startswith('PROXY::RT031_ADDITIONAL::')}
            loop['events']=[e for e in loop['events'] if e['stop_place_id'] not in latest or e['path_node_index']==latest[e['stop_place_id']]]
        opportunities=events_by_site(timetable['trips'],service)
        for (sid,direction),ev in opportunities.items():
            pattern=timetable['trips'][ev[0][0]]['loop'];times=[t for _,t in ev]
            for peak in PEAKS:
                if uncovered_intervals(times,peak['start_min'],peak['end_min'],30): failures['H30_SITE_DIRECTION_SCENARIO']+=1
            if uncovered_intervals(times,390,1180,timetable['wait_limit_min_by_pattern'][pattern]): failures['OFFPEAK_SITE_DIRECTION_SCENARIO']+=1
            for start,end in ((390,420),(1135,1180)):
                if uncovered_intervals(times,start,end,60): failures['EDGE_H60_SITE_DIRECTION_SCENARIO']+=1
    rail_fail=[];bindings=[]
    for wing,kind,minute in targets:
        pattern=next(x for x in PATTERNS if x.startswith(wing))
        candidates=[]
        for i,t in enumerate(timetable['trips']):
            if t['loop']!=pattern: continue
            residual=[minute-t['departure_min']-g[pattern]['road_minutes']-3 for g in grids.values()]
            if kind=='bus_to_rail':
                compatible=all(-1e-8<=v<=p['wait_ceiling']+1e-8 for v in residual)
            else:compatible=3<=t['departure_min']-minute<=8
            if compatible:candidates.append(i)
        if not candidates:rail_fail.append({'wing':wing,'kind':kind,'rail_min':minute})
        for sid in sorted({e['stop_place_id'] for e in loops[pattern]['events']}):
            bindings.append({'stop_place_id':sid,'kind':kind,'rail_min':minute,'eligible_trip_indices':candidates})
        if kind=='bus_to_rail':
            # Maximum attainable minimum margin among trips; independent of upper residual ceiling.
            margins.append(max((min(minute-t['departure_min']-g[pattern]['road_minutes']-3 for g in grids.values())
                               for t in timetable['trips'] if t['loop']==pattern and t['departure_min']<=minute
                               and all(minute-t['departure_min']-g[pattern]['road_minutes']-3<=p['wait_ceiling']+1e-8 for g in grids.values())),default=-math.inf))
    nominal=minimum_blocks(timetable['trips'],grids[1.1,.5],p['family']['joins'],10)['minimum_vehicle_count_conditional']
    if nominal>4:failures['NOMINAL_FLEET']+=1
    if rail_fail:failures['RAIL_TARGET']+=len(rail_fail)
    rides=[]
    for pat,loop in grids[1.1,.5].items():
        for sid in sorted({e['stop_place_id'] for e in loop['events'] if e['stop_place_id'].startswith('PROXY::RT031_ADDITIONAL::')}):
            own=[e for e in loop['events'] if e['stop_place_id']==sid]
            first=min(own,key=lambda e:e['path_node_index']);last=max(own,key=lambda e:e['path_node_index'])
            rides.append({'site_id':sid,'pattern':pat,'from_fs_alighting_occurrence_id':first['occurrence_id'],
                          'to_fs_boarding_occurrence_id':last['occurrence_id'],
                          'from_fs_min':first['offset_from_wing_origin_min']-.5,'to_fs_min':loop['road_minutes']-last['offset_from_wing_origin_min']})
    return {'fixed_31_timetable_pass':not failures,'failure_counts':dict(failures),'failed_rail_targets':rail_fail,
            'nominal_vehicle_count':nominal,'smallest_AM_residual_min_after_3min_transfer':min(margins),
            'per_site_rail_check_count':len(bindings),
            'extra_nominal_running_and_dwell_min':{pat:grids[1.1,.5][pat]['road_minutes']-p['adjusted'][1.1,.5][pat]['road_minutes'] for pat in PATTERNS},
            'extra_stress_running_and_dwell_min':{pat:grids[1.1,1.][pat]['road_minutes']-p['adjusted'][1.1,1.][pat]['road_minutes'] for pat in PATTERNS},
            'new_site_nominal_rides':rides,'retiming_attempted':False,'physical_boarding_certified':False}


def nondominated(cases):
    """15 territorial gain axes and per-wing dwell counts; no scalar score."""
    feasible=[c for c in cases if c['timing']['fixed_31_timetable_pass'] and any(v>0 for v in c['gain_weight_vector'])]
    vectors={c['candidate_id']:c['gain_weight_vector']+[-c['added_event_counts'][p] for p in PATTERNS] for c in feasible}
    return sorted(k for k,v in vectors.items() if not any(j!=k and all(a>=b for a,b in zip(w,v)) and any(a>b for a,b in zip(w,v)) for j,w in vectors.items()))


def build(graph_dir,walk_dir):
    p=sources();timetable=json.loads(TIMETABLE.read_text(encoding='utf-8'))
    paths=inputs(graph_dir)
    paths.update(matrix=walk_dir/'output/rt028_population_unit_stop_walk_matrix_v3.csv',
                 pedestrian_osm=walk_dir/'input/rt028_osm_pedestrian_snapshot_v3.osm',
                 candidates_normalized=paths['candidates_normalized_newlines'],
                 road_screen=BASE.parent/'rt031_unique_line_road_screen_v3/screen.json',
                 access_reference=BASE/'brivio_existing_sites_walk.json')
    edges,nodes,rules,attachments=build_graph(paths)
    oldshape=json.loads((BASE/'local_counterflow.geojson').read_text(encoding='utf-8'))
    lon,lat=next(f['geometry']['coordinates'] for f in oldshape['features'] if f['geometry']['type']=='Point' and f['properties']['site_id']==VIRTUAL)
    nodes[VIRTUAL]={'lon':lon,'lat':lat,'osm_node_id':None}
    loops={pat:p['family']['loops'][pat] for pat in PATTERNS}
    sites={FS:{'node':attachments[FS]['graph_node_id'],'name':'Olgiate-Calco-Brivio FS','events':[]}}
    for pattern,loop in loops.items():
        for event in loop['events']:
            node=edges[event['incoming_edge']]['v_node_id']
            row=sites.setdefault(event['stop_place_id'],{'node':node,'name':event['name'],'events':[]})
            if row['node']!=node: raise ValueError('site bound to ambiguous road nodes')
            row['events'].append({**event,'pattern':pattern})
    if len(sites)!=28: raise ValueError('accepted site inventory changed')
    access,baseline,supported,context=load_access(paths,sites,include_context=True)
    before=inventory_times(sites,context)
    ways,osm_points=road_context(paths['pedestrian_osm'])
    number={sid:i for i,sid in enumerate(sites,1)}
    register=[]
    for sid,s in sites.items():
        inv=attachments.get(sid);ev=[]
        for e in s['events']:
            pat=e['pattern'];same=[x for x in s['events'] if x['pattern']==pat]
            row={k:e[k] for k in ('pattern','occurrence_id','path_node_index','incoming_edge','outgoing_edge')}
            first=min(x['path_node_index'] for x in same);last=max(x['path_node_index'] for x in same)
            row.update(from_fs_earliest_alighting=e['path_node_index']==first,to_fs_latest_boarding=e['path_node_index']==last,
                       physical_platform_side=None,boarding_authorised=False,
                       incoming_osm_way_id=edges[e['incoming_edge']]['osm_way_id'],
                       outgoing_osm_way_id=edges[e['outgoing_edge']]['osm_way_id'] if e['outgoing_edge'] else None)
            ev.append(row)
        register.append({'number':number[sid],'site_id':sid,'name':s['name'],'graph_node_id':s['node'],
                         'road_coordinates':coordinate(s['node'],nodes),
                         'inventory_coordinates':[float(inv['lon']),float(inv['lat'])] if inv else None,
                         'status':'INVENTORY_SITE_PLATFORM_UNVERIFIED' if inv else 'PROPOSED_LOCAL_SITE_NOT_APPROVED',
                         'source_families':inv['source_families'] if inv else 'PRIOR_USER_LOCALITY_REQUIREMENT_AND_ROAD_PROXY',
                         'known_routes':inv['known_routes'].split('|') if inv else [],
                         'graph_attachment_distance_m':float(inv['attachment_distance_m']) if inv else None,
                         'municipality':inv['municipality'] if inv else 'Olgiate Molgora',
                         'occurrences':ev,'hub_boundary_events':hub_boundaries(loops) if sid==FS else [],
                         'platform_count':None,'physical_platform_side':None,
                         'pedestrian_accessibility_on_field':None,'boarding_authorised':False})
    adapter=FrozenRT017ViaNodeAdapter(edges.values(),rules,unresolved_external_via_way_count=2)
    manoeuvres=[]
    for pat,loop in loops.items():
        for i in reversal_indices(loop['edge_ids'],edges):
            inc,out=loop['edge_ids'][i-1:i+1];node=edges[out]['u_node_id'];way=edges[out]['osm_way_id']
            manoeuvres.append({'id':f'M{len(manoeuvres)+1}','pattern':pat,'path_node_index':i,'node_id':node,
                'coordinates':coordinate(node,nodes),'site_numbers':[number[sid] for sid,s in sites.items() if s['node']==node],
                'incoming_edge':inc,'outgoing_edge':out,'osm_way_id':way,
                'street_name_in_snapshot':ways.get(way,{}).get('tags',{}).get('name'),
                'highway':edges[out]['highway'],'represented_via_node_allowed':adapter.decision((inc,),out)['allowed'] is True,
                'road_uncertainty_flags':edges[out]['uncertainty_flags'].split('|'),
                'evidence':'Immediate reversal of adjacent graph edges; not evidence of a bus-sized turnaround.',
                'status':'FIELD_AND_VEHICLE_SWEEP_CHECK_REQUIRED','bus_manoeuvre_authorised':False})
    if len(manoeuvres)!=6: raise ValueError('manoeuvre inventory changed')
    covered_nodes={s['node'] for s in sites.values()}
    node_patterns=defaultdict(set)
    for pat,loop in loops.items():
        for eid in loop['edge_ids']:node_patterns[edges[eid]['v_node_id']].add(pat)
    candidates=sorted(set(node_patterns)-covered_nodes)
    print(f'Register: {len(register)} sites, {len(manoeuvres)} manoeuvres; {len(candidates)} on-path candidate nodes',flush=True)
    cases=[];walk_cache={};gain_masks={}
    denominators={c:sum(context['weights'][i] for i in np.flatnonzero(context['core']&(context['codes']==c))) for c in MUNICIPALITY_NAMES}
    for index,node in enumerate(candidates):
        coords=coordinate(node,nodes)
        times,snap=bounded_walk(context,coords[1],coords[0])
        walk_cache[node]=times
        masks={t:context['core']&(before>t)&(times<=t) for t in (5,8,10)};gain_masks[node]=masks
        vector=[sum(context['weights'][i] for i in np.flatnonzero(masks[t]&(context['codes']==c))) for c in MUNICIPALITY_NAMES for t in (5,8,10)]
        revised=add_site(loops,node,edges)
        added={pat:len({e['path_node_index'] for e in revised[pat]['events']})-len({e['path_node_index'] for e in loops[pat]['events']}) for pat in PATTERNS}
        timing=timing_check(revised,p,timetable)
        ways_here=sorted({edges[e]['osm_way_id'] for pat in node_patterns[node] for e in loops[pat]['edge_ids'] if edges[e]['v_node_id']==node})
        names=sorted({ways[w]['tags']['name'] for w in ways_here if w in ways and 'name' in ways[w]['tags']})
        nearest=min(register,key=lambda s:(s['road_coordinates'][0]-coords[0])**2*math.cos(math.radians(coords[1]))**2+(s['road_coordinates'][1]-coords[1])**2)
        row={'candidate_id':f'N{index+1:04d}','node_id':node,'coordinates':coords,'patterns':sorted(node_patterns[node]),
             'street_names_in_snapshot':names,'osm_way_ids':ways_here,'nearest_reference_site_number':nearest['number'],
             'nearest_reference_site_name':nearest['name'],'pedestrian_snap':snap,'gain_weight_vector':vector,
             'potential_access_gain_pp':{c:{str(t):100*float(Fraction(vector[j*3+k],denominators[c])) for k,t in enumerate((5,8,10))} for j,c in enumerate(MUNICIPALITY_NAMES)},
             'added_event_counts':added,'extra_service_km':0,'timing':timing,
             'physical_suitability_certified':False,'boarding_authorised':False}
        cases.append(row)
        if (index+1)%100==0: print(f'Additional stops screened: {index+1}/{len(candidates)}',flush=True)
    frontier=nondominated(cases)
    frontier_cases=[c for c in cases if c['candidate_id'] in frontier]
    print(f'Singles complete: {len(frontier_cases)} nondominated hypotheses; evaluating distinct coverage/dwell pairs',flush=True)
    for row in frontier_cases:
        row['potential_access_fraction']=ratios(np.minimum(before,walk_cache[row['node_id']]),context)
    # Keep all mutually nondominated single additions; assess pairs only among these.
    # Equivalent screened population masks/dwell counts remain distinct locations.
    # Canonical representatives only bound the pair comparison, not stop selection.
    groups=defaultdict(list)
    for c in frontier_cases:
        signature=tuple(gain_masks[c['node_id']][t].tobytes() for t in (5,8,10))+tuple(c['added_event_counts'][p] for p in PATTERNS)
        groups[signature].append(c)
    representatives=[v[0] for v in groups.values()]
    pairs=[]
    for i,a in enumerate(representatives):
        for b in representatives[i+1:]:
            combined=add_site(add_site(loops,a['node_id'],edges),b['node_id'],edges)
            timing=timing_check(combined,p,timetable)
            after=np.minimum(before,np.minimum(walk_cache[a['node_id']],walk_cache[b['node_id']]))
            pairs.append({'candidate_ids':[a['candidate_id'],b['candidate_id']],
                'potential_access_fraction':ratios(after,context),'timing':timing,'extra_service_km':0,
                'boarding_authorised':False})
        if i%10==0:print(f'Pair representatives: {i+1}/{len(representatives)}',flush=True)
    result={'contract':'RT031_ACCEPTED_31_TRIP_STOP_PLAN_AND_STRATEGIC_ADDITIONS_V3',
            'source_sha256_normalized_newlines':{'timetable':digest(TIMETABLE),'authority31':digest(AUTH),
              'geometry_confirmation':digest(Path(p['authority']['geometry_confirmation_source'])),
              'counterflow':digest(BASE/'local_counterflow.json')},
            'road_and_walk_source_sha256':{k:digest(v) for k,v in paths.items() if k in ('edges','nodes','rules','attachments','matrix','pedestrian_osm')},
            'register':register,'manoeuvres':manoeuvres,'baseline_potential_access_fraction':baseline,
            'municipality_names':MUNICIPALITY_NAMES,'candidate_node_count':len(candidates),'single_additions':cases,
            'single_addition_spatial_dwell_frontier_ids':frontier,'pair_comparisons':pairs,
            'pair_representative_groups':[[c['candidate_id'] for c in v] for v in groups.values()],
            'scope':'Every currently unserved vertex of the two accepted road paths, single-site additions; pairs only among canonical representatives of identical gained population sets and per-wing dwell counts on the fixed-timetable-passing spatial/dwell frontier of singles. Equivalent coverage does not certify equivalent platform safety or combined timing; every representative pair is separately checked. This is not all continuous kerb positions, off-route sites or all pairs; no minimum benefit threshold or scalar territorial weights.',
            'walk_semantics':'Pinned population units and walking graph, 5/8/10-minute access and hypothetical connectors. Potential spatial access, not route passenger demand, trip forecasts or field-safe footpaths.',
            'timing_semantics':'Keep every one of the approved 31 departures. Added dwell at each actual new road-node occurrence, nine timing cases, rebuilt per-site rail checks and nominal fleet. A failure means this exact unchanged timetable needs work, not that the location is inherently impossible. No new stops adopted.',
            'geometry_changed':False,'approved_stop_additions':0,'annual_service_km':timetable['annual_service_km'],
            'platforms_certified':False,'full_history_road_legality_certified':False,
            'actual_timetable_certified':False,'decision_budget_km':None,'uncertainty_band_min':None,**{k:False for k in FLAGS}}
    features=[]
    for pat,loop in loops.items():
        vertices=[edges[loop['edge_ids'][0]]['u_node_id']]+[edges[e]['v_node_id'] for e in loop['edge_ids']]
        features.append({'type':'Feature','properties':{'kind':'route','pattern':pat},'geometry':{'type':'LineString','coordinates':[coordinate(n,nodes) for n in vertices]}})
    for s in register:features.append({'type':'Feature','properties':{'kind':'site',**s},'geometry':{'type':'Point','coordinates':s['road_coordinates']}})
    for m in manoeuvres:features.append({'type':'Feature','properties':{'kind':'manoeuvre',**m},'geometry':{'type':'Point','coordinates':m['coordinates']}})
    for c in frontier_cases:features.append({'type':'Feature','properties':{'kind':'candidate',**c},'geometry':{'type':'Point','coordinates':c['coordinates']}})
    coords=[s['road_coordinates'] for s in register];xmin=min(x for x,y in coords)-.003;xmax=max(x for x,y in coords)+.003;ymin=min(y for x,y in coords)-.003;ymax=max(y for x,y in coords)+.003
    for wid,w in ways.items():
        coords=[osm_points[n] for n in w['nodes'] if n in osm_points]
        if len(coords)>1 and all(xmin<=x<=xmax and ymin<=y<=ymax for x,y in coords):
            features.append({'type':'Feature','properties':{'kind':'context_road','osm_way_id':wid,'name':w['tags'].get('name'), 'highway':w['tags']['highway']},'geometry':{'type':'LineString','coordinates':coords}})
    return result,{'type':'FeatureCollection','features':features}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--graph_dir',type=Path,required=True);parser.add_argument('--walk_dir',type=Path,required=True)
    args=parser.parse_args();result,shape=build(args.graph_dir,args.walk_dir)
    write_result(result)
    SHAPE.write_text(json.dumps(shape,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print(json.dumps({'sites':len(result['register']),'candidates':result['candidate_node_count'],'frontier':len(result['single_addition_spatial_dwell_frontier_ids']),'pairs':len(result['pair_comparisons'])}))
