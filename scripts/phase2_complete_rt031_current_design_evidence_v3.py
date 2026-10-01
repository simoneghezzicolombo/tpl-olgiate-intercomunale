"""Complete conditional vehicle blocks and annual accounting for the fixed design.

No fleet, driver duty, annual calendar, Decision Contract or selection adoption.
"""
import hashlib
import heapq
import json
import math
from collections import Counter
from pathlib import Path

from scripts.phase2_package_rt031_confirmed_design_handoff_v3 import (
    BASE, DESIGN, canonical_sha256, build as confirmed_build, clock,
)
from scripts.phase2_probe_rt031_line8_variable_fs_hold_v3 import wing_offsets

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = BASE / 'caller_confirmed_design_handoff_20261001.json'
CALENDAR_EVIDENCE = ROOT / 'config/rt031_pdb_calendar_reference_evidence_20261001_v3.json'
OUTPUT = BASE / 'caller_confirmed_vehicle_blocks_accounting_20261001.json'
BRIEF = ROOT / 'docs/RT031_LINEA8_MEZZI_E_CALENDARIO_2026_10_01.md'
PDB_PDF_SHA256 = 'e0657cb4e8a078ddf99f28e1ebbde4a67ee36bb9b7a92fcd488e2539a948079a'


def validate_calendar_evidence(evidence, handoff):
    """Validate the reviewed primary-source transcription, not a service adoption."""
    if evidence['contract'] != 'RT031_PDB_CALENDAR_REFERENCE_EVIDENCE_V3':
        raise ValueError('Unsupported calendar evidence contract')
    source = evidence['primary_source']
    if (source['local_path'] != 'data/raw/pdb/PdB_Allegato3.4_Meratese.pdf'
            or source['sha256'] != PDB_PDF_SHA256
            or hashlib.sha256((ROOT/source['local_path']).read_bytes()).hexdigest() != PDB_PDF_SHA256):
        raise ValueError('Primary calendar PDF source drift')
    if [(r['route_id'], r['pdf_page_number_one_based'], r['pdf_page_index_zero_based'])
            for r in source['route_pages']] != [('D184', 7, 6), ('D185', 8, 7)]:
        raise ValueError('Primary calendar PDF page identity drift')
    totals = evidence['published_route_totals_bus_km_per_year']
    if (len(totals) != 2 or {r['route_id']: r['published_total'] for r in totals}
            != {'D184': 52560, 'D185': 58859}):
        raise ValueError('Reviewed published production totals drift')
    reference = sum(r['published_total'] for r in totals)
    if evidence['combined_reference']['published_total_sum_bus_km_per_year'] != reference:
        raise ValueError('Published production reference sum differs')
    table = evidence['day_type_table_shared_by_d184_d185']
    expected_rows = [('Feriale invernale', 187, 6), ('Sabato invernale', 39, 6),
                     ('Festivo invernale', 46, 0), ('Feriale estivo no agosto', 45, 6),
                     ('Sabato estivo no agosto', 9, 6), ('Feriale agosto', 19, 6),
                     ('Sabato agosto', 4, 6), ('Festivo estivo', 14, 0)]
    if [(r['label'], r['days'], r['project_pairs_per_day']) for r in table['rows']] != expected_rows:
        raise ValueError('Reviewed planning day-type transcription drift')
    active_days = sum(r['days'] for r in table['rows'] if r['project_pairs_per_day'] > 0)
    if (table['ordinary_project_service_days'] != active_days
            or table['all_displayed_day_type_counts_sum'] != sum(r['days'] for r in table['rows'])):
        raise ValueError('Planning day-type sum differs')
    design = evidence['current_confirmed_design_arithmetic']
    if (design['source_canonical_sha256'] != canonical_sha256(handoff)
            or design['full_trips_per_identical_day'] != handoff['full_trip_count']
            or not math.isclose(design['complete_path_distance_m'], handoff['complete_path_distance_m'], abs_tol=1e-8)
            or not math.isclose(design['commercial_km_per_identical_day'], handoff['commercial_km_per_comparison_day'], abs_tol=1e-8)):
        raise ValueError('Calendar arithmetic confirmed-design source drift')
    if (design['calendar_adopted'] is not False
            or design['weekend_or_holiday_loss_inferable'] is not False
            or design['full_operating_cost_certified'] is not False
            or design['reference_funding_transfer_certified'] is not False
            or evidence['decisions_made_by_this_record'] != []):
        raise ValueError('Planning evidence cannot adopt calendar, costs or funding')
    scenarios = design['scenarios']
    if [s['days'] for s in scenarios] != [260, active_days]:
        raise ValueError('Missing reviewed annual comparison')
    for scenario in scenarios:
        km = design['commercial_km_per_identical_day']*scenario['days']
        if not all(math.isclose(scenario[key], expected, abs_tol=1e-8)
                   for key, expected in [('commercial_km', km), ('delta_vs_111419_km', km-reference),
                                         ('delta_vs_111419_percent', 100*(km/reference-1))]):
            raise ValueError('Source calendar arithmetic differs')
    return reference, active_days


