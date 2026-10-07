"""Complete the disclosed AM +1/+2 comparisons on the confirmed geometry.

Independent directional transfer budgets remain unmeasured. Rebuilding an
entire timetable is not adopting it, certifying access or choosing a margin.
"""
import hashlib
import json
import math
from pathlib import Path

from scripts.phase2_package_rt031_confirmed_design_handoff_v3 import (
    BASE, DESIGN, OUTPUT as HANDOFF, canonical_sha256, clock,
    build as handoff_build,
)
from scripts.phase2_package_rt031_current_16_trip_proposal_v3 import SOURCE, RAIL
from scripts.phase2_materialise_rt031_weekday_calendar_2027_v3 import (
    OUTPUT as CALENDAR, build as calendar_build,
)
from scripts.phase2_audit_rt031_station_platform_access_v3 import (
    OUTPUT as PLATFORM, ACCESSIBILITY_REVIEW, RFI, dated_flows, planned_platforms,
)
from scripts.phase2_audit_rt031_internal_transfer_margins_v3 import shifted_schedule
from scripts.phase2_probe_rt031_line8_variable_fs_hold_v3 import wing_offsets
from scripts.phase2_strengthen_rt031_fixed_design_v3 import complete_case

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = BASE / 'directional_AM_phase_complete_comparisons_20261002.json'
BRIEF = ROOT / 'docs/RT031_LINEA8_FASI_AM_COMPLETE_2026_10_02.md'
SHIFTS = (0, 1, 2)


def evaluate_budget_inputs(budget, inbound_total_min, outbound_total_min):
    """Check declared total expenses, never fill absent evidence with zero.

    Inbound includes alighting, actual accessible path, boarding and rail
    lateness/reserve. Outbound includes actual path, boarding/door cut-off and
    extra bus lateness/reserve AFTER the inherited worst wing duration.
    This arithmetic does not authenticate measurements or certify reliability.
    """
    caps = (budget['maximum_inbound_total_expenses_min'],
            budget['maximum_outbound_total_expenses_after_worst_bus_model_min'])
    if any(value is None for value in caps):
        raise ValueError('Both sourced directional event budgets required')
    for value in (*caps, inbound_total_min, outbound_total_min):
        if value is not None and (type(value) not in (int, float)
                                  or not math.isfinite(value) or value < 0):
            raise ValueError('Finite nonnegative directional expense inputs required')
    available = inbound_total_min is not None and outbound_total_min is not None
    incoming = None if inbound_total_min is None else caps[0]-inbound_total_min
    outgoing = None if outbound_total_min is None else caps[1]-outbound_total_min
    return dict(inbound_total_min=inbound_total_min, outbound_total_min=outbound_total_min,
                both_expense_inputs_declared=available,
                inbound_residual_min=incoming, outbound_residual_min=outgoing,
                both_fit_event_budgets=None if not available else incoming >= 0 and outgoing >= 0,
                measurements_authenticated=False, passenger_connection_certified=False,
                timetable_adoption_authorised=False)


def approach_flow_changes(before, after):
    """Compare the exact dated wing/train rows without conflating flow senses."""
    def index(rows):
        result = {(r['wing'], r['trip_id']): r for r in rows}
        if len(result) != len(rows):
            raise ValueError('Duplicate dated directional flow identity')
        return result
    old, new = index(before), index(after)
    if set(old) != set(new):
        raise ValueError('Dated directional flow universe drift')
    changes, lost, inbound_lost, outbound_lost, waits = [], [], [], [], []
    for key, a in old.items():
        b = new[key]
        if any(a[k] != b[k] for k in ('train_number', 'train_direction', 'planned_platform',
                                    'approach_inbound_walk_min', 'approach_outbound_walk_min')):
            raise ValueError('Flow identity, platform or diagnostic assumption drift')
        ai, bi = a['rail_to_bus'], b['rail_to_bus']
        ao, bo = a['bus_to_rail'], b['bus_to_rail']
        identity = dict(wing=key[0], trip_id=key[1], train_number=a['train_number'],
                        train_direction=a['train_direction'], planned_platform=a['planned_platform'])
        if ai != bi or ao != bo:
            changes.append(dict(**identity, before_rail_to_bus=ai, after_rail_to_bus=bi,
                                before_bus_to_rail=ao, after_bus_to_rail=bo))
        if ao['same_bus_feasible_in_all_nine_cases'] and not bo['same_bus_feasible_in_all_nine_cases']:
            lost.append(identity)
        if ai['next_wing_departure_min'] is not None and bi['next_wing_departure_min'] is None:
            inbound_lost.append(identity)
        if ao['latest_nominal_bus_arrival_min'] is not None and bo['latest_nominal_bus_arrival_min'] is None:
            outbound_lost.append(identity)
        if ai['wait_from_train_arrival_min'] is not None and bi['wait_from_train_arrival_min'] is not None:
            waits.append(bi['wait_from_train_arrival_min']-ai['wait_from_train_arrival_min'])
    return dict(changes=changes, lost_previous_same_bus_all_nine_approach_diagnostics=lost,
                newly_unavailable_rail_to_bus_approach_diagnostics=inbound_lost,
                newly_unavailable_bus_to_rail_approach_diagnostics=outbound_lost,
                maximum_increase_in_rail_to_bus_wait_min=max(waits, default=0),
                all_passenger_connections_certified=False)


