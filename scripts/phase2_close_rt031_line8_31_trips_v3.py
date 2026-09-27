"""Caller-authorised 31-trip schedule, unchanged geometry and protected peaks.

Finite five-minute minimax waiting comparison; no population weights or
automatic choice between conflicting territorial optima. Historical 34-trip
artifacts remain intact. The annual calendar and operating approval stay open.
"""
from collections import Counter
import json

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csc_matrix

from scripts.phase2_close_rt031_line8_fixed_geometry_timetable_v3 import CONFIRMATION, digest
from scripts.phase2_refresh_rt031_s8_service_date_v3 import ROOT, OUTPUT as RAIL
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import (
    BASE, FLAGS, family_inputs, load_sources, prepare, events_by_site,
    occupied_sets, minimum_blocks, uncovered_intervals)
from scripts.phase2_solve_rt031_line8_flexible_peaks_v3 import interval_covers
from scripts.phase2_compare_rt031_line8_shorter_span_v3 import SPANS

AUTH = ROOT/'config/rt031_31_trip_service_authorisation_v3.json'
OUTPUT = BASE/'approved_31_trip_timetable.json'
PATTERNS = ('west_B', 'east_A')
PEAKS = [{'peak':'AM', 'start_min':420, 'end_min':540},
         {'peak':'PM', 'start_min':1015, 'end_min':1135}]


def sources():
    authority = json.loads(AUTH.read_text(encoding='utf-8'))
    geometry = json.loads(CONFIRMATION.read_text(encoding='utf-8'))
    if (authority['daily_trip_count_approved'] != 31
            or authority['pattern_counts'] != {'west_B':15, 'east_A':16}
            or authority['fixed_peak_windows_min'] != [[420,540],[1015,1135]]
            or authority['first_fs_departures_min'] != {'west_B':390,'east_A':395}
            or authority['last_fs_departure_min'] != 1180
            or authority['annual_service_days_comparison'] != 260
            or any(authority[k] is not False for k in FLAGS)
            or authority['geometry_changed'] is not False
            or geometry['geometry_confirmed_by_caller'] is not True
            or set(geometry['patterns']) != set(PATTERNS)
            or digest(ROOT/geometry['geometry_source']) != geometry['geometry_source_sha256_normalized_newlines']):
        raise ValueError('caller authority or confirmed geometry drift')
    family = family_inputs(load_sources())[1]
    family['rail_anchor_scope'] = 'each_declared_site'
    p = prepare(family,60,False,ready_span=(390,1180),
                pm_arrivals=SPANS['last_fs_1940']['pm_arrivals'])
    p['authority'] = authority
    p['candidate_trips_31'] = [t for t in p['trips'] if t['loop'] in PATTERNS
                              and t['departure_min'] >= authority['first_fs_departures_min'][t['loop']]]
    p['rail'] = json.loads(RAIL.read_text(encoding='utf-8'))
    return p


def rail_bindings(p, trips):
    indices = {(t['loop'],t['departure_min']):i for i,t in enumerate(p['trips'])}
    selected = {indices[t['loop'],t['departure_min']] for t in trips}
    bindings=[]
    for a in p['anchors']:
        eligible = selected.intersection(a['eligible'])
        if not eligible: raise ValueError('rail anchor verification failure')
        direction = 'MILANO' if a['kind']=='bus_to_rail' else 'LECCO'
        clock = 'departure_min' if a['kind']=='bus_to_rail' else 'arrival_min'
        matches = [e for e in p['rail']['events'] if e['direction']==direction and e[clock]==a['rail_min']]
        if len(matches)!=1: raise ValueError('dated rail target absent or ambiguous')
        bindings.append({k:a[k] for k in ('wing','kind','rail_min','stop_place_id')} |
                        {'rail_trip_id':matches[0]['trip_id'],
                         'eligible_bus_trips':[p['trips'][i] for i in sorted(eligible)]})
    return bindings


