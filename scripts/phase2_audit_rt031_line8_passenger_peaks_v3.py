"""Continuous ready-time H30 coverage on hypothetical passenger opportunities."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops


def uncovered_intervals(departures,start,end,max_wait=30):
    """Ready times with no departure within max_wait; ignore measure-zero endpoints."""
    covered=[]
    for t in sorted(set(departures)):
        lo,hi=max(start,t-max_wait),min(end,t)
        if lo>=hi:
            continue
        if covered and lo<=covered[-1][1]+1e-8:
            covered[-1][1]=max(covered[-1][1],hi)
        else:
            covered.append([lo,hi])
    gaps=[]; cursor=start
    for lo,hi in covered:
        if lo>cursor+1e-8:
            gaps.append([round(cursor,6),round(lo,6)])
        cursor=max(cursor,hi)
    if cursor<end-1e-8:
        gaps.append([round(cursor,6),round(end,6)])
    return gaps


def build(wings,joint):
    if wings['contract']!='RT031_LINE8_INDEPENDENT_WINGS_DIAGNOSTIC_V3' or joint['contract']!='RT031_LINE8_JOINT_PHASE_FEASIBILITY_V3':
        raise ValueError('unsupported sources')
    if wings['network_selected'] or joint['network_selected']:
        raise ValueError('decisional source')
    w=joint['illustrative_witness']
    loops=adjusted_loops(wings['loops'],w['runtime_multiplier'],w['dwell_min_assumption'])
    sites={}
    for i,t in enumerate(w['trips']):
        for e in loops[t['loop']]['events']:
            site=sites.setdefault(e['stop_place_id'],{'name':e['name'],'site_status':e['site_status'],'to_fs':[],'from_fs':[]})
            for direction,minute in (('to_fs',t['departure_min']+e['offset_from_wing_origin_min']),('from_fs',t['departure_min'])):
                site[direction].append({'minute':round(minute,6),'event_id':f'{i}:{e["occurrence_id"]}:{direction}',
                    'trip_index':i,'loop':t['loop']})
    windows=[('AM_REFERENCE',420,540),('PM_REFERENCE',1020,1140),('AM_EARLIER_COMPARISON',390,510),('PM_EARLIER_COMPARISON',990,1110)]
    rows=[]
    for sid,site in sorted(sites.items()):
        diagnostics=[]
        for direction in ('to_fs','from_fs'):
            for name,start,end in windows:
                gaps=uncovered_intervals([e['minute'] for e in site[direction]],start,end)
                diagnostics.append({'direction':direction,'window':name,'start_min':start,'end_min':end,
                    'uncovered_ready_time_intervals':gaps,'uncovered_ready_minutes':round(sum(b-a for a,b in gaps),6),
                    'optimistic_max_wait_30_satisfied':not gaps})
        rows.append({'stop_place_id':sid,**site,'diagnostics':diagnostics})
    scan=[]
    for direction in ('to_fs','from_fs'):
        for peak,starts in (('AM',range(360,481,15)),('PM',range(960,1081,15))):
            for start in starts:
                failing=[sid for sid,s in sites.items() if uncovered_intervals([e['minute'] for e in s[direction]],start,start+120)]
                scan.append({'direction':direction,'peak':peak,'start_min':start,'end_min':start+120,
                    'failing_site_ids':sorted(failing),'all_sites_optimistic_h30':not failing})
    return {'contract':'RT031_LINE8_PASSENGER_PEAK_READY_TIME_AUDIT_V3','sites':rows,'two_hour_window_scan':scan,
        'interpretation':'Hypothetical passenger ready at site (to FS) or at FS for a given site (from FS) must have a boardable departure within 30 minutes. Transfer/access to the boarding point is outside this ready-time metric. This is not a total travel-time or rail-connection measure.',
        'scope':'Optimistic union of all encountered identities/occurrences as if accessible and boardable. A failure even under this union refutes that H30 promise for this witness; a pass does not certify physical boarding or through-service continuity.',
        'window_policy':'07-09/17-19 are reference diagnostics, not newly imposed law. Earlier windows and 15-minute phase scan are comparisons, not authorised peak selections.',
        'network_selected':False,'primary_selection_authorised':False,'runner_up_selection_authorised':False,
        'actual_timetable_certified':False,'decision_budget_km':None,'uncertainty_band_min':None}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('wings','joint','output','stop_register'):
        p.add_argument('--'+k,required=True,type=Path)
    a=p.parse_args(); result=build(json.loads(a.wings.read_text(encoding='utf-8')),json.loads(a.joint.read_text(encoding='utf-8')))
    result['source_sha256']={k:hashlib.sha256(v.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for k,v in (('wings',a.wings),('joint',a.joint))}
    a.output.write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    with a.stop_register.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['stop_place_id','name','site_status','boarding_authorised'],lineterminator='\n')
        writer.writeheader()
        for s in result['sites']:
            writer.writerow({k:s[k] for k in ('stop_place_id','name','site_status')}|{'boarding_authorised':False})
        writer.writerow({'stop_place_id':'FROZEN::L00407','name':'Olgiate-Calco-Brivio FS','site_status':'HUB_OCCURRENCES_AND_PLATFORMS_TO_VALIDATE','boarding_authorised':False})
