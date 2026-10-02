"""Quantify the fixed weekday proposal and enumerate evidence still needed.

This is an operator working pack, not a new decision or operating approval.
One stop identity must never approve several different service occurrences.
"""
import hashlib
import json
import math
from pathlib import Path

from scripts.phase2_package_rt031_confirmed_design_handoff_v3 import (
    BASE, DESIGN, GEO, canonical_sha256, clock, build as handoff_build,
)
from scripts.phase2_complete_rt031_current_design_evidence_v3 import (
    OUTPUT as BLOCKS, build as blocks_build, validate_blocks,
)
from scripts.phase2_materialise_rt031_weekday_calendar_2027_v3 import (
    OUTPUT as CALENDAR, build as calendar_build,
)

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = BASE / 'caller_confirmed_design_handoff_20261001.json'
FIELDWORK = BASE / 'caller_confirmed_route_fieldwork_20261001.json'
OUTPUT = BASE / 'operating_closure_working_pack_20261002.json'
BRIEF = ROOT / 'docs/RT031_LINEA8_CHIUSURA_VERIFICHE_2026_10_02.md'


def load_inputs():
    paths = {'handoff': HANDOFF, 'blocks': BLOCKS, 'calendar': CALENDAR,
             'fieldwork': FIELDWORK}
    data = {key: json.loads(path.read_text(encoding='utf-8'))
            for key, path in paths.items()}
    # Reproduce the exact caller-confirmed timetable and derived arithmetic.
    for key, producer in (('handoff', handoff_build), ('blocks', blocks_build),
                          ('calendar', calendar_build)):
        if canonical_sha256(data[key]) != canonical_sha256(producer()):
            raise ValueError(f'Operating pack upstream source drift: {key}')
    for relative, expected in data['fieldwork']['source_sha256'].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Fieldwork source drift: {relative}')
    return data, {str(path.relative_to(ROOT)).replace('\\', '/'):
                  canonical_sha256(data[key]) for key, path in paths.items()}