def clockface_allowed(t):
    if t['departure_min']==1180: return True
    phase = 0 if t['loop']=='west_B' and t['departure_min']<600 else 5
    return t['departure_min']%30 == phase


def constraints(p, limits):
    """Exact ready-time cover cells, fixed first/last, counts, rail and fleet."""
    if set(limits)!=set(PATTERNS) or any(h<30 or h>180 or h%5 for h in limits.values()):
        raise ValueError('invalid finite wait comparison')
    trips = p['candidate_trips_31']; n=len(trips)
    index = {(t['loop'],t['departure_min']):i for i,t in enumerate(trips)}
    covers=set()
    for loops in p['adjusted'].values():
        for ev in events_by_site(trips,loops).values():
            patterns={trips[i]['loop'] for i,_ in ev}
            if len(patterns)!=1: raise ValueError('shared site needs explicit wing semantics')
            limit=limits[next(iter(patterns))]
            covers.update(interval_covers(ev,390,1180,limit))
            for phase in PEAKS:
                covers.update(interval_covers(ev,phase['start_min'],phase['end_min'],30))
            # Keep H60 at the start and after the PM peak, not silently H180 all day.
            for start,end in ((390,420),(1135,1180)):
                covers.update(interval_covers(ev,start,end,60))
    for a in p['anchors']:
        covers.add(tuple(index[key] for i in a['eligible']
                         if (key:=(p['trips'][i]['loop'],p['trips'][i]['departure_min'])) in index))
    rows=[];cols=[];data=[];lo=[];hi=[]
    def add(indices,low,high):
        row=len(lo)
        for i in indices: rows.append(row);cols.append(i);data.append(1.)
        lo.append(low);hi.append(high)
    for cover in sorted(covers): add(cover,1,np.inf)
    for pattern,count in p['authority']['pattern_counts'].items():
        add([i for i,t in enumerate(trips) if t['loop']==pattern],count,count)
    for occupied in occupied_sets(trips,p['adjusted'][1.1,.5],10): add(occupied,-np.inf,4)
    lower=np.zeros(n)
    for pattern in PATTERNS:
        for minute in (p['authority']['first_fs_departures_min'][pattern],1180):
            lower[index[pattern,minute]]=1
    matrix=csc_matrix((data,(rows,cols)),shape=(len(lo),n))
    return matrix,np.array(lo),np.array(hi),lower


def attempt(p, limits, clockface=False):
    trips=p['candidate_trips_31']; matrix,lo,hi,lower=constraints(p,limits)
    upper=np.array([int(not clockface or clockface_allowed(t)) for t in trips])
    answer=milp(np.zeros(len(trips)),integrality=np.ones(len(trips)),bounds=Bounds(lower,upper),
                constraints=LinearConstraint(matrix,lo,hi),options={'time_limit':45,'mip_rel_gap':0})
    result={'limits_min':limits.copy(),'clockface_restricted':clockface,'solver_status':int(answer.status),
            'infeasible_in_finite_domain':answer.status==2,'witness_found':answer.x is not None}
    if answer.x is not None:
        if max(abs(answer.x-np.rint(answer.x)))>1e-5: raise ValueError('fractional schedule')
        selected=sorted([t for i,t in enumerate(trips) if answer.x[i]>.5],key=lambda t:(t['departure_min'],t['loop']))
        verify_schedule(p,selected,limits,clockface)
        result['trips']=selected
    elif answer.status!=2:
        raise ValueError('inconclusive solver; do not infer infeasibility')
    return result


def maximum_wait(times,start,end):
    times=sorted(set(times))
    after=[t for t in times if t>=start]
    if not after or after[-1]<end-1e-8: raise ValueError('unserved end of ready span')
    return max([after[0]-start]+[b-a for a,b in zip(times,times[1:]) if start<=a<end])


