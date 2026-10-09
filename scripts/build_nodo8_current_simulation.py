"""A dated existing-service animation from one coherent official GTFS snapshot."""
import csv
import hashlib
import io
import json
import math
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZIP = ROOT / 'data/raw/gtfs/agency_arriva/GTFS_invernale_2025-2026_-_Arriva_Italia_e_Addabus.zip'
SHA = 'f890c393b909a40ae9500ab5acba71166cdfc5af3d42be92f55a92d92927553b'
OUT = ROOT / 'assets/nodo8-current-simulation.json'
DATE = '20260506'


def minute(value):
    h, m, s = map(int, value.split(':'))
    return h * 60 + m + s / 60


def build():
    if hashlib.sha256(ZIP.read_bytes()).hexdigest() != SHA:
        raise ValueError('Existing-service archive no longer matches the official frozen source')
    with zipfile.ZipFile(ZIP) as z:
        def rows(name):
            return list(csv.DictReader(io.TextIOWrapper(z.open(name), encoding='utf-8-sig')))
        services = {r['service_id'] for r in rows('calendar.txt')
                    if r['start_date'] <= DATE <= r['end_date'] and r['wednesday'] == '1'}
        for row in rows('calendar_dates.txt'):
            if row['date'] == DATE:
                if row['exception_type'] == '1':
                    services.add(row['service_id'])
                elif row['exception_type'] == '2':
                    services.discard(row['service_id'])
        selected = {t['trip_id']: t for t in rows('trips.txt')
                    if t['route_id'] in ('D184', 'D185') and t['service_id'] in services}
        stops = {s['stop_id']: s for s in rows('stops.txt')}
        times = {trip: [] for trip in selected}
        for r in rows('stop_times.txt'):
            if r['trip_id'] in times:
                times[r['trip_id']].append(r)
        shapes = {t['shape_id']: [] for t in selected.values()}
        for r in rows('shapes.txt'):
            if r['shape_id'] in shapes:
                shapes[r['shape_id']].append(r)
    paths = {}
    for sid, shape in shapes.items():
        shape.sort(key=lambda r: int(r['shape_pt_sequence']))
        distances = [float(r['shape_dist_traveled']) for r in shape]
        if len(shape) < 3 or any(a > b for a, b in zip(distances, distances[1:])):
            raise ValueError('Invalid official shape distances')
        paths[sid] = dict(coordinates=[[float(r['shape_pt_lon']), float(r['shape_pt_lat'])] for r in shape], distances=distances)
    trips = []
    for tid, t in sorted(selected.items()):
        calls = []
        for r in sorted(times[tid], key=lambda r: int(r['stop_sequence'])):
            s = stops[r['stop_id']]
            calls.append(dict(stop_id=r['stop_id'], sequence=int(r['stop_sequence']), name=s['stop_name'],
                              coordinates=[float(s['stop_lon']), float(s['stop_lat'])],
                              arrival_min=minute(r['arrival_time']), departure_min=minute(r['departure_time']),
                              distance=float(r['shape_dist_traveled']), pickup_type=r['pickup_type'], drop_off_type=r['drop_off_type']))
        if len(calls) < 2 or any(c['departure_min'] < c['arrival_min'] for c in calls):
            raise ValueError('Incomplete official stop clocks')
        if any(a['distance'] > b['distance'] or a['departure_min'] > b['arrival_min'] for a, b in zip(calls, calls[1:])):
            raise ValueError('Non-monotone official trip')
        path = paths[t['shape_id']]
        if calls[0]['distance'] < path['distances'][0] or calls[-1]['distance'] > path['distances'][-1] + 0.01:
            raise ValueError('Calls outside their official shape')
        trips.append(dict(id=tid, route=t['route_id'], shape_id=t['shape_id'],
                          direction_id=t['direction_id'], destination=t['trip_headsign'], calls=calls))
    counts = {r: sum(t['route'] == r for t in trips) for r in ['D184', 'D185']}
    if counts != {'D184': 15, 'D185': 19}:
        raise ValueError('Dated inventory disagrees with previously certified GTFS crosscheck')
    return dict(contract='nodo8_existing_service_dated_simulation_v1', service_date='2026-05-06',
                source=dict(path=ZIP.relative_to(ROOT).as_posix(), sha256=SHA,
                            url='https://halleyweb.com/atpcolc/images/File%20GTFS%20inv.%202025-2026/GTFS%20invernale%202025-2026%20-%20Arriva%20Italia%20e%20Addabus.zip'),
                semantics=dict(live=False, latest_2026_27_timetable=False, vehicle_identity_certified=False,
                               movement='INTERPOLATED_ON_OFFICIAL_TRIP_SHAPE_BETWEEN_DATED_STOP_CALLS',
                               missing_stop_times_inferred=False, trip_to_shape='EXACT_GTFS_SHAPE_ID'),
                route_counts=counts, shapes=paths, trips=trips)


if __name__ == '__main__':
    data = build()
    payload = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    if '--check' in sys.argv:
        if OUT.read_text(encoding='utf-8') != payload:
            raise SystemExit('Existing-service animation does not reproduce the official snapshot')
    else:
        OUT.write_text(payload, encoding='utf-8')
    print(f"Built {len(data['trips'])} active dated trips, {len(data['shapes'])} exact GTFS shapes")
