"""Point-only walking diagnostic for the caller-confirmed 27-site design.

Observed OSM locality labels are points, not locality boundaries or passengers.
The diagnostic closest site is chosen only by modeled walking access; it is
not an optimal scheduled passenger journey or permission to board.
"""
import argparse
import csv
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path

from phase2_final_stop_pedestrian_accessibility_substrate_v3 import (
    DEFAULT_MAX_CONNECTOR_M, _dijkstra_to_stop, parse_osm_pedestrian_graph,
)
from scripts.phase2_package_rt031_confirmed_design_handoff_v3 import (
    build as build_handoff, canonical_sha256,
)

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'outputs/phase2/rt031_line8_local_shortcuts_v3'
HANDOFF = BASE / 'caller_confirmed_design_handoff_20261001.json'
GEO = BASE / 'calco_centre_adopted_design.geojson'
ANCHORS = ROOT / 'outputs/phase2/stop_universe_v2/settlement_destination_anchors.csv'
RAW_POINTS = ROOT / 'data/raw/osm/osm_points_core.geojson'
PREFERENCE = ROOT / 'config/rt031_caller_locality_itinerary_preference_v3.json'
OUTPUT = BASE / 'caller_confirmed_locality_point_access_20261001.json'
BRIEF = ROOT / 'docs/RT031_LINEA8_LOCALITA_PUNTI_2026_10_01.md'
ANCHOR_IDS = {
    'Mondonico': 'OSM_POINT_1144810206',
    'Monticello': 'OSM_POINT_2101450267',
    'Calco Superiore': 'OSM_POINT_6647016663',
    'Crescenzaga': 'OSM_POINT_2101402496',
}
ANCHOR_CSV_SHA256_NORMALIZED = '6ce1073dc7c30ca51a7ed584f6655ad525d99ca0c68dd2dabe2ea30304d7d3c4'
OSM_SHA256 = '896f192bbb481f0c07cdc5d695424bf29de85f89ac33ea72986a06e521b424cd'
GRAPH_DIGEST = 'aaad8a16e4c3715161cce6f686acccbf29e4e9def57424e8ad02594c9a69f1f4'
FS = 'FROZEN::L00407'
WALK_METRES_PER_MIN = 80.0


def sha256(path, normalized=False):
    data = Path(path).read_bytes()
    return hashlib.sha256(data.replace(b'\r\n', b'\n') if normalized else data).hexdigest()


def validate_points(anchors, raw):
    """Require native identity, point type, label and exact source coordinates."""
    selected = []
    for name, aid in ANCHOR_IDS.items():
        matches = [r for r in anchors if r['anchor_id'] == aid]
        if len(matches) != 1:
            raise ValueError('Locality anchor identity missing or duplicated')
        row = matches[0]
        features = [f for f in raw['features']
                    if str(f['properties'].get('osm_id')) == aid.removeprefix('OSM_POINT_')]
        if len(features) != 1:
            raise ValueError('Raw OSM point identity missing or duplicated')
        feature = features[0]
        coords = [float(row['lon']), float(row['lat'])]
        if (row['name'] != name or row['anchor_type'] != 'SETTLEMENT'
                or row['epistemic_status'] != 'FACT_OSM_OBSERVATION'
                or row['source'] != 'data/raw/osm/osm_points_core.geojson'
                or feature['properties']['name'] != name
                or feature['geometry']['type'] != 'Point'
                or feature['geometry']['coordinates'] != coords):
            raise ValueError('Locality source point drift')
        selected.append(dict(name=name, anchor_id=aid,
                             coordinates_lon_lat=coords,
                             source_epistemic_status='FACT_OSM_OBSERVATION'))
    return selected


