"""Separate planned rail platforms, pedestrian approaches and transfer budgets.

The confirmed route/timetable is unchanged. OSM approach distances are not
observed door-to-door transfer times, and a planned departure platform does
not certify the actual arrival platform or accessible passenger path.
"""
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
import hashlib
import heapq
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from shapely.geometry import LineString, box, mapping

from phase2_final_stop_pedestrian_accessibility_substrate_v3 import (
    _allows_foot, parse_osm_pedestrian_graph,
)
from scripts.phase2_audit_rt031_confirmed_locality_points_v3 import (
    OSM_SHA256, GRAPH_DIGEST, WALK_METRES_PER_MIN,
)
from scripts.phase2_package_rt031_confirmed_design_handoff_v3 import (
    BASE, OUTPUT as HANDOFF, DESIGN, canonical_sha256, build as handoff_build,
)
from scripts.phase2_package_rt031_current_16_trip_proposal_v3 import SOURCE, RAIL
from scripts.phase2_audit_rt031_all_station_rail_v3 import parse_rfi
from scripts.phase2_probe_rt031_line8_variable_fs_hold_v3 import wing_offsets
from scripts.phase2_audit_rt031_line8_current_rail_connections_v3 import connection_row
from scripts.phase2_rt031_station_platform_surface_v3 import augment_platform_surfaces, MODEL_KIND

ROOT = Path(__file__).resolve().parents[1]
RFI = ROOT / 'cache/rt031-all-rail-20261001/rfi_full_day_departures.html'
ACCESSIBILITY_REVIEW = ROOT / 'config/rt031_station_accessibility_primary_review_20261002_v3.json'
CALLER_CORRECTION = ROOT / 'config/rt031_station_underpass_caller_correction_20261007_v3.json'
SOURCE_RECOVERY = ROOT / 'config/rt031_rt028_source_recovery_20261007_v3.json'
DEFAULT_OSM = ROOT / 'cache/rt028-certified-34039162932/input/rt028_osm_pedestrian_snapshot_v3.osm'
OUTPUT = BASE / 'station_platform_transfer_audit_20261002.json'
GEO = BASE / 'station_platform_transfer_paths_20261002.geojson'
BRIEF = ROOT / 'docs/RT031_LINEA8_ACCESSI_BINARI_2026_10_02.md'
FS = 'FROZEN::L00407'
PLATFORM_WAYS = {'1': '1232462159', '2': '1232462158'}


def tags(element):
    return {t.attrib['k']: t.attrib['v'] for t in element.findall('tag')}


def planned_platforms(raw, rail):
    """Exact dated number + departure-clock join; never guess by direction."""
    if hashlib.sha256(raw).hexdigest() != rail['source_sha256']['rfi_departures']:
        raise ValueError('Pinned RFI source drift')
    parsed = parse_rfi(raw, rail['service_date'])
    if parsed != rail['rfi']:
        raise ValueError('RFI dated call inventory drift')
    soup = BeautifulSoup(raw.decode('windows-1252'), 'html.parser')
    table = soup.select_one('table.QOtab')
    headings = [t.get_text(' ', strip=True) for t in table.select('thead th')]
    if len(headings) != 9 or headings[3] != 'Binario programmato':
        raise ValueError('RFI planned platform column not identified')
    indexed = {}
    for row in table.select('tbody > tr'):
        cells = row.find_all('td', recursive=False)
        if len(cells) != 9:
            continue
        values = [c.get_text(' ', strip=True) for c in cells]
        h, m = map(int, values[0].split('.'))
        key = values[1], 60*h+m
        if key in indexed:
            raise ValueError('Duplicate RFI planned platform call')
        platform = values[3]
        if platform not in PLATFORM_WAYS:
            raise ValueError('Missing or unsupported planned platform')
        indexed[key] = platform
    expected = Counter((t['train_number'], t['departure_min'] % 1440)
                       for t in rail['events'])
    if expected != Counter(indexed.keys()):
        raise ValueError('Dated train/platform call set mismatch')
    return [dict(trip_id=t['trip_id'], train_number=t['train_number'],
                 departure_min=t['departure_min'], arrival_min=t['arrival_min'],
                 direction=t['direction'], origin_axis=t['origin_axis'],
                 planned_departure_platform=indexed[t['train_number'], t['departure_min'] % 1440],
                 actual_departure_platform_certified=False,
                 arrival_platform_certified=False)
            for t in rail['events']]


