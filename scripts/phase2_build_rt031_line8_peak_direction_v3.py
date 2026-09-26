"""Explicit two-trip extension of the frozen witness, with peak-direction rides.

This does not repair the stricter simultaneous common-window 13h contract.
The reference cap stays unchanged; budget uplift and operating approval are open.
"""
import argparse
from collections import Counter
import copy
import csv
import hashlib
import itertools
import json
from pathlib import Path

from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops
from scripts.phase2_audit_rt031_line8_independent_wings_v3 import minimum_blocks
from scripts.phase2_audit_rt031_line8_joint_phases_v3 import metrics
from scripts.phase2_audit_rt031_line8_passenger_peaks_v3 import build as peak_audit


PRIORITY_SITES = ('RT031::P2V2S_0031_PROJECTED_ROAD_POINT', 'PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE')


def build(wings, joint, rail, rail_contract, policy):
    for source, contract in ((wings,'RT031_LINE8_INDEPENDENT_WINGS_DIAGNOSTIC_V3'),
                             (joint,'RT031_LINE8_JOINT_PHASE_FEASIBILITY_V3')):
        if source['contract'] != contract or any(source[k] for k in ('network_selected','primary_selection_authorised','runner_up_selection_authorised')):
            raise ValueError('unsupported or decisional source')
    if policy['contract'] != 'PHASE2_HUMAN_APPROVED_FINAL_POLICY_V3':
        raise ValueError('wrong budget reference source')
    if (rail_contract['service_date'] != '2026-09-03' or len(rail) != rail_contract['active_s8_events']
            or {r['service_date'] for r in rail} != {'2026-09-03'}
            or rail_contract['station']['stop_id'] != 'S01514'):
        raise ValueError('frozen rail source drift')
    baseline=joint['illustrative_witness']
    if (Counter(t['loop'] for t in baseline['trips']) != {'west_A':4,'east_B':4,'west_B':13,'east_A':13}
            or baseline['runtime_multiplier'] != 1.1 or baseline['dwell_min_assumption'] != .5):
        raise ValueError('frozen baseline drift')
    additions=[{'loop':p,'departure_min':min(t['departure_min'] for t in baseline['trips'] if t['loop']==p)-30}
               for p in ('west_A','east_B')]
    trips=sorted(copy.deepcopy(baseline['trips'])+additions,key=lambda t:(t['departure_min'],t['loop']))
    adjusted=adjusted_loops(wings['loops'],1.1,.5)
    daily=sum(wings['loops'][t['loop']]['distance_m'] for t in trips)/1000
    base_annual=sum(wings['loops'][t['loop']]['distance_m'] for t in baseline['trips'])/1000*260
    cap=policy['human_policy_decisions']['annual_bus_km_cap']
    all_sites={e['stop_place_id'] for v in wings['loops'].values() for e in v['events']}
    streams=[]
    rides=[]
    rail_rows=[]
    for pattern,loop in adjusted.items():
        own=[t for t in trips if t['loop']==pattern]
        am=pattern in ('west_A','east_B')
        bank=own if am else own[-5:]
        if len(bank)!=5 or any(b['departure_min']-a['departure_min']!=30 for a,b in zip(bank,bank[1:])):
            raise ValueError('not a five-departure H30 bank')
        for e in loop['events']:
            times=[round(t['departure_min']+e['offset_from_wing_origin_min'],6) for t in own]
            bank_times=[round(t['departure_min']+e['offset_from_wing_origin_min'],6) for t in bank]
            streams.append({'pattern':pattern,'occurrence_id':e['occurrence_id'],'path_node_index':e['path_node_index'],
                    'stop_place_id':e['stop_place_id'],'name':e['name'],'departure_times_min':times,
                    'to_fs_ride_min':round(loop['road_minutes']-e['offset_from_wing_origin_min'],6),
                    'from_fs_arrival_ride_min':round(e['offset_from_wing_origin_min']-.5,6),
                'peak':'AM' if am else 'PM','peak_bank_departures_min':bank_times,
                'boarding_authorised':False,'passenger_continuity_certified':False})
            if e['stop_place_id'] in PRIORITY_SITES:
                rides.append({'stop_place_id':e['stop_place_id'],'name':e['name'],'pattern':pattern,
                    'operating_phase':'AM' if am else 'REST_OF_DAY',
                    'to_fs_ride_min':round(loop['road_minutes']-e['offset_from_wing_origin_min'],6),
                    'from_fs_arrival_ride_min':round(e['offset_from_wing_origin_min']-.5,6)})
        for t in bank:
            if am:
                arrive=t['departure_min']+loop['road_minutes']
                train=next((r for r in sorted(rail,key=lambda r:float(r['departure_min']))
                            if r['direction']=='MILANO' and float(r['departure_min'])>=arrive+3),None)
                if train is None:
                    raise ValueError('missing morning frozen train')
                rail_rows.append({'pattern':pattern,'peak':'AM','bus_departure_min':t['departure_min'],
                    'bus_arrival_min':round(arrive,6),'rail_trip_id':train['trip_id'],
                    'train_departure_min':float(train['departure_min']),
                    'transfer_walk_min_assumption':3,'residual_min':round(float(train['departure_min'])-arrive-3,6)})
            else:
                trains=[r for r in rail if r['direction']=='LECCO' and float(r['arrival_min'])+3<=t['departure_min']]
                if not trains:
                    raise ValueError('missing evening frozen train')
                train=max(trains,key=lambda r:float(r['arrival_min']))
                rail_rows.append({'pattern':pattern,'peak':'PM','bus_departure_min':t['departure_min'],
                    'rail_trip_id':train['trip_id'],'train_arrival_min':float(train['arrival_min']),
                    'transfer_walk_min_assumption':3,'residual_min':round(t['departure_min']-float(train['arrival_min'])-3,6)})
    if {s['stop_place_id'] for s in streams} != all_sites:
        raise ValueError('lost locality')
    wing_metrics={w:{k:round(v,6) for k,v in metrics([t for t in trips if t['loop'].startswith(w)],adjusted).items()}
                  for w in ('west','east')}
    sensitivity=[]
    for multiplier,dwell,recovery in itertools.product((.9,1.,1.1),(0.,.5,1.),(5,10,15)):
        loops=adjusted_loops(wings['loops'],multiplier,dwell)
        b=minimum_blocks(trips,loops,wings['represented_via_node_joins'],recovery)
        gap=max(metrics([t for t in trips if t['loop'].startswith(w)],loops)['max_optimistic_identity_gap_min'] for w in ('west','east'))
        missed=[r for r in rail_rows if r['peak']=='AM' and
                r['bus_departure_min']+loops[r['pattern']]['road_minutes']+3 > r['train_departure_min']+1e-8]
        sensitivity.append({'moving_multiplier':multiplier,'dwell_min':dwell,**b,
            'max_optimistic_identity_gap_min':round(gap,6),
            'nominal_morning_train_targets_not_retained_count':len(missed),
            'empirical_missed_connection_probability':None})
    # Retain the harder passenger-window diagnostic, rather than silently
    # declaring five peak departures to satisfy all simultaneous clock windows.
    proxy=copy.deepcopy(joint); proxy['illustrative_witness']['trips']=trips
    strict=peak_audit(wings,proxy)
    strict_counts=[]
    for direction in ('to_fs','from_fs'):
        for window in ('AM_REFERENCE','PM_REFERENCE','AM_EARLIER_COMPARISON','PM_EARLIER_COMPARISON'):
            satisfied=sum(next(d for d in s['diagnostics'] if d['direction']==direction and d['window']==window)['optimistic_max_wait_30_satisfied'] for s in strict['sites'])
            strict_counts.append({'direction':direction,'window':window,'sites_passing':satisfied,'sites_tested':len(strict['sites'])})
    return {'contract':'RT031_LINE8_PEAK_DIRECTION_18_TRIP_COMPARISON_V3',
        'status':'TECHNICAL_BUDGET_UPLIFT_COMPARISON_NOT_SELECTED',
        'change_from_frozen_109k':{'added_trips':additions,'removed_trips':[],'retimed_trips':[],
            'rerouted_trips':[],'annual_service_km_delta':round(daily*260-base_annual,6)},
        'trips':trips,'trip_count_per_wing':18,'stop_identity_count_including_fs':len(all_sites)+1,
        'annual_service_days_assumption':260,'daily_service_km':round(daily,9),'annual_service_km':round(daily*260,6),
        'reference_cap_unchanged':cap,'service_km_excess_over_reference':round(daily*260-cap,6),
        'service_km_excess_percent':round((daily*260/cap-1)*100,6),
        'depot_and_positioning_km':None,'total_operating_km':None,'approved_uplift_percent':None,
        'first_last_fs_departure_span_min':max(t['departure_min'] for t in trips)-min(t['departure_min'] for t in trips),
        'priority_locality_rides':rides,'occurrence_streams':streams,'nominal_wing_metrics':wing_metrics,
        'frozen_day_rail_peak_matches':rail_rows,'conditional_operating_sensitivity':sensitivity,
        'stricter_common_clock_window_pass_counts':strict_counts,
        'frequency_semantics':'Five departures spaced 30 minutes at each fixed occurrence in each peak bank. H60 across the change is only an optimistic union of identity occurrences with boardability unresolved. Banks vary by locality; this is not certification of simultaneous two-hour common H30 windows or 13-hour service.',
        'journey_semantics':'Fast toward FS in AM and from FS in rest of day for south Olgiate and San Zeno. Opposite-direction trips still take the long loop. Through-service, platforms and vehicle suitability unapproved.',
        'rail_scope':'Frozen 2026-09-03, 3 minute walk assumption, not current timetable or empirical reliability.',
        'actual_timetable_certified':False,'reference_cap_changed':False,
        'network_selected':False,'primary_selection_authorised':False,'runner_up_selection_authorised':False,
        'decision_budget_km':None,'uncertainty_band_min':None}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ('wings','joint','rail','rail_contract','policy','output'):
        p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    wings=json.loads(a.wings.read_text(encoding='utf-8')); joint=json.loads(a.joint.read_text(encoding='utf-8'))
    digest=hashlib.sha256(a.wings.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    if joint['source_sha256']['source']!=digest:
        raise ValueError('upstream road mismatch')
    with a.rail.open(encoding='utf-8',newline='') as f:
        rail=list(csv.DictReader(f))
    r=build(wings,joint,rail,json.loads(a.rail_contract.read_text(encoding='utf-8')),json.loads(a.policy.read_text(encoding='utf-8')))
    r['source_sha256']={k:hashlib.sha256(v.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for k,v in vars(a).items() if k!='output'}
    a.output.write_text(json.dumps(r,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print(json.dumps({k:r[k] for k in ('annual_service_km','service_km_excess_over_reference','service_km_excess_percent','priority_locality_rides','nominal_wing_metrics')}))