def validate_sites(handoff, geo):
    sites = handoff['design_stop_register']
    features = [f for f in geo['features'] if f['properties'].get('role') == 'DESIGN_SITE']
    ids = {s['site_id'] for s in sites}
    if (len(sites) != 27 or len(ids) != 27 or len(features) != 27
            or {f['properties']['site_id'] for f in features} != ids
            or handoff['full_trip_count'] != 16 or FS not in ids):
        raise ValueError('Expected exact confirmed 27-site / 16-trip design')
    by_id = {f['properties']['site_id']: f for f in features}
    for site in sites:
        feature = by_id[site['site_id']]
        if (feature['geometry']['type'] != 'Point'
                or feature['geometry']['coordinates'] != site['coordinates_lon_lat']
                or site['physical_boarding_authorised'] is not False):
            raise ValueError('Design coordinates or physical authority drift')
        if site['site_id'] != FS and not site['ordered_occurrences']:
            raise ValueError('Nonhub design site has no ordered service event')
    return sorted(sites, key=lambda s: s['site_id'])


def pair_access(graph, origin_snap, site_snap, from_origin, to_origin):
    if origin_snap.status != 'REACHABLE' or site_snap.status != 'REACHABLE':
        return dict(point_to_site_walk_min=None, site_to_point_walk_min=None,
                    point_to_site_network_m=None, site_to_point_network_m=None,
                    status='ENDPOINT_UNREACHABLE')
    connector = float(origin_snap.connector_distance_m) + float(site_snap.connector_distance_m)
    forward = from_origin.get(site_snap.node_id, math.inf)
    reverse = to_origin.get(site_snap.node_id, math.inf)
    return dict(point_to_site_walk_min=(connector + forward) / WALK_METRES_PER_MIN
                if math.isfinite(forward) else None,
                site_to_point_walk_min=(connector + reverse) / WALK_METRES_PER_MIN
                if math.isfinite(reverse) else None,
                point_to_site_network_m=forward if math.isfinite(forward) else None,
                site_to_point_network_m=reverse if math.isfinite(reverse) else None,
                status='REACHABLE_BOTH_DIRECTIONS' if math.isfinite(forward) and math.isfinite(reverse)
                else 'DIRECTED_NETWORK_UNREACHABLE_IN_AT_LEAST_ONE_DIRECTION')


def point_access(graph, point, sites, site_snaps):
    lon, lat = point['coordinates_lon_lat']
    snap = graph.snap(lat, lon, max_connector_m=DEFAULT_MAX_CONNECTOR_M)
    # The helper expands the passed adjacency: forward gives origin->site,
    # reverse gives site->origin. Keep the two directions distinct.
    from_origin = _dijkstra_to_stop(graph.adjacency, snap.node_id) if snap.node_id else {}
    to_origin = _dijkstra_to_stop(graph.reverse_adjacency, snap.node_id) if snap.node_id else {}
    rows = []
    for site in sites:
        sid = site['site_id']
        rows.append(dict(site_id=sid, name=site['name'], kind=site['kind'],
                         site_snap=asdict(site_snaps[sid]),
                         physical_boarding_authorised=False,
                         **pair_access(graph, snap, site_snaps[sid], from_origin, to_origin)))
    candidates = [r for r in rows if r['site_id'] != FS and r['point_to_site_walk_min'] is not None]
    closest = min(candidates, key=lambda r: (r['point_to_site_walk_min'], r['site_id'])) if candidates else None
    binding = None
    if closest:
        site = next(s for s in sites if s['site_id'] == closest['site_id'])
        occurrences = []
        for occurrence in site['ordered_occurrences']:
            to_fs = occurrence['nominal_occurrence_to_next_fs_in_vehicle_min']
            from_fs = occurrence['nominal_fs_to_occurrence_in_vehicle_min']
            occurrences.append(dict(
                occurrence_id=occurrence['occurrence_id'], wing=occurrence['wing'],
                ordered_nonhub_event_number=occurrence['ordered_nonhub_event_number'],
                nominal_site_to_next_fs_in_vehicle_min=to_fs,
                nominal_fs_to_site_in_vehicle_min=from_fs,
                point_walk_plus_nominal_bus_to_fs_min=closest['point_to_site_walk_min'] + to_fs,
                nominal_bus_from_fs_plus_point_walk_min=(from_fs + closest['site_to_point_walk_min'])
                if closest['site_to_point_walk_min'] is not None else None,
                first_board_event_min=occurrence['first_board_event_min'],
                last_board_event_min=occurrence['last_board_event_min'],
                first_alight_event_min=occurrence['first_alight_event_min'],
                last_alight_event_min=occurrence['last_alight_event_min'],
                physical_boarding_authorised=False))
        binding = dict(**closest, selection_rule='MINIMUM_MODELED_POINT_TO_NONHUB_SITE_WALK_ONLY',
                       scheduled_best_journey_claim=False, occurrences=occurrences)
    return dict(**point, point_snap=asdict(snap), all_design_site_pairs=rows,
                closest_nonhub_site_diagnostic=binding,
                direct_point_to_fs_walk=next(r for r in rows if r['site_id'] == FS),
                whole_locality_coverage_certified=False,
                locality_to_stop_physical_access_certified=False,
                local_passenger_demand_observed=False)


