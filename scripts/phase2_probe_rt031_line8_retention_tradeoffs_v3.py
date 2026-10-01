"""Small explicit site-retention relaxations; territorial access is not demand.

Bounded domain: omit zero, one, or two consecutive distinct inventory sites on
each wing, preserving both local anchors and every other original visit order.
"""
import argparse
from collections import Counter
from fractions import Fraction
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from phase2_final_stop_pedestrian_accessibility_substrate_v3 import parse_osm_pedestrian_graph
from phase2_rt029_v4_substrate import validate_walk_matrix
from scripts.phase2_audit_rt031_conditional_new_stop_access_v3 import scaled_core_weights, weighted_ratio
from scripts.phase2_audit_rt031_unique_line_walk_access_v3 import EXPECTED as WALK_EXPECTED, pedestrian_time, sha256
from scripts.phase2_build_rt031_municipal_access_frontier_v4 import MUNICIPALITY_NAMES
from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import inputs, BASE, FLAGS, endpoint_variant, site_rides
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
from scripts.phase2_audit_rt031_south_road_probe_v3 import FS, VIRTUAL, digest, rows
from scripts.phase2_export_rt031_line8_inclusive_shape_v3 import NORTH
from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops
from scripts.phase2_audit_rt031_line8_independent_wings_v3 import minimum_blocks
from scripts.phase2_probe_rt031_line8_local_split_v3 import gaps
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter


def removal_domain(loop):
    sequence=[]
    for e in sorted(loop['events'],key=lambda e:e['path_node_index']):
        sid=e['stop_place_id']
        if sid not in (FS,VIRTUAL,NORTH) and sid not in sequence:
            sequence.append(sid)
    return [()] + [(s,) for s in sequence] + [tuple(sorted(pair)) for pair in zip(sequence,sequence[1:])]


def load_access(paths, sites, include_context=False):
    for k in ('matrix','pedestrian_osm','candidates_normalized'):
        if sha256(paths[k],k=='candidates_normalized')!=WALK_EXPECTED[k]:
            raise ValueError('pedestrian source drift: '+k)
    columns=['population_unit_id','population_weight_2025','population_scope','population_municipality_code',
        'population_municipality_name','stop_place_id','stop_service_class','walk_time_min','reachability_status',
        'population_snap_node_id','population_connector_distance_m']
    raw=pd.read_csv(paths['matrix'],usecols=columns,dtype={k:str for k in ('population_unit_id','population_weight_2025',
        'population_municipality_code','stop_place_id','population_snap_node_id')})
    raw['population_municipality_code']=raw['population_municipality_code'].map(lambda v:str(int(v)))
    snaps=raw[['population_unit_id','population_weight_2025','population_snap_node_id','population_connector_distance_m']].drop_duplicates()
    if snaps['population_unit_id'].duplicated().any():
        raise ValueError('ambiguous population metadata')
    snap_map=snaps.set_index('population_unit_id')[['population_snap_node_id','population_connector_distance_m']].to_dict('index')
    substrate=validate_walk_matrix(raw)
    units=substrate.population_meta['population_unit_id'].astype(str).tolist()
    if set(units)!=set(snap_map):
        raise ValueError('population universe drift')
    core,weights=scaled_core_weights(substrate,snaps.set_index('population_unit_id')['population_weight_2025'].to_dict())
    codes=substrate.population_meta['population_municipality_code'].astype(str).to_numpy()
    graph=parse_osm_pedestrian_graph(paths['pedestrian_osm'])
    if graph.graph_digest!='aaad8a16e4c3715161cce6f686acccbf29e4e9def57424e8ad02594c9a69f1f4':
        raise ValueError('pedestrian graph drift')
    south=next(r for r in rows(paths['candidates_normalized']) if r['candidate_id']=='P2V2S_0031')
    road=json.loads(paths['road_screen'].read_text(encoding='utf-8'))
    reference=json.loads(paths['access_reference'].read_text(encoding='utf-8'))
    if (road['contract']!='RT031_UNIQUE_LINE_ROAD_SCREEN_V3'
            or road['north_proxy']['boarding_stop_certified'] is not False
            or road['north_proxy']['graph_node_id']!=sites[NORTH]['node']
            or reference['source_sha256']['road_screen']!=sha256(paths['road_screen'],True)):
        raise ValueError('hypothetical north site drift')
    a,_=pedestrian_time(graph,snap_map,units,float(south['lat']),float(south['lon']))
    b,_=pedestrian_time(graph,snap_map,units,float(road['north_proxy']['lat']),float(road['north_proxy']['lon']))
    local=np.minimum(a,b)
    cache={}
    def access(ids):
        key=tuple(sorted(set(ids)-{VIRTUAL,NORTH}))
        if key not in cache:
            if not key or any(s not in substrate.stop_index for s in key):
                raise ValueError('site not in pinned walk matrix')
            t=np.minimum(substrate.walk_time_matrix[:,[substrate.stop_index[s] for s in key]].min(axis=1),local)
            cache[key]={code:{str(limit):str(weighted_ratio(t<=limit,weights,core if code=='TOTAL' else core & (codes==code)))
                        for limit in (5,8,10)} for code in ('TOTAL',*MUNICIPALITY_NAMES)}
        return cache[key]
    baseline=access(set(sites))
    certified=reference['all_reference_contextual_potential_access']
    if baseline!={k:v['potential_walking_access_fraction'] for k,v in certified.items()}:
        raise ValueError('full-retention coverage does not reproduce upstream reference')
    supported={r.stop_place_id for r in raw[['stop_place_id','stop_service_class']].drop_duplicates().itertuples(index=False)
               if r.stop_service_class=='CONVENTIONAL_TPL'}
    if include_context:
        return access,baseline,supported,dict(substrate=substrate, local=local,
            graph=graph, snap_map=snap_map, units=units, weights=weights, core=core, codes=codes)
    return access,baseline,supported