def make_intervals(trips, east_duration, west_duration, recovery):
    if not all(math.isfinite(v) and v >= 0 for v in (east_duration, west_duration, recovery)):
        raise ValueError('Finite nonnegative duration/recovery required')
    intervals = []
    for i, trip in enumerate(trips, 1):
        start, mid = trip['first_fs_min'], trip['second_fs_min']
        if not all(math.isfinite(v) and v >= 0 for v in (start, mid)):
            raise ValueError('Finite nonnegative FS event times required')
        if mid+1e-8 < start+east_duration+1:
            raise ValueError('Intermediate FS lacks assumed public dwell')
        end = mid+west_duration
        intervals.append(dict(full_trip_number=i, fs_start_min=start,
                              intermediate_fs_arrival_min=start+east_duration,
                              intermediate_fs_departure_min=mid,
                              fs_end_min=end, released_after_terminal_recovery_min=end+recovery))
    if len({r['fs_start_min'] for r in intervals}) != len(intervals):
        raise ValueError('Duplicate complete-trip departure')
    return intervals


def validate_blocks(intervals, vehicles, expected_count):
    assigned = [i for block in vehicles for i in block['complete_trip_numbers']]
    if sorted(assigned) != sorted(r['full_trip_number'] for r in intervals):
        raise ValueError('Vehicle blocks omit or duplicate a complete trip')
    if len(vehicles) != expected_count:
        raise ValueError('Block count differs from interval-overlap minimum')
    by_id = {r['full_trip_number']: r for r in intervals}
    for block in vehicles:
        for a, b in zip(block['complete_trip_numbers'], block['complete_trip_numbers'][1:]):
            if by_id[b]['fs_start_min']+1e-8 < by_id[a]['released_after_terminal_recovery_min']:
                raise ValueError('Vehicle reused before full-trip terminal recovery')