def resource_quantities(case, weekday_days):
    """Account for full-trip work, recovery and uncommitted inter-trip time.

    Gaps begin AFTER mandatory model recovery. They are not available driver
    duties or certified opportunities for redeployment to other services.
    """
    if type(weekday_days) is not int or weekday_days <= 0:
        raise ValueError('Positive integer weekday day count required')
    trips = [trip for block in case['vehicles'] for trip in block['trips']]
    validate_blocks(trips, case['vehicles'], case['minimum_vehicle_count_conditional'])
    if not all(math.isfinite(t[k]) for t in trips for k in
               ('fs_start_min', 'fs_end_min', 'released_after_terminal_recovery_min')):
        raise ValueError('Finite vehicle event times required')
    blocks = []
    for block in case['vehicles']:
        ordered = sorted(block['trips'], key=lambda t: t['fs_start_min'])
        occupation = sum(t['released_after_terminal_recovery_min'] - t['fs_start_min']
                         for t in ordered)
        service = sum(t['fs_end_min'] - t['fs_start_min'] for t in ordered)
        gaps = [dict(after_full_trip=a['full_trip_number'],
                     before_full_trip=b['full_trip_number'],
                     begin_min=a['released_after_terminal_recovery_min'],
                     end_min=b['fs_start_min'],
                     duration_min=b['fs_start_min']-a['released_after_terminal_recovery_min'],
                     other_work_or_depot_travel_authorised=False)
                for a, b in zip(ordered, ordered[1:])]
        span = ordered[-1]['released_after_terminal_recovery_min']-ordered[0]['fs_start_min']
        if not math.isclose(span, occupation+sum(g['duration_min'] for g in gaps), abs_tol=1e-7):
            raise ValueError('Block span must equal occupation plus inter-trip gaps')
        blocks.append(dict(model_vehicle_id=block['model_vehicle_id'],
                           complete_trip_numbers=block['complete_trip_numbers'],
                           first_start_min=ordered[0]['fs_start_min'],
                           last_release_min=ordered[-1]['released_after_terminal_recovery_min'],
                           full_trip_service_hours=service/60,
                           occupation_hours_including_terminal_recovery=occupation/60,
                           first_to_last_block_span_hours=span/60,
                           uncommitted_gaps_after_recovery=gaps,
                           actual_vehicle_id=None, driver_duties=None))
    breakpoints = sorted({t[k] for t in trips for k in
                          ('fs_start_min', 'released_after_terminal_recovery_min')})
    concurrent = []
    for begin, end in zip(breakpoints, breakpoints[1:]):
        active = [t['full_trip_number'] for t in trips
                  if t['fs_start_min'] <= begin < t['released_after_terminal_recovery_min']]
        concurrent.append(dict(begin_min=begin, end_min=end,
                               occupied_vehicle_count=len(active),
                               occupied_full_trip_numbers=sorted(active)))
    maximum = max(c['occupied_vehicle_count'] for c in concurrent)
    if maximum != case['minimum_vehicle_count_conditional']:
        raise ValueError('Concurrent occupation disagrees with upstream minimum')
    service = sum(b['full_trip_service_hours'] for b in blocks)
    occupation = sum(b['occupation_hours_including_terminal_recovery'] for b in blocks)
    if not math.isclose(service, case['total_complete_trip_service_hours_excluding_terminal_recovery'], abs_tol=1e-8):
        raise ValueError('Service hour accounting differs from upstream')
    return dict(moving_multiplier=case['moving_multiplier'], dwell_min=case['dwell_min'],
                terminal_recovery_min=case['terminal_recovery_min'],
                weekday_days_before_local_exceptions=weekday_days,
                daily_complete_trip_service_hours=service,
                daily_vehicle_occupation_hours_including_terminal_recovery=occupation,
                weekday_annual_complete_trip_service_hours=service*weekday_days,
                weekday_annual_vehicle_occupation_hours=occupation*weekday_days,
                daily_sum_first_to_last_block_spans_hours=sum(b['first_to_last_block_span_hours'] for b in blocks),
                maximum_simultaneously_occupied_model_vehicles=maximum,
                four_vehicle_occupation_windows=[c for c in concurrent if c['occupied_vehicle_count'] == 4],
                concurrent_vehicle_occupation=concurrent, blocks=blocks,
                hours_are_driver_duties=False, gaps_are_certified_redeployment=False,
                cost_eur=None, fleet_availability_certified=False,
                semantics='Conditional vehicle occupation, including recovery once per complete trip. Block spans are not payable driver shifts. Gaps exclude recovery but not unmodelled depot, positioning, pauses or other-service obligations.')


def service_event_forms(handoff):
    """Separate 28 occurrences and three FS operational roles; leave proof blank."""
    by_site = {s['site_id']: s for s in handoff['design_stop_register']}
    by_occurrence = {o['occurrence_id']: (s, o) for s in by_site.values()
                     for o in s['ordered_occurrences']}
    hub = next(s for s in by_site.values() if s['hub_service_roles'])
    forms = []
    for order, event in enumerate(handoff['ordered_stop_event_ledger_nominal'][0]['events'], 1):
        oid = event.get('occurrence_id')
        if oid:
            site, occurrence = by_occurrence[oid]
            eid = oid
            context = {k: occurrence[k] for k in
                       ('wing', 'ordered_nonhub_event_number', 'full_path_edge_index',
                        'incoming_edge', 'outgoing_edge')}
        else:
            site = hub
            eid = 'FS::'+event['role']
            context = {'fs_role': event['role']}
        times = []
        for trip in handoff['ordered_stop_event_ledger_nominal']:
            matches = [e for e in trip['events'] if
                       (e.get('occurrence_id') == oid if oid else e['role'] == event['role'])]
            if len(matches) != 1:
                raise ValueError('Each event form must bind to every complete trip exactly once')
            times.append({k: v for k, v in matches[0].items()
                          if k in ('time_min', 'arrival_min', 'departure_min', 'board_event_min', 'alight_event_min')})
        forms.append(dict(event_id=eid, ordered_event_number=order,
                          site_id=site['site_id'], name=site['name'],
                          proposed_new_site=site['proposed_new_site'],
                          design_coordinates_lon_lat=site['coordinates_lon_lat'],
                          path_context=context, nominal_event_times_by_full_trip=times,
                          status='PENDING_OPERATOR_AND_STOP_AUTHORITY',
                          actual_platform_id=None, actual_platform_coordinates_lon_lat=None,
                          observed_boarding_side=None, boarding_permission=None,
                          alighting_permission=None, bus_kerb_and_swept_path_approved=None,
                          waiting_area_and_crossing_accessibility_approved=None,
                          required_works=None, evidence_refs=[], reviewed_by=None,
                          assessed_on=None, physical_service_event_authorised=False))
    if len(forms) != 31 or len({f['event_id'] for f in forms}) != 31:
        raise ValueError('Expected 28 distinct stop occurrences plus three FS roles')
    return forms