def scenario_check(loops,trips,joins,targets):
    result=[]
    for m,d in itertools.product((.9,1,1.1),(0,.5,1)):
        adjusted=adjusted_loops(loops,m,d)
        gap=max(r['max_optimistic_identity_gap_min'] for r in gaps(trips,adjusted))
        margin=min(target-t['departure_min']-adjusted[p]['road_minutes']-3
                   for p in ('west_A','east_B') for target,t in zip(targets,sorted((t for t in trips if t['loop']==p),key=lambda t:t['departure_min'])))
        for recovery in (5,10,15):
            result.append({'moving_multiplier':m,'dwell_min':d,'max_optimistic_identity_gap_min':gap,
                'smallest_morning_target_margin_min':margin,**minimum_blocks(trips,adjusted,joins,recovery)})
    return result


def build(paths):
    source=json.loads(paths['counterflow'].read_text(encoding='utf-8'))
    if source['contract']!='RT031_LINE8_LOCAL_COUNTERFLOW_ROAD_COMPARISON_V3' or any(source[k] for k in ('network_selected','primary_selection_authorised','runner_up_selection_authorised')):
        raise ValueError('unsupported or decisional counterflow source')
    road_paths=inputs(paths['edges'].parent.parent)
    for k,p in road_paths.items():
        if source['source_sha256'][k]!=digest(p,k not in ('edges','nodes','rules','attachments','successor')):
            raise ValueError('counterflow source drift: '+k)
    wings=json.loads(paths['wings'].read_text(encoding='utf-8'))
    timetable=json.loads(paths['timetable'].read_text(encoding='utf-8'))
    edges,nodes,rules,attachments=build_graph(paths)
    fs=attachments[FS]['graph_node_id']
    sites={FS:{'node':fs,'name':'Olgiate FS','status':'INVENTORY_NOT_APPROVED'}}
    for loop in wings['loops'].values():
        for e in loop['events']:
            sites[e['stop_place_id']]={'node':edges[e['incoming_edge']]['v_node_id'],'name':e['name'],'status':e['site_status']}
    reference_ids=set(sites)
    access,baseline,supported=load_access(paths,sites)
    for sid in sorted(supported-reference_ids):
        row=attachments.get(sid)
        if row and row['route_ready']=='True' and row['service_class']=='CONVENTIONAL_TPL':
            sites[sid]={'node':row['graph_node_id'],'name':row['stop_name'],'status':'ADDITIONAL_EXISTING_INVENTORY_NOT_BOARDING_APPROVED'}
    counts=Counter(t['loop'] for t in timetable['trips'])
    variants={}
    for wing,first in (('west','west_A'),('east','east_B')):
        variants[wing]=[]
        for index,omit in enumerate(removal_domain(wings['loops'][first])):
            pair={}
            for name,loop in wings['loops'].items():
                if name.startswith(wing):
                    reduced={**loop,'events':[e for e in loop['events'] if e['stop_place_id'] not in omit]}
                    pair[name]=endpoint_variant(name,reduced,edges,rules,sites,fs)
            seen=set.intersection(*({e['stop_place_id'] for e in r['events']} for r in pair.values()))|{FS}
            variants[wing].append({'variant_id':f'{wing}_{index:02d}','omitted_required_ids':list(omit),'loops':pair,
                'both_patterns_seen_ids':sorted(seen),
                'annual_wing_service_km':sum(pair[p]['distance_m']*counts[p] for p in pair)/1000*260})
        print(f'{wing}: {len(variants[wing])} road variants built',flush=True)
    cases=[]
    for west,east in itertools.product(variants['west'],variants['east']):
        seen=set(west['both_patterns_seen_ids'])|set(east['both_patterns_seen_ids'])
        cover=access(seen)
        cases.append({'case_id':west['variant_id']+'+'+east['variant_id'],
            'annual_service_km':west['annual_wing_service_km']+east['annual_wing_service_km'],
            'lost_original_site_ids':sorted(reference_ids-seen),'retained_site_count':len(seen & reference_ids),
            'gained_inventory_site_ids':sorted(seen-reference_ids),'served_site_count':len(seen),
            'potential_access_fraction':cover,
            'potential_access_change_pp':{c:{t:100*float(Fraction(cover[c][t])-Fraction(baseline[c][t])) for t in ('5','8','10')} for c in baseline}})
    # No normative municipal loss threshold. Keep every case; identify exact
    # all-metric equal-or-better territorial access comparisons separately.
    same_access=[c for c in cases if all(Fraction(c['potential_access_fraction'][code][t])>=Fraction(baseline[code][t])
                                       for code in MUNICIPALITY_NAMES for t in ('5','8','10'))]
    # Store the finite frontier without deleting evidence or calling it an
    # operating frontier: runtime/fleet are NOT part of this preliminary filter.
    dimensions={c['case_id']:[-c['annual_service_km']]+[Fraction(c['potential_access_fraction'][m][t]) for m in MUNICIPALITY_NAMES for t in ('5','8','10')] for c in cases}
    losses={c['case_id']:set(c['lost_original_site_ids']) for c in cases}
    frontier=[]
    for c in cases:
        key=c['case_id']; dim=dimensions[key]; lost=losses[key]
        if not any(losses[o['case_id']]<=lost and all(x>=y for x,y in zip(dimensions[o['case_id']],dim))
                   and (losses[o['case_id']]<lost or any(x>y for x,y in zip(dimensions[o['case_id']],dim))) for o in cases if o is not c):
            frontier.append(key)
    # Audit all cases that reach the unchanged cap, plus explicit diagnostic
    # witnesses of the minimum distance and unchanged-access minimum distance.
    audit_ids={c['case_id'] for c in cases if c['annual_service_km']<=timetable['reference_cap_unchanged']}
    least=min(cases,key=lambda c:(c['annual_service_km'],c['case_id']))
    unchanged=min(same_access,key=lambda c:(c['annual_service_km'],c['case_id']))
    audit_ids.update((least['case_id'],unchanged['case_id'],'west_00+east_00'))
    adapter=FrozenRT017ViaNodeAdapter(edges.values(),rules,unresolved_external_via_way_count=2)
    lookup={r['variant_id']:r for values in variants.values() for r in values}
    checks=[]
    for cid in sorted(audit_ids):
        w,e=cid.split('+'); loops={**lookup[w]['loops'],**lookup[e]['loops']}
        joins={a+'>'+b:adapter.decision((ra['edge_ids'][-1],),rb['edge_ids'][0])['allowed'] is True for a,ra in loops.items() for b,rb in loops.items()}
        trip_list=source['full_correction_one_minute_retiming']['trips']
        adjusted=adjusted_loops(loops,1.1,.5)
        checks.append({'case_id':cid,'reason':'Reference-cap cases or unselected illustrative minima',
            'scenarios':scenario_check(loops,trip_list,joins,timetable['new_morning_train_targets_min']),
            'local_rides_nominal':[{'pattern':p,'site_id':s,**site_rides(loop,s,.5)}
                for p,loop in adjusted.items() for s in (VIRTUAL,NORTH) if any(e['stop_place_id']==s for e in loop['events'])]})
    coords={n:[float(v['lon']),float(v['lat'])] for n,v in nodes.items()}
    south=next(r for r in rows(paths['candidates_normalized_newlines']) if r['candidate_id']=='P2V2S_0031')
    coords[VIRTUAL]=[float(south['lon']),float(south['lat'])]
    features=[]
    for cid in sorted(audit_ids):
        w,e=cid.split('+')
        for p,loop in {**lookup[w]['loops'],**lookup[e]['loops']}.items():
            vertex=[edges[loop['edge_ids'][0]]['u_node_id']]+[edges[e]['v_node_id'] for e in loop['edge_ids']]
            features.append({'type':'Feature','properties':{'case_id':cid,'pattern':p,'boarding_authorised':False},
                             'geometry':{'type':'LineString','coordinates':[coords[n] for n in vertex]}})
    for sid,site in sites.items():
        features.append({'type':'Feature','properties':{'site_id':sid,**site,'original_reference_site':sid in reference_ids,'boarding_authorised':False},
                         'geometry':{'type':'Point','coordinates':coords[site['node']]}})
    result={'contract':'RT031_LINE8_SMALL_RETENTION_RELAXATIONS_V3','status':'BOUNDED_NON_DECISIONAL_COMPARISON',
        'source_sha256':{k:digest(p,k not in ('edges','nodes','rules','attachments','successor','matrix','pedestrian_osm')) for k,p in paths.items()},
        'variants':variants,'cases':cases,'preliminary_road_access_frontier_ids':frontier,
        'baseline_potential_access_fraction':baseline,'municipality_names':MUNICIPALITY_NAMES,
        'original_reference_site_ids':sorted(reference_ids),'additional_supported_inventory_ids':sorted(set(sites)-reference_ids),
        'minimum_distance_case_id':least['case_id'],'minimum_distance_unchanged_access_case_id':unchanged['case_id'],
        'reference_cap_case_count':sum(c['annual_service_km']<=timetable['reference_cap_unchanged'] for c in cases),
        'conditional_operating_checks':checks,'trips':source['full_correction_one_minute_retiming']['trips'],
        'reference_cap_unchanged':timetable['reference_cap_unchanged'],'annual_service_days_assumption':260,
        'domain':'Zero/one/two consecutive distinct existing inventory IDs omitted from required order per wing; up to four omissions network-wide. Both new local anchors retain early/late visits. All original remaining node orders fixed. Encountered omitted IDs and other route-ready conventional inventory IDs supported by the pinned walk matrix are counted when physically on path. Not all subsets, route orders, new stop siting or a global optimum.',
        'frontier_semantics':'Minimise km; maximise each of five municipalities 5/8/10-minute potential access and retained-ID set inclusion. No weights. Preliminary road/access frontier ONLY; operating results are separate and all cases retained.',
        'access_semantics':'Conditional walking coverage of population units, with both unapproved local sites. No passengers, demand weights, actual boarding or directional journey guarantee. Exact full-retention baseline reproduced.',
        'selection_semantics':'Minimum-distance IDs are diagnostic witnesses, not authorised primary/runner-up choices. No acceptable coverage loss or new budget declared.',
        'total_operating_km':None,'approved_uplift_percent':None,'full_history_legality_certified':False,**FLAGS}
    return result,{'type':'FeatureCollection','properties':FLAGS,'features':features}


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--graph_dir',type=Path,required=True); p.add_argument('--walk_dir',type=Path,required=True)
    p.add_argument('--output',type=Path,default=BASE/'retention_tradeoffs.json'); p.add_argument('--geojson',type=Path,default=BASE/'retention_tradeoffs.geojson')
    a=p.parse_args(); paths=inputs(a.graph_dir)
    paths.update(counterflow=BASE/'local_counterflow.json',matrix=a.walk_dir/'output/rt028_population_unit_stop_walk_matrix_v3.csv',
        pedestrian_osm=a.walk_dir/'input/rt028_osm_pedestrian_snapshot_v3.osm',
        candidates_normalized=paths['candidates_normalized_newlines'],
        road_screen=BASE.parent/'rt031_unique_line_road_screen_v3/screen.json',access_reference=BASE/'brivio_existing_sites_walk.json')
    result,shape=build(paths)
    for path,value in ((a.output,result),(a.geojson,shape)):
        path.write_text(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    for key in ('minimum_distance_case_id','minimum_distance_unchanged_access_case_id'):
        c=next(c for c in result['cases'] if c['case_id']==result[key]); print(json.dumps({key:c},ensure_ascii=False),flush=True)
    print(json.dumps({'case_count':len(result['cases']),'frontier_count':len(result['preliminary_road_access_frontier_ids']),
        'reference_cap_case_count':result['reference_cap_case_count']}),flush=True)
