"""Caller-approved street corrections, bounded on-path Calco stop exchange.

No new trip count, timetable, normative coverage weight or boarding approval.
"""
import argparse
import copy
import gzip
import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import numpy as np
from shapely.geometry import shape, Point
from scripts.phase2_audit_rt031_line8_caller_streets_v3 import excluded_ways
from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import BASE, FS, VIRTUAL, NORTH, inputs
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
from scripts.phase2_probe_rt031_line8_manoeuvre_cycles_v3 import split_only_edges
from scripts.phase2_probe_rt031_line8_no_reverse_all_orders_v3 import NoReverseAdapter
from scripts.phase2_probe_rt031_line8_order_neighbourhood_v3 import reconstruct
from scripts.phase2_probe_rt031_line8_retention_tradeoffs_v3 import load_access, MUNICIPALITY_NAMES
from scripts.phase2_measure_rt031_line8_omission_walk_v3 import ARLATE
from scripts.phase2_audit_rt031_unique_line_walk_access_v3 import pedestrian_time
from scripts.phase2_audit_rt031_conditional_new_stop_access_v3 import weighted_ratio
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter

OUTPUT=BASE/'santa_calco_exchange.json'
ADOPTED=BASE/'caller_street_exclusions.json'
SOURCE=BASE/'conditional_proposal_17_trips.json'
REMOVED='ASF::SANTA_MARIA_HOE_VIA_COMO'
BOUNDARY=ROOT/'data/raw/boundaries/comuni_core_istat_2026.geojson'
# Explicit engineering siting domain in the Calco-centre corridor seen on the
# route, not all Calco, not a coverage threshold or a claimed global optimum.
CORRIDOR_NAMES={'Via Roma','Via San Rocco','Via Italia','Via San Vigilio'}


def coverage(times, context):
    return {code:{str(limit):str(weighted_ratio(times<=limit,context['weights'],
        context['core'] if code=='TOTAL' else context['core']&(context['codes']==code)))
        for limit in (5,8,10)} for code in ('TOTAL',*MUNICIPALITY_NAMES)}


def dominates(a,b):
    av=[Fraction(a['coverage_fraction'][c][str(t)]) for c in MUNICIPALITY_NAMES for t in (5,8,10)]
    bv=[Fraction(b['coverage_fraction'][c][str(t)]) for c in MUNICIPALITY_NAMES for t in (5,8,10)]
    return all(x>=y for x,y in zip(av,bv)) and any(x>y for x,y in zip(av,bv))