def unresolved_readiness():
    return [
        dict(place='Calco Cornello', state='OFFICIAL_STOP_EXISTS_EXACT_COORDINATE_UNRESOLVED',
             source='outputs/phase2/network_design_method_audit_v3/master_stop_inventory_gpt_v3/arriva_unresolved_official_stop_places_gpt_v4.csv',
             source_identity='AXW013 / AR148_004', additional_point_calculation_supported=False),
        dict(place='Cassina', state='CALLER_PLACE_IDENTITY_AMBIGUOUS',
             source=str(PREFERENCE.relative_to(ROOT)), source_identity=None,
             note='Cassina Fra Martino OSM_POINT_1620729043 is not assumed to be the caller place.',
             additional_point_calculation_supported=False),
        dict(place='Oratorio Olgiate', state='EXACT_VENUE_IDENTITY_UNRESOLVED',
             source=str(PREFERENCE.relative_to(ROOT)), source_identity=None,
             additional_point_calculation_supported=False),
        dict(place='Casa di Comunità Olgiate', state='LOCATED_SPECIAL_SERVICE_STOP_NOT_ORDINARY_LINE_BINDING',
             source='outputs/phase2/network_design_method_audit_v3/master_stop_inventory_gpt_v3/existing_stop_places_operational_gpt_v5.csv',
             source_identity='SPECIAL::CASA_DI_COMUNITA_OLGIATE',
             note='45.7221313,9.3979736 from special-service inventory; point walk can be computed separately.',
             additional_point_calculation_supported=True),
        dict(place='Olgiate sud entire caller neighbourhood', state='CALLER_BOUNDARY_NOT_GEOREFERENCED',
             source=str(PREFERENCE.relative_to(ROOT)), source_identity='CALLER_ANNOTATED_MAP_2026_09_24',
             note='Existing inner/outer envelopes are sensitivities; the actual design site is not a whole-area certificate.',
             authoritative_area_calculation_supported=False),
        dict(place='San Zeno / Via Cantù north', state='DESIGN_ROAD_POINT_AND_ORDERED_EVENTS_PHYSICAL_ACCESS_UNVERIFIED',
             source=str(HANDOFF.relative_to(ROOT)), source_identity='PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE',
             note='Distinct from the southern Canova–San Zeno neighbourhood.', additional_point_calculation_supported=True),
    ]


