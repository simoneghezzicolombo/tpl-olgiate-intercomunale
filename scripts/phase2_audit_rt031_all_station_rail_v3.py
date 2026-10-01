"""Dated ALL-route station inventory, cross-check against the full RFI day.

Never infer a demand weight, delay probability or priority from train counts.
"""
import argparse
from collections import Counter
import csv
from datetime import date, datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

from bs4 import BeautifulSoup
import requests
from scripts.phase2_refresh_rt031_s8_service_date_v3 import active_services
from src.phase2_s8_interchange import parse_gtfs_time, STATION_ID

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'outputs/phase2/rt031_line8_local_shortcuts_v3'
CACHE = ROOT / 'cache/rt031-all-rail-20261001'
OUTPUT = BASE / 'all_station_rail_20261001.json'
GTFS_URL = 'https://dati.lombardia.it/download/3z4k-mxz9/application%2Fzip'
RFI_URL = 'https://prm.rfi.it/qo_prm/QO_Partenze_SiPMR.aspx?Id=1805&alle=23.59&dalle=00.00&guid=&ora=00.00'
MONTHS = {'gennaio':1,'febbraio':2,'marzo':3,'aprile':4,'maggio':5,'giugno':6,
          'luglio':7,'agosto':8,'settembre':9,'ottobre':10,'novembre':11,'dicembre':12}


def load_tables(path):
    with zipfile.ZipFile(path) as archive:
        return {n:list(csv.DictReader(io.StringIO(archive.read(n).decode('utf-8-sig'))))
                for n in ('routes.txt','trips.txt','stops.txt','stop_times.txt','calendar.txt','calendar_dates.txt')
                if n in archive.namelist()}


def axis(names):
    cities = set()
    for name in names:
        name = name.upper().strip()
        if name.startswith('MILANO'): cities.add('MILANO')
        if name in ('LECCO','LECCO MAGGIANICO'): cities.add('LECCO')
    return next(iter(cities)) if len(cities) == 1 else 'UNKNOWN'


def train_number(short_name):
    # Official trip_short_name can be "S8 - 24817". Strip ONLY the
    # explicitly delimited product prefix, never guess from a trip_id.
    match=re.fullmatch(r'(?:[A-Za-z][A-Za-z0-9 ]*\s*-\s*)?(\d+)',short_name.strip())
    if not match: raise ValueError('Unsupported explicit train number')
    return match.group(1)


