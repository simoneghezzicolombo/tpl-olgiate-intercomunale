"""Frozen local S8 visualisation. No new timetable or straight-line rail repairs."""
import csv
import hashlib
import heapq
import io
import json
import math
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OSM_TILES = [(ROOT / f'cache/nodo8-s8-rail-{south}.osm',
              f'https://api.openstreetmap.org/api/0.6/map?bbox=9.388,{south},9.432,{north}')
             for south, north in [('45.688', '45.703'), ('45.703', '45.718'),
                                  ('45.718', '45.733'), ('45.733', '45.748'), ('45.748', '45.762')]]
GTFS = ROOT / 'cache/rt031-all-rail-20261001/trenord_gtfs.zip'
INVENTORY = ROOT / 'outputs/phase2/rt031_line8_local_shortcuts_v3/all_station_rail_20261001.json'
OUT = ROOT / 'assets/nodo8-s8-simulation.json'


def distance(a, b):
    lat = math.radians((a[1] + b[1]) / 2)
    return math.hypot((a[0] - b[0]) * math.cos(lat), a[1] - b[1]) * 111195


def minutes(value):
    h, m, s = map(int, value.split(':'))
    return h * 60 + m + s / 60


def build():
    inventory = json.loads(INVENTORY.read_text(encoding='utf-8'))
    if hashlib.sha256(GTFS.read_bytes()).hexdigest() != inventory['source_sha256']['gtfs']:
        raise ValueError('Rail GTFS no longer matches the certified dated inventory')
    nodes, graph, ways = {}, {}, {}
    for path, _ in OSM_TILES:
        for _, el in ET.iterparse(path, events=('end',)):
            if el.tag == 'node':
                nodes[el.attrib['id']] = [float(el.attrib['lon']), float(el.attrib['lat'])]
                el.clear()
            elif el.tag == 'way':
                tags = {t.attrib['k']: t.attrib['v'] for t in el.findall('tag')}
                if tags.get('railway') == 'rail' and not tags.get('service'):
                    ways[el.attrib['id']] = [n.attrib['ref'] for n in el.findall('nd')]
                el.clear()
    for way, refs in ways.items():
        for a, b in zip(refs, refs[1:]):
            if a not in nodes or b not in nodes:
                # No connectors invented at the snapshot boundary.
                continue
            d = distance(nodes[a], nodes[b])
            graph.setdefault(a, []).append((b, d, way))
            graph.setdefault(b, []).append((a, d, way))
    with zipfile.ZipFile(GTFS) as z:
        def rows(name):
            return csv.DictReader(io.TextIOWrapper(z.open(name), encoding='utf-8-sig'))
        stops = {s['stop_id']: s for s in rows('stops.txt')}
        event_by_id = {e['trip_id']: e for e in inventory['events'] if e['route_id'] == 'S8'}
        stop_times = {trip: {} for trip in event_by_id}
        for row in rows('stop_times.txt'):
            if row['trip_id'] in stop_times:
                stop_times[row['trip_id']][row['stop_id']] = row
    station_ids = ['S01513', 'S01514', 'S01515']
    # Parallel main tracks need not connect within this local snapshot. Select
    # one connected corridor near all three stations, not per-station tracks
    # that would require inventing a crossover. This is not a track assignment.
    coordinates = {sid: [float(stops[sid]['stop_lon']), float(stops[sid]['stop_lat'])] for sid in station_ids}
    remaining, candidates = set(graph), []
    while remaining:
        component, pending = set(), [min(remaining)]
        while pending:
            node = pending.pop()
            if node in component:
                continue
            component.add(node)
            pending.extend(n for n, _, _ in graph[node] if n not in component)
        remaining.difference_update(component)
        closest = {sid: min(component, key=lambda n: (distance(nodes[n], coord), n)) for sid, coord in coordinates.items()}
        distances = [distance(nodes[closest[sid]], coordinates[sid]) for sid in station_ids]
        if max(distances) <= 150:
            candidates.append((sum(distances), closest))
    if not candidates:
        raise ValueError('No connected main rail corridor near all three stations')
    snapped = min(candidates, key=lambda item: item[0])[1]
    stations = []
    for sid in station_ids:
        s = stops[sid]
        coordinate = [float(s['stop_lon']), float(s['stop_lat'])]
        node = snapped[sid]
        snap = distance(nodes[node], coordinate)
        if snap > 150:
            raise ValueError(f'{sid} outside frozen rail geometry: {snap:.1f} m')
        stations.append(dict(id=sid, name=s['stop_name'], coordinates=nodes[node],
                             gtfs_coordinates=coordinate, snap_distance_m=snap, node=node))
    segments = []
    for start, end in zip(stations, stations[1:]):
        queue, seen, prev = [(0, start['node'])], {}, {}
        while queue:
            cost, node = heapq.heappop(queue)
            if node in seen:
                continue
            seen[node] = cost
            if node == end['node']:
                break
            for nxt, d, way in graph[node]:
                if nxt not in seen and cost + d < prev.get(nxt, (math.inf, None, None))[0]:
                    prev[nxt] = (cost + d, node, way)
                    heapq.heappush(queue, (cost + d, nxt))
        if end['node'] not in seen:
            raise ValueError('Disconnected frozen rail graph; no invented connector allowed')
        ids, ways = [end['node']], []
        while ids[-1] != start['node']:
            _, parent, way = prev[ids[-1]]
            ways.append(way)
            ids.append(parent)
        ids.reverse()
        coordinates = [nodes[n] for n in ids]
        if not 2000 < seen[end['node']] < 7000:
            raise ValueError('Unexpected local rail path length')
        segments.append(dict(from_id=start['id'], to_id=end['id'],
                             coordinates=coordinates, distance_m=seen[end['node']],
                             osm_way_ids=sorted(set(ways))))
    trains = []
    for trip, event in event_by_id.items():
        seq = station_ids if event['direction'] == 'LECCO' else station_ids[::-1]
        calls = []
        for sid in seq:
            row = stop_times[trip][sid]
            calls.append(dict(station_id=sid, arrival_min=minutes(row['arrival_time']),
                              departure_min=minutes(row['departure_time'])))
        hub = next(c for c in calls if c['station_id'] == 'S01514')
        if hub['arrival_min'] != event['arrival_min'] or hub['departure_min'] != event['departure_min']:
            raise ValueError('GTFS and certified station inventory disagree')
        if any(a['departure_min'] >= b['arrival_min'] for a, b in zip(calls, calls[1:])):
            raise ValueError('Non-monotone rail times')
        trains.append(dict(id=trip, number=event['train_number'], direction=event['direction'], calls=calls))
    if len(trains) != 74 or {d: sum(t['direction'] == d for t in trains) for d in ['MILANO', 'LECCO']} != {'MILANO': 37, 'LECCO': 37}:
        raise ValueError('Unexpected certified rail inventory')
    sources = []
    for path, url in [*OSM_TILES, (GTFS, inventory['source_urls']['gtfs']), (INVENTORY, None)]:
        sources.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), url=url))
    return dict(contract='nodo8_s8_local_simulation_v1', colour='#f8b1b0', service_date='2026-10-01', geometry_retrieved_on='2026-10-09',
                scope='LOCAL_CERNUSCO_MERATE_OLGIATE_AIRUNO_NOT_FULL_S8', sources=sources,
                semantics=dict(movement='DISTANCE_INTERPOLATION_BETWEEN_DATED_GTFS_CALLS',
                               geometry='SHORTEST_CONNECTED_MAIN_RAIL_PATH_IN_FROZEN_OSM_NOT_TRACK_ASSIGNMENT',
                               live=False, timetable_2027_certified=False, connection_guaranteed=False,
                               platform_assignment_certified=False),
                stations=stations, segments=segments, trains=trains)


if __name__ == '__main__':
    import sys
    result = build()
    payload = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if '--check' in sys.argv:
        if OUT.read_text(encoding='utf-8') != payload:
            raise SystemExit('S8 visualisation does not reproduce the frozen evidence')
    else:
        OUT.write_text(payload, encoding='utf-8')
    print(f"Built {len(result['trains'])} dated trains, {sum(len(s['coordinates']) for s in result['segments'])} rail vertices")