def snapshot_objects(path):
    root = ET.parse(path).getroot()
    nodes = {n.attrib['id']: dict(coordinates_lon_lat=[float(n.attrib['lon']), float(n.attrib['lat'])],
                                tags=tags(n)) for n in root.findall('node')}
    ways = {w.attrib['id']: dict(nodes=[n.attrib['ref'] for n in w.findall('nd')],
                               tags=tags(w)) for w in root.findall('way')}
    return nodes, ways


def edge_sources(graph, ways):
    """Retain original way tags on the exact routable directed edges."""
    pairs = {(u, v) for u, outgoing in graph.adjacency.items() for v, _ in outgoing}
    indexed = defaultdict(list)
    for wid, way in ways.items():
        t = way['tags']
        if not _allows_foot(t):
            continue
        one = t.get('oneway:foot', '').strip().lower()
        for u, v in zip(way['nodes'], way['nodes'][1:]):
            directions = [(v, u)] if one in ('-1', 'reverse') else [(u, v)]
            if one not in ('yes', '1', 'true', '-1', 'reverse'):
                directions.append((v, u))
            for pair in directions:
                if pair in pairs:
                    indexed[pair].append(dict(osm_way_id=wid, tags=t))
    if any(pair not in indexed for pair in pairs):
        raise ValueError('Pedestrian edge lacks original directed-way provenance')
    return indexed


def approach_path(adjacency, provenance, source, targets, no_steps=False):
    """Directed shortest distance to a sourced platform surface-access node.

    No snap to a rail stop/centroid. Explicit local platform-area model edges,
    if supplied, retain distinct provenance from native OSM highway edges.
    Excluding steps is only a sensitivity, not wheelchair/access certification.
    """
    if not targets or source not in adjacency:
        return None
    best, previous = {source: 0.0}, {}
    queue = [(0.0, source)]
    finish = None
    while queue:
        distance, node = heapq.heappop(queue)
        if distance != best[node]:
            continue
        if node in targets:
            finish = node
            break
        for nxt, length in adjacency[node]:
            if not math.isfinite(length) or length <= 0:
                raise ValueError('Finite positive pedestrian edge length required')
            options = [p for p in provenance[node, nxt]
                       if not no_steps or p['tags'].get('highway') != 'steps']
            if not options:
                continue
            chosen = min(options, key=lambda p: (p['tags'].get('highway') == 'steps', p['osm_way_id']))
            value = distance+length
            if value < best.get(nxt, math.inf):
                best[nxt], previous[nxt] = value, (node, length, chosen)
                heapq.heappush(queue, (value, nxt))
    if finish is None:
        return None
    edges = []
    cursor = finish
    while cursor != source:
        before, length, witness = previous[cursor]
        edges.append(dict(u=before, v=cursor, length_m=length, **witness))
        cursor = before
    edges.reverse()
    return dict(path_node_ids=[source]+[e['v'] for e in edges], path_edges=edges,
                approach_node_id=finish, network_distance_m=best[finish],
                contains_steps=any(e['tags'].get('highway') == 'steps' for e in edges),
                steps_distance_m=sum(e['length_m'] for e in edges if e['tags'].get('highway') == 'steps'),
                contains_modelled_platform_surface=any(e.get('geometry_kind') == MODEL_KIND for e in edges),
                modelled_platform_surface_distance_m=sum(e['length_m'] for e in edges if e.get('geometry_kind') == MODEL_KIND),
                step_free_path_certified=False, physical_transfer_certified=False)


