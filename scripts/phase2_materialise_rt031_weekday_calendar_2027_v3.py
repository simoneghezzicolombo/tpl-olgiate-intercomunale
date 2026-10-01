"""Materialise the caller's weekday component; never fill the unresolved Saturday.

The October 2026 dated rail audit is not a 2027 connection certification.
Historical 260/303 comparisons and their authorities remain unchanged.
"""
import json
import math
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from scripts.phase2_complete_rt031_current_design_evidence_v3 import validate_calendar_evidence
from scripts.phase2_package_rt031_confirmed_design_handoff_v3 import (
    AUTHORITY as TIMETABLE_AUTHORITY, BASE, canonical_sha256, build as handoff_build,
)

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY = ROOT / 'config/rt031_weekday_calendar_2027_authority_v3.json'
PDB = ROOT / 'config/rt031_pdb_calendar_reference_evidence_20261001_v3.json'
HANDOFF = BASE / 'caller_confirmed_design_handoff_20261001.json'
OUTPUT = BASE / 'caller_confirmed_weekday_calendar_2027.json'
BRIEF = ROOT / 'docs/RT031_LINEA8_CALENDARIO_FERIALE_2027_V3.md'


def validate_authority(authority, sources):
    if set(sources) != set(authority['source_canonical_sha256']):
        raise ValueError('Weekday authority source set mismatch')
    for key, payload in sources.items():
        if canonical_sha256(payload) != authority['source_canonical_sha256'][key]:
            raise ValueError(f'Weekday authority source drift: {key}')
    if (authority['contract'] != 'RT031_CALLER_DECLARED_WEEKDAY_CALENDAR_2027_V3'
            or authority['service_year'] != 2027
            or authority['weekday_iso_numbers'] != [1, 2, 3, 4, 5]
            or authority['full_trips_per_weekday'] != 16
            or authority['weekday_calendar_declared_for_design'] is not True
            or authority['all_trips_same_complete_path'] is not True
            or authority['national_holidays_excluded_from_weekday_base'] is not True):
        raise ValueError('Caller-confirmed weekday scope mismatch')
    dates = [r['date'] for r in authority['national_holiday_dates_2027']]
    expected = ['2027-01-01', '2027-01-06', '2027-03-28', '2027-03-29', '2027-04-25',
                '2027-05-01', '2027-06-02', '2027-08-15', '2027-10-04', '2027-11-01',
                '2027-12-08', '2027-12-25', '2027-12-26']
    if dates != expected or len(dates) != len(set(dates)):
        raise ValueError('Reviewed 2027 national holiday dates drift')
    for key in ('school_vacation_or_bridge_day_cuts_authorised', 'local_exception_policy_certified',
                'complete_annual_operating_calendar_adopted', 'public_operating_timetable_authorised',
                'funding_secured', 'network_selected', 'primary_selection_authorised',
                'runner_up_selection_authorised'):
        if authority[key] is not False:
            raise ValueError(f'Weekday confirmation cannot authorise {key}')
    for key in ('saturday_trips_per_day', 'local_patronal_or_other_extra_exclusions',
                'decision_budget_km', 'uncertainty_band_min'):
        if authority[key] is not None:
            raise ValueError(f'Undeclared input cannot be filled: {key}')
    if authority['saturday_policy'] != 'TO_BE_ASSESSED_SEPARATELY_NOT_CANCELLED_OR_SELECTED':
        raise ValueError('Saturday cannot be silently cancelled or selected')


