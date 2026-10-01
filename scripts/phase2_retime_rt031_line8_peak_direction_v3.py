"""Same 36 trips: a conditional robust retiming and an explicit early-train tradeoff."""
import argparse
from collections import Counter
import csv
import hashlib
import itertools
import json
from pathlib import Path

from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops
from scripts.phase2_audit_rt031_line8_independent_wings_v3 import minimum_blocks
from scripts.phase2_audit_rt031_line8_joint_phases_v3 import metrics
from scripts.phase2_audit_rt031_line8_passenger_peaks_v3 import build as common_peak_audit


SPECS={'west':{'am_pattern':'west_A','rest_pattern':'west_B','first_am_min':394,'first_rest_min':535},
       'east':{'am_pattern':'east_B','rest_pattern':'east_A','first_am_min':387,'first_rest_min':528}}


def early_train_bound(wings, scenarios, first_train=416, last_train=1112, walk=3):
    """Necessary continuous-time bound for 5 AM + 13 rest trips per wing.

    No extra services, one direction change, two five-trip H30 banks; all other
    FS departure gaps <=60. Fleet assignment cannot relax this passenger bound.
    """
    bounds=[]
    for wing,s in SPECS.items():
        am,rest=s['am_pattern'],s['rest_pattern']
        sites={e['stop_place_id'] for e in wings['loops'][am]['events']}
        if sites != {e['stop_place_id'] for e in wings['loops'][rest]['events']}:
            raise ValueError('wing coverage drift')
        candidates=[]
        for m,d,loops in scenarios:
            for sid in sites:
                offset_a=max(e['offset_from_wing_origin_min'] for e in loops[am]['events'] if e['stop_place_id']==sid)
                offset_b=min(e['offset_from_wing_origin_min'] for e in loops[rest]['events'] if e['stop_place_id']==sid)
                candidates.append({'maximum_fs_switch_gap_min':60-offset_b+offset_a,
                    'stop_place_id':sid,'moving_multiplier':m,'dwell_min':d})
        critical=min(candidates,key=lambda x:(x['maximum_fs_switch_gap_min'],x['stop_place_id'],x['moving_multiplier'],x['dwell_min']))
        bridge=min(60,critical['maximum_fs_switch_gap_min'])
        longest=max(loops[am]['road_minutes'] for _,_,loops in scenarios)
        latest_start=first_train-walk-longest
        # AM five trips => 4*30. Rest thirteen => 12 gaps, of which four
        # belong to its five-trip PM H30 bank: at most 8*60 + 4*30 = 600.
        latest_end=latest_start+120+bridge+600
        earliest_end=last_train+walk
        bounds.append({'wing':wing,'latest_am_first_departure_min':round(latest_start,6),
            'maximum_fs_switch_gap_min':round(bridge,6),'critical_switch':critical,
            'maximum_span_inside_rest_block_min':600,
            'latest_possible_final_departure_min':round(latest_end,6),
            'required_final_departure_min':earliest_end,
            'incompatibility_margin_min':round(earliest_end-latest_end,6),
            'incompatible':latest_end<earliest_end-1e-8})
    return {'first_train_departure_min':first_train,'last_train_arrival_min':last_train,
        'transfer_walk_assumption_min':walk,'rows':bounds,
        'scope':'Continuous retiming necessary bound ONLY for the unchanged five AM trips then thirteen opposite-pattern trips, including a five-trip PM bank, with H60 between. Not an impossibility claim for other trip counts, routes, interleaved patterns or shorter measured runtimes.'}