def paired_budgets(schedule, platform_audit, rail):
    """Exact paired AM events, not a universal transfer time or new threshold."""
    trains = {t['train_number']: t for t in rail['events']}
    result = []
    for trip, pair in zip(schedule['full_trips'][:5], platform_audit['paired_AM_directional_envelopes']):
        incoming = trains[pair['arriving_train_number']]
        outgoing = trains[pair['departing_train_number']]
        if (incoming['arrival_min'] != pair['arrival_min']
                or outgoing['departure_min'] != pair['departure_min']
                or incoming['origin_axis'] != 'MILANO' or outgoing['direction'] != 'MILANO'
                or not incoming['ordinary_alighting_supported'] or not outgoing['ordinary_boarding_supported']):
            raise ValueError('Exact paired AM train/event source drift')
        start = trip['first_fs_min']
        duration = pair['worst_inherited_east_duration_min']
        budget = dict(arriving_train_number=pair['arriving_train_number'],
            departing_train_number=pair['departing_train_number'],
            incoming_trip_id=incoming['trip_id'], outgoing_trip_id=outgoing['trip_id'],
            train_arrival_min=pair['arrival_min'], train_departure_min=pair['departure_min'],
            bus_departure_min=start, bus_worst_modeled_return_min=start+duration,
            worst_inherited_east_duration_min=duration,
            inbound_planned_platform_hypothesis=pair['inbound_planned_platform'],
            outbound_planned_platform=pair['outbound_planned_platform'],
            actual_arrival_platform_certified=False, actual_departure_platform_certified=False,
            maximum_inbound_total_expenses_min=start-pair['arrival_min'],
            maximum_outbound_total_expenses_after_worst_bus_model_min=pair['departure_min']-start-duration,
            observed_inbound_total_expenses_min=None, observed_outbound_total_expenses_min=None,
            observed_transfers_available=False, reserves_declared=False,
            passenger_connection_certified=False)
        budget['declared_expense_assessment'] = evaluate_budget_inputs(budget, None, None)
        result.append(budget)
    if len(result) != 5:
        raise ValueError('Five exact paired AM events required')
    return result