def transfer_envelope(arrival, departure, bus_start, east_duration, inbound_walk, outbound_walk):
    """Independent directional assumptions; no caller margin is selected."""
    values = (arrival, departure, bus_start, east_duration, inbound_walk, outbound_walk)
    if not all(math.isfinite(x) and x >= 0 for x in values):
        raise ValueError('Finite nonnegative transfer-envelope inputs required')
    if departure < arrival:
        raise ValueError('Paired departure precedes arriving train')
    lower = arrival+inbound_walk
    upper = departure-east_duration-outbound_walk
    width = upper-lower
    return dict(earliest_departure_min=lower, latest_departure_min=upper,
                interval_width_min=width, interval_nonempty=width >= 0,
                best_balanced_residual_min=width/2 if width >= 0 else None,
                baseline_inbound_residual_min=bus_start-lower,
                baseline_outbound_residual_min=upper-bus_start,
                theoretical_balanced_phase_min=(lower+upper)/2 if width >= 0 else None,
                phase_selected=False, normative_margin_selected=False)


def validate_accessibility_review(review):
    """Keep primary reported provision separate from this bus-access proof."""
    if (review['contract'] != 'RT031_STATION_ACCESSIBILITY_PRIMARY_SOURCE_REVIEW_V3'
            or review['source_url'] != 'https://www.rfi.it/it/stazioni/olgiate-calco-brivio.html'
            or review['station_name'] != 'Olgiate-Calco-Brivio'
            or review['reported_platform_count'] != 2
            or review['reported_level_or_ramp_access_to_platforms'] != ['1', '2']):
        raise ValueError('Reviewed official station access source drift')
    if (review['geometry_supplied_by_this_record'] is not None
            or review['actual_transfer_minutes'] is not None
            or review['bus_stop_to_accessible_entrance_connected_and_verified'] is not False
            or review['actual_train_door_accessibility_certified'] is not False
            or any(review[k] is not False for k in ('network_selected',
                        'primary_selection_authorised', 'runner_up_selection_authorised'))
            or any(review[k] is not None for k in ('decision_budget_km', 'uncertainty_band_min'))):
        raise ValueError('Official provision cannot certify bus path, transfer time or decision authority')


def dated_flows(schedule, offsets, rail, bindings, platform_access):
    """All 296 flow combinations, platform APPROACH-only diagnostic.

    Planned departure platform is used as an explicitly unverified arrival
    platform hypothesis. Unavailable approach evidence cannot become a zero.
    """
    by_trip = {r['trip_id']: r for r in bindings}
    rows = []
    for wing in ('east_A', 'west_B'):
        starts = [t['first_fs_min' if wing == 'east_A' else 'second_fs_min']
                  for t in schedule['full_trips']]
        durations = {k: g[wing]['road_minutes'] for k, g in offsets.items()}
        for train in rail['events']:
            platform = by_trip[train['trip_id']]['planned_departure_platform']
            access = platform_access[platform]
            inbound, outbound = access['platform_to_bus'], access['bus_to_platform']
            if inbound is None or outbound is None:
                raise ValueError('Cannot impute missing platform approach as zero')
            a = connection_row(train, wing, starts, durations, walk=inbound['approach_only_walk_model_min'])
            b = connection_row(train, wing, starts, durations, walk=outbound['approach_only_walk_model_min'])
            rows.append(dict(wing=wing, trip_id=train['trip_id'], train_number=train['train_number'],
                             train_direction=train['direction'], planned_platform=platform,
                             arrival_platform_assumed_same_as_departure=True,
                             arrival_platform_certified=False,
                             rail_to_bus=a['rail_to_bus'], bus_to_rail=b['bus_to_rail'],
                             approach_inbound_walk_min=inbound['approach_only_walk_model_min'],
                             approach_outbound_walk_min=outbound['approach_only_walk_model_min'],
                             observed_door_to_door_transfer=False,
                             passenger_connection_certified=False))
    return rows