def materialise_dates(authority):
    holiday_names = {date.fromisoformat(r['date']): r['name']
                     for r in authority['national_holiday_dates_2027']}
    days = []
    current = date(authority['service_year'], 1, 1)
    while current.year == authority['service_year']:
        weekday = current.isoweekday()
        holiday = holiday_names.get(current)
        if holiday or weekday == 7:
            state, weekday_trips, complete_day_trips = 'OUTSIDE_DECLARED_WEEKDAY_BASE', 0, None
        elif weekday == 6:
            state, weekday_trips, complete_day_trips = 'SATURDAY_PENDING_SEPARATE_ASSESSMENT', 0, None
        else:
            state = 'DECLARED_WEEKDAY_BASE_BEFORE_LOCAL_EXCEPTION_VALIDATION'
            weekday_trips = complete_day_trips = authority['full_trips_per_weekday']
        days.append(dict(date=current.isoformat(), weekday_iso_number=weekday,
                         national_holiday_name=holiday, state=state,
                         weekday_component_complete_trips=weekday_trips,
                         complete_line_day_trip_count=complete_day_trips))
        current += timedelta(days=1)
    return days


def build():
    authority = json.loads(AUTHORITY.read_text(encoding='utf-8'))
    sources = {p.name: json.loads(p.read_text(encoding='utf-8'))
               for p in (TIMETABLE_AUTHORITY, PDB, HANDOFF)}
    validate_authority(authority, sources)
    handoff = sources[HANDOFF.name]
    if canonical_sha256(handoff) != canonical_sha256(handoff_build()):
        raise ValueError('Current timetable no longer reproduces its authorised sources')
    reference, _ = validate_calendar_evidence(sources[PDB.name], handoff)
    days = materialise_dates(authority)
    weekday_days = [d for d in days if d['weekday_component_complete_trips']]
    weekday_holidays = [d for d in days if d['weekday_iso_number'] <= 5 and d['national_holiday_name']]
    trips = sum(d['weekday_component_complete_trips'] for d in days)
    km_per_trip = handoff['complete_path_distance_m']/1000
    commercial_km = trips*km_per_trip
    margin = reference-commercial_km
    nonholiday_saturdays = [d for d in days if d['state'] == 'SATURDAY_PENDING_SEPARATE_ASSESSMENT']
    if len(days) != 365 or len(weekday_days) != 254 or len(weekday_holidays) != 7 or len(nonholiday_saturdays) != 50:
        raise ValueError('Reviewed 2027 date partition differs')
    return dict(
        contract='RT031_CALLER_CONFIRMED_2027_WEEKDAY_BASE_MATERIALISATION_V3',
        recorded_on='2026-10-02', service_year=2027,
        authority_source=str(AUTHORITY.relative_to(ROOT)),
        authority_canonical_sha256=canonical_sha256(authority),
        source_canonical_sha256={p: canonical_sha256(v) for p, v in sources.items()},
        full_trips_per_weekday=16, same_complete_route_for_each_trip=True,
        national_holiday_base_materialised=True,
        weekday_calendar_declared_for_design=True,
        weekday_base_day_count_before_local_exceptions=len(weekday_days),
        weekdays_before_national_holiday_exclusions=len(weekday_days)+len(weekday_holidays),
        excluded_weekday_national_holiday_dates=[d['date'] for d in weekday_holidays],
        weekday_base_complete_trip_count=trips,
        complete_trip_commercial_km=km_per_trip,
        weekday_base_commercial_km=commercial_km,
        reference_published_pdb_annual_km=reference,
        weekday_base_delta_vs_reference_km=commercial_km-reference,
        weekday_base_delta_vs_reference_percent=100*(commercial_km/reference-1),
        arithmetic_margin_vs_reference_km=margin,
        whole_extra_complete_trips_within_reference=math.floor(margin/km_per_trip),
        extra_trip_capacity_is_service_recommendation=False,
        monthly_weekday_base_day_counts=dict(sorted(Counter(d['date'][:7] for d in weekday_days).items())),
        date_ledger=days,
        saturday_nonholiday_date_count=len(nonholiday_saturdays),
        saturday_service_policy_adopted=False, saturday_trip_count=None,
        saturday_sensitivity_count_only=[dict(
            hypothetical_full_trips_per_nonholiday_saturday=n,
            nonholiday_saturdays=len(nonholiday_saturdays),
            additional_complete_trips=n*len(nonholiday_saturdays),
            additional_commercial_km=n*len(nonholiday_saturdays)*km_per_trip,
            weekday_base_plus_saturday_commercial_km=commercial_km+n*len(nonholiday_saturdays)*km_per_trip,
            delta_vs_reference_percent=100*((commercial_km+n*len(nonholiday_saturdays)*km_per_trip)/reference-1),
            departure_times_selected=False, timetable_feasibility_certified=False,
            h30_peak_promise_inferable=False, policy_adopted=False,
        ) for n in (2, 4, 6, 8, 16)],
        complete_annual_operating_calendar_adopted=False,
        complete_line_annual_commercial_km=None,
        local_patronal_or_other_extra_exclusions=None,
        local_exception_policy_certified=False,
        actual_d184_d185_annual_calendar_certified=False,
        reference_funding_transfer_certified=False,
        annual_noncommercial_km=None, full_annual_operating_cost=None,
        rail_reference_service_date='2026-10-01', rail_connections_for_2027_certified=False,
        observed_runtime_for_2027_certified=False,
        physical_boarding_authorised=False, public_operating_timetable_authorised=False,
        funding_secured=False, network_selected=False,
        primary_selection_authorised=False, runner_up_selection_authorised=False,
        decision_budget_km=None, uncertainty_band_min=None,
        missed_connection_probability=None, demand_weighted_gjt_improvement_min=None,
        remaining_external_inputs=[
            'Local patronal/exception treatment for the complete five-municipality route; no extra closures invented.',
            '2027 dated rail timetable and transfers: October 2026 connection evidence cannot be certified for another year.',
            'Saturday policy and exact full-trip timetable, separately caller-declared and verified.',
            'Bus-accessible road/stops, passenger continuity, measured times, available fleet, driver/depot/deadhead plan and full costs/funding.',
        ],
        semantics='Dated 2027 weekday design component, with national holidays known as of 2026-10-02. No school-vacation cuts, inferred patronal exclusions or Saturday policy. Weekday production is not the complete-line annual total or funding proof. Saturday rows are arithmetic only, not adopted or event-checked timetables.',
    )