def validate_platform_pairs(source, design, rail, platform):
    """Recheck derived pair clocks/runtime rather than trust an audit label."""
    worst = max(g['east_A']['road_minutes'] for g in wing_offsets(design['loops']).values())
    trains = {t['train_number']: t for t in rail['events']}
    bindings = {t['trip_id']: t for t in platform['planned_platform_bindings']}
    if len(trains) != len(rail['events']) or len(bindings) != len(rail['events']):
        raise ValueError('Unique dated train/platform identities required')
    bank = next(b for b in source['selected_real_train_banks_not_adopted']
                if b['wing'] == 'east_A' and b['kind'] == 'bus_to_rail')
    pairs = platform['paired_AM_directional_envelopes']
    if len(pairs) != 5:
        raise ValueError('Five sourced AM event pairs required')
    for trip, pair, target in zip(source['full_trips'][:5], pairs, bank['rail_minutes']):
        a = trains.get(pair['arriving_train_number'])
        b = trains.get(pair['departing_train_number'])
        if (a is None or b is None
                or pair['baseline_bus_start_min'] != trip['first_fs_min']
                or pair['arrival_min'] != trip['first_fs_min']-3
                or pair['arrival_min'] != a['arrival_min']
                or pair['departure_min'] != b['departure_min'] or pair['departure_min'] != target
                or not math.isfinite(pair['worst_inherited_east_duration_min'])
                or abs(pair['worst_inherited_east_duration_min']-worst) > 1e-9
                or pair['inbound_planned_platform'] != bindings[a['trip_id']]['planned_departure_platform']
                or pair['outbound_planned_platform'] != bindings[b['trip_id']]['planned_departure_platform']):
            raise ValueError('Derived AM pair clock, platform or runtime drift')
    for ref in {b['planned_departure_platform'] for b in bindings.values()}:
        for direction in ('platform_to_bus', 'bus_to_platform'):
            path = platform['platforms'][ref][direction]
            if path is None:
                raise ValueError('Missing directed platform approach evidence')
            value = path['approach_only_walk_model_min']
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError('Finite nonnegative platform approach model required')
            if (path['final_platform_walk_and_train_door_time_included'] is not False
                    or path['observed_transfer_time'] is not False):
                raise ValueError('An approach model cannot become an observed door transfer')


def load_inputs():
    paths = (SOURCE, DESIGN, RAIL, HANDOFF, CALENDAR, PLATFORM, ACCESSIBILITY_REVIEW)
    values = [json.loads(p.read_text(encoding='utf-8')) for p in paths]
    source, design, rail, handoff, calendar, platform, review = values
    if canonical_sha256(handoff) != canonical_sha256(handoff_build()):
        raise ValueError('Caller-confirmed geometry/timetable drift')
    if canonical_sha256(calendar) != canonical_sha256(calendar_build()):
        raise ValueError('Caller-confirmed calendar drift')
    for p, v in zip(paths, values):
        if p in (SOURCE, DESIGN, RAIL, HANDOFF, ACCESSIBILITY_REVIEW):
            if platform['source_canonical_sha256'][p.name] != canonical_sha256(v):
                raise ValueError('Directional platform-audit source drift')
    if rail['event_count'] != 74 or not rail['ready_for_dated_rail_diagnostic']:
        raise ValueError('Full dated station train universe required')
    if platform['planned_platform_bindings'] != planned_platforms(RFI.read_bytes(), rail):
        raise ValueError('Dated primary planned-platform binding drift')
    validate_platform_pairs(source, design, rail, platform)
    if any(platform[k] is not False for k in ('observed_transfer_time_available',
            'platform_approach_is_train_door', 'timetable_or_route_change_adopted', 'rail_2027_certified')):
        raise ValueError('Unmeasured approach diagnostics cannot certify or adopt service')
    return paths, values