def build(pedestrian_osm):
    paths = dict(anchors=ANCHORS, raw_points=RAW_POINTS, handoff=HANDOFF, geo=GEO,
                 locality_preference=PREFERENCE, pedestrian_osm=Path(pedestrian_osm))
    if sha256(ANCHORS, True) != ANCHOR_CSV_SHA256_NORMALIZED:
        raise ValueError('Pinned locality-anchor inventory drift')
    if sha256(pedestrian_osm) != OSM_SHA256:
        raise ValueError('Pinned RT028 pedestrian snapshot drift')
    handoff = json.loads(HANDOFF.read_text(encoding='utf-8'))
    if canonical_sha256(handoff) != canonical_sha256(build_handoff()):
        raise ValueError('Confirmed handoff no longer reproduces its authorised sources')
    with ANCHORS.open(encoding='utf-8', newline='') as stream:
        anchors = list(csv.DictReader(stream))
    points = validate_points(anchors, json.loads(RAW_POINTS.read_text(encoding='utf-8')))
    sites = validate_sites(handoff, json.loads(GEO.read_text(encoding='utf-8')))
    graph = parse_osm_pedestrian_graph(pedestrian_osm)
    if graph.graph_digest != GRAPH_DIGEST:
        raise ValueError('Pinned RT028 pedestrian graph drift')
    snaps = {s['site_id']: graph.snap(s['coordinates_lon_lat'][1], s['coordinates_lon_lat'][0],
                                    max_connector_m=DEFAULT_MAX_CONNECTOR_M) for s in sites}
    readiness = unresolved_readiness()
    for row in readiness:
        source = ROOT / row['source']
        paths.setdefault(row['source'], source)
    return dict(
        contract='RT031_CONFIRMED_LOCALITY_POINT_ACCESS_AUDIT_V3',
        status='DERIVED_POINT_DIAGNOSTIC_NOT_WHOLE_LOCALITY_SERVICE_CERTIFICATION',
        recorded_on='2026-10-02', design_reference_date='2026-10-01',
        design_site_count_including_fs=27, full_trip_count=16,
        source_sha256={key: sha256(path, key != 'pedestrian_osm') for key, path in paths.items()},
        provenance={key: dict(source_path=(str(path.relative_to(ROOT)) if path.is_relative_to(ROOT)
                                          else path.name), newline_normalized=key != 'pedestrian_osm')
                    for key, path in paths.items()},
        pedestrian_graph_digest=GRAPH_DIGEST, pedestrian_snapshot_sha256=OSM_SHA256,
        pedestrian_source=dict(
            snapshot_timestamp='2026-09-06T12:00:00Z',
            provider='OpenStreetMap contributors / Overpass', license='ODbL 1.0',
            overpass_endpoint='https://overpass-api.de/api/interpreter',
            query_sha256='aad1dbc5a9ddf5efc953322eaae7232c618518996b2c5e8bb4f411a0ed011b61',
            pinned_github_artifact_id=9991182904,
            pinned_zip_sha256='e1ca83699593dd9e605d2870667da1b4dfc6068436a0c3116faf8587901b2e28',
            acquisition_reference='.github/workflows/phase2-rt031-south-olgiate-provisional-area-v3.yml'),
        assumptions=dict(walk_metres_per_min=WALK_METRES_PER_MIN,
                         max_connector_m=DEFAULT_MAX_CONNECTOR_M,
                         endpoint_connectors='RT028_BARRIER_AWARE_NODE_SNAP',
                         graph_directionality_preserved=True,
                         locality_point_snap_recomputed_on_RT028=True,
                         inventory_current_walk_min_and_old_node_ids_reused=False),
        points=[point_access(graph, p, sites, snaps) for p in points],
        remaining_locality_readiness=readiness,
        semantics='Point-label walking to actual design coordinates, with endpoint connectors. Nominal bus legs use exact ordered design occurrences. Walk+bus sums exclude readiness wait, train transfer, timetable waiting and empirical delays; they are not total scheduled journey time, GJT or observed demand.',
        whole_locality_coverage_certified=False, physical_boarding_authorised=False,
        accessible_pedestrian_paths_certified=False, locality_service_certified=False,
        scheduled_total_journey_time_certified=False, new_service_policy_adopted=False,
        passenger_od_downscaled=False, network_selected=False,
    )


