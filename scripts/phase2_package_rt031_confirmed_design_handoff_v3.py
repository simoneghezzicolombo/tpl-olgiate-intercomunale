"""Caller-confirmed design handoff, without promoting model evidence to operation.

Preserves the preceding review artifact. No new search, weights or selection.
"""
import copy
import hashlib
import json
from fractions import Fraction
from pathlib import Path

from scripts.phase2_package_rt031_current_16_trip_proposal_v3 import (
    BASE, DESIGN, RAIL, SOURCE, build as review_build,
)

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY = ROOT / 'config/rt031_design_timetable_confirmation_20261001_v3.json'
GEO = DESIGN.with_suffix('.geojson')
OUTPUT = BASE / 'caller_confirmed_design_handoff_20261001.json'
BRIEF = ROOT / 'docs/RT031_LINEA8_PROPOSTA_UNICA_CONSOLIDATA_2026_10_01.md'
MUNICIPALITIES = {
    '97010': 'Brivio', '97012': 'Calco', '97058': 'Olgiate Molgora',
    '97074': 'Santa Maria Hoè', '97092': 'La Valletta Brianza', 'TOTAL': 'Totale',
}


def canonical_sha256(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def validate_authority(authority, sources):
    expected = authority['source_canonical_sha256']
    if set(expected) != set(sources):
        raise ValueError('Authority source set mismatch')
    for name, value in sources.items():
        if canonical_sha256(value) != expected[name]:
            raise ValueError(f'Caller-confirmed source drift: {name}')
    schedule = sources[SOURCE.name]
    pairs = [[t['first_fs_min'], t['second_fs_min']] for t in schedule['full_trips']]
    if pairs != authority['full_trip_fs_departure_pairs_min']:
        raise ValueError('Exact caller-confirmed departure pairs changed')
    if schedule['ready_windows_min'] != authority['ready_windows_min']:
        raise ValueError('Caller-confirmed readiness windows changed')
    if not all(authority[k] for k in ('caller_confirmed_design_timetable_basis',
                                     'transition_extension_adopted_for_design',
                                     'exact_peak_phases_adopted_for_design',
                                     'all_trips_same_complete_path',
                                     'bidirectional_h30_action_deferred')):
        raise ValueError('Missing design-only confirmation')
    if (authority['full_commercial_trips_per_day'] != 16 or
            authority['design_site_count_including_fs'] != 27 or
            authority['ordered_nonhub_events_per_trip'] != 28 or
            authority['public_route_name'] != 'Linea 8' or
            authority['public_wing_sequence'] != ['east_A', 'west_B'] or
            authority['short_turn_public_trips_allowed']):
        raise ValueError('Confirmed complete-line scope mismatch')
    for key in ('annual_calendar_adopted', 'public_operating_timetable_authorised',
                'physical_boarding_authorised', 'physical_passenger_continuity_certified',
                'fleet_or_operator_availability_certified', 'funding_secured',
                'network_selected', 'primary_selection_authorised', 'runner_up_selection_authorised'):
        if authority[key] is not False:
            raise ValueError(f'Design confirmation cannot certify {key}')
    for key in ('decision_budget_km', 'uncertainty_band_min'):
        if authority[key] is not None:
            raise ValueError(f'No new Decision Contract input authorised: {key}')


def stop_register(proposal, geo):
    features = [f for f in geo['features'] if f['properties'].get('role') == 'DESIGN_SITE']
    ids = [f['properties']['site_id'] for f in features]
    if len(ids) != 27 or len(set(ids)) != 27:
        raise ValueError('Expected 27 distinct design sites including FS')
    trips = proposal['ordered_stop_event_ledger_nominal']
    sequences = []
    for trip in trips:
        events = [e for e in trip['events'] if e['role'] == 'DESIGN_STOP_OCCURRENCE']
        if len(events) != 28 or len({e['occurrence_id'] for e in events}) != 28:
            raise ValueError('Expected 28 explicit nonhub occurrences per complete trip')
        sequences.append([(e['occurrence_id'], e['site_id'], e['wing'], e['full_path_edge_index']) for e in events])
        if any(e['board_event_min'] < e['alight_event_min'] for e in events):
            raise ValueError('Boarding/alighting event order violated')
    if len(trips) != 16 or any(s != sequences[0] for s in sequences[1:]):
        raise ValueError('Complete trips have different service-event sequences')
    register = []
    for feature in features:
        p = feature['properties']; sid = p['site_id']
        occurrences = []
        for occurrence in p['ordered_occurrences']:
            oid = occurrence['occurrence_id']
            matches = [[e for e in t['events'] if e.get('occurrence_id') == oid] for t in trips]
            if any(len(m) != 1 or m[0]['site_id'] != sid for m in matches):
                raise ValueError('GeoJSON occurrence does not match every timetable trip')
            events = [m[0] for m in matches]
            order = next(i for i, item in enumerate(sequences[0], 1) if item[0] == oid)
            ti = 0
            later_fs = next(e for e in trips[ti]['events']
                            if e['role'] in ('INTERMEDIATE_FS_STAY_ONBOARD_DESIGN', 'FULL_TRIP_END_FS')
                            and e['arrival_min'] >= events[ti]['board_event_min'])
            wing_start = trips[ti]['first_fs_min'] if occurrence['wing'] == 'east_A' else trips[ti]['second_fs_min']
            occurrences.append(dict(
                **occurrence, ordered_nonhub_event_number=order,
                full_path_edge_index=events[0]['full_path_edge_index'],
                first_board_event_min=min(e['board_event_min'] for e in events),
                last_board_event_min=max(e['board_event_min'] for e in events),
                first_alight_event_min=min(e['alight_event_min'] for e in events),
                last_alight_event_min=max(e['alight_event_min'] for e in events),
                nominal_fs_to_occurrence_in_vehicle_min=events[0]['alight_event_min']-wing_start,
                nominal_occurrence_to_next_fs_in_vehicle_min=later_fs['arrival_min']-events[0]['board_event_min'],
                physical_boarding_authorised=False,
            ))
        if p['kind'] != 'INVENTORY_HUB' and not occurrences:
            raise ValueError('Served nonhub identity without a service occurrence')
        register.append(dict(site_id=sid, name=p['name'], kind=p['kind'],
                             coordinates_lon_lat=feature['geometry']['coordinates'],
                             proposed_new_site=p['kind'].startswith('PROPOSED_'),
                             physical_boarding_authorised=False, physical_platform_count=None,
                             ordered_occurrences=occurrences,
                             hub_service_roles=['FULL_TRIP_START_FS', 'INTERMEDIATE_FS_STAY_ONBOARD_DESIGN',
                                                'FULL_TRIP_END_FS'] if p['kind'] == 'INVENTORY_HUB' else []))
    if sum(len(s['ordered_occurrences']) for s in register) != 28:
        raise ValueError('Occurrence register and timetable disagree')
    return sorted(register, key=lambda s: min([o['ordered_nonhub_event_number'] for o in s['ordered_occurrences']] or [0]))


def build():
    authority = json.loads(AUTHORITY.read_text(encoding='utf-8'))
    sources = {p.name: json.loads(p.read_text(encoding='utf-8')) for p in (SOURCE, DESIGN, RAIL, GEO)}
    validate_authority(authority, sources)
    result = copy.deepcopy(review_build())  # Revalidates the actual schedule, not just its hash.
    result.update(
        contract='RT031_CALLER_CONFIRMED_LINE8_DESIGN_HANDOFF_V3',
        status='DESIGN_BASIS_CONFIRMED_OPERATIONAL_REVIEW_PENDING',
        recorded_on=authority['recorded_on'],
        caller_confirmed_design_timetable_basis=True,
        detailed_timetable_adopted_for_design=True,
        transition_extension_adopted_for_design=True,
        exact_peak_phases_adopted_for_design=True,
        exact_peak_phases_require_caller_confirmation=False,
        public_operating_timetable_authorised=False,
        full_history_road_legality_certified=False,
        physical_platform_count=None,
        annual_full_operating_cost=None,
        funding_secured=False,
        preceding_review_artifact='current_16_trip_proposal_for_caller_review.json',
        authority_source=str(AUTHORITY.relative_to(ROOT)).replace('\\', '/'),
        authority_canonical_sha256=canonical_sha256(authority),
        source_canonical_sha256=authority['source_canonical_sha256'],
        adopted_scope='DESIGN_ONLY_NOT_PUBLIC_OPERATION_NOT_TOURNAMENT_SELECTION',
        semantics='One caller-confirmed design basis. Exact full-route service events and train flows retained; unsupported metrics remain null. No global optimum, empirical reliability, physical stop, annual calendar, operating or funding approval is inferred.',
    )
    # The old unqualified fields remain explicitly non-operational, not stealth authority.
    result['unqualified_adoption_flags_semantics'] = 'detailed_timetable_adopted and transition_extension_adopted remain false for unqualified/public operating adoption; explicit *_for_design fields record the caller confirmation.'
    for row in result['requirements_readiness']:
        if row['input'] in ('h30_peak_banks', 'offpeak_transition'):
            row['state'] = 'CALLER_CONFIRMED_DESIGN_ONLY'
            row['source'] = result['authority_source']
            row['upstream_evidence'] = SOURCE.name
        if row['input'] == 'offpeak_transition':
            row['semantics'] = 'Caller-confirmed design readiness cap 120 min 10:00-16:20; cap60 on shoulders. Not exact H120 bus departures throughout that window or physical reliability.'
    result['design_stop_register'] = stop_register(result, sources[GEO.name])
    result['proposed_new_design_site_count'] = sum(s['proposed_new_site'] for s in result['design_stop_register'])
    result['inventory_design_site_count_including_fs'] = 27-result['proposed_new_design_site_count']
    result['coverage_percent'] = {code: {m: 100*float(Fraction(v)) for m, v in values.items()}
                                  for code, values in result['coverage_fraction'].items()}
    result['coverage_semantics'] = 'Potential walking-network population coverage at 5/8/10 min on frozen substrate; not observed passengers, route-downscaled municipal OD, certified accessible paths or time-of-day utility.'
    result['locality_claims_not_certified'] = ['Monticello/Mondonico', 'Calco alta/Cornello', 'Cassina',
                                            'Crescenzaga', 'Oratorio/Casa di Comunità', 'Entire Olgiate south neighbourhood']
    result['remaining_external_validations'] = [
        dict(id='ROAD_AND_STOPS', owner='Operator and road/stop authorities',
             required_evidence='Bus suitability, full-history restrictions, all junction/FS manoeuvres, boarding sides, stop areas and safe accessible paths; check all 27 sites including four proposed sites.',
             close_when='Signed route/stop assessment identifies authorised directional occurrences; unresolved or incompatible movements keep operational readiness false.'),
        dict(id='TIMING_AND_CONTINUITY', owner='Operator',
             required_evidence='Measured runtimes/dwell by period, FS stay-onboard passenger permission, recovery, vehicle blocks and duty/depot/deadhead plan; physical transfer walk time.',
             close_when='An executable full-trip timetable and resourcing plan supports this design; any required service change is disclosed for caller acceptance, not silently substituted.'),
        dict(id='CALENDAR_AND_FULL_COST', owner='Agency and operator, with caller calendar choice',
             required_evidence='Annual service dates, weekend/holiday/school scope, service and noncommercial km, fleet and staff cost, procurement/funding requirements.',
             close_when='Agreed calendar and full-cost estimate reconcile commercial production and resources; 260 comparison days are not automatically adopted.'),
    ]
    result['best_practice_current_assessment'] = [
        dict(id='BP-01', state='DESIGN_MODEL_CHECKED', finding='16 full trips; phased H30 peak banks; precise first/last occurrence events and offpeak readiness caps reported, not universal H30.'),
        dict(id='BP-02', state='PARTIAL_UNWEIGHTED_ONLY', finding='Occurrence-level in-vehicle times and transfer waits; no passenger OD or demand-weighted GJT certified.'),
        dict(id='BP-03', state='COMPROMISE_EXPLICIT', finding='Clockface 30-minute banks, irregular offpeak departures; no all-day clockface claim.'),
        dict(id='BP-04', state='DATED_ALL_RAIL_DIAGNOSTIC', finding='All 74 calls and 296 wing/train/flow combinations disclosed, not all short-wait connections protected.'),
        dict(id='BP-05', state='EXTERNAL_VALIDATION_REQUIRED', finding='9 deterministic moving/dwell cases, 27 with recovery; conditional 3/4 vehicles, not empirical reliability or available fleet.'),
        dict(id='BP-06', state='LIMITS_RETAINED', finding='Fast separate local occurrences; long reverse journeys elsewhere remain, not cured by timetable shifts.'),
        dict(id='BP-07', state='DESIGN_EXCHANGE_CONFIRMED_FIELD_PENDING', finding='Alpino removed, Santa Maria retained, Calco Municipio added; 27 sites are not certified platforms.'),
        dict(id='BP-08', state='DESIGN_CONFIRMED_OPERATION_PENDING', finding='One Linea8 with identical complete east→west sequence every trip; FS remain-onboard permission pending.'),
        dict(id='BP-09', state='HISTORICAL_SEARCH_NOT_GLOBAL_OPTIMUM', finding='Caller-confirmed design basis, not a tournament winner; no weighted retention or fabricated passengers affected.'),
        dict(id='BP-10', state='SPATIAL_POTENTIAL_ONLY', finding='Five municipality percentages disclosed; temporal equity, missing locality crosswalks and passenger utility not certified.'),
        dict(id='BP-11', state='FIVE_MUNICIPALITIES_MODELLED', finding='Intermunicipal fixed path and rail axes retained; broader destination demand is not inferred.'),
        dict(id='BP-12', state='EXTERNAL_VALIDATION_REQUIRED', finding='Olgiate south and San Zeno separate; an occurrence does not certify whole neighbourhood coverage, safe walking or inclusive access.'),
    ]
    result['requirements_readiness'].extend([
        dict(input='physical_route_stops_accessibility', state='EXTERNAL_VALIDATION_REQUIRED', source=GEO.name,
             semantics='Coordinates and graph events are design hypotheses, not authorised bus-accessible platforms or full-history legal movements.'),
        dict(input='passenger_continuity_and_vehicle_blocks', state='EXTERNAL_VALIDATION_REQUIRED', source=SOURCE.name,
             semantics='Intended remain-onboard full trips; physical carrier alone does not certify service continuation or passenger permission.'),
        dict(input='locality_to_stop_crosswalk', state='NOT_CERTIFIED_FOR_ALL_DESIRED_LOCALITIES',
             source='docs/RT031_LINEA8_DOSSIER_UNICO_ISTRUTTORIO_V3.md', semantics='No named settlement is declared served from proximity alone.'),
    ])
    result['commercial_km_per_comparison_day'] = result['full_trip_count']*result['complete_path_distance_m']/1000
    result['annual_production_formula'] = '16 * complete_path_distance_m / 1000 * actual_adopted_service_day_count; add separately any noncommercial km'
    return result


def clock(minute):
    seconds = round(minute*60)
    return f'{seconds//3600:02d}:{seconds//60%60:02d}:{seconds%60:02d}'


def render_brief(r):
    def italian(value, decimals=2):
        return f'{value:,.{decimals}f}'.replace(',', '_').replace('.', ',').replace('_', '.')
    # The dated weekday amendment is separate from this pinned 1 October
    # geometry/timetable artifact. Never rewrite its historical source hashes.
    from scripts.phase2_materialise_rt031_weekday_calendar_2027_v3 import build as weekday_build
    weekday = weekday_build()
    lines = [
        '# Linea 8 — proposta unica consolidata, 1 ottobre 2026', '',
        'Aggiornamento del 7 ottobre: corretta la topologia del sottopasso FS, ritirato il giro esterno da 251 m e ricalcolati tutti i flussi ferroviari. Restano anche le evidenze del 2 ottobre su mezzi, calendario e località. Percorso e orario confermati restano invariati.', '',
        'Disponibile la [distinta per chiudere sopralluogo e preventivo](RT031_LINEA8_CHIUSURA_VERIFICHE_2026_10_02.md): quantità feriali, ore di modello distinte dai turni, gap dopo recupero e 31 schede per evento. Non contiene risposte esterne o approvazioni simulate.', '',
        f'**Base feriale 2027 ora dichiarata:** 16 giri lunedì-venerdì, esclusi festivi nazionali, **{weekday["weekday_base_day_count_before_local_exceptions"]} giornate / {italian(weekday["weekday_base_commercial_km"],3)} km commerciali** ({italian(weekday["weekday_base_delta_vs_reference_percent"])}% sul riferimento 111.419). Il sabato è da valutare separatamente, non cancellato. Il totale annuo completo non è ancora definito. [Conferma, tutte le date e limiti](RT031_LINEA8_CALENDARIO_FERIALE_2027_V3.md). Eventuali eccezioni locali restano da verificare.', '',
        '## La proposta da verificare con Agenzia e operatore', '',
        '**Base progettuale e orario confermati dal committente.** Non è un servizio autorizzato né una selezione PRIMARY: questa è la proposta unica su cui chiedere verifica operativa, senza riaprire la ricerca o sostituire tacitamente percorso e corse.', '',
        f'Una Linea 8, **16 giri completi/giorno**, stesso percorso a otto di **{italian(r["complete_path_distance_m"]/1000,3)} km** a ogni corsa. FS → est → FS intermedia → ovest → FS finale. Est/ovest sono sequenze della stessa corsa, non due linee. Permanenza a bordo a FS progettata, ancora da autorizzare.', '',
        f'**27 siti di progetto inclusa FS: {r["inventory_design_site_count_including_fs"]} derivati dall’inventario e {r["proposed_new_design_site_count"]} proposti nuovi.** Le occorrenze non-FS sono 28: Olgiate sud e San Zeno ricorrono due volte, in eventi distinti. Il numero di paline fisiche non è ancora certificato. Una corrispondenza con l’inventario non autorizza automaticamente l’accosto scelto.', '',
        'Confermati: niente Via Mirasole/Cartiglio/Tessitura nel modello, Piazza San Zenone mantenuta, Santa Maria Hoè mantenuta, Via Como/Alpino esclusa e Calco Centro–Municipio aggiunta in Via Italia senza nuovo percorso di marcia. H30 anche nel senso inverso resta rinviato.', '',
        '## Orario di progetto: una riga = un giro completo', '',
        '| Giro | FS → est | FS intermedia → ovest | Rientro FS nominale |',
        '|---:|---|---|---|',
    ]
    for i, (trip, ledger) in enumerate(zip(r['full_trips'], r['ordered_stop_event_ledger_nominal']), 1):
        end = next(e['arrival_min'] for e in ledger['events'] if e['role'] == 'FULL_TRIP_END_FS')
        lines.append(f'| {i} | {clock(trip["first_fs_min"])[:5]} | {clock(trip["second_fs_min"])[:5]} | {clock(end)} |')
    lines.extend(['', 'Secondi di rientro e tempi di fermata sono risultati nominali ingegneristici, non precisione promessa al pubblico. Prima/ultima corsa per ciascuna occorrenza sono nel registro macchina, non automaticamente 06:05–21:08 per tutta la linea.', '',
                  '**Punte H30 sfalsate confermate come base:** est AM 06:05–08:05, ovest AM 07:00–09:00; est PM 16:40–18:40, ovest PM 17:35–19:35. Non H30 simultaneo 07–09/17–19 ovunque, né H30 nei due sensi di percorrenza.', '',
                  '**Morbida confermata nel modello fino alle 16:20:** cap di attesa 120 minuti 10:00–16:20; cap60 nelle spalle 06:50–10:00 e 16:20–19:40, verificati sugli eventi direzionali pertinenti negli scenari ereditati. Non è l’affermazione che tutti i distanziamenti siano esattamente H60/H120. Le partenze concrete della tabella prevalgono sullo slogan.', '',
                  '## Fermate: registro dei siti, in ordine del primo incontro', '',
                  '| # | Sito di progetto | Origine | Eventi non-FS nel giro |', '|---:|---|---|---:|'])
    for i, site in enumerate(r['design_stop_register'], 1):
        state = 'Nuovo, da validare' if site['proposed_new_site'] else 'Inventario, accosto da validare'
        lines.append(f'| {i} | {site["name"]} | {state} | {len(site["ordered_occurrences"])} |')
    lines.extend(['', 'FS ha tre ruoli di servizio — partenza, passaggio intermedio e arrivo finale — non zero passaggi. Coordinate, archi entranti/uscenti, occorrenze e orari distinti sono nel JSON e nel GeoJSON.', '',
                  '## Copertura potenziale: tutti e cinque i comuni', '',
                  '| Comune | Entro 5 min a piedi | Entro 8 min | Entro 10 min |', '|---|---:|---:|---:|'])
    for code, name in MUNICIPALITIES.items():
        p = r['coverage_percent'][code]
        lines.append(f'| {name} | {italian(p["5"])}% | {italian(p["8"])}% | {italian(p["10"])}% |')
    lines.extend(['', 'Popolazione potenzialmente raggiunta sul substrato pedonale congelato: non passeggeri previsti, non domanda OD downscalata, non certificazione di percorsi sicuri/accessibili. Rispetto al riferimento precedente allo scambio, Calco guadagna circa 14,15/15,17/8,92 punti percentuali; Santa Maria perde 2,84 punti a 5 minuti e La Valletta 0,21, senza perdite a 8/10 minuti. Brivio e Olgiate invariati nello scambio.', '',
                  'Monticello/Mondonico, Calco alta/Cornello, Cassina, Crescenzaga, oratorio/Casa di Comunità e l’intero quartiere Olgiate sud **non sono dichiarati tutti serviti**: manca la certificazione località→fermata/accesso. Olgiate sud e San Zeno sono esigenze distinte e hanno eventi separati, non una garanzia estesa ai rispettivi quartieri.', '',
                  'L’[audit dei quattro punti OSM](RT031_LINEA8_LOCALITA_PUNTI_2026_10_01.md) misura ora il cammino verso i 27 siti effettivi: minimo dal punto di Mondonico 11,27 min, Monticello 7,20, Calco Superiore 11,42 e Crescenzaga 13,71. Tre punti non sono entro 10 minuti dalla fermata più vicina nel modello. Sono punti di località, non confini o abitanti: nessuna copertura dell’intera frazione è certificata. I tempi bus restano distinti per evento e verso, senza attesa iniziale inclusa.', '',
                  '## Treni, tempi di viaggio e limiti che restano', '',
                  'Registro del 1 ottobre: **74 chiamate ferroviarie**, entrambe le direttrici Milano/Lecco e entrambi i flussi di interscambio; **296 combinazioni ala/treno/flusso** nel JSON. GTFS ufficiale riconciliato con il quadro RFI vigente, non dati in tempo reale o promessa di servire ogni treno. [Quadro e fonti](RT031_LINEA8_QUADRO_FERROVIARIO_2026_10_01.md).', '',
                  '**Validità temporale:** questa verifica ferroviaria è del 2026 e non certifica le coincidenze nel 2027. Percorso e fasi dell’orario restano la base di progetto; prima dell’esercizio vanno ricontrollati sui treni pubblicati per il nuovo anno. Nessuno spostamento di orario è autorizzato tacitamente.', '',
                  'I quattro gruppi H30 supportano cinque treni consecutivi per ciascun flusso di punta: est→Milano 06:56–08:56, ovest→Milano 07:56–09:56; da Milano→est arrivi 16:32–18:32 e da Milano→ovest 17:32–19:32. Il 16:32 ha anche bus ovest 16:35. Trasferimento pedonale di 3 minuti ancora da misurare.', '',
                  '**19/22 vecchi obiettivi compatibili con eventi distinti.** Restano: ovest→Milano 07:26 senza arrivo utile; est→Milano 09:26 raggiungibile ma circa 40 minuti di attesa; arrivo da Milano 17:02→ovest con 33 minuti di attesa. Anche il 16:02 richiede 38 minuti verso est e 33 verso ovest. Non sono problemi risolti né probabilità di ritardo stimate.', '',
                  f'Sosta FS nominale **{italian(r["nominal_intermediate_fs_hold_range_min"][0])}–{italian(r["nominal_intermediate_fs_hold_range_min"][1])} min**, fino a {italian(r["engineering_intermediate_fs_hold_range_min"][1])} min negli stress. I viaggi lunghi altrove restano: l’orario non rende diretta una tratta circuitale. Il registro seguente rende espliciti i due tempi per ogni evento, non solo il più favorevole.', '',
                  '| Evento non-FS | Sito | Sequenza | FS → evento, min | Evento → prossima FS, min |', '|---:|---|---|---:|---:|'])
    occurrences = sorted([(o, s['name']) for s in r['design_stop_register'] for o in s['ordered_occurrences']], key=lambda x: x[0]['ordered_nonhub_event_number'])
    for o, name in occurrences:
        lines.append(f'| {o["ordered_nonhub_event_number"]} | {name} | {o["wing"]} | {italian(o["nominal_fs_to_occurrence_in_vehicle_min"])} | {italian(o["nominal_occurrence_to_next_fs_in_vehicle_min"])} |')
    lines.extend(['', 'Tempi a bordo nominali, senza cammino/attesa iniziale o treno. Ogni riga riguarda una precisa occorrenza; un evento veloce non garantisce viaggi veloci da un altro evento dello stesso sito. Prosecuzioni intercomunali possono includere la sosta FS: ledger completo disponibile, senza utilità OD inventata.', '',
                  '## Produzione e risorse: numeri non da confondere', '',
                  f'- Commerciale per giorno di confronto: **{italian(r["commercial_km_per_comparison_day"],3)} km**.',
                  f'- **Confronto corrente della base lunedì-venerdì 2027:** {weekday["weekday_base_day_count_before_local_exceptions"]} giorni, **{italian(weekday["weekday_base_commercial_km"],3)} km**, margine aritmetico **{italian(weekday["arithmetic_margin_vs_reference_km"],3)} km** sul riferimento pubblicato. Patroni/eccezioni locali da verificare; sabato e km a vuoto non inclusi. Il margine non è finanziamento garantito.',
                  f'- A 260 giorni, solo confronto: **{italian(r["annual_service_km_260_day_comparison"],3)} km/anno**, **+{italian(r["difference_vs_111419_reference_km"],3)} km / +{italian(r["difference_vs_111419_reference_percent"])}%** rispetto al riferimento 111.419.',
                  f'- A **303 giorni identici**, sensibilità al conteggio dei tipi di giornata attivi PdB: **{italian(r["commercial_km_per_comparison_day"]*303,3)} km/anno**, **+{italian(100*(r["commercial_km_per_comparison_day"]*303/111419-1))}%**. I 303 non sono un calendario attuale accertato: [fonte primaria e limiti](RT031_LINEA8_CALENDARIO_E_RISORSE_2026_10_01.md). **Il +1,27% non è una differenza annua generale.**',
                  '- I confronti 260/303 rimangono sensibilità storiche, non il nuovo calendario. La base lunedì-venerdì 2027 è dichiarata; il calendario operativo completo, il sabato e le eccezioni locali non sono chiusi. Km non commerciali e costo di flotta si conteggiano separatamente.',
                  '- Fabbisogno ingegneristico condizionale: 3 mezzi in 2 casi e 4 in 25 dei 27 casi. Non disponibilità mezzi, turni reali o costo operativo approvati.',
                  '- [Blocchi completi e prova del minimo](RT031_LINEA8_MEZZI_E_CALENDARIO_2026_10_01.md): nel nominale e nel caso con recuperi maggiori B1 esegue i giri 1/5/9/13, B2 2/6/10/14, B3 3/7/11/15 e B4 4/8/12/16. Alle 07:35 quattro giri occupano contemporaneamente quattro mezzi. Ogni giro conserva est e ovest sullo stesso mezzo di modello; l’autorizzazione a restare a bordo e i turni autista reali rimangono aperti.',
                  '- Tetto decisionale e banda di incertezza non dichiarati; nessuna probabilità empirica di coincidenza e nessuna GJT pesata costruita artificialmente.', '',
                  '## Best practices: verifica aggiornata, non conformità generica', '',
                  '| Principio | Stato su questa precisa proposta |', '|---|---|'])
    italian_findings = [
        'Frequenza/durata: punte sfalsate e orari per evento; non H30 ovunque.',
        'Viaggio completo: tempi e attese separati; GJT pesata non disponibile.',
        'Memorabilità: punte regolari, morbida con partenze non tutte cadenzate.',
        'Ferrovia: tutte le chiamate e i flussi auditati; non tutte le coincidenze utili.',
        'Affidabilità: stress deterministici, non osservazioni; esercizio da validare.',
        'Direttezza: eventi locali rapidi ma viaggi lunghi residui mostrati sopra.',
        'Fermate: scambio Santa Maria–Calco chiuso nel progetto, accosti da validare.',
        'Semplicità: una sola linea e percorso completo sempre; permanenza FS da autorizzare.',
        'Continuità: esperienza storica conservata, nessuna prova di ottimo globale.',
        'Equità/domanda: copertura per comune, non domanda o utilità temporale certificata.',
        'Area funzionale: cinque comuni e ferrovia, non servizio del solo Olgiate.',
        'Inclusione: sud e San Zeno distinti; quartieri/accessi sicuri ancora da verificare.',
    ]
    for item, finding in zip(r['best_practice_current_assessment'], italian_findings):
        lines.append(f'| {item["id"]} | {finding} |')
    lines.extend(['', 'Riferimenti: [principi storici](PHASE2_TRANSIT_BEST_PRACTICES.md), [precedente audit, con numeri storici da non trapiantare](RT031_LINEA8_VERIFICA_BEST_PRACTICES_V3.md). La conferma di progetto non rende automaticamente soddisfatto un principio privo di prove.', '',
                  '## Tre verifiche per la consegna operativa', '',
                  'La [scheda per Agenzia e operatore](RT031_LINEA8_SCHEDA_VERIFICA_OPERATORE_2026_10_01.md) rende controllabili le richieste sotto. Sul tracciato attuale sono state controllate le transizioni di 1.435 archi diretti: **zero inversioni immediate**. Le sei M1–M6 erano del vecchio percorso. Rimane da verificare fisicamente un tratto di 85,68 m classificato `highway=service` presso Scarpone, oltre a svolte, accosti e restrizioni non certificati.', '',
                  '1. **Percorso e fermate — operatore/enti stradali:** sopralluogo e prova con bus, manovre e restrizioni a storia completa, accosti e lati, attraversamenti e accessibilità dei 27 siti. In particolare i quattro nuovi punti e FS.',
                  '2. **Tempi, continuità e turni — operatore:** tempi misurati per fascia, sosta/recupero, permanenza passeggeri a bordo, trasferimento pedonale reale, disponibilità e blocchi mezzi, deposito e km a vuoto. Un cambio necessario va esplicitato e accettato, non chiamato ancora lo stesso orario.',
                  '3. **Calendario e costo completo — Agenzia/operatore con scelta del committente:** la base 2027 lunedì-venerdì è dichiarata; restano sabato, eccezioni locali, produzione non commerciale, flotta/personale e copertura finanziaria. I +1,27%/+18,02% sono sensibilità a 260/303 giorni, non il nuovo confronto corrente. Il riferimento 111.419 è produzione PdB pubblicata, non prova di risorse attualmente trasferibili.', '',
                  '**Questa fissa la base progettuale, non conclude il suo rafforzamento tecnico e non certifica l’esercizio.** L’obiettivo del committente è una proposta implementabile e solida prima del confronto con l’azienda, non trasferire a quest’ultima la progettazione ancora incompleta. Nessuna email inviata, nessuna nuova variante selezionata.', '',
                  '## Rafforzamento interno: fragilità concrete dell’orario', '',
                  'L’[audit interno dei margini](../outputs/phase2/rt031_line8_local_shortcuts_v3/internal_transfer_margin_audit_20261002.json) riguarda il tracciato confermato, i treni del **1 ottobre 2026** e gli scenari ingegneristici ereditati. Dopo il cammino **assunto di 3 minuti**, il margine minimo delle cinque coincidenze mattutine est verso Milano è **13,4 secondi**; per le cinque serali da Milano verso ovest è **zero**. Non sono probabilità di ritardo o misure osservate. Un confronto con cammino di 5 minuti fa fallire queste due banche, senza adottare quel tempo come requisito o banda decisionale.', '',
                  'Sono stati verificati **11 confronti locali di fase**, ricalcolando tutte le 74 chiamate, 296 combinazioni ala/treno/flusso e 27 casi di mezzi. Risultati da non trasformare in modifiche automatiche:', '',
                  '- **Est mattina −4 minuti:** H30 e cap di attesa ereditati conservati, massimo quattro mezzi nel dominio, margine minimo verso Milano 4,22 minuti; ma l’attesa da alcuni treni in arrivo aumenta fino a **55 minuti**. L’arrivo 06:02, per esempio, passa da bus 06:05 a bus 06:31: attesa 3→29 minuti.',
                  '- **Est mattina −5 minuti:** richiede **cinque mezzi in alcuni dei 27 casi**, pur avendo gli stessi km. Non è un miglioramento gratuito.',
                  '- **Ovest +2 minuti nei giri 9–15:** cap di attesa e H30 conservati; massimo quattro mezzi, nessuna perdita delle precedenti compatibilità bus→treno in tutti i nove casi di marcia/dwell. Margine della banca serale da Milano 0→2 minuti, attese ferroviarie modificate al massimo di +2 minuti. Aumentano le soste e il servizio di **14 minuti/giorno**, non i km; il costo non è invariato per definizione.',
                  '- **Ovest +3 minuti negli stessi giri:** sette precedenti collegamenti bus→treno non sono più compatibili in tutti i nove casi; +5 minuti viola anche un cap di attesa. Il miglioramento di un solo margine non prova la solidità dell’insieme.', '',
                  '**Nessuna fase è selezionata o adottata.** Gli undici confronti restano diagnostici. Il successivo [rafforzamento interno](RT031_LINEA8_RAFFORZAMENTO_INTERNO_2026_10_02.md) ha ricostruito tutti gli eventi e i blocchi per la correzione ovest +2 minuti, e per il confronto con bypass Scarpone: 16 giri, nove ledger verificati, 27 blocchi e tutti i flussi ferroviari per ciascun confronto. Nessuna nuova fase è adottata tacitamente; la verifica 2027 e la solidità fisica restano distinte.', '',
                  'Il bypass Scarpone Via Pilata–rotatoria–Via Como aggiunge 25,84 m/giro e richiede un attacco ipotetico a 17,89 m dal nodo originale: non è la stessa occorrenza fisica certificata per nome. Ricalcolata sul substrato pedonale, la copertura 5/8/10 e le perdite lorde restano invariate. In combinazione con +2 minuti serali: 110.334,948 km feriali 2027, massimo quattro mezzi nei casi ereditati, nessuna precedente compatibilità bus→treno persa; attese da alcuni treni +2 minuti. È un confronto non adottato, non un accosto già sicuro.', '',
                  'Il problema AM è circoscritto: mantenere la stessa corsa per le cinque coppie di treni da Milano in arrivo a :02/:32 e verso Milano in partenza a :26/:56 (54 minuti dopo), sul percorso est e nel caso più lento con due cammini assunti da 3 minuti, lascia una finestra di fase di soli 13,4 secondi. Una fase bilanciata offre al massimo 6,7 secondi per lato; anticipare non migliora entrambi i flussi. Nessuna soglia di affidabilità è inventata. Le schede per l’operatore non sostituiscono questa criticità ingegneristica.', '',
                  'La [correzione del sottopasso del 7 ottobre](RT031_LINEA8_ACCESSI_BINARI_2026_10_02.md) recupera scala binario 2 → sottopasso → scala binario 1. La fonte OSM originale era completa per quelle scale: il controllo ometteva gli accessi interni alle aree delle banchine. Il cammino ricostruito è circa 108 m verso binario 1 e 76 m verso binario 2, non 251 m; solo 5,93 m sulla banchina 2 sono un raccordo geometrico locale esplicitamente modellato, senza attraversamenti dei binari a raso. Non sono tempi misurati alle porte. Il grafo RT028 certificato non è alterato. Gli accessi senza scale indicati da RFI restano una verifica separata.', '',
                  'Il [confronto AM completo corretto](RT031_LINEA8_FASI_AM_COMPLETE_2026_10_02.md) conserva nella base il bus a 3 minuti dai cinque arrivi AM nel proxy: non 33/58. I residui geometrici minimo AM sono 1,648 minuti in ingresso e 2,271 in uscita dopo il caso est più lento; non includono scale, porte o ritardi. +1/+2 non risolvono più un’attesa artificiale: aumentano l’attesa dei cinque arrivi di 1/2 minuti e riducono il residuo verso il treno, accorciando la sosta FS. Si mantiene l’orario confermato, senza altra scelta normativa. Nove ledger, 27 blocchi e 296 flussi per ciascuna diagnostica; H30, cap, 110.229,936 km feriali e massimo quattro mezzi di modello restano. Il confronto uniforme di 3 minuti è una sensibilità distinta, non il trasferimento effettivo.', '',
                  'L’[audit conclusivo del tempo minimo e della scelta AM](RT031_LINEA8_LIMITE_TEMPO_E_SCELTA_AM_2026_10_02.md) chiude la verifica sul grafo per questo ordine: due obiettivi × tre livelli di protezione degli arrivi alle fermate. Il percorso più rapido nel proxy aggiunge 41,62 m a Calco e risparmia solo 13,72 secondi nello stress; non viene adottato. Anche questo minimo lascia una finestra comune di appena 27,12 secondi. L’esempio completo est AM −2 minuti, sera +2 e Scarpone conserva 16 giri e 110.334,948 km feriali; aumenta il margine AM verso Milano a 2,223 minuti ma l’attesa dai primi quattro arrivi passa 3→31 minuti e dall’ultimo 3→58. Non è una nuova priorità del committente: serve scelta esplicita o evidenza osservata diversa, non un altro ricalcolo cosmetico.', '',
                  '## Tre controlli paralleli di chiusura, 7 ottobre', '',
                  'Il riesame separato strada/tempi/risorse conserva la stessa proposta, senza riaprire il dominio. La prova sulle [due restrizioni via-way note](../scripts/phase2_closure_roads_20261007.py) esclude entrambe dal percorso confermato: nessuna delle rispettive from/via/to ways appare nei 1.435 archi. In particolare mancano le to ways vietate, quindi anche una memoria di restrizione ereditata da un precedente posizionamento non può attivare quei due divieti sul giro. Questo non certifica completezza/attualità delle norme, sagoma, accosti o permessi.', '',
                  'Il [controllo dei tempi per ogni giro e blocco](RT031_closure_timing_20261007.md) produce 432 righe: 16 corse × 27 scenari. Separa marcia, dwell, sosta FS e recupero, senza scegliere una riserva; non inventa una scadenza di deposito per gli ultimi impieghi. I [controlli delle risorse](../scripts/phase2_closure_resources_20261007.py) riconciliano occupazione e gap, conteggiano eventuali esclusioni locali una sola volta e mantengono ignoti km a vuoto e costo. I 1.189,064 km di differenza dal riferimento non sono un finanziamento né un budget assegnato ai posizionamenti.', '',
                  'La topologia del sottopasso è ora anche confermata dal committente sulla propria esperienza. Le dodici verifiche residue restano assegnate nella distinta: ciò che richiede misure o attestazioni esterne non viene convertito in PASS dai controlli aritmetici. Nessuna nuova variante o priorità è adottata.', '',
                  '## Pacchetto autorevole', '',
                  '- [Integrità delle evidenze e residui di chiusura: 16 fallimenti corretti, nove ancora espliciti](RT031_LINEA8_VERIFICA_INTEGRITA_2026_10_02.md).',
                  '- [Conferma del committente, limiti e hash delle fonti](../config/rt031_design_timetable_confirmation_20261001_v3.json).',
                  '- [Amendamento del calendario feriale 2027, senza scelta del sabato](../config/rt031_weekday_calendar_2027_authority_v3.json).',
                  '- [Registro datato 2027 e sensibilità del sabato, senza orari inventati](../outputs/phase2/rt031_line8_local_shortcuts_v3/caller_confirmed_weekday_calendar_2027.json).',
                  '- [Dossier macchina: orario, registro fermate/eventi, treni, copertura, requisiti e verifiche](../outputs/phase2/rt031_line8_local_shortcuts_v3/caller_confirmed_design_handoff_20261001.json).',
                  '- [Tracciato stradale e coordinate attuali](../outputs/phase2/rt031_line8_local_shortcuts_v3/calco_centre_adopted_design.geojson).',
                  '- [Scheda per Agenzia e operatore con audit stradale aggiornato](RT031_LINEA8_SCHEDA_VERIFICA_OPERATORE_2026_10_01.md).',
                  '- [Blocchi dei mezzi nei 27 scenari e contabilità annua](../outputs/phase2/rt031_line8_local_shortcuts_v3/caller_confirmed_vehicle_blocks_accounting_20261001.json).',
                  '- [Rafforzamento interno: registri ricostruiti, deviazione Scarpone e limite AM](../outputs/phase2/rt031_line8_local_shortcuts_v3/fixed_design_strengthening_20261002.json).',
                  '- [Audit conclusivo: estremi distanza/tempo, tutte le occorrenze e compromesso AM non adottato](../outputs/phase2/rt031_line8_local_shortcuts_v3/fixed_order_runtime_closure_20261002.json).',
                  '- [Evidenza primaria PdB: produzione, giorni di progetto e limiti del calendario](../config/rt031_pdb_calendar_reference_evidence_20261001_v3.json).',
                  '- [Audit puntuale di accesso alle località, 108 abbinamenti](../outputs/phase2/rt031_line8_local_shortcuts_v3/caller_confirmed_locality_point_access_20261001.json).',
                  '- [Scheda precedente di proposta: conservata come stato storico](RT031_LINEA8_PROPOSTA_ORARIO_16_GIRI_V3.md).', '',
                  '`detailed_timetable_adopted_for_design=true`; `public_operating_timetable_authorised=false`; `network_selected=false`; `primary_selection_authorised=false`; `runner_up_selection_authorised=false`; `decision_budget_km=null`; `uncertainty_band_min=null`.', ''])
    return '\n'.join(lines)


if __name__ == '__main__':
    result = build()
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)+'\n', encoding='utf-8')
    BRIEF.write_text(render_brief(result), encoding='utf-8')
    print(json.dumps(dict(status=result['status'], trips=result['full_trip_count'],
                         sites=len(result['design_stop_register']), new_sites=result['proposed_new_design_site_count'],
                         nonhub_events=sum(len(s['ordered_occurrences']) for s in result['design_stop_register']),
                         operational_approval=result['public_operating_timetable_authorised']), ensure_ascii=False))
