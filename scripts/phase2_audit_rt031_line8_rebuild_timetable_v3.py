"""Finite-domain optimistic minimum-km timetable reconstruction on fixed wings."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csc_matrix
from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops
from scripts.phase2_audit_rt031_line8_passenger_peaks_v3 import uncovered_intervals
from scripts.phase2_audit_rt031_line8_independent_wings_v3 import minimum_blocks


def build(wings,peak_advance=0):
    if wings['contract']!='RT031_LINE8_INDEPENDENT_WINGS_DIAGNOSTIC_V3' or wings['network_selected']:
        raise ValueError('unexpected source')
    loops=adjusted_loops(wings['loops'],1.1,.5)
    candidates=[{'loop':k,'departure_min':m} for k in sorted(loops) for m in range(360,1201,5)]
    maps=[]
    for t in candidates:
        events={}
        for e in loops[t['loop']]['events']:
            for direction,time in (('to_fs',t['departure_min']+e['offset_from_wing_origin_min']),('from_fs',t['departure_min'])):
                events.setdefault((e['stop_place_id'],direction),[]).append(time)
        maps.append(events)
    keys=sorted({k for m in maps for k in m})
    if peak_advance not in (0,15,30):
        raise ValueError('undeclared peak comparison')
    windows=tuple((a,b,h) for a,b,h in ((360,420-peak_advance,60),(420-peak_advance,540-peak_advance,30),
        (540-peak_advance,1020-peak_advance,60),(1020-peak_advance,1140-peak_advance,30),(1140-peak_advance,1140,60)) if a<b)
    constraints=set()
    for key in keys:
        for lo,hi,wait in windows:
            points={lo,hi}
            for m in maps:
                for time in m.get(key,[]):
                    points.update(x for x in (time-wait,time) if lo<x<hi)
            boundaries=sorted(points)
            for left,right in zip(boundaries,boundaries[1:]):
                if right-left<1e-7:
                    continue
                mid=(left+right)/2
                ids=tuple(i for i,m in enumerate(maps) if any(time-wait<=mid<=time for time in m.get(key,[])))
                if not ids:
                    raise ValueError('uncoverable ready-time interval')
                constraints.add(ids)
    rows=[]; cols=[]
    for i,ids in enumerate(sorted(constraints)):
        rows.extend([i]*len(ids)); cols.extend(ids)
    matrix=csc_matrix((np.ones(len(rows)),(rows,cols)),shape=(len(constraints),len(candidates)))
    costs=np.array([loops[t['loop']]['distance_m']/1000 for t in candidates])
    answer=milp(costs,integrality=np.ones(len(candidates)),bounds=Bounds(0,1),
        constraints=LinearConstraint(matrix,1,np.inf),options={'time_limit':45,'mip_rel_gap':0})
    if not answer.success or answer.x is None:
        raise ValueError('finite-domain optimum not established: '+answer.message)
    chosen=[i for i,x in enumerate(answer.x) if x>.5]
    for key in keys:
        times=[t for i in chosen for t in maps[i].get(key,[])]
        for lo,hi,wait in windows:
            if uncovered_intervals(times,lo,hi,wait):
                raise ValueError('continuous postsolve coverage failed')
    trips=sorted((candidates[i] for i in chosen),key=lambda t:(t['departure_min'],t['loop']))
    return {'contract':'RT031_LINE8_FINITE_TIMETABLE_RECONSTRUCTION_V3',
        'candidate_trip_count':len(candidates),'distinct_interval_constraints':len(constraints),
        'peak_window_advance_min':peak_advance,
        'ready_time_windows':[{'start_min':a,'end_min':b,'max_wait_min':h} for a,b,h in windows],
        'trip_witness':trips,'daily_km':round(sum(costs[i] for i in chosen),6),
        'annual_km_before_extras':round(sum(costs[i] for i in chosen)*260,3),
        'solver_status':int(answer.status),'mip_gap':float(answer.mip_gap),
        'continuous_ready_time_recheck_passed':True,
        'fleet_is_for_returned_witness_not_minimised_over_km_optima':True,
        'conditional_blocks':[minimum_blocks(trips,loops,wings['represented_via_node_joins'],r) for r in (5,10,15)],
        'scope':'All fixed four wing patterns, departure grid 06:00..20:00 every five minutes, no old trips retained as constraints. Minimise physical km only for declared ready-time promise. Not optimum over street paths, short turns, calendars, phases outside grid or peak windows.',
        'semantics':'13-hour passenger-ready comparison 06-19, H30 windows explicitly listed (reference 07-09/17-19 or advanced) and H60 elsewhere. Optimistic identity union and boarding assumption; +10% moving time, 0.5 min per hypothetical stop. Clockface regularity, useful journey duration, rail matching, depot and actual boarding are not guaranteed.',
        'window_policy':'Explicit reference comparison; neither selected operating span nor newly imposed peak law.',
        'network_selected':False,'primary_selection_authorised':False,'runner_up_selection_authorised':False,
        'decision_budget_km':None,'uncertainty_band_min':None}


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--source',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    p.add_argument('--compare_peaks',action='store_true')
    a=p.parse_args(); source=json.loads(a.source.read_text(encoding='utf-8'))
    result=({'contract':'RT031_LINE8_REBUILT_PEAK_WINDOW_COMPARISON_V3','comparisons':[build(source,advance) for advance in (0,15,30)],
        'network_selected':False,'primary_selection_authorised':False,'runner_up_selection_authorised':False,
        'decision_budget_km':None,'uncertainty_band_min':None} if a.compare_peaks else build(source))
    result['source_sha256']=hashlib.sha256(a.source.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    a.output.write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