def complete_trip_blocks(intervals):
    if not intervals:
        raise ValueError('At least one complete trip required')
    ordered = sorted(intervals, key=lambda r: (r['fs_start_min'], r['full_trip_number']))
    vehicles, available = [], []
    for trip in ordered:
        if available and available[0][0] <= trip['fs_start_min']+1e-8:
            _, vehicle = heapq.heappop(available)
        else:
            vehicle = len(vehicles)
            vehicles.append(dict(model_vehicle_id=f'B{vehicle+1}', complete_trip_numbers=[]))
        vehicles[vehicle]['complete_trip_numbers'].append(trip['full_trip_number'])
        heapq.heappush(available, (trip['released_after_terminal_recovery_min'], vehicle))
    candidates = [(r['fs_start_min'], sorted(t['full_trip_number'] for t in intervals
                                           if t['fs_start_min'] <= r['fs_start_min']
                                           and t['released_after_terminal_recovery_min'] > r['fs_start_min']+1e-8))
                  for r in ordered]
    count = max(len(ids) for _, ids in candidates)
    witness_time, witness_ids = next((time, ids) for time, ids in candidates if len(ids) == count)
    validate_blocks(intervals, vehicles, count)
    by_id = {t['full_trip_number']: t for t in intervals}
    for vehicle in vehicles:
        vehicle['trips'] = [dict(**by_id[i],
                                terminal_layover_to_next_full_trip_min=(
                                    by_id[vehicle['complete_trip_numbers'][j+1]]['fs_start_min']-by_id[i]['fs_end_min']
                                    if j+1 < len(vehicle['complete_trip_numbers']) else None))
                            for j, i in enumerate(vehicle['complete_trip_numbers'])]
        vehicle['same_model_vehicle_through_intermediate_fs'] = True
        vehicle['actual_vehicle_identity'] = None
        vehicle['driver_duty_assignment'] = None
    return dict(minimum_vehicle_count_conditional=count,
                overlap_lower_bound_witness=dict(time_min=witness_time, simultaneous_full_trip_numbers=witness_ids,
                                                semantics='Half-open vehicle occupation intervals include terminal recovery, charged once per complete trip.'),
                vehicles=vehicles)


def accounting(daily_km, reference, planning_days):
    if not math.isfinite(daily_km) or daily_km <= 0:
        raise ValueError('Finite positive commercial km/day required')
    if (not math.isfinite(reference) or reference <= 0
            or type(planning_days) is not int or planning_days <= 0):
        raise ValueError('Positive reference and planning day count required')
    maximum = math.floor(reference/daily_km)
    return dict(commercial_km_per_identical_service_day=daily_km,
                reference_annual_commercial_km=reference,
                maximum_whole_identical_days_within_reference=maximum,
                annual_calendar_adopted=False,
                actual_annual_service_day_count=None,
                annual_noncommercial_km=None,
                full_annual_operating_cost=None,
                annual_commercial_comparisons=[dict(
                    identical_service_days=days, commercial_km=daily_km*days,
                    delta_vs_reference_km=daily_km*days-reference,
                    delta_vs_reference_percent=100*(daily_km*days/reference-1),
                    scenario_semantics=('PDB_PLANNING_ACTIVE_DAY_COUNT_APPLIED_TO_IDENTICAL_PROPOSED_DAY'
                                        if days == planning_days else 'HYPOTHETICAL_IDENTICAL_SERVICE_DAYS_NOT_ADOPTED'),
                ) for days in dict.fromkeys((maximum, maximum+1, 260, planning_days))],
                semantics='Arithmetic commercial production only. The PdB day-type count is planning evidence, not a certified current dated annual calendar. No service dates, weekend/holiday cuts, budget uplift or cost estimate adopted.')