def build():
    paths, values = load_inputs()
    source, design, rail, handoff, calendar, platform, review = values
    offsets = wing_offsets(design['loops'])
    baseline_flows = dated_flows(source, offsets, rail, platform['planned_platform_bindings'], platform['platforms'])
    days = calendar['weekday_base_day_count_before_local_exceptions']
    reference = calendar['reference_published_pdb_annual_km']
    cases = []
    for shift in SHIFTS:
        schedule = shifted_schedule(source, am_advance=-shift)
        complete = complete_case('confirmed_baseline' if shift == 0 else f'AM_plus{shift}_confirmed_geometry',
            schedule, design['loops'], source, design['loops'], rail, days, reference)
        directional = dated_flows(schedule, offsets, rail, platform['planned_platform_bindings'], platform['platforms'])
        if len(directional) != 148:
            raise ValueError('Complete 296 directional flow diagnostic required')
        nominal = next(b for b in complete['all_27_complete_vehicle_blocks']
                       if (b['moving_multiplier'], b['dwell_min'], b['terminal_recovery_min']) == (1.1,.5,10))
        service = nominal['total_service_min_per_day']
        baseline = service if shift == 0 else cases[0]['nominal_full_trip_service_min_per_day']
        cases.append(dict(east_first_five_departures_delay_min=shift,
            comparison_not_adopted=shift != 0, entire_complete_timetable_checks=complete,
            nominal_full_trip_service_min_per_day=service,
            nominal_full_trip_service_delta_min_per_day=service-baseline,
            nominal_full_trip_service_delta_hours_2027=(service-baseline)*days/60,
            shorter_intermediate_hold_not_shorter_road_route=True,
            all_dated_rail_flows_approach_only=directional,
            approach_only_flow_comparison=approach_flow_changes(baseline_flows, directional),
            paired_directional_total_expense_budgets=paired_budgets(schedule, platform, rail),
            actual_implementation_ready=False, phase_change_adopted=False))
    helpers = (Path(__file__), ROOT/'scripts/phase2_strengthen_rt031_fixed_design_v3.py',
               ROOT/'scripts/phase2_audit_rt031_internal_transfer_margins_v3.py',
               ROOT/'scripts/phase2_audit_rt031_station_platform_access_v3.py',
               ROOT/'scripts/phase2_rt031_station_platform_surface_v3.py')
    return dict(contract='RT031_COMPLETE_DIRECTIONAL_AM_PHASE_COMPARISON_V3', recorded_on='2026-10-02',
        corrected_on='2026-10-07',
        source_canonical_sha256={p.name: canonical_sha256(v) for p, v in zip(paths, values)},
        generator_code_sha256={p.name: hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in helpers},
        rail_reference_date=rail['service_date'], declared_bounded_phase_domain_min=list(SHIFTS),
        phase_comparisons=cases, confirmed_geometry_unchanged=True, confirmed_timetable_unchanged=True,
        complete_case_count=3, nine_event_ledgers_per_case=9, vehicle_scenarios_per_case=27,
        transfer_flow_combinations_per_case_per_diagnostic=296,
        directional_approach_times_are_complete_transfers=False,
        uniform_3min_times_are_measured=False, actual_arrival_platforms_certified=False,
        normative_rail_priority_required_by_this_audit=False,
        global_or_exhaustive_phase_optimality_claimed=False, best_phase_selected=False,
        timetable_change_adopted=False, normative_rail_priority_adopted=False,
        external_operating_evidence_available=False, physical_operation_ready=False,
        rail_2027_certified=False, full_operating_cost_certified=False,
        network_selected=False, primary_selection_authorised=False, runner_up_selection_authorised=False,
        decision_budget_km=None, uncertainty_band_min=None, missed_connection_probability=None,
        demand_weighted_gjt_improvement_min=None,
        semantics='Three disclosed whole-timetable comparisons, not a new search, ranking or service selection. Same complete path, 28 ordered nonhub occurrences, 16 trips and caller-confirmed weekday calendar. Uniform three-minute transfers and platform-specific approach-only models are separately labelled sensitivities; their different outcomes expose unresolved evidence, not actual guarantees. The exact inbound/outbound expense budgets include separate lateness/reserve and door-event costs; all missing observed totals remain null.')


