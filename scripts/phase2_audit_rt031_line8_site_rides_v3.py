"""Inspect nominal within-trip journeys without certifying passenger service."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'outputs/phase2/rt031_line8_local_shortcuts_v3'
SOURCE = BASE / 'shorter_span_1940_witness.json'
DOC = ROOT / 'docs/RT031_LINEA8_TEMPI_PER_SITO_V3.md'
FLAGS = ('network_selected', 'primary_selection_authorised', 'runner_up_selection_authorised')


def minute(value):
    h, m, s = map(int, value.split(':'))
    return h * 60 + m + s / 60


def audit(ledger):
    if ledger['contract'] != 'RT031_LINE8_JOINT_EVENING_LABELLED_WITNESS_LEDGER_V3' or any(ledger[k] for k in FLAGS):
        raise ValueError('expected unselected comparison ledger')
    trips = {t['trip_id']: t for t in ledger['trips']}
    sites = {s['stop_place_id']: s for s in ledger['nonhub_sites']}
    if len(trips) != len(ledger['trips']) or len(sites) != len(ledger['nonhub_sites']):
        raise ValueError('duplicate trip or site identity')
    groups = defaultdict(list)
    seen = set()
    for event in ledger['nominal_stop_occurrence_events']:
        tid, sid = event['trip_id'], event['stop_place_id']
        if tid not in trips or sid not in sites:
            raise ValueError('unknown trip or site')
        trip = trips[tid]
        arrival, departure = minute(event['arrival_nominal']), minute(event['departure_nominal'])
        key = (tid, event['occurrence_id'])
        if key in seen or event['pattern'] != trip['pattern']:
            raise ValueError('duplicate occurrence or pattern mismatch')
        seen.add(key)
        # Display clocks were rounded to seconds by the upstream exporter.
        if not trip['fs_departure_min'] - 1/60 <= arrival <= departure <= trip['fs_return_nominal_min'] + 1/60:
            raise ValueError('event outside ordered trip')
        groups[tid, sid].append(event)
    rows = []
    for sid, site in sorted(sites.items()):
        journeys = []
        for (tid, group_sid), events in sorted(groups.items()):
            if group_sid != sid:
                continue
            trip = trips[tid]
            early = min(events, key=lambda e: minute(e['arrival_nominal']))
            late = max(events, key=lambda e: minute(e['departure_nominal']))
            journeys.append({
                'trip_id': tid, 'pattern': trip['pattern'],
                'from_fs_alighting_occurrence_id': early['occurrence_id'],
                'to_fs_boarding_occurrence_id': late['occurrence_id'],
                'from_fs_ride_min': round(minute(early['arrival_nominal']) - trip['fs_departure_min'], 6),
                'to_fs_ride_min': round(trip['fs_return_nominal_min'] - minute(late['departure_nominal']), 6),
                'to_fs_boarding_clock': late['departure_nominal'],
                'distinct_occurrences_required': early['occurrence_id'] != late['occurrence_id'],
                'boarding_authorised': False, 'passenger_continuity_certified': False,
            })
        if not journeys:
            raise ValueError('site has no service event')
        rows.append({**site, 'boarding_authorised': False,
                     'from_fs_ride_min_range': [min(j['from_fs_ride_min'] for j in journeys), max(j['from_fs_ride_min'] for j in journeys)],
                     'to_fs_ride_min_range': [min(j['to_fs_ride_min'] for j in journeys), max(j['to_fs_ride_min'] for j in journeys)],
                     'journeys': journeys})
    return {'contract': 'RT031_LINE8_NOMINAL_SITE_RIDES_AUDIT_V3',
            'status': 'CONDITIONAL_WITHIN_TRIP_EVENTS_NOT_SERVICE_CERTIFICATION',
            'source': SOURCE.relative_to(ROOT).as_posix(),
            'scope': 'H90 19:40 labelled witness only; do not extrapolate other witnesses',
            'semantics': 'For each trip and site: earliest alighting from FS and latest boarding to FS. Different occurrences remain separate. No inter-trip or vehicle-block passenger continuity inferred. Nominal on-board minutes exclude waiting, walking and rail transfer; input event clocks rounded to one second. No ride-time acceptance threshold or demand weighting.',
            'sites': rows, 'site_count_including_fs': len(rows) + 1,
            'actual_timetable_certified': False, **{k: False for k in FLAGS},
            'decision_budget_km': None, 'uncertainty_band_min': None}


def report(result):
    lines = ['# Linea 8 — tempi nominali per sito, nei due versi', '',
             'Audit del solo testimone **H90, ultima partenza FS 19:40**, non selezionato. '
             'Non è una nuova proposta e non approva H90. Tutti i 27 siti non-hub sono elencati; FS è il ventottesimo.', '',
             'Minuti sul bus nel modello nominale: marcia +10% e soste di 30 secondi. '
             'Sono esclusi cammino, attesa e cambio treno. Nessuna soglia di accettabilità viene decisa qui. '
             'Le cifre sono arrotondate, non misure sul campo.', '',
             '| Sito | Da FS, min | Verso FS, min | Passaggi distinti per viaggio breve nei due versi |',
             '|---|---:|---:|---|']
    for row in result['sites']:
        def span(key):
            low, high = row[key]
            return f'{low:.1f}' if abs(high-low) < .02 else f'{low:.1f}–{high:.1f}'
        distinct = any(j['distinct_occurrences_required'] for j in row['journeys'])
        lines.append(f"| {row['name']} | {span('from_fs_ride_min_range')} | {span('to_fs_ride_min_range')} | {'Sì' if distinct else 'No'} |")
    lines += ['', '## Come leggere il risultato', '',
              'Il giro resta asimmetrico: risolvere i viaggi lunghi di Olgiate sud e San Zeno non rende brevi entrambi i versi in tutte le altre località. '
              'Una percentuale di accesso pedonale invariata non misura questi tempi. Non viene calcolata alcuna media pesata per passeggeri.', '',
              'Per i siti ripetuti, il passaggio iniziale serve per scendere da FS; quello finale per salire verso FS. '
              'Il JSON conserva entrambi gli identificativi di occorrenza e la corsa: non sono una sola promessa di servizio. '
              'Paline, lato strada e continuità passeggeri non sono autorizzati. Non vengono concatenati viaggi appartenenti a corse diverse.', '',
              '[Tracciato del testimone](../outputs/phase2/rt031_line8_local_shortcuts_v3/shorter_span_1940_witness.png) · '
              '[Audit macchina e occorrenze per corsa](../outputs/phase2/rt031_line8_local_shortcuts_v3/site_rides_audit.json) · '
              '[Confronto completo H60/H90/H120 e km](RT031_LINEA8_FASCIA_PIU_CORTA_E_BUDGET_V3.md)', '',
              'Il riferimento richiesto resta H30 in punta/H60 fuori punta. H90 e H120 sono rilassamenti non approvati; '
              'non si può dichiarare conclusa la proposta scegliendo implicitamente uno dei due.']
    return '\n'.join(lines) + '\n'


def build():
    raw = SOURCE.read_bytes().replace(b'\r\n', b'\n')
    result = audit(json.loads(raw))
    result['source_sha256_normalized_newlines'] = hashlib.sha256(raw).hexdigest()
    return result


if __name__ == '__main__':
    result = build()
    (BASE / 'site_rides_audit.json').write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    DOC.write_text(report(result), encoding='utf-8')
    print(json.dumps({'sites_including_fs': result['site_count_including_fs'], 'selected': False}))
