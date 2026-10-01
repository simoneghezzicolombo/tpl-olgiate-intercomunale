"""All four frozen railway flows on the unchanged conditional nominal timetable."""
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'outputs/phase2/rt031_line8_local_shortcuts_v3'
SOURCE=BASE/'conditional_proposal_17_trips.json'
RAIL=ROOT/'outputs/phase2/s8_events.csv'
OUTPUT=BASE/'conditional_four_rail_flows_nominal.json'


def onward_bus(arrival, departures, walk=3):
    departure=next((d for d in sorted(departures) if d>=arrival+walk),None)
    return {'bus_departure_min':departure,
        'total_wait_from_train_arrival_min':None if departure is None else departure-arrival,
        'meets_inherited_3_to_8_min_window':departure is not None and 3<=departure-arrival<=8}


def build():
    source=json.loads(SOURCE.read_text(encoding='utf-8'))
    with RAIL.open(encoding='utf-8',newline='') as stream:
        trains=list(csv.DictReader(stream))
    if len(trains)!=74 or {r['service_date'] for r in trains}!={'2026-09-03'}:
        raise ValueError('Frozen railway source drift')
    if source['wing_sequence']!=['east_A','west_B'] or source['network_selected']:
        raise ValueError('Wrong conditional timetable')
    rows=[]
    for wing,loop in source['loops'].items():
        key='first_fs_min' if wing=='east_A' else 'second_fs_min'
        departures=sorted(t[key] for t in source['full_trips'])
        # Same nominal assumption as the upstream ledger: 1.1 moving time,
        # 0.5 min dwell per distinct nonhub path-node service event.
        duration=loop['road_minutes']*1.1+len({e['path_node_index'] for e in loop['events']})*.5
        arrivals=[d+duration for d in departures]
        for train in trains:
            rail_arrival=float(train['arrival_min']); rail_departure=float(train['departure_min'])
            inbound=onward_bus(rail_arrival,departures)
            eligible=[a for a in arrivals if a+3<=rail_departure]
            latest=max(eligible,default=None)
            rows.append({'wing':wing,'train_id':train['trip_id'],
                'train_direction':train['direction'],
                'train_origin_city':'LECCO' if train['direction']=='MILANO' else 'MILANO',
                'train_arrival_min':rail_arrival,'train_departure_min':rail_departure,
                'rail_to_bus':inbound,'bus_to_rail':{
                    'latest_eligible_nominal_bus_arrival_min':latest,
                    'total_wait_to_train_departure_min':None if latest is None else rail_departure-latest,
                    'useful_connection_certified':False}})
    return {'contract':'RT031_FOUR_RAIL_FLOWS_NOMINAL_DIAGNOSTIC_V3',
        'service_date':'2026-09-03','rows':rows,'transfer_walk_assumption_min':3,
        'all_four_flows_explicit':True,
        'semantics':'Each wing, bus to each railway direction and arrivals from each origin. Next feasible bus/latest feasible nominal bus arrival with 3-minute assumed transfer. Long waits retained, not relabelled useful. The inherited 3-8-minute rail-to-bus test is disclosed, not a newly declared user maximum. Frozen date, nominal moving/dwell assumptions only; no current schedule validation, delay distribution, route OD, new rail priority selection or empirical miss probability. Street revisions have NOT been retimed here.',
        'source_sha256':{k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in {'proposal':SOURCE,'rail':RAIL}.items()},
        'current_rail_timetable_verified':False,'street_revisions_retimed':False,
        'network_selected':False,'primary_selection_authorised':False,'runner_up_selection_authorised':False,
        'decision_budget_km':None,'uncertainty_band_min':None}


if __name__=='__main__':
    OUTPUT.write_text(json.dumps(build(),ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