def build(wings, source, rail, rail_contract):
    for data,contract in ((wings,'RT031_LINE8_INDEPENDENT_WINGS_DIAGNOSTIC_V3'),
                          (source,'RT031_LINE8_PEAK_DIRECTION_18_TRIP_COMPARISON_V3')):
        if data['contract']!=contract or any(data[k] for k in ('network_selected','primary_selection_authorised','runner_up_selection_authorised')):
            raise ValueError('wrong or decisional source')
    if (len(rail)!=rail_contract['active_s8_events'] or rail_contract['service_date']!='2026-09-03'
            or {r['service_date'] for r in rail}!={'2026-09-03'} or rail_contract['station']['stop_id']!='S01514'):
        raise ValueError('rail evidence drift')
    trips=[]; changes=[]
    for wing,s in SPECS.items():
        own=sorted((t for t in source['trips'] if t['loop'].startswith(wing)),key=lambda t:t['departure_min'])
        if len(own)!=18 or [t['loop'] for t in own] != [s['am_pattern']]*5+[s['rest_pattern']]*13:
            raise ValueError('trip inventory drift')
        if [t['departure_min'] for t in own[-5:]] != [1000,1030,1060,1090,1120]:
            raise ValueError('evening bank drift')
        for i,old in enumerate(own):
            minute=s['first_am_min']+30*i if i<5 else s['first_rest_min'] if i==5 else old['departure_min']
            new={**old,'departure_min':minute}
            trips.append(new)
            if minute!=old['departure_min']:
                changes.append({'wing':wing,'trip_ordinal':i+1,'pattern':old['loop'],
                    'old_departure_min':old['departure_min'],'new_departure_min':minute})
    trips.sort(key=lambda t:(t['departure_min'],t['loop']))
    if Counter(t['loop'] for t in trips)!=Counter(t['loop'] for t in source['trips']):
        raise ValueError('retiming changed km-producing trip counts')
    annual=sum(wings['loops'][t['loop']]['distance_m'] for t in trips)/1000*260
    if abs(annual-source['annual_service_km'])>1e-5:
        raise ValueError('unchanged km failed')
    scenarios=[(m,d,adjusted_loops(wings['loops'],m,d)) for m,d in itertools.product((.9,1.,1.1),(0.,.5,1.))]
    target_trains=[446+30*i for i in range(5)]
    if not all(any(r['direction']=='MILANO' and float(r['departure_min'])==minute for r in rail) for minute in target_trains):
        raise ValueError('missing exact new train targets')
    rows=[]
    for m,d,loops in scenarios:
        gap=max(metrics([t for t in trips if t['loop'].startswith(wing)],loops)['max_optimistic_identity_gap_min'] for wing in SPECS)
        targets=[]
        for wing,s in SPECS.items():
            for i,target in enumerate(target_trains):
                arrive=s['first_am_min']+30*i+loops[s['am_pattern']]['road_minutes']
                targets.append({'wing':wing,'trip_ordinal':i+1,'bus_arrival_min':round(arrive,6),
                    'target_train_departure_min':target,'residual_after_three_min_walk':round(target-arrive-3,6)})
        for recovery in (5,10,15):
            rows.append({'moving_multiplier':m,'dwell_min':d,
                'max_optimistic_identity_gap_min':round(gap,6),
                'morning_target_rows':targets,
                'all_morning_targets_retained':all(t['residual_after_three_min_walk']>=0 for t in targets),
                **minimum_blocks(trips,loops,wings['represented_via_node_joins'],recovery)})
    nominal=adjusted_loops(wings['loops'],1.1,.5)
    streams=[]
    for pattern,loop in nominal.items():
        own=[t for t in trips if t['loop']==pattern]
        bank=own if pattern in ('west_A','east_B') else own[-5:]
        for e in loop['events']:
            streams.append({'pattern':pattern,'occurrence_id':e['occurrence_id'],'path_node_index':e['path_node_index'],
                'stop_place_id':e['stop_place_id'],'name':e['name'],
                'departures_min':[round(t['departure_min']+e['offset_from_wing_origin_min'],6) for t in own],
                'peak_bank_departures_min':[round(t['departure_min']+e['offset_from_wing_origin_min'],6) for t in bank],
                'boarding_authorised':False,'passenger_continuity_certified':False})
    pseudo={'contract':'RT031_LINE8_JOINT_PHASE_FEASIBILITY_V3','network_selected':False,
            'illustrative_witness':{'trips':trips,'runtime_multiplier':1.1,'dwell_min_assumption':.5}}
    strict=common_peak_audit(wings,pseudo)
    counts=[]
    for direction in ('to_fs','from_fs'):
        for window in ('AM_REFERENCE','PM_REFERENCE','AM_EARLIER_COMPARISON','PM_EARLIER_COMPARISON'):
            passed=sum(next(d for d in s['diagnostics'] if d['direction']==direction and d['window']==window)['optimistic_max_wait_30_satisfied'] for s in strict['sites'])
            counts.append({'direction':direction,'window':window,'sites_passing':passed,'sites_tested':len(strict['sites'])})
    return {'contract':'RT031_LINE8_SAME_KM_CONDITIONAL_RETIMING_V3',
        'status':'CONSTRUCTED_COMPARISON_NOT_ADOPTED',
        'trips':trips,'retimed_trips':changes,'added_trips':[],'removed_trips':[],'changed_paths':[],
        'annual_service_km':round(annual,6),'annual_service_km_delta':0,
        'annual_service_days_assumption':260,'reference_cap_unchanged':source['reference_cap_unchanged'],
        'service_km_excess_percent':source['service_km_excess_percent'],
        'depot_and_positioning_km':None,'total_operating_km':None,'approved_uplift_percent':None,
        'new_morning_train_targets_min':target_trains,'old_first_train_target_min':416,
        'old_first_train_target_retained_across_grid':False,
        'unchanged_pm_bus_departures_min':[1000,1030,1060,1090,1120],
        'first_last_fs_departure_span_min':max(t['departure_min'] for t in trips)-min(t['departure_min'] for t in trips),
        'scenario_count':len(rows),'conditional_scenarios':rows,
        'all_scenarios_optimistic_h60':all(r['max_optimistic_identity_gap_min']<=60.000001 for r in rows),
        'all_scenarios_new_morning_targets_retained':all(r['all_morning_targets_retained'] for r in rows),
        'worst_minimum_vehicle_count_conditional':max(r['minimum_vehicle_count_conditional'] for r in rows),
        'occurrence_streams':streams,'priority_locality_rides_unchanged':source['priority_locality_rides'],
        'common_clock_peak_diagnostics':counts,'original_early_train_bound':early_train_bound(wings,scenarios),
        'selection_semantics':'One constructed witness, not a minimum-fleet or best-phase claim. No weighted ranking. Source 18-trip inventory and priority-site journey lengths remain unchanged.',
        'robustness_semantics':'Equal runtime/dwell assumptions applied to each trip within each deterministic scenario. Not trip-specific stochastic delay, empirical reliability, authorised boarding, current railway timetable or actual duty/depot certification.',
        'frequency_semantics':'Five H30 departures per fixed occurrence bank; H60 across direction change is an optimistic union of identities. Simultaneous two-hour common-window H30 and 13-hour span are NOT certified.',
        'tradeoffs':['first retained morning train shifts from 06:56 to 07:26','morning transfer waiting increases',
            'four vehicles in the nominal case, five in some stress cases','counterflow journeys still long','depot/costs/boarding/current rail unverified'],
        'actual_timetable_certified':False,'network_selected':False,'primary_selection_authorised':False,
        'runner_up_selection_authorised':False,'decision_budget_km':None,'uncertainty_band_min':None}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ('wings','source','rail','rail_contract','output'):
        p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    wings=json.loads(a.wings.read_text(encoding='utf-8')); source=json.loads(a.source.read_text(encoding='utf-8'))
    for key in ('wings','rail','rail_contract'):
        if source['source_sha256'][key]!=hashlib.sha256(getattr(a,key).read_bytes().replace(b'\r\n',b'\n')).hexdigest():
            raise ValueError('upstream source mismatch: '+key)
    with a.rail.open(encoding='utf-8',newline='') as f:
        rail=list(csv.DictReader(f))
    result=build(wings,source,rail,json.loads(a.rail_contract.read_text(encoding='utf-8')))
    result['source_sha256']={k:hashlib.sha256(v.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for k,v in vars(a).items() if k!='output'}
    a.output.write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('annual_service_km','all_scenarios_optimistic_h60','all_scenarios_new_morning_targets_retained','worst_minimum_vehicle_count_conditional','original_early_train_bound')}))
