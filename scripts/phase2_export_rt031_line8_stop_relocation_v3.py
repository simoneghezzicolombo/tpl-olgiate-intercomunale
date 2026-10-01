"""Publish the complete non-weighted screen and a labelled, non-selected map."""
import argparse
from fractions import Fraction
import json
from pathlib import Path

from scripts.phase2_probe_rt031_line8_stop_relocation_v3 import BASE, OUTPUT as SCREEN, RETENTION
from scripts.phase2_check_rt031_line8_relocation_timetable_v3 import OUTPUT as TIMETABLE, sha, materialize
from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import load_sources, FLAGS
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import family_inputs

DOC = Path(__file__).resolve().parents[1] / 'docs/RT031_LINEA8_SPOSTAMENTO_FERMATE_E_SCORCIATOIE_V3.md'


def frontier(screen, retention):
    """Preliminary road/access/ride Pareto only; no operating dominance claim."""
    cases = screen['cases']
    base = {p: l['distance_m'] for vs in retention['variants'].values() for p, l in vs[0]['loops'].items()}
    journey_keys = sorted({(r['pattern'], r['site_id'], direction) for c in cases
                           for r in c['retained_site_ride_changes_nominal'] for direction in ('from_fs', 'to_fs')})
    dims, losses = {}, {}
    for c in cases:
        rides = {(r['pattern'], r['site_id'], d): r[d + '_delta_min'] for r in c['retained_site_ride_changes_nominal'] for d in ('from_fs', 'to_fs')}
        losses[c['case_id']] = set(c['lost_original_site_ids'])
        dims[c['case_id']] = (
            tuple(c['pattern_distance_m'].get(p, base[p]) for p in sorted(base))
            + tuple(-Fraction(c['potential_access_fraction'][m][t]) for m in screen['municipality_names'] for t in ('5', '8', '10'))
            + tuple(Fraction(c['previously_covered_population_fraction_lost'][m][t]) for m in screen['municipality_names'] for t in ('5', '8', '10'))
            + tuple(float('inf') if sid in losses[c['case_id']] else rides.get((p, sid, d), 0.) for p, sid, d in journey_keys))
    ids = []
    for c in cases:
        cid = c['case_id']
        dominated = False
        for other in cases:
            oid = other['case_id']
            if oid == cid or not losses[oid] <= losses[cid]:
                continue
            if all(a <= b for a, b in zip(dims[oid], dims[cid])) and (losses[oid] < losses[cid] or any(a < b for a, b in zip(dims[oid], dims[cid]))):
                dominated = True
                break
        if not dominated:
            ids.append(cid)
    return {'contract': 'RT031_LINE8_RELOCATION_PRELIMINARY_FRONTIER_V3',
            'source_sha256_normalized_screen': sha(SCREEN), 'case_count': len(cases),
            'frontier_case_ids': ids,
            'semantics': 'Minimise each pattern distance, maximise each of 15 municipal access metrics, minimise each of 15 gross covered-population losses and each original site/pattern/direction nominal ride change; retain original identity set by inclusion. Missing original site ride is unavailable, not zero. New-site rides, approved boarding, timetable, fleet, and operating costs are NOT dimensions certified here. No weights; all cases remain in the source, and this preliminary frontier must not prune a later operating search.',
            **{k: False for k in FLAGS}, 'decision_budget_km': None, 'uncertainty_band_min': None}


