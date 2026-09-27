"""Extract an explicit current comparison date, never relabel frozen train events."""
import argparse
import csv
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import zipfile

from src.phase2_s8_interchange import _infer_direction, parse_gtfs_time, STATION_ID

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'outputs/phase2/rt031_line8_local_shortcuts_v3/s8_20260928_events.json'
URL='https://dati.lombardia.it/download/3z4k-mxz9/application%2Fzip'


def active_services(calendar,exceptions,service_date):
    day=date.fromisoformat(service_date);key=day.strftime('%Y%m%d')
    weekday=('monday','tuesday','wednesday','thursday','friday','saturday','sunday')[day.weekday()]
    active={r['service_id'] for r in calendar if r['start_date']<=key<=r['end_date'] and r[weekday]=='1'}
    seen=set()
    for row in exceptions:
        if row['date']!=key:continue
        sid=row['service_id']
        if sid in seen:raise ValueError('duplicate service/date exception')
        seen.add(sid)
        if row['exception_type']=='1':active.add(sid)
        elif row['exception_type']=='2':active.discard(sid)
        else:raise ValueError('unsupported GTFS exception')
    return active


def extract(tables,service_date):
    active=active_services(tables.get('calendar.txt',[]),tables['calendar_dates.txt'],service_date)
    routes={r['route_id'] for r in tables['routes.txt'] if r['route_short_name']=='S8'}
    if not routes:raise ValueError('S8 route missing')
    trips={r['trip_id']:r for r in tables['trips.txt'] if r['route_id'] in routes and r['service_id'] in active}
    sequences={tid:[] for tid in trips}
    for row in tables['stop_times.txt']:
        if row['trip_id'] in trips:sequences[row['trip_id']].append(row)
    events=[]
    for tid,rows in sequences.items():
        rows.sort(key=lambda r:int(r['stop_sequence']))
        station=[(i,r) for i,r in enumerate(rows) if r['stop_id']==STATION_ID]
        if not station:continue
        if len(station)!=1:raise ValueError('ambiguous station occurrence')
        i,r=station[0]
        direction=_infer_direction({s['stop_id'] for s in rows[i+1:]})
        events.append({'service_date':service_date,'trip_id':tid,'service_id':trips[tid]['service_id'],
                       'trip_short_name':trips[tid].get('trip_short_name',''),'direction':direction,
                       'arrival_min':parse_gtfs_time(r['arrival_time']),'departure_min':parse_gtfs_time(r['departure_time']),
                       'arrival_time':r['arrival_time'],'departure_time':r['departure_time'],
                       'downstream_stop_ids':[s['stop_id'] for s in rows[i+1:]]})
    if not events:raise ValueError('no active station S8 events for date')
    return sorted(events,key=lambda r:(r['departure_min'],r['trip_id']))


def signature(events):
    return sorted((e['direction'],e['arrival_min'],e['departure_min']) for e in events)


def build(path):
    raw=path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names=('routes.txt','trips.txt','stop_times.txt','calendar_dates.txt','calendar.txt')
        tables={name:list(csv.DictReader(io.StringIO(archive.read(name).decode('utf-8-sig')))) for name in names if name in archive.namelist()}
    dates=['2026-09-28','2026-09-29','2026-09-30','2026-10-01','2026-10-02']
    events=extract(tables,dates[0])
    old=list(csv.DictReader((ROOT/'outputs/phase2/s8_events.csv').open(encoding='utf-8')))
    old_signature=sorted((e['direction'],float(e['arrival_min']),float(e['departure_min'])) for e in old)
    return {'contract':'RT031_S8_CURRENT_DATED_EVENT_REFRESH_V3','source_url':URL,
            'retrieved_on':'2026-09-27','official_gtfs_sha256':hashlib.sha256(raw).hexdigest(),
            'station_stop_id':STATION_ID,'service_date':dates[0],'events':events,
            'direction_method':'DOWNSTREAM_ENDPOINT_STOP_SEQUENCE_NOT_TRAIN_NUMBER',
            'weekday_checks':[{'service_date':d,'event_count':len(e),'same_station_clock_signature_as_reference_day':signature(e)==signature(events)} for d in dates for e in [extract(tables,d)]],
            'same_station_clock_signature_as_20260903':signature(events)==old_signature,
            'reuses_legacy_trip_ids':bool({e['trip_id'] for e in events}&{e['trip_id'] for e in old}),
            'semantics':'Dated scheduled events from officially downloaded GTFS. Calendar dates applied and directions inferred from downstream endpoints. Same zip may contain several validity periods: archive age is not trip expiry. No actual on-time probability, live cancellation check, annual calendar adoption or future-year applicability.',
            'annual_calendar_certified':False,'empirical_connection_probability':None}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--gtfs',type=Path,default=ROOT/'cache/rt031-s8-20260927/trenord_gtfs.zip')
    args=parser.parse_args();result=build(args.gtfs)
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('events','semantics')}))