def build(pedestrian_osm, rfi_path=RFI):
    pedestrian_osm = Path(pedestrian_osm)
    if hashlib.sha256(pedestrian_osm.read_bytes()).hexdigest() != OSM_SHA256:
        raise ValueError('Pinned RT028 pedestrian source drift')
    handoff = json.loads(HANDOFF.read_text(encoding='utf-8'))
    if canonical_sha256(handoff) != canonical_sha256(handoff_build()):
        raise ValueError('Caller-confirmed design source drift')
    schedule, design, rail = [json.loads(p.read_text(encoding='utf-8')) for p in (SOURCE, DESIGN, RAIL)]
    accessibility = json.loads(ACCESSIBILITY_REVIEW.read_text(encoding='utf-8'))
    validate_accessibility_review(accessibility)
    correction = json.loads(CALLER_CORRECTION.read_text(encoding='utf-8'))
    recovery = json.loads(SOURCE_RECOVERY.read_text(encoding='utf-8'))
    if (correction['reported_transfer_minutes'] is not None
            or correction['timetable_change_authorised'] is not False
            or correction['caller_confirmed_displayed_path_topology'] is not True
            or correction['step_free_access_claimed'] is not False
            or correction['reported_path_sequence'] != ['platform_2','stairs_down','underpass','stairs_up','platform_1']
            or recovery['expected_osm_sha256'] != OSM_SHA256):
        raise ValueError('Caller path correction cannot fabricate measured time or authority')
    bindings = planned_platforms(Path(rfi_path).read_bytes(), rail)
    graph = parse_osm_pedestrian_graph(pedestrian_osm)
    if graph.graph_digest != GRAPH_DIGEST:
        raise ValueError('Pinned RT028 pedestrian graph drift')
    nodes, ways = snapshot_objects(pedestrian_osm)
    provenance = edge_sources(graph, ways)
    adjacency, reverse, routed_sources, surface = augment_platform_surfaces(
        graph.adjacency, provenance, nodes, ways, PLATFORM_WAYS)
    fs = next(s for s in handoff['design_stop_register'] if s['site_id'] == FS)
    lon, lat = fs['coordinates_lon_lat']
    snap = graph.snap(lat, lon)
    if snap.status != 'REACHABLE':
        raise ValueError('Confirmed FS point has no pedestrian attachment')
    platforms, features, previous_paths = {}, [], {}
    # Real snapshot streets and rails clipped for a compact station basemap.
    extent = box(9.4028, 45.7282, 9.4049, 45.7300)
    for wid, way in ways.items():
        if not (way['tags'].get('highway') or way['tags'].get('railway') == 'rail'):
            continue
        coords = [nodes[n]['coordinates_lon_lat'] for n in way['nodes']]
        if len(coords) < 2:
            continue
        geom = LineString(coords).intersection(extent)
        if geom.is_empty:
            continue
        features.append(dict(type='Feature', geometry=mapping(geom), properties=dict(
            role='BASEMAP', osm_way_id=wid, **way['tags'])))
    for ref, wid in PLATFORM_WAYS.items():
        way = ways[wid]
        if (way['tags'].get('railway') != 'platform' or way['tags'].get('ref') != ref
                or way['tags'].get('area') != 'yes' or way['nodes'][0] != way['nodes'][-1]):
            raise ValueError('OSM platform identity/topology drift')
        old_targets = set(way['nodes']) & set(graph.node_ids)
        targets = set(surface[ref]['surface_access_node_ids'])
        routes = {}
        previous_paths[ref] = {}
        for direction in ('bus_to_platform', 'platform_to_bus'):
            graph_direction = adjacency if direction == 'bus_to_platform' else reverse
            directed_sources = routed_sources if direction == 'bus_to_platform' else {
                (v, u): records for (u, v), records in routed_sources.items()}
            old_graph = graph.adjacency if direction == 'bus_to_platform' else graph.reverse_adjacency
            old_sources = provenance if direction == 'bus_to_platform' else {
                (v,u): records for (u,v), records in provenance.items()}
            previous = approach_path(old_graph, old_sources, snap.node_id, old_targets)
            previous_paths[ref][direction] = dict(
                old_boundary_only_network_distance_m=None if previous is None else previous['network_distance_m'],
                used_in_current_transfer_diagnostic=False,
                superseded_reason='Platform internal stair tops and platform surface continuity were omitted.')
            path = approach_path(graph_direction, directed_sources, snap.node_id, targets)
            if path is not None:
                if direction == 'platform_to_bus':
                    path['path_node_ids'].reverse()
                    path['path_edges'] = [dict(e, u=e['v'], v=e['u']) for e in reversed(path['path_edges'])]
                distance = path['network_distance_m']+snap.connector_distance_m
                path.update(design_point_connector_m=snap.connector_distance_m,
                            distance_including_connector_m=distance,
                            approach_only_walk_model_min=distance/WALK_METRES_PER_MIN,
                            final_platform_walk_and_train_door_time_included=False,
                            slope_steps_congestion_penalty_included=False,
                            observed_transfer_time=False)
                features.append(dict(type='Feature', properties=dict(role='PLATFORM_APPROACH', platform=ref,
                    flow=direction, distance_m=distance, contains_steps=path['contains_steps']),
                    geometry=dict(type='LineString', coordinates=[nodes[n]['coordinates_lon_lat'] for n in path['path_node_ids']])))
            routes[direction] = path
            no_steps = approach_path(graph_direction, directed_sources, snap.node_id, targets, no_steps=True)
            if no_steps is not None and direction == 'platform_to_bus':
                no_steps['path_node_ids'].reverse()
                no_steps['path_edges'] = [dict(e, u=e['v'], v=e['u']) for e in reversed(no_steps['path_edges'])]
            routes[direction+'_excluding_steps'] = no_steps
        platforms[ref] = dict(osm_platform_way_id=wid, osm_tags=way['tags'],
                              native_shared_approach_node_ids=sorted(old_targets),
                              local_surface_topology=surface[ref], **routes)
        features.append(dict(type='Feature', properties=dict(role='PLATFORM', platform=ref),
                             geometry=dict(type='Polygon', coordinates=[[nodes[n]['coordinates_lon_lat'] for n in way['nodes']]])))
    for ref, info in surface.items():
        for edge in info['modelled_surface_edges']:
            features.append(dict(type='Feature', properties=dict(role='MODELLED_PLATFORM_SURFACE', platform=ref,
                geometry_kind=MODEL_KIND, original_osm_highway_edge=False),
                geometry=dict(type='LineString', coordinates=edge['coordinates_lon_lat'])))
    offsets = wing_offsets(design['loops'])
    rows = dated_flows(schedule, offsets, rail, bindings, platforms)
    # Five exact paired train identities, independent inbound/outbound platforms.
    bank = next(b for b in schedule['selected_real_train_banks_not_adopted']
                if b['wing'] == 'east_A' and b['kind'] == 'bus_to_rail')
    by_trip = {b['trip_id']: b for b in bindings}
    pairs = []
    worst = max(g['east_A']['road_minutes'] for g in offsets.values())
    for bus, target in zip(bank['bus_departures_min'], bank['rail_minutes']):
        incoming = [t for t in rail['events'] if t['ordinary_alighting_supported']
                    and t['arrival_min'] == bus-3 and t['origin_axis'] == 'MILANO']
        outgoing = [t for t in rail['events'] if t['ordinary_boarding_supported']
                    and t['departure_min'] == target and t['direction'] == 'MILANO']
        if len(incoming) != 1 or len(outgoing) != 1:
            raise ValueError('Paired AM train identity ambiguous')
        a, b = incoming[0], outgoing[0]
        pa, pb = by_trip[a['trip_id']]['planned_departure_platform'], by_trip[b['trip_id']]['planned_departure_platform']
        wi = platforms[pa]['platform_to_bus']['approach_only_walk_model_min']
        wo = platforms[pb]['bus_to_platform']['approach_only_walk_model_min']
        pairs.append(dict(arriving_train_number=a['train_number'], departing_train_number=b['train_number'],
            arrival_min=a['arrival_min'], departure_min=b['departure_min'], baseline_bus_start_min=bus,
            inbound_planned_platform=pa, outbound_planned_platform=pb,
            worst_inherited_east_duration_min=worst,
            assumed_3min_each_side=transfer_envelope(a['arrival_min'], b['departure_min'], bus, worst, 3, 3),
            platform_approach_only_diagnostic=transfer_envelope(a['arrival_min'], b['departure_min'], bus, worst, wi, wo),
            measured_transfer_time_budgets=[dict(
                bus_departure_shift_min=shift,
                maximum_inbound_transfer_plus_train_lateness_min=bus+shift-a['arrival_min'],
                maximum_outbound_transfer_plus_extra_bus_lateness_min=b['departure_min']-bus-shift-worst,
                timetable_change_adopted=False)
                for shift in (0, 1, 2)],
            actual_arrival_platform_and_door_position_verified=False))
    features.append(dict(type='Feature', geometry=dict(type='Point', coordinates=fs['coordinates_lon_lat']),
                         properties=dict(role='DESIGN_BUS_FS', site_id=FS, physical_platform_authorised=False)))
    result = dict(contract='RT031_STATION_PLANNED_PLATFORM_APPROACH_AND_TRANSFER_ENVELOPE_V3',
        recorded_on='2026-10-02', corrected_on='2026-10-07', rail_service_date=rail['service_date'],
        source_canonical_sha256={p.name: canonical_sha256(v) for p, v in
                                ((HANDOFF, handoff), (SOURCE, schedule), (DESIGN, design), (RAIL, rail),
                                 (ACCESSIBILITY_REVIEW, accessibility), (CALLER_CORRECTION, correction),
                                 (SOURCE_RECOVERY, recovery))},
        source_raw_sha256=dict(pedestrian_osm=OSM_SHA256,
                               rfi_departures=rail['source_sha256']['rfi_departures']),
        pedestrian_graph_digest=GRAPH_DIGEST, walk_metres_per_min_model=WALK_METRES_PER_MIN,
        graph_snapshot_timestamp='2026-09-06T12:00:00Z',
        design_bus_point=dict(site_id=FS, coordinates_lon_lat=fs['coordinates_lon_lat'], snap=asdict(snap)),
        planned_platform_bindings=bindings, platforms=platforms,
        caller_underpass_correction=correction, certified_source_recovery=recovery,
        superseded_boundary_only_approaches=previous_paths,
        local_platform_area_edges_change_frozen_rt028_graph=False,
        modelled_surface_connectivity_is_original_osm_highway=False,
        geometry_reconstruction_is_observed_transfer_time=False,
        source_code_sha256={p.name: hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
                           for p in (Path(__file__), ROOT/'scripts/phase2_rt031_station_platform_surface_v3.py')},
        all_dated_rail_flows_approach_only=rows, transfer_flow_combinations_checked=2*len(rows),
        paired_AM_directional_envelopes=pairs,
        official_accessibility_review=accessibility,
        native_graph_platform_approach_universe_complete=False,
        no_steps_result_proves_physical_impossibility=False,
        no_uniform_3min_transfer_certified=True,
        station_centroid_or_train_stop_used_as_pedestrian_goal=False,
        platform_approach_is_train_door=False,
        stair_penalty_or_train_door_time_imputed=False,
        normative_rail_priority_adopted=False, timetable_or_route_change_adopted=False,
        observed_transfer_time_available=False, step_free_access_certified=False,
        physical_operation_ready=False, rail_2027_certified=False,
        network_selected=False, primary_selection_authorised=False, runner_up_selection_authorised=False,
        decision_budget_km=None, uncertainty_band_min=None, missed_connection_probability=None,
        demand_weighted_gjt_improvement_min=None,
        close_with_evidence='Measure alighting-to-bus and bus-to-train-door times separately for actual platforms and accessible paths; reconcile bus runtime, dwell, door cut-off and actual rail lateness with the exact event budgets. No automated adoption of an AM/PM phase or arrival-platform assumption.',
        semantics='Pinned OSM highways, native surface stair tops and explicitly inferred short walks contained in published platform polygons, excluding underground targets and at-grade rail crossings. The original RT028 graph/digest is not modified. Area model edges are NOT original OSM highways or physical clearance certificates. Horizontal distance divided by inherited flat 80 m/min omits stair/congestion/door penalties: not measured transfers, a physical lower bound on time, a wheelchair route, rail-platform guarantee, probability or caller uncertainty band. Only planned DEPARTURE platforms are sourced; arrival platform remains an unverified hypothesis. The old 251 m boundary-only path is superseded, not used to infer missed trains.')
    return result, dict(type='FeatureCollection', features=features)