def report(screen, timetable, front):
    if any(screen[k] or timetable[k] for k in FLAGS) or not timetable.get('all_diagnostic_cases_proven_optimal'):
        raise ValueError('incomplete or selected comparison')
    if timetable['source_sha256_normalized_newlines']['screen'] != sha(SCREEN):
        raise ValueError('timetable screen provenance drift')
    cases = screen['cases']
    h60 = sorted({round(c['annual_service_km'], 3) for c in timetable['cases'] if c['offpeak_wait_comparison_min'] == 60})
    h90 = sorted({round(c['annual_service_km'], 3) for c in timetable['cases'] if c['offpeak_wait_comparison_min'] == 90})
    if len(h60) != 1 or len(h90) != 1:
        raise ValueError('diagnostic timetable results changed; update explanation')
    selected_ids = timetable['diagnostic_case_ids']
    selected = [c for c in cases if c['case_id'] in selected_ids]
    if len(selected) != 3 or {c['variant_id'] for c in selected} != {'west_09'}:
        raise ValueError('illustrative no-loss geometry changed')
    lines = ['# Linea 8 — fermate spostate sulle scorciatoie: primo confronto', '',
             f"**{screen['candidate_node_count']} punti stradali nuovi, {screen['case_count']} casi strada/fermate/copertura.** "
             'Sono stati analizzati tutti i nodi condivisi dai due versi sulle deviazioni ereditate, esclusi quelli già serviti da un sito d’inventario. '
             'Il primo conteggio era 282: un nodo era già servito e non è stato presentato come nuova fermata.', '',
             '## Esito verificato', '',
             '**Una piccola correzione senza perdita dei nuclei già coperti esiste, ma non risolve il budget né i viaggi lunghi.** '
             'Tre posizioni alternative presso Rovagnate–Vinicola Ghezzi permettono di sostituire il sito attuale con uno nuovo sulla scorciatoia. '
             'Non sono tre fermate da aggiungere: sono tre alternative non autorizzate.', '',
             '- Restano 28 identità di sito compresa FS, ma una è sostituita: `FROZEN::300879` non è più servita.',
             '- Nessun nucleo già entro 5, 8 o 10 minuti perde quella copertura nel modello pedonale; tutte le 15 metriche dei cinque comuni sono non peggiori.',
             '- Risparmio stradale: **33,19 metri per corsa ovest**, circa **66,38 metri sommando un giro A e un giro B**.',
             '- I tempi nominali sul bus dei siti conservati possono aumentare fino a circa **3 secondi**: meno metri non garantiscono meno tempo nel modello stradale.', '',
             '## Orario ricalcolato, non moltiplicazione dei metri a priori', '',
             '| Confronto fino alle 19:40 | Prima | Dopo lo spostamento | Risparmio annuo |',
             '|---|---:|---:|---:|',
             f"| H30 in punta / H60 nel resto | 143.929 km | {h60[0]:,.0f} km | {143929.083516-h60[0]:.0f} km |".replace(',', '.'),
             f"| H30 in punta / H90 nel resto, non approvato | 122.340 km | {h90[0]:,.0f} km | {122339.720989-h90[0]:.0f} km |".replace(',', '.'), '',
             'Tutte e tre le posizioni sono state ricalcolate in entrambi i confronti: sei ottimi nel dominio finito. '
             'Il riferimento resta **111.419 km**; il caso H60 rimane circa 32.337 km sopra, prima di deposito e riposizionamenti. '
             'Quattro mezzi nominali; nei testimoni fino a sei nella griglia di stress, non una prova di fabbisogno minimo di riserva.', '',
             'Sono mantenuti calendario ipotetico a 260 giorni, punte comuni 06:50–08:50 e 16:35–18:35, '
             'treni congelati al 3 settembre 2026 e lo stesso limite di attesa AM del riferimento. '
             'L’ultimo obiettivo PM è 19:32; il precedente 20:32 resta escluso da questa fascia. '
             'H90, le fasi e la fascia non sono approvati automaticamente. Non è un orario pubblico certificato.', '',
             '## Gli altri casi non sono stati scartati imponendo perdita zero', '',
             'Il controllo senza perdite è un gruppo diagnostico, **non un nuovo vincolo politico**. '
             f"Tutti i {len(cases)} casi sono conservati. La frontiera preliminare senza pesi comprende {len(front['frontier_case_ids'])} casi; "
             'considera separatamente metri per verso, copertura, residenti precedentemente coperti che perdono accesso, identità mantenute e tempi di viaggio. '
             'Non è una frontiera di esercizio: i casi con perdite territoriali non hanno ancora un nuovo orario validato.', '',
             'Alcuni limiti misurati delle scorciatoie più grandi:', '',
             '| Sito da sostituire / deviazione | Risparmio sommando i due versi | Comune esaminato | Perdita minima di popolazione prima coperta a 10 min, punti percentuali |',
             '|---|---:|---|---:|']
    examples = [('east_01', 'Calco–Via Virgilio', '97012'), ('east_04', 'Arlate–Cantina Pirovano', '97012'),
                ('west_08', 'Hoè', '97074'), ('east_08', 'Beverate–Quattro Strade', '97010')]
    for vid, name, code in examples:
        group = [c for c in cases if c['variant_id'] == vid and c['new_road_node'] is not None]
        best_loss = min(100 * float(Fraction(c['previously_covered_population_fraction_lost'][code]['10'])) for c in group)
        saved = group[0]['direction_pair_m_saved'] / 1000
        lines.append(f"| {name} | {saved:.3f} km | {screen['municipality_names'][code]} | {best_loss:.4f} pp |")
    lines += ['', 'La colonna finale è un **limite inferiore della perdita** tra tutte le posizioni provate per quella deviazione, '
              'non la scelta di un candidato e non una soglia accettabile. Non comprende le ulteriori perdite possibili a 5 e 8 minuti o i cambi di tempo sul bus. '
              'Per Beverate il saldo comunale a 10 minuti può perfino migliorare, ma alcuni nuclei prima coperti restano esclusi: saldo netto e persone perse non sono la stessa cosa.', '',
              '## Mappa e limiti', '',
              '![Rovagnate: tre posizioni alternative sullo stesso percorso condizionale](../outputs/phase2/rt031_line8_local_shortcuts_v3/stop_relocation_diagnostic.png)', '',
              'La mappa illustra le tre alternative senza perdita, non seleziona una proposta. '
              'Olgiate sud e San Zeno rimangono esigenze distinte e presenti. '
              'Le coordinate sono nodi del grafo, **non punti di salita sicuri o autorizzati**. '
              'I collegamenti pedonali usano lo stesso modello e gli stessi connettori del riferimento; non equivalgono a sopralluoghi.', '',
              'Il dominio resta circoscritto: una sola ala modificata alla volta, omissione di uno o due siti consecutivi dall’ordine richiesto, '
              'al massimo una fermata alternativa su ciascuna scorciatoia già generata. '
              'Non sono state cercate tutte le combinazioni di modifiche, tutti gli ordini delle fermate o tutte le posizioni lungo le strade. '
              'Le restrizioni stradali dipendenti dall’intera storia del percorso e l’idoneità autobus restano non certificate.', '',
              '[709 casi e risultati pedonali](../outputs/phase2/rt031_line8_local_shortcuts_v3/stop_relocation_screen.json) · '
              '[Frontiera preliminare senza pesi](../outputs/phase2/rt031_line8_local_shortcuts_v3/stop_relocation_frontier.json) · '
              '[Sei orari ricalcolati](../outputs/phase2/rt031_line8_local_shortcuts_v3/stop_relocation_timetable.json) · '
              '[Tracciato GeoJSON delle alternative illustrate](../outputs/phase2/rt031_line8_local_shortcuts_v3/stop_relocation_diagnostic.geojson)', '',
              '**Non possiamo attribuire a questo piccolo spostamento il raggiungimento dei 111 mila km.** '
              'I casi che risparmiano di più presentano rinunce territoriali esplicite; servono confronto operativo e accettazione del compromesso, non una selezione automatica.']
    return '\n'.join(lines) + '\n'