def extract_all(tables, service_date):
    active = active_services(tables.get('calendar.txt',[]), tables.get('calendar_dates.txt',[]), service_date)
    if not active: raise ValueError('No active service calendar: date unsupported')
    stops = {r['stop_id']:r for r in tables['stops.txt']}
    if STATION_ID not in stops: raise ValueError('Station missing')
    cluster = {STATION_ID}
    while True:
        more = {s for s,r in stops.items() if r.get('parent_station') in cluster}
        if more <= cluster: break
        cluster |= more
    routes = {r['route_id']:r for r in tables['routes.txt']}
    trips = {r['trip_id']:r for r in tables['trips.txt'] if r['service_id'] in active}
    calls = {r['trip_id'] for r in tables['stop_times.txt'] if r['stop_id'] in cluster and r['trip_id'] in trips}
    sequences = {tid:[] for tid in calls}
    for r in tables['stop_times.txt']:
        if r['trip_id'] in sequences: sequences[r['trip_id']].append(r)
    events = []
    for tid, rows in sequences.items():
        rows.sort(key=lambda r:int(r['stop_sequence']))
        if len({r['stop_sequence'] for r in rows}) != len(rows): raise ValueError('Duplicate trip stop sequence')
        hits = [(i,r) for i,r in enumerate(rows) if r['stop_id'] in cluster]
        if len(hits) != 1: raise ValueError('Ambiguous station event')
        i, call = hits[0]; trip = trips[tid]
        if trip['route_id'] not in routes: raise ValueError('Unknown calling route')
        route = routes[trip['route_id']]
        names = [stops[r['stop_id']]['stop_name'] for r in rows]
        arrival = parse_gtfs_time(call['arrival_time']); departure = parse_gtfs_time(call['departure_time'])
        if departure < arrival: raise ValueError('Nonmonotone station arrival/departure')
        pickup = call.get('pickup_type') or '0'; dropoff = call.get('drop_off_type') or '0'
        if pickup not in ('0','1','2','3') or dropoff not in ('0','1','2','3'):
            raise ValueError('Unsupported boarding/alighting type')
        events.append(dict(service_date=service_date, trip_id=tid, service_id=trip['service_id'],
            train_number=train_number(trip.get('trip_short_name','')), trip_short_name_raw=trip.get('trip_short_name',''), route_id=trip['route_id'],
            route_short_name=route.get('route_short_name',''), route_long_name=route.get('route_long_name',''),
            route_type=route.get('route_type'), station_stop_id=call['stop_id'],
            arrival_time=call['arrival_time'], departure_time=call['departure_time'],
            arrival_min=arrival, departure_min=departure,
            origin_stop_id=rows[0]['stop_id'], origin_name=names[0],
            destination_stop_id=rows[-1]['stop_id'], destination_name=names[-1],
            upstream_stop_ids=[r['stop_id'] for r in rows[:i]],
            downstream_stop_ids=[r['stop_id'] for r in rows[i+1:]],
            direction=axis(names[i+1:]), origin_axis=axis(names[:i]),
            pickup_type=pickup, drop_off_type=dropoff,
            ordinary_boarding_supported=pickup=='0' and i<len(rows)-1,
            ordinary_alighting_supported=dropoff=='0' and i>0))
    if not events: raise ValueError('No station calls on requested date')
    return sorted(events,key=lambda e:(e['departure_min'],e['trip_id']))


def parse_rfi(raw, service_date):
    soup = BeautifulSoup(raw.decode('windows-1252'), 'html.parser')
    text = soup.get_text(' ',strip=True)
    match = re.search(r'ORARIO PROGRAMMATO\s+(\d{1,2})\s+(\w+)\s+(\d{4})\s*-\s*(\d{1,2})\s+(\w+)\s+(\d{4})',text,re.I)
    if not match: raise ValueError('RFI timetable validity missing')
    d,m,y,d2,m2,y2 = match.groups()
    start = date(int(y),MONTHS[m.lower()],int(d)); end = date(int(y2),MONTHS[m2.lower()],int(d2))
    if not start <= date.fromisoformat(service_date) <= end: raise ValueError('RFI validity excludes service date')
    if 'OLGIATE-CALCO-BRIVIO' not in text: raise ValueError('Wrong RFI station')
    table = soup.select_one('table.QOtab')
    if table is None: raise ValueError('RFI departure table missing')
    calls = []
    for row in table.select('tbody > tr'):
        cells = row.find_all('td',recursive=False)
        if len(cells) != 9:
            if cells and re.fullmatch(r'\d\d\.\d\d',cells[0].get_text(' ',strip=True)):
                raise ValueError('Unrecognized RFI call row')
            continue
        values = [c.get_text(' ',strip=True) for c in cells]
        clock, number = values[:2]
        if not re.fullmatch(r'\d\d\.\d\d',clock) or not re.fullmatch(r'\d+',number):
            raise ValueError('Unsupported RFI train number/time')
        h,minute = map(int,clock.split('.'))
        if h>23 or minute>59: raise ValueError('Invalid RFI clock')
        calls.append(dict(train_number=number, departure_clock=clock, departure_clock_min=h*60+minute,
            product_types=[i.get('alt','') for i in cells[1].select('img')],
            destination_text=values[2], upstream_text=values[6], downstream_text=values[7],
            periodicity_and_warnings_text=values[8]))
    if not calls: raise ValueError('Empty RFI day')
    return dict(valid_from=start.isoformat(),valid_until=end.isoformat(),calls=calls,
        periodicity_applied_by_gtfs_calendar_not_rfi_text=True)