def render_brief(r):
    p1, p2 = (r['platforms'][ref]['bus_to_platform'] for ref in ('1', '2'))
    pair = r['paired_AM_directional_envelopes'][0]
    model = pair['platform_approach_only_diagnostic']
    return '\n'.join([
        '# Linea 8 — accessi distinti ai binari, senza cambiare la proposta', '',
        '**Correzione del 7 ottobre:** recuperata la fonte RT028 originale e incluso il passaggio binario 2 → scala → sottopasso → scala → binario 1 segnalato dal committente. Il precedente giro esterno da 251 m è superato e non viene più usato per le coincidenze. Percorso bus, fermate, 16 giri, calendario feriale 2027 e km restano invariati.', '',
        'Il committente ha poi confermato esplicitamente il tragitto mostrato, in base alla propria esperienza locale. È un riscontro sulla topologia del percorso, non un cronometraggio, un rilievo delle coordinate o un’approvazione degli accosti/tempi alle porte.', '',
        '## Evidenza recuperata dal quadro ferroviario già salvato', '',
        'Il campo RFI «Binario programmato» è riconciliato per numero treno e partenza con tutte le 74 chiamate del 1 ottobre 2026: Milano binario 2, Lecco binario 1. È un binario di partenza programmato, non quello reale né una certificazione del binario di arrivo o del 2027.', '',
        'L’accosto di progetto FS deriva da L00407, non dal diverso record 300407: la coordinata 45,733710 del vecchio spot-check non è quella usata dalla Linea 8. Non occorre spostare il tracciato per correggere quel confronto.', '',
        '## Correzione topologica: il sottopasso esisteva già nella fonte', '',
        'Le scale OSM 1193795237 e 1193795239 raggiungono il sottopasso 784178060. Le loro estremità superiori sono dentro le aree delle banchine, non sul bordo: il controllo precedente le ignorava. Sono esclusi come obiettivi i nodi sotterranei che ricadono nella proiezione della stessa banchina. Non si inventa un attraversamento dei binari a raso.', '',
        f'Dal punto bus all’accesso di superficie della banchina 1: **{p1["distance_including_connector_m"]:.1f} m**; banchina 2: **{p2["distance_including_connector_m"]:.1f} m**. Il primo passa per la banchina 2, le due scale e il sottopasso. Solo **{p1["modelled_platform_surface_distance_m"]:.2f} m** di cammino interno alla banchina 2 sono un’inferenza geometrica esplicita, interamente contenuta nel poligono OSM e senza intersezione con i binari in superficie; tutti gli altri archi sono highways OSM. Quel tratto non viene spacciato per un arco OSM originale o un rilievo di agibilità.', '',
        'Il grafo RT028 certificato e il suo digest non cambiano: il raccordo di superficie è un modello locale separato per la stazione. L’artefatto originale 9991182904/run 34039162932 è stato recuperato in `cache/rt028-certified-34039162932`; il checksum coincide con quello certificato. Non dipende più dalla cartella temporanea eliminata.', '',
        f'Il proxy pianeggiante ereditato di 80 m/min restituisce rispettivamente **{p1["approach_only_walk_model_min"]:.2f} e {p2["approach_only_walk_model_min"]:.2f} minuti**, ma omette rallentamenti sulle scale, cammino lungo banchina, discesa/salita e chiusura porte. Non li si adotta come nuovi tempi di trasferimento.', '',
        'La sensibilità senza archi “steps” non trova un accesso a questi ingressi nel grafo. **Non dimostra che una soluzione senza scale sia fisicamente impossibile.** La [scheda ufficiale RFI](https://www.rfi.it/it/stazioni/olgiate-calco-brivio.html), verificata anche nel browser il 2 ottobre (aggiornamento visualizzato 13:05), indica accessi in piano/rampa a entrambi i binari, senza ascensore e senza servizio di assistenza. Il grafo non ne ricostruisce il collegamento: è incompleto per quella prova. La disponibilità dall’ingresso della stazione non certifica il percorso dall’accosto bus, il tempo o la porta del treno. Nessun attraversamento dei binari o rampa viene inventato.', '',
        '## Cosa cambia nella conclusione mattutina', '',
        'L’audit precedente restava valido nell’ipotesi di 3 minuti per ciascun verso. Non dimostrava però che anticipare il bus perdendo la coincidenza da Milano fosse l’unica scelta reale: i due cammini sono diversi e non sono misurati.', '',
        f'Usando la geometria corretta come diagnostica, il bus base delle 06:05 ha residuo ingresso **{model["baseline_inbound_residual_min"]:.3f} min** e uscita **{model["baseline_outbound_residual_min"]:.3f} min** nello stress est massimo, dopo il solo proxy di cammino. **Entrambi sono positivi**: il vecchio conflitto dovuto al giro esterno non è una ragione per spostare l’orario confermato. Non sono però riserve garantite: mancano scale, porte, ritardi e misure effettive.', '',
        'Per ciascuna delle cinque coppie mattutine il giro est stressato vale 47,7766 minuti. La prima coppia è arrivo da Milano 06:02 / partenza verso Milano 06:56. I seguenti sono **budget temporali da misurare**, non un orario nuovo:', '',
        '| Partenza bus est ipotetica | Trasferimento treno→bus + ritardo treno massimo | Trasferimento bus→treno + ritardo bus aggiuntivo massimo |',
        '|---|---:|---:|',
        '| 06:05, base confermata | 3 min | 3 min 13,4 s |',
        '| 06:06, confronto non adottato | 4 min | 2 min 13,4 s |',
        '| 06:07, confronto non adottato | 5 min | 1 min 13,4 s |', '',
        'Il budget in uscita è ciò che resta **dopo** il tempo est massimo del modello; una riserva positiva desiderata e la chiusura porte vanno sottratte. Nessuna banda viene scelta. Questa tabella è un bilancio locale, non un’approvazione dell’orario. Il successivo [confronto AM completo](RT031_LINEA8_FASI_AM_COMPLETE_2026_10_02.md) ricostruisce ledger, cap, blocchi e tutti i flussi delle ipotesi +1/+2: entrambe rispettano i controlli di corsa completa, ma i trasferimenti reali restano da misurare e nessuna fase è adottata.', '',
        'Ricontrollati tutti i 296 flussi dell’orario invariato con i due accessi distinti. I cinque arrivi AM da Milano hanno ora il bus est a 3 minuti nel proxy corretto, non 33/58; anche il gap serale ovest di 3 minuti non è più superato dal solo accesso al binario 1. Questa compatibilità geometrica non garantisce porte, accessibilità o ritardi e non autorizza +1/+2.', '',
        '**Prossima prova decisiva: misurare separatamente binario 1→bus e bus→binario 2**, includendo scale, posizione porte e accessibilità, insieme al giro est in punta. Se i budget sono rispettati con una riserva dichiarata, si può valutare una fase che mantenga entrambe le coincidenze; se non lo sono, il trade-off ferroviario torna da decidere. Non si forza ora una priorità normativa.', '',
        '[Audit macchina](../outputs/phase2/rt031_line8_local_shortcuts_v3/station_platform_transfer_audit_20261002.json) · [Percorsi pedonali sorgente](../outputs/phase2/rt031_line8_local_shortcuts_v3/station_platform_transfer_paths_20261002.geojson)', '',
        '`physical_operation_ready=false`; `rail_2027_certified=false`; nessuna modifica adottata; `decision_budget_km=null`; `uncertainty_band_min=null`.', '',
        'Riproduzione dalla fonte recuperata: `PYTHONPATH=.;src python -m scripts.phase2_audit_rt031_station_platform_access_v3` (in PowerShell impostare prima `$env:PYTHONPATH=".;src"`). Un percorso esplicito assente o con checksum diverso continua a fallire chiuso.', '',
    ])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pedestrian-osm', type=Path, default=DEFAULT_OSM)
    parser.add_argument('--rfi', type=Path, default=RFI)
    args = parser.parse_args()
    result, geo = build(args.pedestrian_osm, args.rfi)
    for path, value in ((OUTPUT, result), (GEO, geo)):
        path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+'\n', encoding='utf-8', newline='\n')
    BRIEF.write_text(render_brief(result), encoding='utf-8', newline='\n')
    print(json.dumps(dict(platform_distances={p: r['bus_to_platform']['distance_including_connector_m']
                                             for p, r in result['platforms'].items()},
                          dated_platforms=len(result['planned_platform_bindings']),
                          flows=result['transfer_flow_combinations_checked'], proposal_unchanged=True)))
