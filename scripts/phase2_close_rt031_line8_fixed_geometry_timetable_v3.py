"""One working timetable: fixed accepted paths, trip counts and peak windows.

Minimise documented clockface exceptions at the unchanged service-km level.
No weighted passenger score or automatic budget/operating approval.
"""
from collections import Counter
import hashlib
import json

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csc_matrix, hstack, vstack

from scripts.phase2_compare_rt031_line8_deep_offpeak_v3 import build_problem
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import BASE,FLAGS,PHASES,verify
from scripts.phase2_refresh_rt031_s8_service_date_v3 import OUTPUT as RAIL
from scripts.phase2_refresh_rt031_s8_service_date_v3 import ROOT

OUTPUT=BASE/'fixed_geometry_timetable.json'
CONFIRMATION=ROOT/'config/rt031_geometry_confirmation_and_timetable_closure_v3.json'


def digest(path):return hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()


def solve():
    confirmation=json.loads(CONFIRMATION.read_text(encoding='utf-8'))
    if (confirmation['geometry_confirmed_by_caller'] is not True
            or digest(ROOT/confirmation['geometry_source'])!=confirmation['geometry_source_sha256_normalized_newlines']
            or set(confirmation['patterns'])!={'west_B','east_A'}):
        raise ValueError('missing or drifted caller-confirmed geometry')
    p=build_problem((600,960),120)
    n=len(p['costs']);count=len(p['trips'])
    phases=[(w,b,r) for w in ('west','east') for b in ('before_10','from_10') for r in range(0,30,5)]
    # Each candidate can carry an exception, counted only when dispatched.
    total=n+len(phases)+count
    rows=[];cols=[];data=[];lo=[];hi=[]
    def add(terms,low,high):
        row=len(lo)
        for c,v in terms:rows.append(row);cols.append(c);data.append(v)
        lo.append(low);hi.append(high)
    for i,t in enumerate(p['trips']):
        wing=t['loop'].split('_')[0];band='before_10' if t['departure_min']<600 else 'from_10'
        z=n+phases.index((wing,band,t['departure_min']%30));exc=n+len(phases)+i
        if t['departure_min']!=1180:add([(i,1),(z,-1),(exc,-1)],-np.inf,0)
        add([(exc,1),(i,-1)],-np.inf,0)
    for wing in ('west','east'):
        add([(i,1) for i,t in enumerate(p['trips']) if t['loop'].startswith(wing)],17,17)
        for band in ('before_10','from_10'):
            add([(n+j,1) for j,(w,b,_) in enumerate(phases) if w==wing and b==band],1,1)
    matrix=vstack([hstack([p['matrix'],csc_matrix((p['matrix'].shape[0],total-n))]),csc_matrix((data,(rows,cols)),shape=(len(lo),total))],format='csc')
    upper=p['upper'].copy();upper[p['fleet_rows']]=4
    bounds=np.ones(total)
    for i,t in enumerate(p['trips']):
        if t['loop'] not in ('west_B','east_A'):bounds[i]=0
    for i,(label,start) in enumerate(PHASES):
        if start!={'AM':420,'PM':1015}[label]:bounds[count+i]=0
    objective=np.zeros(total);objective[n+len(phases):]=1
    result=milp(objective,integrality=np.ones(total),bounds=Bounds(0,bounds),
                constraints=LinearConstraint(matrix,np.r_[p['lower'],lo],np.r_[upper,hi]),options={'time_limit':60,'mip_rel_gap':0})
    if result.x is None:raise ValueError('No verified timetable: do not replace reference')
    if max(abs(result.x-np.rint(result.x)))>1e-5:raise ValueError('fractional witness')
    trips=sorted([t for i,t in enumerate(p['trips']) if result.x[i]>.5],key=lambda t:(t['departure_min'],t['loop']))
    peaks=[{'peak':l,'start_min':s,'end_min':s+120} for i,(l,s) in enumerate(PHASES) if result.x[count+i]>.5]
    scenarios=verify(p,trips,peaks,4)
    phases_used=[{'wing':w,'band':b,'modulo_30':r} for i,(w,b,r) in enumerate(phases) if result.x[n+i]>.5]
    exception_trips=[]
    for t in trips:
        band='before_10' if t['departure_min']<600 else 'from_10'
        match=next(f for f in phases_used if f['wing']==t['loop'].split('_')[0] and f['band']==band)
        if t['departure_min']!=1180 and t['departure_min']%30!=match['modulo_30']:exception_trips.append(t)
    if abs(len(exception_trips)-result.fun)>1e-5:raise ValueError('exception objective mismatch')
    rail=json.loads(RAIL.read_text(encoding='utf-8'))
    # Current dated train identity binding for every inherited engineering target.
    anchors=[]
    for a in p['anchors']:
        direction='MILANO' if a['kind']=='bus_to_rail' else 'LECCO'
        clock='departure_min' if a['kind']=='bus_to_rail' else 'arrival_min'
        found=[r for r in rail['events'] if r['direction']==direction and r[clock]==a['rail_min']]
        if len(found)!=1:raise ValueError('current railway target missing or ambiguous')
        anchors.append({'wing':a['wing'],'kind':a['kind'],'stop_place_id':a['stop_place_id'],'rail_trip_id':found[0]['trip_id'],'rail_min':a['rail_min']})
    nominal=p['adjusted'][1.1,.5]
    ledger=[]
    for i,t in enumerate(trips):
        loop=nominal[t['loop']]
        ledger.append({**t,'trip_index':i,'service_km':p['family']['loops'][t['loop']]['distance_m']/1000,
                       'fs_return_nominal_min':t['departure_min']+loop['road_minutes'],
                       'events_nominal':[{**e,'departure_min':t['departure_min']+e['offset_from_wing_origin_min']} for e in loop['events']]})
    return {'contract':'RT031_FIXED_ACCEPTED_GEOMETRY_WORKING_TIMETABLE_V3',
            'status':'SINGLE_WORKING_TIMETABLE_PROPOSED_NOT_OPERATING_APPROVAL',
            'geometry_confirmed_by_caller':True,'geometry_patterns':['west_B','east_A'],
            'geometry_source':'deep_offpeak_witness.geojson','road_geometry_changed':False,
            'source_sha256_normalized_newlines':{'reference':digest(BASE/'deep_offpeak_witness.json'),'rail':digest(RAIL),'confirmation':digest(CONFIRMATION)},
            'trips':trips,'trip_ledger':ledger,'patterns_used':dict(Counter(t['loop'] for t in trips)),
            'comparison_peak_windows':peaks,'offpeak_wait_windows_comparison':p['offpeak_windows'],
            'annual_service_days_assumption':260,'annual_service_km':sum(t['service_km'] for t in ledger)*260,
            'clockface_phases':phases_used,'clockface_exceptions':exception_trips,
            'final_departure_exception_allowed_min':1180,
            'minimum_exception_count_in_declared_domain':bool(result.success),'exception_count':len(exception_trips),
            'solver_status':int(result.status),'solver_message':str(result.message),
            'current_rail_service_date':rail['service_date'],'dated_rail_target_bindings':anchors,
            'conditional_scenarios':scenarios,'worst_grid_vehicle_count_conditional':max(s['minimum_vehicle_count_conditional'] for s in scenarios),
            'semantics':'One illustrative timetable proposed to close scheduling on the caller-confirmed geometry. Fixed 17 complete trips per wing and unchanged 07-09/16:55-18:55 peaks, H120 only 10-16 and H60 elsewhere. Minimise departures outside one half-hour phase per wing and before/after 10 band, with last departure exempt; no normative weighted score or universal timetable optimum. Dated scheduled rail checks, not empirical reliability. No through-service across trips inferred.',
            'timetable_accepted_by_caller':False,'midday_window_adopted':False,
            'actual_timetable_certified':False,'decision_budget_km':None,'uncertainty_band_min':None,
            'approved_uplift_percent':None,'total_operating_km':None,**{k:False for k in FLAGS}}


if __name__=='__main__':
    r=solve();OUTPUT.write_text(json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
    print(json.dumps({k:r[k] for k in ('annual_service_km','patterns_used','clockface_phases','clockface_exceptions','minimum_exception_count_in_declared_domain','comparison_peak_windows')}))
