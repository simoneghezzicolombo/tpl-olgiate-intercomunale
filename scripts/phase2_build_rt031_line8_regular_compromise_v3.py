"""Construct an explicit 12-hour compromise, not an approved 13-hour plan.

No identity-union substitution: headways are checked on each repeated occurrence
stream of a single fixed pattern. Four orientations remain unselected.
"""
import argparse
import csv
import hashlib
import itertools
import json
from pathlib import Path

from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops
from scripts.phase2_audit_rt031_line8_independent_wings_v3 import minimum_blocks
from scripts.phase2_audit_rt031_line8_passenger_peaks_v3 import uncovered_intervals


TIMES = [400, 430, 460, 490, 520, 580, 640, 700, 760, 820, 880, 940, 1000, 1030, 1060, 1090, 1120]
SOUTH = 'RT031::P2V2S_0031_PROJECTED_ROAD_POINT'
ZENO = 'PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE'


def build(wings, rail, rail_contract, policy):
    if wings['contract'] != 'RT031_LINE8_INDEPENDENT_WINGS_DIAGNOSTIC_V3' or wings['network_selected']:
        raise ValueError('wrong road source')
    if wings['primary_selection_authorised'] or wings['runner_up_selection_authorised']:
        raise ValueError('decisional road source')
    if policy['contract'] != 'PHASE2_HUMAN_APPROVED_FINAL_POLICY_V3':
        raise ValueError('wrong cap source')
    if (rail_contract['service_date'] != '2026-09-03' or len(rail) != rail_contract['active_s8_events']
            or {r['service_date'] for r in rail} != {'2026-09-03'}):
        raise ValueError('frozen railway evidence drift')
    cap = policy['human_policy_decisions']['annual_bus_km_cap']
    loops = adjusted_loops(wings['loops'], 1.1, .5)
    all_sites = {e['stop_place_id'] for loop in loops.values() for e in loop['events']}
    rows = []
    for west, east in itertools.product(('west_A', 'west_B'), ('east_A', 'east_B')):
        patterns = (west, east)
        if {e['stop_place_id'] for p in patterns for e in loops[p]['events']} != all_sites:
            raise ValueError('identity loss')
        trips = [{'loop': p, 'departure_min': t} for t in TIMES for p in patterns]
        annual = sum(loops[t['loop']]['distance_m'] for t in trips)/1000*260
        streams = []
        journeys = {}
        for p in patterns:
            for e in loops[p]['events']:
                offset = e['offset_from_wing_origin_min']
                times = [t+offset for t in TIMES]
                gaps = [b-a for a,b in zip(times, times[1:])]
                if max(gaps) > 60+1e-8 or any(abs(gaps[i]-30)>1e-8 for i in (0,1,2,3,12,13,14,15)):
                    raise ValueError('fixed occurrence headway failure')
                streams.append({'pattern': p, 'occurrence_id': e['occurrence_id'],
                    'path_node_index': e['path_node_index'], 'stop_place_id': e['stop_place_id'], 'name': e['name'],
                    'departures_min': [round(t,6) for t in times],
                    'to_fs_ride_min': round(loops[p]['road_minutes']-offset,6),
                    'from_fs_arrival_ride_min': round(offset-.5,6),
                    'first_to_last_span_min': 720,
                    'AM_five_departure_bank_min': [round(times[0],6),round(times[4],6)],
                    'PM_five_departure_bank_min': [round(times[12],6),round(times[16],6)],
                    'boarding_authorised': False})
                if e['stop_place_id'] in (SOUTH, ZENO):
                    journeys[e['stop_place_id']] = {'name': e['name'],
                        'to_fs_ride_min': round(loops[p]['road_minutes']-offset,6),
                        'from_fs_arrival_ride_min': round(offset-.5,6)}
        # Common ready-time coverage differs from five 30-minute departures at
        # each occurrence. Publish the exact intersection, do not relabel it 2h.
        max_offset = max(e['offset_from_wing_origin_min'] for p in patterns for e in loops[p]['events'])
        common = [{'start_min': round(TIMES[i]+max_offset-30,6), 'end_min': TIMES[j],
                   'duration_min': round(TIMES[j]-TIMES[i]-max_offset+30,6)} for i,j in ((0,4),(12,16))]
        reference_failures = []
        for s in streams:
            for direction, times in (('to_fs',s['departures_min']), ('from_fs',TIMES)):
                for lo,hi,wait in ((360,1140,60),(405,525,30),(1005,1125,30)):
                    gaps = uncovered_intervals(times,lo,hi,wait)
                    if gaps:
                        reference_failures.append({'occurrence_id':s['occurrence_id'],'direction':direction,
                            'window_min':[lo,hi],'max_wait_min':wait,'uncovered_intervals':gaps})
        fleet = []
        train_rows = []
        for multiplier,dwell,recovery in itertools.product((.9,1.,1.1),(0.,.5,1.),(5,10,15)):
            adjusted = adjusted_loops(wings['loops'], multiplier, dwell)
            b = minimum_blocks(trips,adjusted,wings['represented_via_node_joins'],recovery)
            fleet.append({'moving_multiplier':multiplier,'dwell_min':dwell,**b})
        for p in patterns:
            arrivals = [t+loops[p]['road_minutes'] for t in TIMES]
            for index in range(5):
                available = arrivals[index]+3
                train = next((r for r in sorted(rail,key=lambda r:float(r['departure_min']))
                              if r['direction']=='MILANO' and float(r['departure_min'])>=available), None)
                train_rows.append({'pattern':p,'bank':'AM_TO_MILANO','bus_departure_min':TIMES[index],
                    'bus_arrival_min':round(arrivals[index],6),'transfer_walk_assumption_min':3,
                    'rail_trip_id':train['trip_id'] if train else None,
                    'train_departure_min':float(train['departure_min']) if train else None,
                    'residual_min':round(float(train['departure_min'])-available,6) if train else None})
            for t in TIMES[12:]:
                # LECCO-bound S8 is the return from Milano; latest reachable arrival.
                trains = [r for r in rail if r['direction']=='LECCO' and float(r['arrival_min'])+3<=t]
                train = max(trains,key=lambda r:float(r['arrival_min'])) if trains else None
                train_rows.append({'pattern':p,'bank':'PM_FROM_MILANO','bus_departure_min':t,
                    'transfer_walk_assumption_min':3,'rail_trip_id':train['trip_id'] if train else None,
                    'train_arrival_min':float(train['arrival_min']) if train else None,
                    'residual_min':round(t-float(train['arrival_min'])-3,6) if train else None})
        rows.append({'case_id':west+'__'+east,'patterns':list(patterns),'trips':trips,
            'annual_service_km':round(annual,6),'daily_service_km':round(annual/260,9),
            'remaining_reference_cap_before_extras_km':round(cap-annual,6),
            'stop_identity_count_including_fs':len(all_sites)+1,'occurrence_streams':streams,
            'priority_locality_journeys':journeys,'common_h30_ready_time_windows':common,
            'reference_13h_windows_satisfied':not reference_failures,'reference_window_failures':reference_failures,
            'conditional_fleet_sensitivity':fleet,'frozen_day_rail_peak_matches':train_rows})
    return {'contract':'RT031_LINE8_REGULAR_12H_COMPROMISE_V3',
        'status':'CONCRETE_COMPROMISE_REQUIRING_CALLER_ACCEPTANCE_NOT_FINAL_SELECTION',
        'fs_departures_min':TIMES,'first_last_departure_span_hours':12,
        'annual_service_days_assumption':260,'case_count':len(rows),'cases':rows,
        'reference_cap_from_existing_policy':cap,
        'frequency_semantics':'Five actual departures spaced 30 min over two hours at EACH fixed occurrence in each peak bank, H60 between banks. Banks shift by route offset. This does NOT certify a simultaneous two-hour H30 ready-time window everywhere or 06-19 availability.',
        'territorial_semantics':'Same 27 nonhub identities, ordered fixed-pattern occurrences retained; physical boarding/platform authorisation and through-service at FS not inferred.',
        'explicit_tradeoffs':['12 hours first-to-last departures, not 13 or 14', 'fixed direction all day: some return journeys lengthen',
            'common H30 ready-time intersection shorter than two hours', 'service km exclude depot and positioning',
            '260 days are an assumption; no weekend/calendar cut is implemented', 'rail matches use frozen 2026-09-03, not current GTFS',
            'headway checks use deterministic equal runtimes, not observed reliability'],
        'user_acceptance_recorded':False,'actual_timetable_certified':False,
        'network_selected':False,'primary_selection_authorised':False,'runner_up_selection_authorised':False,
        'decision_budget_km':None,'uncertainty_band_min':None}


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    for key in ('wings','rail','rail_contract','policy','output'):
        p.add_argument('--'+key,required=True,type=Path)
    a=p.parse_args()
    with a.rail.open(encoding='utf-8',newline='') as f:
        rail=list(csv.DictReader(f))
    r=build(json.loads(a.wings.read_text(encoding='utf-8')),rail,
            json.loads(a.rail_contract.read_text(encoding='utf-8')),json.loads(a.policy.read_text(encoding='utf-8')))
    r['source_sha256']={k:hashlib.sha256(v.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for k,v in vars(a).items() if k!='output'}
    a.output.write_text(json.dumps(r,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print(json.dumps([{k:v for k,v in c.items() if k in ('case_id','annual_service_km','remaining_reference_cap_before_extras_km','priority_locality_journeys','common_h30_ready_time_windows')} for c in r['cases']]))
