"""Minimum added road km in a finite full-wing trip repair domain, not selection."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csc_matrix
from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops
from scripts.phase2_audit_rt031_line8_passenger_peaks_v3 import uncovered_intervals


def build(wings,joint,peak):
    if peak['contract']!='RT031_LINE8_PASSENGER_PEAK_READY_TIME_AUDIT_V3' or joint['network_selected']:
        raise ValueError('unexpected source')
    w=joint['illustrative_witness']
    loops=adjusted_loops(wings['loops'],w['runtime_multiplier'],w['dwell_min_assumption'])
    candidates=[{'loop':loop,'departure_min':minute} for loop in sorted(loops)
                for minute in list(range(360,571,5))+list(range(960,1171,5))]
    event_maps=[]
    for t in candidates:
        events={}
        for e in loops[t['loop']]['events']:
            sid=e['stop_place_id']
            events.setdefault((sid,'to_fs'),[]).append(t['departure_min']+e['offset_from_wing_origin_min'])
            events.setdefault((sid,'from_fs'),[]).append(t['departure_min'])
        event_maps.append(events)
    constraints=set()
    for s in peak['sites']:
        for d in s['diagnostics']:
            if d['window'] not in ('AM_REFERENCE','PM_REFERENCE'):
                continue
            key=(s['stop_place_id'],d['direction'])
            for lo,hi in d['uncovered_ready_time_intervals']:
                points={lo,hi}
                for m in event_maps:
                    for time in m.get(key,[]):
                        points.update(x for x in (time-30,time) if lo<x<hi)
                ordered=sorted(points)
                for left,right in zip(ordered,ordered[1:]):
                    if right-left<1e-7:
                        continue
                    mid=(left+right)/2
                    covering=tuple(i for i,m in enumerate(event_maps) if any(time-30<=mid<=time for time in m.get(key,[])))
                    if not covering:
                        raise ValueError('candidate domain cannot cover a passenger-ready interval')
                    constraints.add(covering)
    rows=[]; columns=[]
    for row,indices in enumerate(sorted(constraints)):
        rows.extend([row]*len(indices)); columns.extend(indices)
    matrix=csc_matrix((np.ones(len(rows)),(rows,columns)),shape=(len(constraints),len(candidates)))
    costs=np.array([loops[t['loop']]['distance_m']/1000 for t in candidates])
    answer=milp(costs,integrality=np.ones(len(candidates)),bounds=Bounds(0,1),
        constraints=LinearConstraint(matrix,1,np.inf),options={'time_limit':45,'mip_rel_gap':0})
    if not answer.success or answer.x is None:
        raise ValueError('optimal finite-domain repair not established: '+answer.message)
    chosen=[i for i,x in enumerate(answer.x) if x>.5]
    failures=[]
    for s in peak['sites']:
        for direction in ('to_fs','from_fs'):
            times=[e['minute'] for e in s[direction]]+[t for i in chosen for t in event_maps[i].get((s['stop_place_id'],direction),[])]
            for start,end in ((420,540),(1020,1140)):
                if uncovered_intervals(times,start,end):
                    failures.append([s['stop_place_id'],direction,start])
    if failures:
        raise ValueError('continuous ready-time verification failed')
    additional=sum(costs[i] for i in chosen)
    return {'contract':'RT031_LINE8_FINITE_FULL_WING_PEAK_REPAIR_V3',
        'candidate_domain_count':len(candidates),'distinct_interval_constraints':len(constraints),
        'added_trip_witness':[candidates[i] for i in chosen],
        'minimum_added_daily_km_in_domain':round(additional,6),
        'annual_km_before_extras_after_repair':round(w['annual_km_before_extras']+additional*260,3),
        'base_annual_km_before_extras':w['annual_km_before_extras'],
        'solver_status':int(answer.status),'mip_gap':float(answer.mip_gap),
        'continuous_ready_time_recheck_passed':True,
        'scope':'Only add complete wing trips, both orientations, 5-minute origin dispatch grid 06:00..09:30 and 16:00..19:30. Existing trips fixed. Minimise additional physical km in this finite domain; not global network optimisation, not a selected repair.',
        'semantics':'Optimistic boardable identity union, +10% moving time and 0.5 min per hypothetical stop. Reference ready-time windows 07-09/17-19. No depot, repaired fleet plan, observed runtime or safe-stop certification.',
        'optimal_trip_witness_uniqueness_proven':False,'network_selected':False,'primary_selection_authorised':False,
        'runner_up_selection_authorised':False,'decision_budget_km':None,'uncertainty_band_min':None}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('wings','joint','peak','output'):
        p.add_argument('--'+k,required=True,type=Path)
    a=p.parse_args(); result=build(*(json.loads(getattr(a,k).read_text(encoding='utf-8')) for k in ('wings','joint','peak')))
    result['source_sha256']={k:hashlib.sha256(v.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for k,v in vars(a).items() if k!='output'}
    a.output.write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