def render_brief(payload):
    lines = ['# Linea 8 — accesso dai quattro punti OSM di località', '',
             'Audit del 2 ottobre 2026 sulla proposta confermata del 1° ottobre: 27 siti e 16 giri completi.', '',
             'I quattro nomi hanno un punto OSM verificabile. Il calcolo riguarda quel punto; '
             'non delimita la frazione e non dimostra che tutti i suoi abitanti siano serviti. '
             'Le fermate e i percorsi pedonali restano da verificare fisicamente.', '',
             '| Punto OSM | Sito di progetto con minor cammino dal punto | A piedi punto→sito | A piedi sito→punto | Bus sito→FS | Bus FS→sito |',
             '| --- | --- | ---: | ---: | ---: | ---: |']
    for point in payload['points']:
        binding = point['closest_nonhub_site_diagnostic']
        if binding is None:
            lines.append(f"| {point['name']} | Non raggiungibile nel modello | — | — | — | — |")
            continue
        fmt = lambda value: '—' if value is None else f'{value:.2f}'
        for occurrence in binding['occurrences']:
            lines.append(f"| {point['name']} | {binding['name']} ({occurrence['wing']}) | "
                         f"{fmt(binding['point_to_site_walk_min'])} | {fmt(binding['site_to_point_walk_min'])} | "
                         f"{fmt(occurrence['nominal_site_to_next_fs_in_vehicle_min'])} | "
                         f"{fmt(occurrence['nominal_fs_to_site_in_vehicle_min'])} |")
    lines += ['', 'Minuti modellati. La scelta del sito minimizza soltanto il cammino verso '
              'una fermata diversa da FS. Un sito più vicino può offrire un viaggio in bus più lungo; '
              'questo abbinamento non è una scelta della migliore combinazione oraria.', '',
              'Il JSON conserva tutti i 108 abbinamenti punto–sito, i cammini distinti nei due versi, '
              'i connettori, le occorrenze del bus e le finestre nominali. I tempi a bordo '
              'sono quelli dell’orario di progetto con soste nominali. Sommare cammino e bus '
              'non aggiunge l’attesa: manca una domanda con ora di partenza/arrivo per confrontare '
              'i viaggi programmati. Nessuna domanda passeggeri è dedotta dagli OD comunali.', '',
              'Il grafo è lo snapshot RT028 del 6 settembre 2026, con snap a nodi entro 90 m '
              'e controllo delle barriere, velocità assunta 80 m/min e direzioni pedonali preservate. '
              'Le coordinate dei punti sono confrontate con gli ID OSM grezzi; quelle dei siti '
              'sono confrontate con il registro confermato. Le distanze del precedente inventario '
              'verso la rete esistente non sono riutilizzate.', '',
              'Restano da risolvere Cornello (coordinata di fermata), Cassina (identità richiesta), '
              'l’oratorio di Olgiate (sede esatta), il legame con una fermata ordinaria della Casa '
              'di Comunità e il perimetro georeferenziato del quartiere meridionale. '
              'Il punto Via Cantù a nord resta distinto dall’area Canova–San Zeno a sud.', '',
              'Fonti e checksum normalizzati per i file testuali sono registrati nel '
              '[JSON dell’audit](../outputs/phase2/rt031_line8_local_shortcuts_v3/caller_confirmed_locality_point_access_20261001.json). '
              'Script: `scripts/phase2_audit_rt031_confirmed_locality_points_v3.py`. '
              'Per riprodurre: `python -m scripts.phase2_audit_rt031_confirmed_locality_points_v3 '
              '--pedestrian-osm <rt028_osm_pedestrian_snapshot_v3.osm>` con `PYTHONPATH=.;src`.', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pedestrian-osm', required=True, type=Path)
    parser.add_argument('--output', default=OUTPUT, type=Path)
    parser.add_argument('--brief', default=BRIEF, type=Path)
    args = parser.parse_args()
    result = build(args.pedestrian_osm)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    args.brief.write_text(render_brief(result), encoding='utf-8')
    print(json.dumps(dict(status=result['status'], points=[dict(
        name=p['name'], closest_nonhub_site_diagnostic=p['closest_nonhub_site_diagnostic'])
        for p in result['points']]), ensure_ascii=False))
