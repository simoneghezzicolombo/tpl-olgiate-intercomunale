#!/usr/bin/env python3
"""Build transparent passenger-stop options for named V3 service areas.

The catalog prefers no option. It exposes name-match and distance evidence for
existing official stops and proposed hypotheses so corridor generation can use
human-facing territorial identities instead of anonymous coordinate samples.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, re, unicodedata
from math import asin, cos, radians, sin, sqrt
from pathlib import Path


def norm(s):
    s=unicodedata.normalize('NFKD',str(s or '')).encode('ascii','ignore').decode().lower()
    return ' '.join(re.findall(r'[a-z0-9]+',s))

def hdist(a,b,c,d):
    r=6371008.8; p1,p2=radians(a),radians(c); dp=radians(c-a); dl=radians(d-b)
    x=sin(dp/2)**2+cos(p1)*cos(p2)*sin(dl/2)**2
    return 2*r*asin(sqrt(x))

def sha(path):
    h=hashlib.sha256();
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''): h.update(chunk)
    return h.hexdigest()

def rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def toks(row):
    raw='|'.join([row.get('area_name',''),row.get('aliases','')])
    out=[]
    for part in raw.split('|'):
        n=norm(part)
        # municipality-only generic words are weak; locality words remain useful.
        if n and n not in {'centro','stazione','paese'}: out.append(n)
    return sorted(set(out))

def match_strength(label, aliases):
    nl=norm(label)
    if not nl:return (0,'NONE')
    exact=[a for a in aliases if a==nl]
    if exact:return (3,'EXACT_NORMALIZED')
    contained=[a for a in aliases if a in nl or nl in a]
    if contained:return (2,'CONTAINMENT')
    # token overlap is discovery evidence only
    lt=set(nl.split()); best=0
    for a in aliases:
        at=set(a.split());
        if at: best=max(best,len(lt&at)/len(at))
    return (1,'TOKEN_OVERLAP') if best>=0.5 else (0,'NONE')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--contract',type=Path,required=True)
    p.add_argument('--existing',type=Path,required=True)
    p.add_argument('--proposed',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args()
    contract=[r for r in rows(a.contract) if r.get('record_type')=='SERVICE_AREA_AUDIT']
    existing=rows(a.existing); proposed=rows(a.proposed)
    out=[]; area_summary=[]
    for area in contract:
        lat=area.get('evidence_lat',''); lon=area.get('evidence_lon',''); aliases=toks(area)
        if not lat or not lon:
            area_summary.append({'area_id':area['area_id'],'area_name':area['area_name'],'municipality':area['municipality'],'evidence_coordinate_available':'false','existing_named_match_count':0,'proposed_named_match_count':0,'nearest_existing_official_m':'','nearest_proposed_hypothesis_m':'','catalog_status':'NO_CERTIFIED_AREA_COORDINATE'})
            continue
        alat,alon=float(lat),float(lon)
        candidates=[]
        for source_class,source_rows in [('EXISTING_OFFICIAL',existing),('PROPOSED_HYPOTHESIS',proposed)]:
            for r in source_rows:
                rlat=r.get('stop_lat') if source_class=='EXISTING_OFFICIAL' else r.get('lat')
                rlon=r.get('stop_lon') if source_class=='EXISTING_OFFICIAL' else r.get('lon')
                if not rlat or not rlon:continue
                label=r.get('stop_name','') if source_class=='EXISTING_OFFICIAL' else ' | '.join(x for x in [r.get('settlement_additional_10min_names',''),r.get('destination_additional_10min_names','')] if x)
                sid=r.get('physical_cluster_id','') if source_class=='EXISTING_OFFICIAL' else r.get('candidate_id','')
                strength,kind=match_strength(label,aliases)
                d=hdist(alat,alon,float(rlat),float(rlon))
                candidates.append((source_class,-strength,d,sid,label,kind,r))
        # materialize best 5 existing and best 5 proposed by name-match first, then distance
        for source_class in ('EXISTING_OFFICIAL','PROPOSED_HYPOTHESIS'):
            selected=sorted([x for x in candidates if x[0]==source_class],key=lambda x:(x[1],x[2],x[3]))[:5]
            for rank,item in enumerate(selected,1):
                _,neg,d,sid,label,kind,r=item
                out.append({'area_id':area['area_id'],'area_name':area['area_name'],'area_municipality':area['municipality'],'option_class':source_class,'option_rank_within_class':rank,'stop_or_candidate_id':sid,'human_label':label,'option_municipality':r.get('COMUNE',''),'distance_to_area_anchor_m_geodesic':f'{d:.1f}','name_match_strength':-neg,'name_match_kind':kind,'official_routes_reference_gtfs':r.get('official_routes_reference_gtfs',''),'current_d184_d185_name_membership':str(any(x in (r.get('official_routes_reference_gtfs','').split('|')) for x in ('D184','D185'))).lower(),'road_eligibility_status':r.get('road_eligibility_status',''),'field_check_pending':str('FIELD_CHECK_PENDING' in (r.get('epistemic_status','')+'|'+r.get('physical_status',''))).lower(),'option_semantics':'IDENTITY_AND_PROXIMITY_EVIDENCE_NOT_AUTOMATIC_SELECTION'})
        ex=[x for x in candidates if x[0]=='EXISTING_OFFICIAL']; pr=[x for x in candidates if x[0]=='PROPOSED_HYPOTHESIS']
        area_summary.append({'area_id':area['area_id'],'area_name':area['area_name'],'municipality':area['municipality'],'evidence_coordinate_available':'true','existing_named_match_count':sum(-x[1]>=2 for x in ex),'proposed_named_match_count':sum(-x[1]>=2 for x in pr),'nearest_existing_official_m':f'{min(x[2] for x in ex):.1f}' if ex else '','nearest_proposed_hypothesis_m':f'{min(x[2] for x in pr):.1f}' if pr else '','catalog_status':'OPTIONS_MATERIALIZED'})
    a.output_dir.mkdir(parents=True,exist_ok=True)
    for path,data in [(a.output_dir/'service_area_stop_options_v3.csv',out),(a.output_dir/'service_area_stop_options_summary_v3.csv',area_summary)]:
        with path.open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0].keys()),lineterminator='\n');w.writeheader();w.writerows(data)
    val={'status':'PASS_SERVICE_AREA_STOP_OPTIONS_V3','automatic_stop_selected':False,'existing_official_preference_encoded_as_rank':False,'service_area_count':len(contract),'areas_with_coordinates':sum(r['evidence_coordinate_available']=='true' for r in area_summary),'areas_without_coordinates':[r['area_id'] for r in area_summary if r['evidence_coordinate_available']!='true'],'option_rows':len(out),'proposed_field_check_pending_options':sum(r['option_class']=='PROPOSED_HYPOTHESIS' and r['field_check_pending']=='true' for r in out),'lineage':{'contract_sha256':sha(a.contract),'existing_sha256':sha(a.existing),'proposed_sha256':sha(a.proposed)}}
    (a.output_dir/'service_area_stop_options_v3_validation.json').write_text(json.dumps(val,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(val,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
