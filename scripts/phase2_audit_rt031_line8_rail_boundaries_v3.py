"""Frozen-day deterministic interchange gaps, without probability or selection."""
import argparse
import csv
import hashlib
import json
import itertools
from pathlib import Path
from scripts.phase2_audit_rt031_line8_independent_wings_v3 import minimum_blocks
from scripts.phase2_audit_rt031_line8_band_switch_v3 import largest_gap


def next_event(events, earliest, time_key):
    return next((e for e in events if float(e[time_key]) >= earliest), None)


def build(wings, rail, profiles, rail_contract):
    if wings['contract'] != 'RT031_LINE8_INDEPENDENT_WINGS_DIAGNOSTIC_V3' or wings['network_selected']:
        raise ValueError('wrong road source')
    if (len(rail)!=rail_contract['active_s8_events'] or len(rail)!=74
        or {r['service_date'] for r in rail}!={'2026-09-03'}
        or rail_contract['service_date']!='2026-09-03'
        or rail_contract['station']['stop_id']!='S01514'
        or any(r['direction'] not in ('MILANO','LECCO') for r in rail)):
        raise ValueError('frozen rail evidence drift')
    if profiles['status']!='ASSUMPTION_SENSITIVITY_NOT_EMPIRICAL_INTERVAL':
        raise ValueError('unlabelled transfer assumptions')
    results=[]
    for case in wings['cases']:
        if case['east_shift_min']!=-15:
            continue
        for advance,scope in itertools.product(range(30),('whole_day','morning_only')):
            shifted=[{**t,'departure_min':t['departure_min']-(advance if scope=='whole_day' or t['loop'] in ('west_A','east_B') else 0)} for t in case['trips']]
            shifted.sort(key=lambda t:(t['departure_min'],t['loop']))
            opportunities={}
            for i,t in enumerate(shifted):
                for e in wings['loops'][t['loop']]['events']:
                    for direction,minute in (('to_fs',t['departure_min']+e['offset_from_wing_origin_min']),('from_fs',t['departure_min'])):
                        opportunities.setdefault((e['stop_place_id'],direction),[]).append({'minute':minute,'event_id':f'{i}:{e["occurrence_id"]}'})
            worst_gap=max(({'site':sid,'journey_direction':direction,**largest_gap(events)} for (sid,direction),events in opportunities.items()),key=lambda g:g['minutes'])
            rows=[]
            for wing in ('west','east'):
                trips=[t for t in shifted if t['loop'].startswith(wing)]
                arrivals=sorted(t['departure_min']+wings['loops'][t['loop']]['road_minutes'] for t in trips)
                departures=[{'minute':t['departure_min'],'loop':t['loop']} for t in trips]
                for profile in profiles['transfer_profiles']:
                    walk=profile['transfer_walk_min']
                    for direction in ('MILANO','LECCO'):
                        trains=sorted((r for r in rail if r['direction']==direction),key=lambda r:float(r['departure_min']))
                        first=next_event(trains,arrivals[0]+walk,'departure_min')
                        possible_returns=[(r,next_event(departures,float(r['arrival_min'])+walk,'minute')) for r in trains]
                        connected=[(r,b) for r,b in possible_returns if b is not None]
                        last=max(connected,key=lambda pair:float(pair[0]['arrival_min'])) if connected else None
                        matched_bus=[(a,next_event(trains,a+walk,'departure_min')) for a in arrivals]
                        bus_gaps=[float(r['departure_min'])-a-walk for a,r in matched_bus if r is not None]
                        return_gaps=[b['minute']-float(r['arrival_min'])-walk for r,b in connected]
                        rows.append({'wing':wing,'rail_direction':direction,'transfer_profile':profile['profile_id'],
                            'transfer_walk_min_assumption':walk,'first_bus_arrival_min_road_only':round(arrivals[0],6),
                            'first_reachable_train_departure_min':float(first['departure_min']) if first else None,
                            'first_reachable_train_trip_id':first['trip_id'] if first else None,
                            'first_train_residual_for_all_bus_delay_and_dwell_min':round(float(first['departure_min'])-arrivals[0]-walk,6) if first else None,
                            'last_train_arrival_with_onward_bus_min':float(last[0]['arrival_min']) if last else None,
                            'last_train_trip_id':last[0]['trip_id'] if last else None,
                            'last_onward_bus_departure_min':last[1]['minute'] if last else None,
                            'bus_arrivals_without_later_train_count':sum(r is None for _,r in matched_bus),
                            'rail_arrivals_without_later_bus_count':sum(b is None for _,b in possible_returns),
                            'max_wait_after_transfer_walk_bus_to_rail_min':round(max(bus_gaps),6) if bus_gaps else None,
                            'max_wait_after_transfer_walk_rail_to_bus_min':round(max(return_gaps),6) if return_gaps else None})
            results.append({'calendar_case':case['calendar_case'],'common_advance_min':advance,
                'advance_scope':scope,'departures':shifted,'worst_optimistic_identity_gap':worst_gap,
                'blocks_by_allowance': [minimum_blocks(shifted,wings['loops'],wings['represented_via_node_joins'],r) for r in (0,5,10,15)],
                'east_shift_relative_to_west_min':-15,'annual_km_before_extras':case['annual_km_before_extras'],
                'remaining_km_before_extras':case['remaining_km_before_extras'],'interchange_rows':rows})
    return {'contract':'RT031_LINE8_FROZEN_RAIL_BOUNDARY_DIAGNOSTIC_V3','service_date':'2026-09-03',
        'cases':results,'phase_domain':'30 integer-minute common advances (0..29), whole-day or morning-only, only east-minus-15 cases; clocks and peak boundaries shift. No best phase selected.',
        'semantics':'Passenger use of every wing return/departure is hypothetical. Zero dwell at intermediate stops. Next feasible train/bus after transfer walk, with no invented maximum wait. A matched event may involve a very long wait; not a useful-connection guarantee.',
        'provenance_scope':'Repository frozen CSV and contract consistency checked, original GTFS not re-downloaded. This is not validation of current railway service.',
        'depot_input_status':'NOT_AVAILABLE_IN_THIS_AUDIT','extra_km_imputed':False,
        'empirical_probability_computed':False,'actual_timetable_certified':False,
        'network_selected':False,'primary_selection_authorised':False,'runner_up_selection_authorised':False,
        'decision_budget_km':None,'uncertainty_band_min':None}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('wings','rail','profiles','rail_contract','output'):
        p.add_argument('--'+k,required=True,type=Path)
    a=p.parse_args()
    with a.rail.open(encoding='utf-8',newline='') as f:
        rail=list(csv.DictReader(f))
    result=build(json.loads(a.wings.read_text(encoding='utf-8')),rail,
                 json.loads(a.profiles.read_text(encoding='utf-8')),json.loads(a.rail_contract.read_text(encoding='utf-8')))
    result['source_sha256']={k:hashlib.sha256(v.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for k,v in vars(a).items() if k!='output'}
    a.output.write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