def build(graph_dir, walk_dir):
    source=json.loads(SOURCE.read_text(encoding='utf-8'))
    adopted=json.loads(ADOPTED.read_text(encoding='utf-8'))
    corrected=next(c for c in adopted['cases'] if c['id']=='caller_adopted_mirasole_cartiglio_tessitura')
    if not corrected['reachable_with_same_ordered_events_and_boundaries']:
        raise ValueError('Caller street corrections unreachable')
    paths=inputs(graph_dir)
    raw,nodes,rules,attachments=build_graph(paths)
    edges=split_only_edges(raw)
    osm_path=graph_dir/'rt017/frozen_osm_snapshot.json.gz'
    osm=json.loads(gzip.decompress(osm_path.read_bytes()))
    ways={str(w['id']):w for w in osm['elements'] if w['type']=='way'}
    forbidden=excluded_ways(osm['elements'],corrected['avoid_exact_osm_names'])
    usable={eid:e for eid,e in edges.items() if e['osm_way_id'] not in forbidden}
    adapter=NoReverseAdapter(usable,FrozenRT017ViaNodeAdapter(usable.values(),rules,unresolved_external_via_way_count=2))
    fs=attachments[FS]['graph_node_id']
    loops=copy.deepcopy(corrected['loops'])
    old=loops['west_B']
    ordered=sorted([e for e in old['events'] if e['stop_place_id']!=REMOVED],key=lambda e:(e['path_node_index'],e['stop_place_id']))
    loops['west_B']=reconstruct(old,ordered,usable,adapter,fs,None,True,'west_B')
    if loops['west_B'] is None:
        raise ValueError('Alpino exchange path unreachable')
    paths.update(matrix=walk_dir/'output/rt028_population_unit_stop_walk_matrix_v3.csv',
        pedestrian_osm=walk_dir/'input/rt028_osm_pedestrian_snapshot_v3.osm',
        candidates_normalized=paths['candidates_normalized_newlines'],
        road_screen=BASE.parent/'rt031_unique_line_road_screen_v3/screen.json',
        access_reference=BASE/'brivio_existing_sites_walk.json')
    register=json.loads(gzip.decompress((BASE/'stop_plan_and_additions.json.gz').read_bytes()))
    sites={r['site_id']:{'node':r['graph_node_id']} for r in register['register'] if r['site_id']!=ARLATE}
    _,_,_,context=load_access(paths,sites,include_context=True)
    substrate=context['substrate']
    served={FS}|{e['stop_place_id'] for l in corrected['loops'].values() for e in l['events']}
    matrix_ids=sorted(served-{VIRTUAL,NORTH,ARLATE,'FROZEN::300634'})
    matrix=substrate.walk_time_matrix
    arlate_node=nodes['n:534398.29:5063851.64']
    arlate,_=pedestrian_time(context['graph'],context['snap_map'],context['units'],float(arlate_node['lat']),float(arlate_node['lon']))
    baseline=np.minimum(matrix[:,[substrate.stop_index[s] for s in matrix_ids]].min(axis=1),np.minimum(context['local'],arlate))
    baseline_cover=coverage(baseline,context)
    if baseline_cover!=source['coverage_fraction']:
        raise ValueError('Current 27-site coverage not reproduced')
    reduced=np.minimum(matrix[:,[substrate.stop_index[s] for s in matrix_ids if s!=REMOVED]].min(axis=1),np.minimum(context['local'],arlate))
    boundaries=json.loads(BOUNDARY.read_text(encoding='utf-8'))
    calco=shape(next(f['geometry'] for f in boundaries['features'] if f['properties']['COMUNE']=='Calco'))
    if not calco.covers(Point(9.4159051,45.7248681)):
        raise ValueError('Municipal boundary coordinate semantics drift')
    path=loops['east_A']['edge_ids']
    candidates={}
    existing_nodes={usable[e['incoming_edge']]['v_node_id'] for l in loops.values() for e in l['events']}
    for i,eid in enumerate(path,1):
        e=usable[eid]; name=ways[e['osm_way_id']].get('tags',{}).get('name')
        for node,index in ((e['u_node_id'],i-1),(e['v_node_id'],i)):
            n=nodes.get(node)
            if not n or node in existing_nodes or name not in CORRIDOR_NAMES:
                continue
            coord=[float(n['lon']),float(n['lat'])]
            if calco.covers(Point(*coord)):
                item=candidates.setdefault(node,{'node_id':node,'coordinates':coord,'street_names':set(),'path_node_indices':set()})
                item['street_names'].add(name);item['path_node_indices'].add(index)
    rows=[]
    def row(times):
        cover=coverage(times,context)
        return dict(coverage_fraction=cover,
            change_percentage_points={c:{t:100*float(Fraction(cover[c][t])-Fraction(baseline_cover[c][t])) for t in ('5','8','10')} for c in cover},
            gross_previously_covered_fraction_lost={c:{str(t):str(weighted_ratio((baseline<=t)&(times>t),context['weights'],context['core'] if c=='TOTAL' else context['core']&(context['codes']==c))) for t in (5,8,10)} for c in cover})
    for node,item in sorted(candidates.items()):
        lon,lat=item['coordinates']
        times,snap=pedestrian_time(context['graph'],context['snap_map'],context['units'],lat,lon)
        combined=np.minimum(reduced,times)
        r={**item, 'candidate_id':'RT031::CALCO_CENTRE::'+node,
            'street_names':sorted(item['street_names']),'path_node_indices':sorted(item['path_node_indices']),
            'pedestrian_snap':snap,'physical_boarding_authorised':False,
            'site_status':'NEW_SITE_FIELD_CHECK_PENDING','additional_road_distance_m':0,
            'timetable_recalculated':False,**row(combined)}
        rows.append(r)
    if not rows:
        raise ValueError('No supported on-path Calco siting candidate')
    frontier=[r['candidate_id'] for r in rows if not any(dominates(o,r) for o in rows)]
    print(json.dumps({'candidate_count':len(rows),'frontier_count':len(frontier)},ensure_ascii=False),flush=True)
    coords={n:[float(v['lon']),float(v['lat'])] for n,v in nodes.items()}
    prior_shape=json.loads(SOURCE.with_suffix('.geojson').read_text(encoding='utf-8'))
    coords[VIRTUAL]=next(f['geometry']['coordinates'] for f in prior_shape['features'] if f['geometry']['type']=='Point' and f['properties'].get('site_id')==VIRTUAL)
    features=[]
    for wing,loop in loops.items():
        vertex=[usable[loop['edge_ids'][0]]['u_node_id']]+[usable[e]['v_node_id'] for e in loop['edge_ids']]
        features.append({'type':'Feature','properties':{'wing':wing,'role':'REVISED_DEVELOPMENT_PATH','retimed':False},'geometry':{'type':'LineString','coordinates':[coords[n] for n in vertex]}})
    for feature in prior_shape['features']:
        if feature['geometry']['type']=='Point' and feature['properties'].get('role')=='DESIGN_SITE':
            f=copy.deepcopy(feature)
            if f['properties']['site_id']==REMOVED:
                f['properties'].update(role='REMOVED_FOR_EXCHANGE',exchange_authorised_for_development=True)
                f['properties']['ordered_occurrences']=[]
            else:
                f['properties']['ordered_occurrences']=[{
                    'wing':wing,'occurrence_id':e['occurrence_id'],
                    'path_node_index':e['path_node_index'],'incoming_edge':e['incoming_edge'],
                    'outgoing_edge':e['outgoing_edge']}
                    for wing,loop in loops.items() for e in loop['events']
                    if e['stop_place_id']==f['properties']['site_id']]
            features.append(f)
    for r in rows:
        features.append({'type':'Feature','properties':{'role':'CALCO_SITING_CANDIDATE','candidate_id':r['candidate_id'],'street_names':r['street_names'],'on_coverage_frontier':r['candidate_id'] in frontier,'boarding_authorised':False},'geometry':{'type':'Point','coordinates':r['coordinates']}})
    result=dict(contract='RT031_SANTA_MARIA_CALCO_ON_PATH_EXCHANGE_V3',
        removed_site_id=REMOVED,removal_authorised_for_development=True,
        retained_santa_maria_centre_id='FROZEN::300782',
        piazza_san_zenone_retained=True,street_exclusions_adopted_for_development=corrected['avoid_exact_osm_names'],
        corrected_path_before_exchange_m=corrected['complete_path_distance_m'],
        revised_path_m=sum(l['distance_m'] for l in loops.values()),loops_without_new_calco_event=loops,
        baseline_27_site_coverage_reproduced=True,baseline_coverage_fraction=baseline_cover,
        removal_only_diagnostic=row(reduced),candidate_domain_street_names=sorted(CORRIDOR_NAMES),
        candidate_count=len(rows),candidates=rows,unweighted_municipal_coverage_frontier_ids=frontier,
        new_calco_site_selected=False,final_stop_count_after_one_addition=27,
        source_sha256={k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in dict(proposal=SOURCE,street_audit=ADOPTED,municipal_boundary=BOUNDARY,osm=osm_path,matrix=paths['matrix'],pedestrian_osm=paths['pedestrian_osm']).items()},
        semantics='Every existing road-graph vertex on the actual east path on four named Calco-centre corridor streets, inside the official Calco boundary, excluding already served nodes. Not all possible new stops or all Calco. Add one explicit service event per actual visit after point selection; mere geometric crossing is not boarding. Same path, zero added moving distance; dwell and rail feasibility must be recalculated. Joint exact pedestrian coverage, gross losses, all five municipal 5/8/10 metrics, no weights or accepted-loss threshold. Field safety, stop platforms, full-history restrictions and current timetable unverified.',
        bidirectional_h30_action_deferred=True,ready_for_rail_retiming=False,
        network_selected=False,primary_selection_authorised=False,runner_up_selection_authorised=False,
        decision_budget_km=None,uncertainty_band_min=None)
    return result,{'type':'FeatureCollection','features':features}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--graph_dir',type=Path,required=True);p.add_argument('--walk_dir',type=Path,required=True)
    args=p.parse_args();result,geo=build(args.graph_dir,args.walk_dir)
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
    OUTPUT.with_suffix('.geojson').write_text(json.dumps(geo,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