def pending_items():
    # Finite work list: proofs may close an issue; a failed proof triggers a
    # local correction and recheck, never an undocumented replacement proposal.
    specs = [
        ('ROADS', 'Operatore ed enti stradali', 'Percorso completo e Scarpone',
         'Prova/sopralluogo sul percorso con tipo e ingombri del bus; svolte, accessi e restrizioni dipendenti dalla storia. Esito specifico sugli 85,68 m service a Scarpone.', True),
        ('STOP_EVENTS', 'Operatore e autorità fermate', 'Accosti per ogni evento',
         'Riscontri per i 31 contesti: 28 occorrenze e tre ruoli FS, con palina/lato/coordinate, permessi e accessi sicuri. San Zeno e Olgiate sud hanno ciascuno due righe indipendenti.', True),
        ('RUNTIME', 'Operatore', 'Tempi misurati e orario eseguibile',
         'Tempi di marcia e dwell osservati per fascia; recuperi e blocchi eseguibili per i 16 giri. Campione e limiti dichiarati; lo stress non diventa probabilità.', True),
        ('FS_CONTINUITY', 'Operatore', 'Continuità passeggeri a FS',
         'Stesso mezzo e diritto dei passeggeri di restare a bordo alla FS intermedia confermati separatamente; eventuale cambio/discesa modifica il servizio e va accettato.', True),
        ('FS_TRANSFER', 'Operatore/Agenzia', 'Cammino bus–binari',
         'Misura separata binario 1→bus e bus→binario 2, e dei versi opposti: binario effettivo, scale/percorso accessibile, cammino in banchina, salita/discesa e chiusura porte. Confrontare i budget degli eventi dell’audit accessi binari, non un cammino uniforme di 3 minuti; nessuna banda decisionale scelta.', True),
        ('FLEET_DUTIES', 'Operatore', 'Mezzi, autisti e deposito',
         'Disponibilità reale nelle punte, tipo di bus, turni autista e piano deposito. Valutare i gap senza chiamarli disponibilità certificata per altre linee.', True),
        ('NONCOMMERCIAL', 'Operatore', 'Km e ore non commerciali',
         'Posizionamenti da deposito e tra servizi, con quantità separate dai 110.229,936 km della base commerciale.', True),
        ('LOCAL_CALENDAR', 'Agenzia/operatore', 'Eccezioni locali 2027',
         'Regola esplicita per patroni/eccezioni sulla linea intercomunale; elenco datato oppure attestazione che non si applicano. Nessuna esclusione dedotta dal solo patrono.', True),
        ('RAIL_2027', 'Fonte ferroviaria ufficiale e operatore/Agenzia', 'Treni validi per il 2027',
         'Inventari di tutte le chiamate, arrivi/partenze e calendari per le date di esercizio coperte dalle pubblicazioni; ricontrollo di tutti i flussi, inclusi casi deboli. Una verifica parziale dichiara il periodo, non tutto l’anno.', True),
        ('FULL_COST_FUNDING', 'Operatore/Agenzia', 'Preventivo e risorse effettive',
         'Costo completo per base feriale, personale/mezzi/lavori e km a vuoto; produzione D184/D185 contrattualizzata e risorse realmente riorganizzabili, senza doppio conteggio di tariffa/km e costo/ora.', True),
        ('SATURDAY', 'Committente, dopo confronto di servizio e costo', 'Sabato separato',
         'Calendario e orario utili espliciti, poi scelta del committente. I conteggi 2/4/6/8/16 non sono orari né raccomandazioni. Senza scelta, totale completo della linea resta null.', False),
        ('LOCALITY_CLAIMS', 'Committente ed enti/operatore per accessi', 'Promesse territoriali',
         'Conservare le percentuali come copertura potenziale; non dichiarare tutte le frazioni o tutto Olgiate sud serviti. Identificare luoghi/perimetri e accessi prima di estendere la promessa.', False),
    ]
    return [dict(id=key, owner=owner, title=title, close_when=proof,
                 blocking_weekday_operational_claim=block, status='PENDING_EXTERNAL_EVIDENCE',
                 evidence_refs=[], reviewed_by=None, assessed_on=None)
            for key, owner, title, proof, block in specs]