def verify_schedule(p,trips,limits,clockface=False):
    allowed={(t['loop'],t['departure_min']) for t in p['candidate_trips_31']}
    keys={(t['loop'],t['departure_min']) for t in trips}
    if len(keys)!=len(trips) or not keys<=allowed or Counter(t['loop'] for t in trips)!=p['authority']['pattern_counts']:
        raise ValueError('count, duplicate or candidate domain drift')
    if clockface and not all(clockface_allowed(t) for t in trips): raise ValueError('clockface drift')
    for pattern in PATTERNS:
        if any((pattern,minute) not in keys for minute in (p['authority']['first_fs_departures_min'][pattern],1180)):
            raise ValueError('first/last trip changed')
    bindings=rail_bindings(p,trips)
    grid=[];maxima={pattern:0 for pattern in PATTERNS};failures=[]
    for (m,d),loops in p['adjusted'].items():
        available=events_by_site(trips,loops)
        expected={(e['stop_place_id'],direction) for pattern in PATTERNS for e in loops[pattern]['events']
                  for direction in ('to_fs','from_fs')}
        if set(available)!=expected: raise ValueError('missing site/direction')
        for (sid,direction),ev in available.items():
            pattern=trips[ev[0][0]]['loop'];times=[t for _,t in ev]
            if uncovered_intervals(times,390,1180,limits[pattern]): raise ValueError('offpeak wait violation')
            maxima[pattern]=max(maxima[pattern],maximum_wait(times,390,1180))
            for phase in PEAKS:
                if uncovered_intervals(times,phase['start_min'],phase['end_min'],30): raise ValueError('H30 peak violation')
            for start,end in ((390,420),(1135,1180)):
                if uncovered_intervals(times,start,end,60): raise ValueError('edge H60 violation')
            for start,end,wait in ((390,600,60),(600,960,120),(960,1180,60)):
                gaps=uncovered_intervals(times,start,end,wait)
                if gaps: failures.append({'moving_multiplier':m,'dwell_min':d,'stop_place_id':sid,'direction':direction,
                                          'old_wait_limit_min':wait,'old_policy_uncovered_ready_intervals_min':gaps})
        for recovery in (5,10,15):
            blocks=minimum_blocks(trips,loops,p['family']['joins'],recovery)
            occupation=max(map(len,occupied_sets(trips,loops,recovery)))
            if occupation!=blocks['minimum_vehicle_count_conditional']: raise ValueError('fleet formulation disagreement')
            if (m,d,recovery)==(1.1,.5,10) and occupation>4: raise ValueError('nominal fleet violation')
            grid.append({'moving_multiplier':m,'dwell_min':d,'recovery_min':recovery,**blocks})
    km=sum(p['family']['loops'][t['loop']]['distance_m']/1000 for t in trips)*260
    if abs(km-p['authority']['approved_scenario_annual_service_km'])>1e-6: raise ValueError('approved scenario km exceeded or drifted')
    return {'annual_service_km':km,'maximum_ready_wait_min_by_pattern':maxima,
            'dated_rail_target_bindings':bindings,'conditional_scenarios':grid,
            'old_34_trip_offpeak_policy_violations':failures}


def minimum_bound(p,pattern,clockface):
    lo=6;hi=36;checks=[]
    initial=attempt(p,{x:180 for x in PATTERNS},clockface);checks.append(initial)
    if not initial['witness_found']: raise ValueError('no schedule within disclosed 180-minute boundary')
    while lo<hi:
        mid=(lo+hi)//2
        result=attempt(p,{x:mid*5 if x==pattern else 180 for x in PATTERNS},clockface);checks.append(result)
        if result['witness_found']: hi=mid
        else: lo=mid+1
    return lo*5,checks