def build():
    handoff = json.loads(HANDOFF.read_text(encoding='utf-8'))
    if canonical_sha256(handoff) != canonical_sha256(confirmed_build()):
        raise ValueError('Confirmed handoff differs from verified inputs')
    calendar = json.loads(CALENDAR_EVIDENCE.read_text(encoding='utf-8'))
    reference_km, planning_days = validate_calendar_evidence(calendar, handoff)
    design = json.loads(DESIGN.read_text(encoding='utf-8'))
    offsets = wing_offsets(design['loops'])
    cases = []
    for resource in handoff['vehicle_cases_conditional']:
        moving, dwell = resource['moving_multiplier'], resource['dwell_min']
        recovery = resource['terminal_recovery_min']
        duration = offsets[moving, dwell]
        intervals = make_intervals(handoff['full_trips'], duration['east_A']['road_minutes'],
                                   duration['west_B']['road_minutes'], recovery)
        result = complete_trip_blocks(intervals)
        if result['minimum_vehicle_count_conditional'] != resource['minimum_vehicle_count_conditional']:
            raise ValueError('Explicit blocks contradict upstream conditional fleet count')
        cases.append(dict(**resource, **{k:v for k,v in result.items() if k != 'minimum_vehicle_count_conditional'},
                          total_complete_trip_service_hours_excluding_terminal_recovery=sum(t['fs_end_min']-t['fs_start_min'] for t in intervals)/60,
                          total_vehicle_occupation_hours_including_terminal_recovery=sum(t['released_after_terminal_recovery_min']-t['fs_start_min'] for t in intervals)/60,
                          time_totals_are_driver_duties=False,
                          physical_vehicle_and_passenger_continuity_certified=False))
    if len(cases) != 27:
        raise ValueError('Missing inherited resource scenario')
    nominal = next(c for c in cases if (c['moving_multiplier'], c['dwell_min'], c['terminal_recovery_min']) == (1.1,.5,10))
    severe = next(c for c in cases if (c['moving_multiplier'], c['dwell_min'], c['terminal_recovery_min']) == (1.1,1.,15))
    daily = handoff['commercial_km_per_comparison_day']
    distribution = dict(sorted(Counter(str(c['minimum_vehicle_count_conditional']) for c in cases).items()))
    return dict(contract='RT031_CURRENT_CONFIRMED_DESIGN_COMPLETE_TRIP_BLOCKS_ACCOUNTING_V3',
                source_canonical_sha256={HANDOFF.name:canonical_sha256(handoff), DESIGN.name:canonical_sha256(design),
                                         CALENDAR_EVIDENCE.name:canonical_sha256(calendar)},
                primary_calendar_pdf_sha256=calendar['primary_source']['sha256'],
                recorded_on='2026-10-02', design_reference_date='2026-10-01',
                all_27_resource_cases=cases,
                nominal_case=nominal,
                slower_dwell_recovery_case=severe,
                conditional_fleet_distribution=distribution,
                calendar_accounting=accounting(daily, reference_km, planning_days),
                calendar_primary_evidence_source=str(CALENDAR_EVIDENCE.relative_to(ROOT)),
                declared_display_cases=dict(nominal=[1.1,.5,10], slower_dwell_recovery=[1.1,1.,15],
                                            uncertainty_band_selected=False),
                same_full_route_for_all_trips=True,
                separate_wing_fleets=False,
                driver_duties_and_depot_plan_certified=False,
                operating_plan_adopted=False,
                physical_vehicle_and_passenger_continuity_certified=False,
                network_selected=False,
                primary_selection_authorised=False,
                runner_up_selection_authorised=False,
                decision_budget_km=None,
                uncertainty_band_min=None,
                missed_connection_probability=None,
                demand_weighted_gjt_improvement_min=None,
                semantics='Exact minimal interval assignments for the current complete trips, within the inherited deterministic time/recovery scenarios and without depot travel. Model vehicles are not real fleet availability or driver shifts; remaining service/physical validations are unchanged.')