def reconcile(events, rfi):
    # RFI is a clock-day panel: GTFS 24:03 is 00:03, but the dated GTFS
    # service-day event itself retains 1443 minutes and is never moved earlier.
    gt = Counter((e['train_number'],e['departure_min']%1440) for e in events)
    rf = Counter((e['train_number'],e['departure_clock_min']) for e in rfi['calls'])
    return dict(matched=gt==rf,gtfs_only=list((gt-rf).elements()),rfi_only=list((rf-gt).elements()),
        method='Exact train number + station DEPARTURE clock modulo 24h; no arrival/departure conflation. RFI lists timetable-period calls; per-date applicability comes from GTFS calendars.')


def build(gtfs_path, rfi_path, retrieved_at_utc, service_date='2026-10-01'):
    if not retrieved_at_utc: raise ValueError('Source retrieval metadata required')
    tables = load_tables(gtfs_path); events = extract_all(tables,service_date)
    rfi = parse_rfi(rfi_path.read_bytes(),service_date); cross = reconcile(events,rfi)
    checks = []
    for d in ('2026-10-01','2026-10-02','2026-10-03','2026-10-04','2026-10-05'):
        rows = extract_all(tables,d)
        checks.append(dict(service_date=d,event_count=len(rows),route_counts=dict(Counter(e['route_short_name'] for e in rows))))
    unknown = [e['trip_id'] for e in events if e['direction']=='UNKNOWN' or e['origin_axis']=='UNKNOWN']
    return dict(contract='RT031_ALL_STATION_DATED_RAIL_INVENTORY_V3',
        required_scope='ALL_CALLING_ROUTES_NO_S8_FILTER',station_stop_id=STATION_ID,service_date=service_date,
        source_urls=dict(gtfs=GTFS_URL,rfi_departures=RFI_URL),retrieved_at_utc=retrieved_at_utc,
        source_sha256=dict(gtfs=hashlib.sha256(gtfs_path.read_bytes()).hexdigest(),rfi_departures=hashlib.sha256(rfi_path.read_bytes()).hexdigest()),
        events=events,event_count=len(events),route_counts=dict(Counter(e['route_short_name'] for e in events)),
        direction_counts=dict(Counter(e['direction'] for e in events)),unknown_axes_trip_ids=unknown,
        rfi=rfi,rfi_gtfs_reconciliation=cross,calendar_checks=checks,
        scheduled_call_inventory_crosschecked=cross['matched'],
        ready_for_dated_rail_diagnostic=cross['matched'] and not unknown,
        real_time_disruption_check_performed=False,annual_calendar_certified=False,
        empirical_connection_probability=None,network_selected=False,
        primary_selection_authorised=False,runner_up_selection_authorised=False,
        decision_budget_km=None,uncertainty_band_min=None,
        semantics='All active GTFS trips calling at the station/child platforms, across all routes, with dated calendar exceptions and actual origin/destination. Exact full-day RFI departure-panel reconciliation for the stated date and timetable validity. Not a guarantee of future-year or annual calendar validity, actual operations, cancellations, demand or on-time connections. Counting a train does not make it a mandatory guaranteed target.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--fetch',action='store_true')
    parser.add_argument('--service-date',default='2026-10-01'); args=parser.parse_args()
    metadata_path=CACHE/'retrieval.json'; rfi_path=CACHE/'rfi_full_day_departures.html'; gtfs_path=CACHE/'trenord_gtfs.zip'
    if args.fetch:
        CACHE.mkdir(parents=True,exist_ok=True)
        for url,path in ((GTFS_URL,gtfs_path),(RFI_URL,rfi_path)):
            response=requests.get(url,timeout=40); response.raise_for_status(); path.write_bytes(response.content)
        metadata_path.write_text(json.dumps(dict(retrieved_at_utc=datetime.now(timezone.utc).isoformat(),source_urls=[GTFS_URL,RFI_URL]),indent=2)+'\n',encoding='utf-8')
    metadata=json.loads(metadata_path.read_text(encoding='utf-8'))
    result=build(gtfs_path,rfi_path,metadata['retrieved_at_utc'],args.service_date)
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('event_count','route_counts','direction_counts','rfi_gtfs_reconciliation','calendar_checks','ready_for_dated_rail_diagnostic')}))