def build():
    data, manifest = load_inputs()
    handoff, blocks, calendar = (data[k] for k in ('handoff', 'blocks', 'calendar'))
    fieldwork = data['fieldwork']
    if (len(fieldwork['stop_fieldwork_register']) != 27
            or fieldwork['all_stops_authorised'] is not False
            or fieldwork['physical_bus_operation_authorised'] is not False):
        raise ValueError('This pending working pack cannot presume physical approval')
    days = calendar['weekday_base_day_count_before_local_exceptions']
    trip_km = calendar['complete_trip_commercial_km']
    base_km = calendar['weekday_base_commercial_km']
    saturday_count = calendar['saturday_nonholiday_date_count']
    one_per_saturday = saturday_count*trip_km
    return dict(contract='RT031_FIXED_WEEKDAY_PROPOSAL_OPERATING_CLOSURE_WORKING_PACK_V3',
                recorded_on='2026-10-02', source_canonical_sha256=manifest,
                design_manifest_sha256=canonical_sha256(manifest),
                additional_geometry_raw_sha256={str(p.relative_to(ROOT)).replace('\\', '/'):
                                               hashlib.sha256(p.read_bytes()).hexdigest() for p in (DESIGN, GEO)},
                closed_with_model_evidence=['Caller-confirmed same complete route and 16 trip timetable',
                                            '27 design sites, 28 ordered non-FS occurrences',
                                            'Dated weekday national-holiday arithmetic',
                                            'Explicit minimal vehicle blocks in all 27 inherited scenarios'],
                weekday_bill_of_quantities=dict(service_year=2027,
                    days_before_local_exceptions=days,
                    full_commercial_trips=calendar['weekday_base_complete_trip_count'],
                    commercial_km_per_complete_trip=trip_km, commercial_km=base_km,
                    reference_published_pdb_km=calendar['reference_published_pdb_annual_km'],
                    reference_is_secured_funding=False,
                    nominal=resource_quantities(blocks['nominal_case'], days),
                    slower_dwell_recovery=resource_quantities(blocks['slower_dwell_recovery_case'], days),
                    annual_noncommercial_km=None, payable_driver_hours=None,
                    actual_dedicated_fleet_count=None, capital_works_cost_eur=None,
                    operating_cost_eur=None, funding_amount_eur=None,
                    is_complete_line_annual_total=False),
                saturday_scope=dict(policy='SEPARATE_ASSESSMENT_NOT_CANCELLED_OR_ADOPTED',
                    nonholiday_saturday_count=saturday_count,
                    annual_km_increment_for_one_full_trip_each_saturday=one_per_saturday,
                    weekday_plus_one_trip_each_saturday_km=base_km+one_per_saturday,
                    delta_vs_published_reference_km=base_km+one_per_saturday-calendar['reference_published_pdb_annual_km'],
                    at_most_full_trips_in_remaining_arithmetic_margin=calendar['whole_extra_complete_trips_within_reference'],
                    count_only_sensitivities=calendar['saturday_sensitivity_count_only'],
                    exact_departures=None, useful_saturday_service_certified=False,
                    caller_selection=None, complete_line_annual_commercial_km=None),
                directional_service_event_forms=service_event_forms(handoff),
                road_priority_details=fieldwork['current_route_audit']['service_road_segments'],
                closure_items=pending_items(),
                rail_review=dict(checked_on='2026-10-02', certified_upstream_service_date='2026-10-01',
                    upstream_reported_rfi_validity=['2026-06-14', '2026-12-12'],
                    reviewed_official_pages=[
                        'https://www.trenord.it/linee-e-orari/circolazione/orario-ferroviario/',
                        'https://prm.rfi.it/qo_prm/QO_Partenze_SiPMR.aspx?Id=1805&alle=07.59&dalle=07.00&guid=&lin=&ora=07.00'],
                    review_result='NO_2027_COVERAGE_ESTABLISHED_IN_REVIEWED_SOURCES',
                    caution='RFI search and rendered page returned different 2025/2026 periods. Neither establishes 2027 validity. Existing dated rail cache remains unchanged; no future timetable is inferred.',
                    whole_2027_connections_certified=False,
                    claims_all_2027_timetables_globally_unpublished=False),
                changes_requiring_recheck=['path/stop position or side: km, pedestrian coverage, times and train flows',
                    'runtime/dwell/recovery: FS holds, all service-event times, train flows, occupation and duties',
                    'vehicle carrier or passenger permission: service continuity, transfer semantics and journeys',
                    'calendar/Saturday: dated annual production, duty quantities and complete cost'],
                physical_operation_ready=False, all_service_events_authorised=False,
                complete_annual_operating_calendar_adopted=False, funding_secured=False,
                network_selected=False, primary_selection_authorised=False,
                runner_up_selection_authorised=False, decision_budget_km=None,
                uncertainty_band_min=None, missed_connection_probability=None,
                demand_weighted_gjt_improvement_min=None,
                semantics='Fixed-design quantities and finite evidence requests. No external reply, price, physical platform, calendar exception, service preference or operating approval is manufactured. Saturday is outside this weekday quotation component, not assumed absent from the eventual line.')