def render_brief(r):
    nominal = r['nominal_case']; severe = r['slower_dwell_recovery_case']
    rows = ['# Linea 8 — mezzi e calendario della proposta confermata', '',
            'I blocchi mezzi restano validi per lo stesso giorno di progetto. I confronti 260/303 sotto sono precedenti alla dichiarazione della [base feriale datata 2027](RT031_LINEA8_CALENDARIO_FERIALE_2027_V3.md): 254 giornate dopo i festivi nazionali, 110.229,936 km della sola base, sabato ancora da valutare. Non usare i confronti storici come calendario corrente.', '',
            'Sono stati assegnati i 16 giri completi a mezzi di modello per tutti i 27 scenari ereditati. Il minimo condizionale è 4 nel nominale e nel caso con sosta/recupero maggiori: 25 casi richiedono 4 mezzi, due casi 3. Non sono turni autista o disponibilità reale della flotta.', '',
            '| Mezzo di modello | Giri completi assegnati, nominale e stress mostrato |', '|---|---|']
    for block in nominal['vehicles']:
        rows.append(f'| {block["model_vehicle_id"]} | '+', '.join(map(str,block['complete_trip_numbers']))+' |')
    rows += ['', 'Ogni mezzo assegnato percorre entrambe le ali dentro ogni giro; FS intermedia è una sosta dello stesso mezzo. Quattro mezzi non significa due linee. Nei due casi mostrati, alle 07:35 i giri 1, 2, 3 e 4 occupano contemporaneamente un mezzo: questo prova che tre non bastano entro le ipotesi dichiarate.', '',
             f'Nominale: fine ultimo giro {clock(max(t["fs_end_min"] for v in nominal["vehicles"] for t in v["trips"]))}. Stress con marcia ×1,1, sosta 1 minuto ed ultimo recupero 15 minuti: fine {clock(max(t["fs_end_min"] for v in severe["vehicles"] for t in v["trips"]))}. Dati ingegneristici, non ritardi osservati o probabilità.', '',
             'Nel JSON le ore di servizio del giro (incluse le soste FS intermedie) sono separate dalle ore di occupazione del mezzo comprensive del recupero finale. Nessuna delle due è un turno autista: deposito, posizionamento, pause e norme di lavoro non sono modellati.', '',
             '## Il calendario cambia il confronto annuo', '',
             '| Giorni con identico servizio | Km commerciali/anno | Differenza su 111.419 |', '|---:|---:|---:|']
    for comparison in r['calendar_accounting']['annual_commercial_comparisons']:
        rows.append(f'| {comparison["identical_service_days"]} | {comparison["commercial_km"]:,.3f} | {comparison["delta_vs_reference_percent"]:+.2f}% |'.replace(',','_').replace('.',',').replace('_','.'))
    rows += ['', 'I 260 giorni sono un confronto ipotetico. I 303 giorni sono la somma dei tipi di giornata attivi del progetto D184/D185 nel Programma di Bacino: applicarli alla nuova proposta è una sensibilità aritmetica. Nessuno dei due costituisce un calendario annuale attuale già accertato o scelto. [Prova primaria e dettaglio dei tipi di giornata](RT031_LINEA8_CALENDARIO_E_RISORSE_2026_10_01.md).', '',
             '**Il +1,27% non vale senza specificare i 260 giorni.** Con 303 giorni identici il confronto sale a +18,02%. Per rimanere entro il solo riferimento commerciale 111.419 si possono conteggiare al massimo 256 giorni identici; nessuna giornata è eliminata con questo calcolo. Km a vuoto, costo completo e finanziamento restano da definire.', '',
             '[Blocchi e prove di minimo nei 27 scenari, contabilità e limiti](../outputs/phase2/rt031_line8_local_shortcuts_v3/caller_confirmed_vehicle_blocks_accounting_20261001.json) · [Proposta unica](RT031_LINEA8_PROPOSTA_UNICA_CONSOLIDATA_2026_10_01.md) · [Richieste operative](RT031_LINEA8_SCHEDA_VERIFICA_OPERATORE_2026_10_01.md)', '',
             '`operating_plan_adopted=false`; `network_selected=false`; PRIMARY/RUNNER-UP non autorizzati; calendario non adottato; `decision_budget_km=null`; `uncertainty_band_min=null`.', '']
    return '\n'.join(rows)


if __name__ == '__main__':
    result = build()
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    BRIEF.write_text(render_brief(result),encoding='utf-8')
    print(json.dumps(dict(fleet=result['conditional_fleet_distribution'],
                         nominal_blocks=[v['complete_trip_numbers'] for v in result['nominal_case']['vehicles']],
                         max_days=result['calendar_accounting']['maximum_whole_identical_days_within_reference'])))