def render_brief(r):
    lines = ['# Linea 8 — confronto AM completo, senza cambiare la proposta', '',
        '**Corretto il 7 ottobre dopo il riscontro del committente sul sottopasso.** Chiusa la verifica interna dei tre casi già esposti: fase confermata, prime cinque partenze est +1 o +2 minuti. Stessa geometria, 27 siti, 28 eventi non-FS, 16 giri, H30 e calendario feriale 2027. Ovest e tutte le partenze successive restano invariati; nessuna variante viene adottata.', '',
        'Per ogni caso sono ricostruiti e verificati nove registri ordinati di tutte le corse, 27 blocchi mezzi e tutti i 296 flussi ferroviari in ciascuna delle due diagnostiche. Non sono 27 prove empiriche e non danno una probabilità.', '',
        '## Quanto tempo deve realmente bastare', '',
        'La prima coppia è arrivo da Milano 06:02 e partenza verso Milano 06:56; le quattro successive sono ogni 30 minuti. Il tempo est peggiore del modello è 47,7766 minuti. I budget sono **totali**, non tempi di solo cammino: ingresso include discesa, percorso effettivo, salita e ritardo/riserva treno; uscita include percorso alla porta, salita/chiusura porte e ritardo/riserva bus aggiuntivo rispetto al tempo est già stressato. Nessuna riserva è stata scelta.', '',
        '| Prima partenza est | Budget totale treno→bus | Budget totale bus→treno dopo giro stressato | Km feriali 2027 | Massimo mezzi di modello |',
        '|---|---:|---:|---:|---:|']
    for case in r['phase_comparisons']:
        budget = case['paired_directional_total_expense_budgets'][0]
        full = case['entire_complete_timetable_checks']
        label = 'base' if case['east_first_five_departures_delay_min'] == 0 else 'non adottata'
        lines.append(f'| {clock(budget["bus_departure_min"])[:5]} ({label}) | {budget["maximum_inbound_total_expenses_min"]:g} min | {budget["maximum_outbound_total_expenses_after_worst_bus_model_min"]:.3f} min | {full["weekday_commercial_km"]:.3f} | {full["maximum_conditional_vehicles"]} |')
    lines += ['',
        'L’ipotesi +1 ha partenze 06:06, 06:36, 07:06, 07:36, 08:06; +2: 06:07, 06:37, 07:07, 07:37, 08:07. Entrambe rispettano i cap direzionali di attesa e superano i controlli di corsa completa del modello ereditato. “Superano i controlli” non significa che le coincidenze reali siano garantite.', '',
        'Il +1 riduce di 5 minuti/giorno la sosta intermedia complessiva, il +2 di 10; rispettivamente −21,167 e −42,333 ore di servizio nominale sui 254 giorni. Non si percorrono meno metri e non sono risparmi economici o turni autista certificati.', '',
        '## Due diagnostiche, due esiti: non scegliere quella più favorevole', '',
        'Con **3 minuti uguali per ogni trasferimento**, +1 e +2 fanno perdere il rispetto di tutti i nove scenari alla stessa corsa verso ciascuno dei cinque treni AM Milano. Non si occulta questo esito.', '',
        'Con il **sottopasso corretto**, +1 e +2 non introducono perdite rispetto alle coincidenze bus→treno già rispettate in tutti i nove casi di quella diagnostica. Ma la base ora offre già il bus a **3 minuti dai cinque arrivi AM** nel proxy, non 33/58. Le due ipotesi portano quell’attesa a 4/5 minuti e riducono il residuo verso il treno di 1/2 minuti, pur accorciando la sosta intermedia. Tutte le righe Milano/Lecco sono conservate. Questo è un confronto fra effetti distinti, non una graduatoria pesata. Il proxy corretto omette ancora scale, porte e ritardi.', '',
        '**Conclusione:** viene ritirata la motivazione del +1 come rimedio al vecchio giro esterno. Si mantiene la fase confermata: non occorre un’altra scelta del committente per correggere quell’errore. Le ipotesi +1/+2 restano confronti non adottati, non vincitori. Nella base le spese totali devono stare entro 3 minuti in ingresso e 3 minuti 13,4 secondi in uscita dopo il giro est stressato. I due trasferimenti effettivi e l’eventuale riserva restano da verificare, senza imporre una priorità normativa.', '',
        '## Dove finisce la chiusura interna', '',
        'Percorso e orario confermati rimangono la proposta di base. Non servono altre varianti per chiudere questo confronto locale: serve una prova del giro est in punta e dei trasferimenti effettivi, con piattaforme reali e percorso accessibile; poi si confrontano i totali con questi budget, senza trasformare dati assenti in zero. Treni 2027, accosti/sagoma, continuità passeggeri, turni/deposito e costo completo restano nella [distinta operativa](RT031_LINEA8_CHIUSURA_VERIFICHE_2026_10_02.md). Nessuna misurazione o risposta dell’operatore è simulata.', '',
        '[Confronto macchina completo e tutte le righe](../outputs/phase2/rt031_line8_local_shortcuts_v3/directional_AM_phase_complete_comparisons_20261002.json) · [Accessi e fonti distinti](RT031_LINEA8_ACCESSI_BINARI_2026_10_02.md)', '',
        '`physical_operation_ready=false`; `rail_2027_certified=false`; `timetable_change_adopted=false`; `primary_selection_authorised=false`; `runner_up_selection_authorised=false`; `decision_budget_km=null`; `uncertainty_band_min=null`.', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    result = build()
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(',',':'))+'\n', encoding='utf-8', newline='\n')
    BRIEF.write_text(render_brief(result), encoding='utf-8', newline='\n')
    print(json.dumps(dict(cases=result['complete_case_count'], unchanged_geometry=True,
                         phase_selected=False, observed_transfer_inputs_available=False)))