def export_geometry(screen, timetable, graph_dir):
    from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import inputs
    from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
    from scripts.phase2_audit_rt031_south_road_probe_v3 import rows, VIRTUAL
    paths = inputs(graph_dir)
    edges, nodes, _, _ = build_graph(paths)
    coords = {nid: [float(r['lon']), float(r['lat'])] for nid, r in nodes.items()}
    south = next(r for r in rows(paths['candidates_normalized_newlines']) if r['candidate_id'] == 'P2V2S_0031')
    coords[VIRTUAL] = [float(south['lon']), float(south['lat'])]
    retention = json.loads(RETENTION.read_text(encoding='utf-8'))
    reference = next(f for f in family_inputs(load_sources()) if f['name'] == 'fast_local_both_directions')
    cases = [c for c in screen['cases'] if c['case_id'] in timetable['diagnostic_case_ids']]
    variants = [materialize(reference, retention, c) for c in cases]
    if not variants or any(v['loops'][p]['edge_ids'] != variants[0]['loops'][p]['edge_ids'] for v in variants for p in reference['loops']):
        raise ValueError('diagnostic cases do not share the same road shape')
    features = []
    for label, family in (('baseline', reference), ('relocation_alternatives', variants[0])):
        for pattern, loop in family['loops'].items():
            vertex = [edges[loop['edge_ids'][0]]['u_node_id']] + [edges[e]['v_node_id'] for e in loop['edge_ids']]
            features.append({'type': 'Feature', 'properties': {'case': label, 'pattern': pattern,
                'distance_m': loop['distance_m'], 'bus_suitability_certified': False},
                'geometry': {'type': 'LineString', 'coordinates': [coords[n] for n in vertex]}})
    e = next(e for l in reference['loops'].values() for e in l['events'] if e['stop_place_id'] == 'FROZEN::300879')
    original_node = edges[e['incoming_edge']]['v_node_id']
    features.append({'type': 'Feature', 'properties': {'kind': 'replaced_reference_site', 'name': e['name'], 'boarding_authorised': False},
                     'geometry': {'type': 'Point', 'coordinates': coords[original_node]}})
    for c in cases:
        features.append({'type': 'Feature', 'properties': {'kind': 'alternative_new_site', 'case_id': c['case_id'], 'boarding_authorised': False},
                         'geometry': {'type': 'Point', 'coordinates': coords[c['new_road_node']]}})
    result = {'type': 'FeatureCollection', 'properties': {**{k: False for k in FLAGS},
        'semantics': 'Three alternative replacement sites on one shared road shape, not three added stops or an adopted route.'}, 'features': features}
    return result, coords, edges


