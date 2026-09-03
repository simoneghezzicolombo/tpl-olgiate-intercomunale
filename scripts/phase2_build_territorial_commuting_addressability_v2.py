#!/usr/bin/env python3
"""Build municipal-OD territorial commuting structural addressability for Phase 2."""
from __future__ import annotations

import argparse, csv, gzip, hashlib, io, json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.phase2_territorial_commuting_addressability_v2 import CONTRACT, STATUS, RouteGeometry, WorkOD, summarise_addressability


def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def loadj(path:Path)->dict: return json.loads(path.read_text(encoding='utf-8'))
def tf(v:bool)->str: return 'true' if v else 'false'

def parse_json_list(v:str,field:str)->list[str]:
    x=json.loads(v)
    if not isinstance(x,list) or any(not isinstance(i,str) or not i for i in x): raise ValueError(f'Invalid {field}')
    if len(x)!=len(set(x)): raise ValueError(f'Duplicate IDs in {field}')
    return x

def gz_writer(path:Path):
    path.parent.mkdir(parents=True,exist_ok=True); raw=path.open('wb'); gz=gzip.GzipFile(filename='',mode='wb',fileobj=raw,compresslevel=9,mtime=0); txt=io.TextIOWrapper(gz,encoding='utf-8',newline=''); return raw,txt

def load_anchors(path:Path)->dict[str,frozenset[str]]:
    out={}
    with path.open(encoding='utf-8-sig',newline='') as f:
        r=csv.DictReader(f)
        if not {'anchor_id','enabled','municipalities'}<=set(r.fieldnames or []): raise ValueError('Anchor universe schema invalid')
        for row in r:
            if row['enabled'].strip().lower()!='true': continue
            aid=row['anchor_id'].strip(); names=frozenset(x.strip() for x in row['municipalities'].split('|') if x.strip())
            if not aid or not names: raise ValueError(f'Enabled anchor lacks municipality lineage: {aid}')
            if aid in out: raise ValueError(f'Duplicate anchor {aid}')
            out[aid]=names
    return out

def load_routes(path:Path, anchors:dict[str,frozenset[str]])->dict[str,RouteGeometry]:
    out={}
    with path.open(encoding='utf-8-sig',newline='') as f:
        r=csv.DictReader(f)
        req={'route_id','anchors_json','public_service_starts_at_hub','vehicle_closure_added'}
        if not req<=set(r.fieldnames or []): raise ValueError('Route universe schema invalid')
        for row in r:
            if row['public_service_starts_at_hub']!='true': raise ValueError('Route does not start as public service at hub')
            ids=tuple(parse_json_list(row['anchors_json'],'anchors_json'))
            if any(a not in anchors for a in ids): raise ValueError(f'Route references anchor without municipality lineage: {row["route_id"]}')
            route=RouteGeometry(row['route_id'],ids); route.validate()
            if route.route_id in out: raise ValueError(f'Duplicate route {route.route_id}')
            out[route.route_id]=route
    return out

def load_od(path:Path, validation:dict, footprint:set[str], output:Path)->tuple[list[WorkOD],dict]:
    core=set(map(str,validation['core_codes'])); rows=[]; seen=set(); category_mass={k:0.0 for k in ('SELF','OTHER_CORE','S8_DIRECT','OTHER_EXTERNAL')}; universe=[]
    with path.open(encoding='utf-8-sig',newline='') as f:
        r=csv.DictReader(f); req={'procom_res','origin_name','procom_lav','destination_name','workers','category','rail_semantics'}
        if not req<=set(r.fieldnames or []): raise ValueError('OD source schema invalid')
        for src in r:
            if src['procom_res'] not in core: raise ValueError('OD origin outside certified five-municipality core')
            if src['rail_semantics']!='INFRASTRUCTURE_ADDRESSABILITY_NOT_MODAL_SHARE': raise ValueError('OD rail semantics changed')
            key=(src['procom_res'],src['procom_lav'])
            if key in seen: raise ValueError(f'Duplicate municipal OD {key}')
            seen.add(key); od=WorkOD(src['procom_res'],src['origin_name'],src['procom_lav'],src['destination_name'],float(src['workers']),src['category']); od.validate(); rows.append(od); category_mass[od.category]+=od.workers
            in_fp=od.destination_name in footprint
            scorable=od.category!='SELF' and in_fp
            universe.append({'origin_code':od.origin_code,'origin_municipality':od.origin_name,'destination_code':od.destination_code,'destination_municipality':od.destination_name,'workers':f'{od.workers:.9f}','category':od.category,'destination_in_structural_search_footprint':tf(in_fp),'territorial_structural_addressability_scorable':tf(scorable),'self_od_resolution_status':'SELF_MUNICIPAL_OD_UNRESOLVED' if od.category=='SELF' else 'NOT_SELF','worker_semantics':'MUNICIPAL_WORK_OD_WEIGHT_NOT_BUS_RIDERSHIP_NOT_ROUTE_DEMAND'})
    expected={'SELF':validation['self_workers'],'OTHER_CORE':validation['other_core_workers'],'S8_DIRECT':validation['s8_direct_workers'],'OTHER_EXTERNAL':validation['other_external_workers']}
    for k,v in expected.items():
        if abs(category_mass[k]-float(v))>1e-9: raise ValueError(f'OD category mass mismatch {k}: {category_mass[k]} != {v}')
    if abs(sum(o.workers for o in rows)-float(validation['resident_workers']))>1e-9: raise ValueError('OD total does not match certified resident workers')
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(universe[0]),lineterminator='\n'); w.writeheader(); w.writerows(universe)
    scoped=[o for o in rows if o.category!='SELF' and o.destination_name in footprint]
    meta={'od_relation_count':len(rows),'resident_worker_od_mass':sum(o.workers for o in rows),'self_worker_od_mass':sum(o.workers for o in rows if o.category=='SELF'),'intermunicipal_worker_od_mass':sum(o.workers for o in rows if o.category!='SELF'),'footprint_intermunicipal_od_relation_count':len(scoped),'footprint_intermunicipal_worker_od_mass':sum(o.workers for o in scoped),'footprint_destination_municipalities':sorted({o.destination_name for o in scoped}),'structural_footprint_municipalities':sorted(footprint)}
    return scoped,meta