def build():
    p=sources();comparisons=[]
    old=json.loads((BASE/'fixed_geometry_timetable.json').read_text(encoding='utf-8'))
    removed={('west_B',600),('west_B',935),('east_A',605)}
    deletion_trips=[t for t in old['trips'] if (t['loop'],t['departure_min']) not in removed]
    deletion_audit=verify_schedule(p,deletion_trips,{pattern:180 for pattern in PATTERNS})
    for restricted in (False,True):
        minima={};checks=[]
        for pattern in PATTERNS:
            minima[pattern],cases=minimum_bound(p,pattern,restricted);checks+=cases
        joint=attempt(p,minima,restricted)
        if not joint['witness_found']: raise ValueError('wing minima conflict; retain Pareto alternatives, do not choose weights')
        comparisons.append({'clockface_restricted':restricted,'independent_wing_minima_min':minima,
                            'joint_minima_attainable':True,'checks':checks,'joint_witness':joint})
    selected=comparisons[1]['joint_witness']
    audit=verify_schedule(p,selected['trips'],selected['limits_min'],True)
    nominal=p['adjusted'][1.1,.5]
    ledger=[]
    for i,t in enumerate(selected['trips']):
        loop=nominal[t['loop']]
        ledger.append({**t,'trip_index':i,'service_km':p['family']['loops'][t['loop']]['distance_m']/1000,
                       'fs_return_nominal_min':t['departure_min']+loop['road_minutes'],
                       'events_nominal':[{**e,'departure_min':t['departure_min']+e['offset_from_wing_origin_min']} for e in loop['events']]})
    return {'contract':'RT031_CALLER_31_TRIP_WORKING_TIMETABLE_V3',
            'status':'CALLER_APPROVED_COUNT_AND_SPECIFIC_SERVICE_KM_TIMETABLE_PROPOSED',
            'source_sha256_normalized_newlines':{'authority':digest(AUTH),'geometry_confirmation':digest(CONFIRMATION),
              'reference_34':digest(BASE/'fixed_geometry_timetable.json'),'rail':digest(RAIL)},
            'geometry_changed':False,'geometry_patterns':list(PATTERNS),'site_count_including_fs':28,
            'daily_trip_count':31,'patterns_used':dict(Counter(t['loop'] for t in selected['trips'])),
            'trips':selected['trips'],'trip_ledger':ledger,'comparison_peak_windows':PEAKS,
            'wait_limit_min_by_pattern':selected['limits_min'],'finite_domain_comparisons':comparisons,
            'previous_deletion_only_example':{'trips':deletion_trips,
                'annual_service_km':deletion_audit['annual_service_km'],
                'maximum_ready_wait_min_by_pattern':deletion_audit['maximum_ready_wait_min_by_pattern'],
                'peaks_rail_and_fleet_rechecked':True},
            'clockface_restricted':True,'clockface_rule':'West :00/:30 before 10, east :05/:35; from 10 both :05/:35; final 19:40 exempt. Not every slot is served.',
            'working_timetable_choice':'Readable clockface witness proposed, not automatic final selection. Unrestricted wing minima are separately reported; any readability penalty remains explicit.',
            'semantics':'Full unchanged west_B/east_A paths, 5-minute candidate grid, fixed first/last departures and 15/16 counts. Both 2-hour peaks and all dated per-site rail targets preserved across nine deterministic running/dwell cases. Independent wing minimax bounds attained together, without passenger weights. Hypothetical boarding as upstream; no empirical probabilities, demand weighting, through-service or annual/operating certification.',
            'annual_service_days_assumption':260,'service_km_excess_vs_reference':audit['annual_service_km']-111419,
            'specific_service_km_scenario_accepted_by_caller':True,'precise_offpeak_timetable_accepted_by_caller':False,
            'current_rail_service_date':p['rail']['service_date'],'annual_calendar_certified':False,
            'actual_timetable_certified':False,'funding_secured':False,'total_operating_km':None,
            'decision_budget_km':None,'uncertainty_band_min':None,**{k:False for k in FLAGS},**audit}


if __name__=='__main__':
    result=build()
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('patterns_used','annual_service_km','wait_limit_min_by_pattern','trips')}))
