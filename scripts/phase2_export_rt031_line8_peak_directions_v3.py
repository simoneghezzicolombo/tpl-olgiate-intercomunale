"""Explain all direction comparisons, preserving losses and source geometry."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from scripts.phase2_compare_rt031_line8_peak_directions_v3 import OUTPUT, POLICIES, BASE, FLAGS
from scripts.phase2_export_rt031_line8_joint_evening_v3 import GEOMETRY_SHA256

DOC = Path(__file__).resolve().parents[1] / 'docs/RT031_LINEA8_DIREZIONI_NELLE_PUNTE_V3.md'


def report(result):
    by_key = {(c['direction_policy_id'], c['offpeak_wait_comparison_min']): c for c in result['cases']}
    if not result['all_cases_proven_optimal'] or len(by_key) != 32 or any(result[k] for k in FLAGS):
        raise ValueError('report requires complete finite comparison')
    lines = ['# Linea 8 — cambiare direzione nelle punte: benefici e perdite', '',
             '**32 confronti completati:** 16 combinazioni mattina/sera × H60 oppure H90 fuori punta. '
             'Tutti ottimi nei rispettivi domini finiti. Nessuna direzione è adottata.', '',
             '## Risultato pratico', '',
             'Invertire il giro non rende il collegamento veloce per tutti: sposta il viaggio lungo da alcune località ad altre. '
             'Ad esempio, con ovest A al mattino Scarpone→FS scende da circa 32,4 a 8,4 minuti, '
             'ma Via della Salute→FS sale da 9,7 a 31,0. Con est B, Beverate-Cariplo→FS scende da 30,8 a 8,6, '
             'ma Calco-Via Virgilio→FS sale da 7,7 a 32,9.', '',
             '**Questi cambi di direzione non risolvono il riferimento di 111.419 km.** '
             'Il minimo fra i confronti H60 è 143.929 km/anno; quello H90 è 122.340. '
             'Sono gli stessi minimi già trovati senza imporre direzioni ai treni: aggiungere un vincolo non può migliorare quel minimo. '
             'Non è una nuova ricerca di scorciatoie stradali, né una prova di impossibilità su altre reti.', '',
             '## Tutti i confronti, senza scegliere un vincitore', '',
             'Ogni coppia indica **ovest, est**: `AB` = ovest A + est B. La prima coppia riguarda '
             'le corse legate ai cinque treni AM; la seconda quelle legate ai sei arrivi PM, compreso 19:32. '
             'Le altre corse possono usare entrambi i versi per chiudere le frequenze. '
             'Non è quindi necessariamente un cambio di senso unico a una certa ora.', '',
             '| Direzioni AM → PM | Km/anno H60 nel resto | Km/anno H90 nel resto, non approvato |',
             '|---|---:|---:|']
    for pid in POLICIES:
        values = [f"{by_key[pid, h]['annual_service_km']:,.0f}".replace(',', '.') for h in (60, 90)]
        lines.append(f"| {pid.replace('_', ' → ')} | {values[0]} | {values[1]} |")
    lines += ['', 'Il confronto intuitivo **AB → BA** (versi invertiti al mattino, B/A nel resto ferroviario) '
              'richiede 145.166 km con H60 oppure 130.774 con H90: non è una modifica gratuita delle ore di partenza. '
              'Cambiano percorsi e corse necessarie per mantenere le finestre comuni e le coincidenze.', '',
              'Tutti i testimoni usano quattro mezzi nominali e arrivano a sei nella griglia di stress. '
              'Questo **non dimostra che sei siano necessari**: il precedente testimone BA→BA/H90, agli stessi km, '
              'è stato riverificato sotto i nuovi vincoli e resta a cinque nello stress. '
              'Il risolutore minimizza km, non sceglie fra orari a pari km in base alla riserva.', '',
              '## Tempi per tutti i siti, entrambi i versi stradali', '',
              'Minuti nominali sul bus, senza cammino, attesa o cambio treno. '
              'Per ogni ala A e B sono **due cammini stradali del grafo**, non un’inversione geometrica presunta. '
              'Verso FS è la dimensione mostrata per la punta AM; da FS per la PM. '
              'La stessa direzione deve valere per tutti i siti sulla corsa: non si possono combinare i minimi di righe diverse.', '',
              '| Ala / sito | Verso FS con A | Verso FS con B | Da FS con A | Da FS con B |',
              '|---|---:|---:|---:|---:|']
    profiles = result['nominal_ride_profiles']
    for wing in ('west', 'east'):
        a = {r['stop_place_id']: r for r in profiles[wing + '_A']['sites']}
        b = {r['stop_place_id']: r for r in profiles[wing + '_B']['sites']}
        if set(a) != set(b):
            raise ValueError('site footprint differs between directions')
        for sid, row in a.items():
            values = [a[sid]['to_fs_ride_min'], b[sid]['to_fs_ride_min'], a[sid]['from_fs_ride_min'], b[sid]['from_fs_ride_min']]
            lines.append(f"| {'Ovest' if wing == 'west' else 'Est'} / {row['name']} | " + ' | '.join(f'{v:.1f}' for v in values) + ' |')
    lines += ['', 'Olgiate sud e San Zeno mantengono i passaggi brevi distinti per scendere da FS e salire verso FS. '
              'I siti sono sempre 28 compresa FS; non equivalgono a 28 paline autorizzate. '
              'Nessuna continuità passeggeri viene inferita dal riuso dello stesso mezzo.', '',
              '## Assunzioni e limiti mantenuti visibili', '',
              '- Finestre comuni H30: **06:50–08:50 e 16:35–18:35**, fissate solo per confrontare le direzioni a parità di servizio; non approvate.',
              '- Disponibilità passeggeri confrontata: **06:30–19:40**. Il treno 20:32 del riferimento più lungo non è servito; primo treno AM vincolato 07:26, non 06:56.',
              '- Treni congelati al **3 settembre 2026**, non orario corrente. Cinque obiettivi AM e sei PM, stessi margini del confronto precedente.',
              '- Nove scenari marcia/sosta per frequenze e coincidenze; 27 includendo recuperi per i mezzi. Non probabilità di affidabilità.',
              '- **260 giorni ipotizzati**; km di servizio soltanto, senza deposito e riposizionamenti. H60 resta la richiesta, H90 è un rilassamento non adottato.',
              '- Tempi, percorribilità autobus, restrizioni dipendenti dalla storia del percorso, paline, turni e budget totale restano da validare. Nessuna soglia normativa sui tempi di viaggio.', '',
              '## Tracciati e dati riproducibili', '',
              '![Quattro tracciati confrontati, non un nuovo orario adottato](../outputs/phase2/rt031_line8_local_shortcuts_v3/peak_direction_comparison.png)', '',
              '[GeoJSON dei quattro cammini effettivamente usati nei testimoni](../outputs/phase2/rt031_line8_local_shortcuts_v3/peak_direction_comparison.geojson) · '
              '[32 orari, vincoli ferroviari e profili di viaggio macchina](../outputs/phase2/rt031_line8_local_shortcuts_v3/peak_direction_comparison.json)', '',
              '```powershell', "$env:PYTHONPATH='.;src'",
              'python -m scripts.phase2_compare_rt031_line8_peak_directions_v3 --time_limit 15',
              'python -m scripts.phase2_export_rt031_line8_peak_directions_v3',
              'python -m unittest discover -s tests -p test_phase2_rt031_line8_peak_directions_v3.py', '```', '',
              '**Conclusione:** nessuna delle combinazioni può essere presentata come soluzione che migliora tutti i collegamenti senza rinunce. '
              'La frequenza e il budget non sono gli unici nodi rimasti: occorre anche rendere espliciti i tempi accettabili per località. '
              'Non viene scelto un vincitore tramite somme, pesi o conteggi dei siti favoriti.']
    return '\n'.join(lines) + '\n'


def geometry(result):
    if any(result[k] for k in FLAGS):
        raise ValueError('selected evidence cannot be exported as an unselected comparison')
    raw = (BASE / 'local_counterflow.geojson').read_bytes().replace(b'\r\n', b'\n')
    if hashlib.sha256(raw).hexdigest() != GEOMETRY_SHA256:
        raise ValueError('frozen road geometry drift')
    source = json.loads(raw)
    features = []
    for feature in source['features']:
        if feature['geometry']['type'] == 'Point':
            features.append(copy.deepcopy(feature))
        elif feature['geometry']['type'] == 'LineString' and feature['properties'].get('case') == 'both':
            item = copy.deepcopy(feature)
            pattern = item['properties']['pattern']
            if abs(item['properties']['distance_m'] / 1000 - result['nominal_ride_profiles'][pattern]['distance_km']) > 1e-9:
                raise ValueError('shape distance differs from used pattern')
            item['properties']['comparison_witnesses_using_pattern'] = [f"{c['direction_policy_id']}_H{c['offpeak_wait_comparison_min']}"
                for c in result['cases'] if c['witness_found'] and any(t['loop'] == pattern for t in c['trips'])]
            features.append(item)
    if len(features) != 32:
        raise ValueError('geometry footprint drift')
    return {'type': 'FeatureCollection', 'features': features, 'properties': {
        'semantics': 'Four alternative road patterns used by the enumerated comparison witnesses, not a single selected service or approved bus route.',
        'source_geometry_sha256_normalized_newlines': GEOMETRY_SHA256,
        'network_selected': False, 'primary_selection_authorised': False, 'runner_up_selection_authorised': False}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--graph_dir', type=Path)
    args = parser.parse_args()
    result = json.loads(OUTPUT.read_text(encoding='utf-8'))
    DOC.write_text(report(result), encoding='utf-8')
    (BASE / 'peak_direction_comparison.geojson').write_text(json.dumps(geometry(result), ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
    if args.graph_dir:
        from scripts.phase2_render_rt031_line8_counterflow_v3 import render
        render(args.graph_dir, BASE / 'peak_direction_comparison.png',
               patterns=('west_A', 'west_B', 'east_A', 'east_B'), show_baseline=False,
               pattern_labels={'west_A': 'Ovest A', 'west_B': 'Ovest B', 'east_A': 'Est A', 'east_B': 'Est B'},
               title='Linea 8 — quattro tracciati per 32 confronti di direzione\nStessi 28 siti; nessun orario o verso selezionato')
