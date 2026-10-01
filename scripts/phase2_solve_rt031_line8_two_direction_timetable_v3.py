"""Finite full-eight directional service comparison, no passenger utility weights."""
import argparse
import gzip
import hashlib
import heapq
import json
import math

import numpy as np
from scipy.optimize import Bounds,LinearConstraint,milp
from scipy.sparse import csc_matrix

from scripts.phase2_probe_rt031_line8_bidirectional_closure_v3 import OUTPUT as ROAD
from scripts.phase2_rebuild_rt031_uniform_complete_line_v3 import inputs
from scripts.phase2_probe_rt031_line8_variable_fs_hold_v3 import wing_offsets,windows,ordered_stop_ledger
from scripts.phase2_solve_rt031_line8_flexible_peaks_v3 import interval_covers
from scripts.phase2_audit_rt031_line8_passenger_peaks_v3 import uncovered_intervals

OUTPUT=ROAD.parent/'two_direction_timetable.json.gz'


def solve(case,policy,limit=60,max_mid=55,shoulder=60,peak_direction_locked=True,
          nominal_only=False,forward_only=False):
    profiles={
        'F':{'loops':case['forward_loops'],'first':'west_B','second':'east_A'},
        'R':{'loops':case['reverse_loops'],'first':'east_A','second':'west_B'},
    }
    if forward_only:profiles.pop('R')
    if forward_only and peak_direction_locked:raise ValueError('reverse AM not in forward-only pool')
    trips=[]
    for key,p in profiles.items():
        p['offsets']=wing_offsets(p['loops'])
        intermediate_scenario=(1.1,.5) if nominal_only else (1.1,1.)
        minimum=5*math.ceil((p['offsets'][intermediate_scenario][p['first']]['road_minutes']+1)/5)
        for t in range(300,1181,5):
            for delta in range(minimum,min(minimum+30,max_mid)+1,5):
                trips.append({'direction':key,'first_fs_min':t,'second_fs_min':t+delta,
                    'intermediate_offset_min':delta})
    ntrip=len(trips)
    if not ntrip:raise ValueError('empty full-trip domain')
    targets=[(wing,kind,minute) for wing in ('west_B','east_A')
        for kind,minutes in (('bus_to_rail',range(416,597,30)),('rail_to_bus',range(962,1173,30)))
        for minute in minutes]
    # Certified archived train inventory, not a newly fetched/current timetable.
    actual_morning={int(e['departure_min']) for e in policy['rail']['events'] if e['direction']=='MILANO'}
    actual_evening={int(e['arrival_min']) for e in policy['rail']['events'] if e['direction']=='LECCO'}
    if not set(range(416,597,30))<=actual_morning or not set(range(962,1173,30))<=actual_evening:
        raise ValueError('archived train bank mismatch')
    assignments=[]
    for r,(wing,kind,minute) in enumerate(targets):
        for i,q in enumerate(trips):
            if peak_direction_locked and q['direction']!=('R' if kind=='bus_to_rail' else 'F'):
                continue
            p=profiles[q['direction']]
            t=q['first_fs_min'] if wing==p['first'] else q['second_fs_min']
            if kind=='bus_to_rail':
                scenarios=[p['offsets'][1.1,.5]] if nominal_only else p['offsets'].values()
                waits=[minute-t-s[wing]['road_minutes']-3 for s in scenarios]
                valid=min(waits)>=-1e-8 and max(waits)<=policy['wait_ceiling']+1e-8
            else:valid=3<=t-minute<=8
            if valid:assignments.append({'target':r,'trip':i,'wing_fs_departure_min':t})
    banks=[]
    for wing in ('west_B','east_A'):
        for kind in ('bus_to_rail','rail_to_bus'):
            group=[r for r,t in enumerate(targets) if t[:2]==(wing,kind)]
            banks.extend((wing,kind,tuple(group[start:start+5])) for start in range(len(group)-4))
    na=len(assignments);n=ntrip+na+len(banks)
    rr=[];cc=[];vv=[];lower=[];upper=[]
    def row(entries,lo,hi):
        ix=len(lower)
        for col,v in entries:rr.append(ix);cc.append(col);vv.append(v)
        lower.append(lo);upper.append(hi)
    row([(i,1) for i in range(ntrip)],16,16)
    # Duplicate departures of the same public directional pattern are not useful.
    for d in profiles:
        for t in range(300,1181,5):
            row([(i,1) for i,q in enumerate(trips) if q['direction']==d and q['first_fs_min']==t],0,1)
    covers=set()
    required_scenarios=[(1.1,.5)] if nominal_only else list(profiles['F']['offsets'])
    for scenario in required_scenarios:
        for wing in ('west_B','east_A'):
            sids=profiles['F']['offsets'][scenario][wing]['sites']
            for sid in sids:
                for direction in ('from_fs','to_fs'):
                    events=[]
                    for i,q in enumerate(trips):
                        p=profiles[q['direction']]
                        t=q['first_fs_min'] if wing==p['first'] else q['second_fs_min']
                        offset=p['offsets'][scenario][wing]['sites'][sid][direction]
                        events.append((i,t+offset))
                    for lo,hi,wait in windows(405,shoulder):
                        covers.update(interval_covers(events,lo,hi,wait))
    for cover in sorted(covers):row([(i,1) for i in cover],1,np.inf)
    by_target={r:[j for j,a in enumerate(assignments) if a['target']==r] for r in range(len(targets))}
    for j,a in enumerate(assignments):row([(ntrip+j,1),(a['trip'],-1)],-np.inf,0)
    for r,own in by_target.items():
        row([(ntrip+j,1) for j in own],0,1)
        containing=[k for k,b in enumerate(banks) if r in b[2]]
        row([(ntrip+j,1) for j in own]+[(ntrip+na+k,-1) for k in containing],-np.inf,0)
    for wing in ('west_B','east_A'):
        for kind in ('bus_to_rail','rail_to_bus'):
            row([(ntrip+na+k,1) for k,b in enumerate(banks) if b[:2]==(wing,kind)],1,1)
    for k,bank in enumerate(banks):
        bcol=ntrip+na+k
        for r in bank[2]:row([(ntrip+j,1) for j in by_target[r]]+[(bcol,-1)],0,np.inf)
        for before,after in zip(bank[2],bank[2][1:]):
            difference=[(ntrip+j,assignments[j]['wing_fs_departure_min']*(1 if r==after else -1))
                for r in (before,after) for j in by_target[r]]
            row(difference+[(bcol,2000)],-np.inf,2030)
            row(difference+[(bcol,-2000)],-1970,np.inf)
    # Pure production objective only within this service-feasible domain.
    # Not a weighted quality score, Pareto decision or recommended network.
    distances={d:sum(l['distance_m'] for l in p['loops'].values())/1000 for d,p in profiles.items()}
    answer=milp(np.r_[[distances[q['direction']] for q in trips],np.zeros(na+len(banks))],
        integrality=np.ones(n),bounds=Bounds(0,1),
        constraints=LinearConstraint(csc_matrix((vv,(rr,cc)),shape=(len(lower),n)),lower,upper),
        options={'time_limit':limit,'mip_rel_gap':0})
    result={'case_id':case['case_id'],'max_intermediate_offset_min':max_mid,
        'shoulder_readiness_cap_min':shoulder,'deep_offpeak_window_min':[600,960],
        'peak_direction_locked_reverse_am_forward_pm_comparison':peak_direction_locked,
        'scenario_policy':'NOMINAL_ONLY_COMPARISON' if nominal_only else 'COMMON_NINE_SCENARIOS',
        'forward_direction_only':forward_only,
        'full_trip_count':16,'candidate_trip_count':ntrip,'coverage_cell_count':len(covers),
        'solver_status':int(answer.status),'solver_message':str(answer.message),
        'infeasibility_proven':answer.status==2,'witness_found':answer.x is not None,
        'kilometre_minimum_proven_in_declared_domain':answer.status==0,
        'network_selected':False,'primary_selection_authorised':False,'runner_up_selection_authorised':False}
    if answer.x is None:return result
    if max(abs(answer.x-np.rint(answer.x)))>1e-6:raise ValueError('noninteger witness')
    selected=[dict(q) for i,q in enumerate(trips) if answer.x[i]>.5]
    selected.sort(key=lambda q:(q['first_fs_min'],q['direction']))
    if len(selected)!=16:raise ValueError('wrong complete-trip count')
    failures=[]
    for scenario in profiles['F']['offsets']:
        for wing in ('west_B','east_A'):
            for sid in profiles['F']['offsets'][scenario][wing]['sites']:
                for direction in ('from_fs','to_fs'):
                    values=[]
                    for q in selected:
                        p=profiles[q['direction']]
                        t=q['first_fs_min'] if wing==p['first'] else q['second_fs_min']
                        values.append(t+p['offsets'][scenario][wing]['sites'][sid][direction])
                    for lo,hi,wait in windows(405,shoulder):
                        missing=uncovered_intervals(values,lo,hi,wait)
                        if missing:
                            failures.append({'scenario':scenario,'wing':wing,'site_id':sid,
                                'direction':direction,'window':[lo,hi],
                                'uncovered_ready_time_intervals':missing})
                            if scenario in required_scenarios:
                                raise ValueError('independent readiness verification failed')
    chosen=[{'wing':targets[a['target']][0],'kind':targets[a['target']][1],
        'rail_min':targets[a['target']][2],'direction':trips[a['trip']]['direction'],
        'first_fs_min':trips[a['trip']]['first_fs_min'],'wing_fs_departure_min':a['wing_fs_departure_min']}
        for j,a in enumerate(assignments) if answer.x[ntrip+j]>.5]
    if len(chosen)!=20:raise ValueError('incomplete archived H30 bindings')
    rail_stress_failures=[];intermediate_stress_failures=[]
    for q in selected:
        p=profiles[q['direction']]
        for scenario,s in p['offsets'].items():
            margin=q['intermediate_offset_min']-s[p['first']]['road_minutes']-1
            if margin < -1e-8:
                intermediate_stress_failures.append({'scenario':scenario,**q,
                    'margin_before_intermediate_fs_departure_min':margin})
    for a in chosen:
        if a['kind']!='bus_to_rail':continue
        p=profiles[a['direction']]
        for scenario,s in p['offsets'].items():
            wait=a['rail_min']-a['wing_fs_departure_min']-s[a['wing']]['road_minutes']-3
            if wait < -1e-8 or wait > policy['wait_ceiling']+1e-8:
                rail_stress_failures.append({'scenario':scenario,**a,
                    'modelled_residual_wait_min':wait,'outside_engineering_margin':True})
    ledgers=[];waits=[];vehicles=[]
    for q in selected:
        p=profiles[q['direction']]
        ledgers.append({'direction':q['direction'],**ordered_stop_ledger(p['loops'],p['first'],[q])[0]})
        waits.append(q['intermediate_offset_min']-p['offsets'][1.1,.5][p['first']]['road_minutes'])
    for scenario in profiles['F']['offsets']:
        for recovery in (5,10,15):
            ongoing=[];maximum=0
            for q in selected:
                p=profiles[q['direction']];t=q['first_fs_min']
                while ongoing and ongoing[0]<=t+1e-8:heapq.heappop(ongoing)
                heapq.heappush(ongoing,q['second_fs_min']+p['offsets'][scenario][p['second']]['road_minutes']+recovery)
                maximum=max(maximum,len(ongoing))
            vehicles.append({'moving_multiplier':scenario[0],'dwell_min':scenario[1],
                'recovery_min':recovery,'minimum_vehicle_count_conditional':maximum})
    result.update(full_trips=selected,rail_assignments=chosen,ordered_stop_event_ledger_nominal=ledgers,
        annual_service_km_260_day_comparison=sum(distances[q['direction']] for q in selected)*260,
        maximum_intermediate_fs_wait_nominal_min=max(waits),vehicle_cases=vehicles,
        pure_km_objective_not_utility_selection=True,
        readiness_stress_failures=failures,rail_stress_failures=rail_stress_failures,
        intermediate_fs_stress_failures=intermediate_stress_failures,
        all_nine_readiness_scenarios_pass=not failures,
        all_nine_rail_scenarios_pass=not rail_stress_failures)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--time-limit',type=int,default=60)
    p.add_argument('--focused-common85',action='store_true')
    a=p.parse_args();source_bytes=ROAD.read_bytes()
    road=json.loads(gzip.decompress(source_bytes));_,policy,_,_,_=inputs()
    if a.focused_common85:
        existing=json.loads(gzip.decompress(OUTPUT.read_bytes()))
        case=next(c for c in road['cases'] if c['case_id']=='hoe_omission_28_not_adopted')
        result=solve(case,policy,a.time_limit,85,60,False)
        result['solver_time_limit_seconds']=a.time_limit
        existing['cases']=[result if c['case_id']==case['case_id']
            and c['max_intermediate_offset_min']==85 and c['scenario_policy']=='COMMON_NINE_SCENARIOS'
            and not c['peak_direction_locked_reverse_am_forward_pm_comparison'] else c
            for c in existing['cases']]
        existing['source_sha256']=hashlib.sha256(source_bytes).hexdigest()
        OUTPUT.write_bytes(gzip.compress((json.dumps(existing,ensure_ascii=False,sort_keys=True,
            separators=(',',':'))+'\n').encode('utf-8'),mtime=0))
        print(result['solver_status'],result['witness_found'],result.get('annual_service_km_260_day_comparison'),flush=True)
        raise SystemExit(0)
    results=[]
    for case in road['cases']:
        for max_mid in (55,85):
            for locked in (True,False):
                result=solve(case,policy,a.time_limit,max_mid,60,locked);results.append(result)
                print(case['case_id'],max_mid,locked,result['solver_status'],result['witness_found'],
                    result.get('annual_service_km_260_day_comparison'),flush=True)
            for forward_only in (True,False):
                result=solve(case,policy,a.time_limit,max_mid,60,False,True,forward_only);results.append(result)
                print(case['case_id'],max_mid,'nominal',forward_only,result['solver_status'],result['witness_found'],
                    result.get('annual_service_km_260_day_comparison'),flush=True)
    payload={'contract':'RT031_TWO_DIRECTION_COMPLETE_LINE_TIMETABLE_DIAGNOSTIC_V3',
        'source_sha256':hashlib.sha256(source_bytes).hexdigest(),'cases':results,
        'scope':'Two complete public directional patterns, F=west-forward then east-forward; '
            'R=east-reversed then west-reversed. 16 complete trips total, not 16 per direction. '
            'Readiness H60 shoulders/H120 10-16 across nine deterministic scenarios and '
            'all designated sites. Local inbound uses last ordered local occurrence, '
            'not arbitrary identity crossing. Four five-train real archived H30 banks '
            'per wing/kind; direction-locked comparison has R AM and F PM, unrestricted '
            'comparison may aggregate both directions and cannot claim H30 per direction. '
            'Root05:00-19:40 five-minute grid, intermediate offset maxima55/85 minutes. '
            'Distance-only optimum is not passenger utility or primary selection. '
            'Nominal-only cases enforce moving1.1/dwell0.5 and separately report every failure '
            'in the nine-scenario engineering screen; they are not robustly certified replacements. '
            'No full-history road, platform, actual-calendar or empirical reliability certification.',
        'network_selected':False,'primary_selection_authorised':False,
        'runner_up_selection_authorised':False,'decision_budget_km':None,'uncertainty_band_min':None}
    OUTPUT.write_bytes(gzip.compress((json.dumps(payload,ensure_ascii=False,sort_keys=True,
        separators=(',',':'))+'\n').encode('utf-8'),mtime=0))