def render_brief(r):
    def fmt(v, decimals=3):
        return f'{v:,.{decimals}f}'.replace(',', '_').replace('.', ',').replace('_', '.')
    rows = ['# Linea 8 - base feriale datata 2027', '',
            'Scelta del committente del 2 ottobre 2026: **16 giri completi dal lunedì al venerdì, esclusi festivi; sabato da valutare separatamente; anno 2027**. Stessa geometria, stessi 27 siti, stessi eventi e stesso orario di progetto. Non è un’autorizzazione all’esercizio.', '',
            f'**261 lunedì-venerdì meno 7 festività nazionali in quei giorni = {r["weekday_base_day_count_before_local_exceptions"]} giornate della base. {r["weekday_base_complete_trip_count"]} giri × {fmt(r["complete_trip_commercial_km"],6)} km = {fmt(r["weekday_base_commercial_km"])} km commerciali.** Rispetto al riferimento PdB pubblicato 111.419: {fmt(r["weekday_base_delta_vs_reference_km"])} km ({fmt(r["weekday_base_delta_vs_reference_percent"],2)}%). Nessuna corsa dei giorni feriali della base è stata eliminata.', '',
            '## Date e festività', '',
            'Le sette esclusioni nei giorni lunedì-venerdì sono: 1 e 6 gennaio, 29 marzo (Pasquetta), 2 giugno, 4 ottobre, 1 novembre, 8 dicembre. Le altre festività cadono nel weekend: non si sottraggono una seconda volta. Nessun ponte, vacanza scolastica o riduzione di agosto è stato aggiunto.', '',
            'Il 4 ottobre è festivo nazionale dal 2026: [Legge 151/2025](https://www.gazzettaufficiale.it/eli/id/2025/10/10/25G00153/sg). Elenco generale e aggiornamenti, ripristino del 2 giugno e corroborazione della Pasquetta 2027 sono nel registro delle fonti della [conferma di calendario](../config/rt031_weekday_calendar_2027_authority_v3.json). La vecchia pagina del Cerimoniale non va copiata senza l’aggiornamento legislativo del 2025.', '',
            '| Mese 2027 | Giornate della base |', '|---|---:|']
    for month, count in r['monthly_weekday_base_day_counts'].items():
        rows.append(f'| {month} | {count} |')
    rows += ['', 'Il [registro datato](../outputs/phase2/rt031_line8_local_shortcuts_v3/caller_confirmed_weekday_calendar_2027.json) elenca tutti i 365 giorni. I patroni locali e le eccezioni del servizio intercomunale richiedono verifica: non sono stati inventati giorni di chiusura. I 254 giorni sono la base dopo i festivi nazionali, prima di eventuali eccezioni confermate.', '',
             '## Sabato: separato, non cancellato e non scelto', '',
             f'Nel 2027 ci sono {r["saturday_nonholiday_date_count"]} sabati non festivi nazionali. Il margine aritmetico della sola base sul riferimento è {fmt(r["arithmetic_margin_vs_reference_km"])} km, equivalente al massimo a {r["whole_extra_complete_trips_within_reference"]} giri completi aggiuntivi in tutto l’anno. Non è una proposta di servizio.', '',
             '| Giri ipotetici per ciascun sabato non festivo | Km sabato aggiuntivi | Km base + sabato | Scarto sul riferimento |', '|---:|---:|---:|---:|']
    for s in r['saturday_sensitivity_count_only']:
        rows.append(f'| {s["hypothetical_full_trips_per_nonholiday_saturday"]} | {fmt(s["additional_commercial_km"])} | {fmt(s["weekday_base_plus_saturday_commercial_km"])} | {fmt(s["delta_vs_reference_percent"],2)}% |')
    rows += ['', 'Sono sole quantità chilometriche: nessun orario del sabato, gruppo H30 o livello utile di servizio è certificato da queste righe. Non si propongono corse parziali né ali separate. Il totale annuo della linea resta `null` finché non si decide il sabato e si verifica il calendario completo.', '',
             '## Che cosa chiude questa scelta, e che cosa no', '',
             '- Chiude anno e struttura della base lunedì-venerdì: il confronto corrente non è più 260 giorni idealizzati o 303 giorni di pianificazione applicati automaticamente.',
             '- I 110.229,936 km sono produzione commerciale della base: non costo completo, km a vuoto, disponibilità o risorse D184/D185 già trasferibili.',
             '- Le coincidenze già verificate riguardano il 1 ottobre 2026: **non certificano i treni 2027**. Le fasi dell’orario restano progetto da rivalidare sui treni pubblicati per il nuovo anno, senza modificarle tacitamente.',
             '- Restano verifica fisica di strade/fermate, tempi e continuità passeggeri, flotta/turni/deposito, costo completo e finanziamento.', '',
             '[Proposta unica consolidata](RT031_LINEA8_PROPOSTA_UNICA_CONSOLIDATA_2026_10_01.md) · [Blocchi dei mezzi](RT031_LINEA8_MEZZI_E_CALENDARIO_2026_10_01.md) · [Fonti e limiti dei confronti precedenti](RT031_LINEA8_CALENDARIO_E_RISORSE_2026_10_01.md)', '',
             '`weekday_calendar_declared_for_design=true`; `complete_annual_operating_calendar_adopted=false`; `rail_connections_for_2027_certified=false`; PRIMARY/RUNNER-UP non autorizzati; `decision_budget_km=null`; `uncertainty_band_min=null`.', '']
    return '\n'.join(rows)


if __name__ == '__main__':
    result = build()
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)+'\n', encoding='utf-8')
    BRIEF.write_text(render_brief(result), encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('service_year', 'weekday_base_day_count_before_local_exceptions',
                                           'weekday_base_commercial_km', 'arithmetic_margin_vs_reference_km',
                                           'saturday_nonholiday_date_count')}))