FIELDS=['scenario_id','topology_family','public_structurally_addressable_od_relation_count','public_structurally_addressable_worker_od_mass_upper_bound','public_structurally_addressable_relation_share_of_footprint','public_structurally_addressable_worker_mass_share_of_footprint','public_plus_extensions_structurally_addressable_od_relation_count','public_plus_extensions_structurally_addressable_worker_od_mass_upper_bound','public_plus_extensions_structurally_addressable_relation_share_of_footprint','public_plus_extensions_structurally_addressable_worker_mass_share_of_footprint','public_other_core_worker_od_mass_upper_bound','public_s8_direct_worker_od_mass_upper_bound','public_other_external_worker_od_mass_upper_bound','public_plus_extensions_other_core_worker_od_mass_upper_bound','public_plus_extensions_s8_direct_worker_od_mass_upper_bound','public_plus_extensions_other_external_worker_od_mass_upper_bound','worker_assignment_to_routes','modal_share_inferred','submunicipal_worker_allocation','walking_access_combined','timetable_feasibility_evaluated','territorial_metric_is_observed_bus_ridership','topology_ranked','service_policy_selected']

def main()->int:
    p=argparse.ArgumentParser();
    for name in ('od','od_validation','anchors','matrix_validation','routes','s8_validation','scenario_mapping'): p.add_argument('--'+name.replace('_','-'),dest=name,type=Path,required=True)
    p.add_argument('--od-universe-output',type=Path,required=True); p.add_argument('--scenario-output',type=Path,required=True); p.add_argument('--validation',type=Path,required=True); a=p.parse_args()
    ov=loadj(a.od_validation); mv=loadj(a.matrix_validation); sv=loadj(a.s8_validation)
    if ov.get('source_scope')!='ISTAT_2021_WORK_COMMUTING_ONLY' or int(ov.get('resident_workers',-1))!=8754: raise ValueError('OD validation contract/scope unexpected')
    if mv.get('status')!='PASS_REDUCED_PATH_MATRIX_V2_BUILD' or mv.get('lineage',{}).get('routing_anchor_universe_sha256')!=sha(a.anchors): raise ValueError('Routing-anchor lineage mismatch')
    if sv.get('status')!='PASS_S8_PHASE_OPPORTUNITY_V2_BUILD' or sv.get('lineage',{}).get('route_universe_sha256')!=sha(a.routes) or sv.get('lineage',{}).get('scenario_route_mapping_sha256')!=sha(a.scenario_mapping): raise ValueError('Route/scenario lineage mismatch')
    anchors=load_anchors(a.anchors); footprint={m for names in anchors.values() for m in names}; routes=load_routes(a.routes,anchors)
    if len(routes)!=int(sv['unique_route_count']): raise ValueError('Route count mismatch')
    scoped,meta=load_od(a.od,ov,footprint,a.od_universe_output)
    den_rel=len(scoped); den_mass=sum(o.workers for o in scoped)
    raw,txt=gz_writer(a.scenario_output); scenario_count=0; improved=0; max_public=0.0; max_plus=0.0
    try:
        w=csv.DictWriter(txt,fieldnames=FIELDS,lineterminator='\n'); w.writeheader()
        with gzip.open(a.scenario_mapping,'rt',encoding='utf-8-sig',newline='') as f:
            for row in csv.DictReader(f):
                pub_ids=parse_json_list(row['public_route_ids_json'],'public_route_ids_json'); ext_ids=parse_json_list(row['extension_route_ids_json'],'extension_route_ids_json')
                try: pub=[routes[x] for x in pub_ids]; ext=[routes[x] for x in ext_ids]
                except KeyError as e: raise ValueError(f'Scenario references unknown route {e.args[0]}') from e
                ps=summarise_addressability(scoped,pub,anchors); xs=summarise_addressability(scoped,pub+ext,anchors)
                pm=float(ps['structurally_addressable_worker_od_mass_upper_bound']); xm=float(xs['structurally_addressable_worker_od_mass_upper_bound'])
                if xm+1e-9<pm: raise AssertionError('Adding optional extensions reduced structural addressability')
                if xm>pm+1e-9: improved+=1
                max_public=max(max_public,pm); max_plus=max(max_plus,xm)
                out={'scenario_id':row['scenario_id'],'topology_family':row['topology_family'],'public_structurally_addressable_od_relation_count':ps['structurally_addressable_od_relation_count'],'public_structurally_addressable_worker_od_mass_upper_bound':f'{pm:.9f}','public_structurally_addressable_relation_share_of_footprint':f'{(int(ps["structurally_addressable_od_relation_count"])/den_rel if den_rel else 0):.9f}','public_structurally_addressable_worker_mass_share_of_footprint':f'{(pm/den_mass if den_mass else 0):.9f}','public_plus_extensions_structurally_addressable_od_relation_count':xs['structurally_addressable_od_relation_count'],'public_plus_extensions_structurally_addressable_worker_od_mass_upper_bound':f'{xm:.9f}','public_plus_extensions_structurally_addressable_relation_share_of_footprint':f'{(int(xs["structurally_addressable_od_relation_count"])/den_rel if den_rel else 0):.9f}','public_plus_extensions_structurally_addressable_worker_mass_share_of_footprint':f'{(xm/den_mass if den_mass else 0):.9f'}
                for prefix,s in (('public',ps),('public_plus_extensions',xs)):
                    for cat in ('other_core','s8_direct','other_external'): out[f'{prefix}_{cat}_worker_od_mass_upper_bound']=f'{float(s[f"{cat}_addressable_worker_od_mass_upper_bound"]):.9f}'
                out.update({'worker_assignment_to_routes':'false','modal_share_inferred':'false','submunicipal_worker_allocation':'false','walking_access_combined':'false','timetable_feasibility_evaluated':'false','territorial_metric_is_observed_bus_ridership':'false','topology_ranked':'false','service_policy_selected':'false'})
                w.writerow(out); scenario_count+=1
    finally: txt.close(); raw.close()
    if scenario_count!=int(sv['scenario_count']): raise ValueError('Scenario count mismatch')
    report={'status':STATUS,'contract':CONTRACT,'source_scope':'ISTAT_2021_WORK_COMMUTING_ONLY','source_resolution':'MUNICIPAL_OD','scenario_count':scenario_count,**meta,'scoped_worker_semantics':'STRUCTURALLY_ADDRESSABLE_MUNICIPAL_OD_MASS_UPPER_BOUND_NOT_SERVED_PASSENGERS','self_od_structural_scoring':'EXCLUDED_UNRESOLVED_AT_MUNICIPAL_OD_RESOLUTION','scenarios_where_optional_extensions_increase_addressable_worker_mass':improved,'max_public_structurally_addressable_worker_od_mass_upper_bound':max_public,'max_public_plus_extensions_structurally_addressable_worker_od_mass_upper_bound':max_plus,'worker_assignment_to_routes':False,'modal_share_inferred':False,'submunicipal_worker_allocation':False,'walking_access_combined':False,'timetable_feasibility_evaluated':False,'territorial_metric_is_observed_bus_ridership':False,'s8_feeder_metric_combined_into_territorial_metric':False,'topology_ranked':False,'service_policy_selected':False,'lineage':{'od':str(a.od),'od_sha256':sha(a.od),'od_validation_sha256':sha(a.od_validation),'anchors_sha256':sha(a.anchors),'matrix_validation_sha256':sha(a.matrix_validation),'routes_sha256':sha(a.routes),'s8_validation_sha256':sha(a.s8_validation),'scenario_mapping_sha256':sha(a.scenario_mapping),'od_universe_output_sha256':sha(a.od_universe_output),'scenario_output_sha256':sha(a.scenario_output)},'epistemic_note':'Worker weights remain municipal workplace-commuting OD weights. Scenario values are upper-bound structural addressability masses: a municipality-level OD is counted only when a directed passenger-service path exists between at least one anchor in each municipality. This does not establish that the worker lives or works within walking distance of those anchors, uses bus, or has a feasible timetable. SELF OD is retained in the inventory but excluded from structural scoring.'}
    a.validation.parent.mkdir(parents=True,exist_ok=True); a.validation.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({k:report[k] for k in ('scenario_count','resident_worker_od_mass','footprint_intermunicipal_worker_od_mass','scenarios_where_optional_extensions_increase_addressable_worker_mass','max_public_structurally_addressable_worker_od_mass_upper_bound','max_public_plus_extensions_structurally_addressable_worker_od_mass_upper_bound')},indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