def render(shape, coords, edges):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    fig, axes = plt.subplots(1, 2, figsize=(13, 6), gridspec_kw={'width_ratios': [1.4, 1]}, constrained_layout=True)
    lines = [f for f in shape['features'] if f['geometry']['type'] == 'LineString']
    points = [f for f in shape['features'] if f['geometry']['type'] == 'Point']
    roads = [(coords[e['u_node_id']], coords[e['v_node_id']]) for e in edges.values()]
    for ax, zoom in zip(axes, (False, True)):
        ax.add_collection(LineCollection(roads, colors='#d9dfe2', linewidths=.8))
        for f in lines:
            old = f['properties']['case'] == 'baseline'
            ax.plot(*zip(*f['geometry']['coordinates']), color='#9b9b9b' if old else '#087e8b', lw=5 if old else 1.7, alpha=.7 if old else 1)
        for i, f in enumerate(points):
            old = f['properties']['kind'] == 'replaced_reference_site'
            xy = f['geometry']['coordinates']
            ax.scatter(*xy, marker='x' if old else 'D', s=75 if zoom else 30, color='#b32055' if old else '#e5a600', zorder=8)
            if zoom:
                ax.annotate('Sito attuale' if old else f'Alternativa {i}', xy, xytext=(12, 15 if old else 15 - i*15),
                            textcoords='offset points', fontsize=9, arrowprops={'arrowstyle': '-', 'lw': .5},
                            bbox={'facecolor': 'white', 'alpha': .85, 'edgecolor': 'none'}, zorder=9)
        extent = [f['geometry']['coordinates'] for f in points] if zoom else [xy for f in lines for xy in f['geometry']['coordinates']]
        pad = .0010 if zoom else .003
        ax.set_xlim(min(p[0] for p in extent)-pad, max(p[0] for p in extent)+pad)
        ax.set_ylim(min(p[1] for p in extent)-pad, max(p[1] for p in extent)+pad)
        ax.set_aspect(1/.7); ax.set_xticks([]); ax.set_yticks([])
        ax.set_title('Dettaglio Rovagnate–Vinicola Ghezzi' if zoom else 'Rete intercomunale: modifica localizzata', fontsize=11)
    fig.suptitle('Tre alternative di fermata, non tre fermate aggiuntive\nGrigio: prima · verde: percorso comune alle alternative · nessuna selezione', fontsize=13)
    fig.supxlabel('Grafo e accessibilità condizionali. Siti, paline, attraversamenti e percorribilità autobus da validare.', fontsize=9)
    fig.savefig(BASE / 'stop_relocation_diagnostic.png', dpi=150); plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--graph_dir', type=Path, required=True)
    args = parser.parse_args()
    screen = json.loads(SCREEN.read_text(encoding='utf-8'))
    timetable = json.loads(TIMETABLE.read_text(encoding='utf-8'))
    retention = json.loads(RETENTION.read_text(encoding='utf-8'))
    front = frontier(screen, retention)
    (BASE / 'stop_relocation_frontier.json').write_text(json.dumps(front, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    DOC.write_text(report(screen, timetable, front), encoding='utf-8')
    shape, coords, edges = export_geometry(screen, timetable, args.graph_dir)
    (BASE / 'stop_relocation_diagnostic.geojson').write_text(json.dumps(shape, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    render(shape, coords, edges)
    print(json.dumps({'preliminary_frontier_cases': len(front['frontier_case_ids'])}))