def italian(value, places=2):
    return f'{value:,.{places}f}'.replace(',', '_').replace('.', ',').replace('_', '.')


def render_brief(result):
    bill = result['weekday_bill_of_quantities']
    nominal = bill['nominal']; slower = bill['slower_dwell_recovery']
    rows = ['# Linea 8 — chiusura delle verifiche, 2 ottobre 2026', '',
        '**Base feriale ferma; verifiche esterne ancora aperte.** Il lavoro tecnico non sceglie un nuovo tracciato, un sabato o un finanziamento. Questa è la distinta da verificare/preventivare, non un’autorizzazione all’esercizio.', '',
        '## Quantità della base feriale 2027', '',
        f'254 giornate prima delle eccezioni locali, 4.064 giri completi, **{italian(bill["commercial_km"],3)} km commerciali**. Quattro mezzi contemporanei entro le ipotesi nominali e nello stress mostrato; non quattro bus dedicati per tutto il giorno.', '',
        '| Quantità di modello | Nominale | Sosta/recupero maggiori |',
        '|---|---:|---:|',
        f'| Ore giornaliere dei giri, inclusa sosta FS intermedia | {italian(nominal["daily_complete_trip_service_hours"])} | {italian(slower["daily_complete_trip_service_hours"])} |',
        f'| Ore giornaliere di occupazione, incluso recupero finale | {italian(nominal["daily_vehicle_occupation_hours_including_terminal_recovery"])} | {italian(slower["daily_vehicle_occupation_hours_including_terminal_recovery"])} |',
        f'| Ore annue dei giri sulla base feriale | {italian(nominal["weekday_annual_complete_trip_service_hours"])} | {italian(slower["weekday_annual_complete_trip_service_hours"])} |',
        f'| Ore annue di occupazione sulla base feriale | {italian(nominal["weekday_annual_vehicle_occupation_hours"])} | {italian(slower["weekday_annual_vehicle_occupation_hours"])} |', '',
        '**Non sono ore autista né un preventivo.** Gli intervalli liberi tra giri sono calcolati dopo il recupero obbligatorio, ma deposito, altre linee e norme dei turni non sono verificati. Il prezzo va chiesto sulla distinta, evitando doppio conteggio di costi/ora già inclusi in una tariffa/km.', '',
        '| Mezzo di modello | Giri | Prima partenza | Ultimo rilascio nominale | Ore giri | Ore occupazione | Gap tra giri dopo recupero, min |',
        '|---|---|---|---|---:|---:|---|']
    for block in nominal['blocks']:
        gaps = ', '.join(italian(g['duration_min']) for g in block['uncommitted_gaps_after_recovery'])
        rows.append(f'| {block["model_vehicle_id"]} | '+', '.join(map(str, block['complete_trip_numbers']))+
                    f' | {clock(block["first_start_min"])} | {clock(block["last_release_min"])} | {italian(block["full_trip_service_hours"])} | {italian(block["occupation_hours_including_terminal_recovery"])} | {gaps} |')
    rows += ['', 'Rilascio significa fine giro più recupero terminale nel modello, non rientro al deposito. Non si presume che un autista copra l’intero intervallo prima–ultima corsa.', '',
        '## Sabato: separato, non eliminato', '',
        f'Ci sono 50 sabati non festivi. Anche **un solo giro completo ogni sabato** aggiunge {italian(result["saturday_scope"]["annual_km_increment_for_one_full_trip_each_saturday"],3)} km: totale commerciale {italian(result["saturday_scope"]["weekday_plus_one_trip_each_saturday_km"],3)}, **{italian(result["saturday_scope"]["delta_vs_published_reference_km"],3)} km sopra il riferimento**. Il margine feriale consente 43 giri aggiuntivi annui, non un servizio settimanale già utile.', '',
        '| Giri completi per ciascuno dei 50 sabati, sola sensibilità | Base feriale + sabato, km | Delta sul riferimento |',
        '|---:|---:|---:|']
    for case in result['saturday_scope']['count_only_sensitivities']:
        rows.append(f'| {case["hypothetical_full_trips_per_nonholiday_saturday"]} | {italian(case["weekday_base_plus_saturday_commercial_km"],3)} | +{italian(case["delta_vs_reference_percent"])}% |')
    rows += ['', 'Nessuno di questi conteggi è un orario: non certifica H30, durata della fascia o utilità. Il sabato resta un’opzione separata da progettare e scegliere; il totale annuo completo della linea rimane non definito.', '',
        '## Dodici risposte finite, non una nuova ricerca', '',
        '| ID | Responsabile | Questione da chiudere | Prova necessaria |', '|---|---|---|---|']
    for item in result['closure_items']:
        rows.append(f'| {item["id"]} | {item["owner"]} | {item["title"]} | {item["close_when"]} |')
    rows += ['', 'Le prime dieci risposte impediscono oggi di dichiarare esercibile/finanziata la base feriale. Il sabato serve anche alla chiusura del servizio annuo completo. I limiti territoriali restano da dichiarare, non sono garanzie estese automaticamente a tutte le frazioni.', '',
        '## Registro di sopralluogo per evento', '',
        'Il JSON contiene **31 schede indipendenti**, con coordinate, archi entranti/uscenti e orari dei 16 giri: 28 occorrenze non-FS e tre ruoli FS. San Zeno e Olgiate sud hanno due schede ciascuno. Si può approvare lo stesso accosto per più eventi, ma serve un riscontro esplicito per ogni evento: approvare il nome della fermata non approva automaticamente tutti i passaggi.', '',
        '| Ordine | Sito | Nuovo | Ruolo/occorrenza da verificare | Coordinate di progetto lat, lon |', '|---:|---|---|---|---|']
    fs_names = {'FULL_TRIP_START_FS': 'FS: partenza del giro',
                'INTERMEDIATE_FS_STAY_ONBOARD_DESIGN': 'FS: sosta e prosecuzione',
                'FULL_TRIP_END_FS': 'FS: fine del giro'}
    for form in result['directional_service_event_forms']:
        lon, lat = form['design_coordinates_lon_lat']
        context = form['path_context']
        label = (fs_names[context['fs_role']] if 'fs_role' in context else
                 ('Est' if context['wing'] == 'east_A' else 'Ovest')+
                 f' · evento non-FS {context["ordered_nonhub_event_number"]}')
        rows.append(f'| {form["ordered_event_number"]} | {form["name"]} | '+('sì' if form['proposed_new_site'] else 'no')+
                    f' | {label} | {lat:.7f}, {lon:.7f} |')
    rows += ['', 'Coordinate ancora di progetto, non paline approvate. Ogni scheda lascia vuoti palina/lato effettivi, permessi salita/discesa, accessibilità, lavori e riferimenti del riscontro. Nessuna risposta esterna è stata ricevuta o simulata.', '',
        '**Raccolta riscontri:** compilare una copia separata delle schede, conservando `event_id` e `design_manifest_sha256`. Non inserire risposte nel file generato: la riproduzione lo sovrascrive. Una risposta deve indicare autore, data e documento/foto/misura di prova; un cambio del progetto richiede riesame e non eredita l’approvazione della versione precedente.', '',
        '## Ferrovia: limite temporale verificato', '',
        'Il registro ferroviario certificato a monte riguarda il 1 ottobre 2026, con validità RFI riportata fino al 12 dicembre 2026. Il riesame del 2 ottobre delle [pubblicazioni Trenord](https://www.trenord.it/linee-e-orari/circolazione/orario-ferroviario/) e del [quadro RFI](https://prm.rfi.it/qo_prm/QO_Partenze_SiPMR.aspx?Id=1805&alle=07.59&dalle=07.00&guid=&lin=&ora=07.00) non ha stabilito una validità 2027. Il risultato RFI indicizzato e quello renderizzato mostrano periodi 2025/2026 diversi: non li si usa per inventare treni futuri né si sovrascrive il cache datato.', '',
        'Per il 2027 serviranno pubblicazioni valide per le date considerate, con arrivi e partenze, tutte le chiamate e calendari. Una verifica dell’inverno non certificherà automaticamente l’estate; le fasi confermate non si modificano senza mostrare gli effetti e ottenere accettazione.', '',
        '## Conclusione operativa', '',
        '**La base feriale è fissata; la chiusura tecnica generale e le prove esterne sono ancora aperte.** Il committente vuole una proposta solida e implementabile prima del confronto con l’azienda. Questa distinta raccoglie le quantità e le verifiche residue: non conclude la progettazione interna. Il [rafforzamento interno](RT031_LINEA8_RAFFORZAMENTO_INTERNO_2026_10_02.md) ricostruisce eventi, blocchi, copertura e flussi per +2 minuti serali e il bypass Scarpone. L’[audit conclusivo AM](RT031_LINEA8_LIMITE_TEMPO_E_SCELTA_AM_2026_10_02.md) chiude la verifica del minimo sul grafo nel dominio dichiarato e quantifica la scelta ferroviaria residua, non autorizzata. Quei confronti non modificano la base confermata di questa distinta.', '',
        '[Pacchetto macchina e schede da copiare per i riscontri](../outputs/phase2/rt031_line8_local_shortcuts_v3/operating_closure_working_pack_20261002.json) · [Dossier unico](RT031_LINEA8_PROPOSTA_UNICA_CONSOLIDATA_2026_10_01.md) · [Scheda Agenzia/operatore](RT031_LINEA8_SCHEDA_VERIFICA_OPERATORE_2026_10_01.md)', '',
        'Riproduzione: `python -m scripts.phase2_prepare_rt031_operating_closure_v3`.', '',
        '`physical_operation_ready=false`; nessuna scelta del sabato; costo/finanziamento non certificati; PRIMARY/RUNNER-UP non autorizzati; `decision_budget_km=null`; `uncertainty_band_min=null`.', '']
    return '\n'.join(rows)


if __name__ == '__main__':
    result = build()
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)+'\n', encoding='utf-8')
    BRIEF.write_text(render_brief(result), encoding='utf-8')
    print(json.dumps(dict(weekday_km=result['weekday_bill_of_quantities']['commercial_km'],
                         event_forms=len(result['directional_service_event_forms']),
                         pending_items=len(result['closure_items']),
                         nominal_service_hours=result['weekday_bill_of_quantities']['nominal']['daily_complete_trip_service_hours'],
                         physical_operation_ready=result['physical_operation_ready'])))
