"""Finite-domain closure, visible territorial losses, and exact witness map."""
import argparse
from fractions import Fraction
import json
from pathlib import Path

from scripts.phase2_bound_rt031_line8_combined_timing_v3 import OUTPUT as BOUNDS, choices, BASE, SCREEN, RETENTION
from scripts.phase2_check_rt031_line8_combined_edits_v3 import OUTPUT as JOINT, combine_family
from scripts.phase2_check_rt031_line8_relocation_timetable_v3 import sha
from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import FLAGS, load_sources
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import family_inputs, prepare, verify
from scripts.phase2_compare_rt031_line8_shorter_span_v3 import SPANS

DOC = Path(__file__).resolve().parents[1] / 'docs/RT031_LINEA8_ESITO_TAGLI_COMBINATI_V3.md'


def close(bounds, joint, pool, reference):
    if any(bounds[k] or joint[k] for k in FLAGS) or not bounds['all_choices_bounded']:
        raise ValueError('selected or incomplete evidence')
    if joint['source_sha256_normalized_newlines'] != {'screen': sha(SCREEN), 'retention': sha(RETENTION), 'bounds': sha(BOUNDS)}:
        raise ValueError('joint source drift')
    lookup = {c['choice_id']: c for options in pool.values() for c in options}
    witnesses = []
    lower = bounds['minimum_annual_service_km_lower_bound']
    for c in joint['cases']:
        if not c['witness_found']:
            continue
        family = combine_family(reference, lookup[c['west_choice_id']], lookup[c['east_choice_id']])
        p = prepare(family, 60, False, ready_span=(390, 1180), pm_arrivals=SPANS['last_fs_1940']['pm_arrivals'],
                    am_wait_ceiling_comparison_min=bounds['frozen_reference_am_wait_ceiling_comparison_min'])
        grid = verify(p, c['trips'], c['comparison_peak_windows'], 4)
        if grid != c['conditional_scenarios']:
            raise ValueError('joint scenario ledger drift')
        km = sum(family['loops'][t['loop']]['distance_m'] for t in c['trips']) * .26
        if abs(km - c['annual_service_km']) > 1e-5:
            raise ValueError('joint kilometres drift')
        if abs(km - lower) < 1e-5:
            witnesses.append([c['west_choice_id'], c['east_choice_id']])
    if not witnesses:
        raise ValueError('lower bound not attained: cannot claim a finite-domain minimum')
    return {'contract': 'RT031_LINE8_COMBINED_EDITS_FINITE_DOMAIN_CLOSURE_V3',
            'status': 'FINITE_DOMAIN_MINIMUM_PROVEN_NOT_AN_ACCEPTED_PROPOSAL',
            'source_sha256_normalized_newlines': {'bounds': sha(BOUNDS), 'joint_diagnostics': sha(JOINT)},
            'combination_count': bounds['combination_count'], 'finite_domain_minimum_proven': True,
            'annual_service_km_minimum_in_declared_domain': round(lower, 6),
            'reference_cap_unchanged': 111419, 'service_km_excess_vs_reference': round(lower - 111419, 6),
            'reference_cap_excluded_in_declared_domain': lower > 111419 + 1e-5,
            'attaining_diagnostic_choice_pairs': witnesses,
            'domain': '285 west choices × 426 east choices from frozen adjacent-omission bypasses and at most one added node stop per wing. Each choice fixes A/B road patterns and served-site identity set. Five-minute dispatch grid 06:00-19:40; ready span 06:30-19:40; common H30 06:50-08:50 and 16:35-18:35, H60 elsewhere; frozen AM five/PM six rail anchors through 19:32, reference AM waiting ceiling, nine deterministic running/dwell scenarios, four nominal vehicles; 260 assumed service days. Independent lower bound drops other-site service and fleet but four full witnesses attain it. Not all stop orders, roads, phase choices, calendars, service spans, or combined services across wings.',
            'coverage_scope': 'Joint pedestrian access recomputed only for four explicit attaining diagnostics. No claim that all 121410 combinations have been evaluated for access or all attaining combinations have the same territorial loss. Those four have severe losses, are not recommended, and do not meet the caller desire for limited territorial reduction.',
            'all_territorial_requirements_met': False, 'actual_timetable_certified': False,
            'total_operating_km': None, **{k: False for k in FLAGS},
            'decision_budget_km': None, 'uncertainty_band_min': None, 'approved_uplift_percent': None}


def report(closure, joint):
    if not closure['finite_domain_minimum_proven'] or any(closure[k] for k in FLAGS):
        raise ValueError('unsupported closure')
    c = next(c for c in joint['cases'] if c['west_choice_id'].endswith('__no_new_stop') and c['east_choice_id'].endswith('__no_new_stop'))
    lines = ['# Linea 8 — esito delle modifiche combinate', '',
             '**Questa famiglia di tentativi è chiusa rispetto ai 111.419 km:** combinando le modifiche esaminate, '
             'il minimo del dominio dichiarato è **121.340,751 km/anno di servizio**, con H30 in punta/H60 nel resto. '
             'È **+9.921,751 km (+8,90%)**, prima di deposito e riposizionamenti.', '',
             'Non è la proposta finale: i quattro testimoni completi che raggiungono il minimo presentano perdite territoriali importanti. '
             'Nessuna delle quattro combinazioni viene adottata o raccomandata.', '',
             '## Che cosa è stato dimostrato', '',
             '- **285 scelte ovest × 426 est = 121.410 combinazioni**, comprese le ali senza modifiche. Sono tutte le combinazioni del precedente schermo di spostamento fermate, non tutte le reti possibili.',
             '- Primo controllo: 50 problemi molto ottimistici, con marcia al 90% e soste nulle, danno già un limite inferiore di 111.852,616 km per l’intera famiglia. Non era ancora un orario.',
             '- Secondo controllo: **41 gruppi equivalenti solo per tempi locali, treni e costo**, con tutti i nove scenari marcia/sosta. Il limite inferiore sale a 121.340,751 km. Nessuna equivalenza di copertura viene dedotta dal raggruppamento.',
             '- Quattro orari completi, verificati per **tutti i siti dichiarati**, raggiungono quel limite con quattro mezzi nominali. Limite inferiore e testimone fattibile coincidono: il minimo è provato nel dominio.',
             '- Le 121.410 combinazioni non sono state tutte risolte come orari completi: sono coperte dal limite inferiore. La copertura pedonale congiunta è stata ricalcolata per quattro testimoni, senza sommare le perdite delle singole ali.', '',
             '## Il prezzo territoriale dei quattro testimoni economici', '',
             'Tutti e quattro rinunciano ai siti originari **Arlate–Cantina Pirovano, Brivio–Via Bergamo (Scuola Materna), S. Maria Hoè e Hoè**. '
             'Il caso senza nuove fermate contiene 25 siti: 24 dei 28 originari e un altro sito d’inventario incontrato sul nuovo percorso. '
             'Gli altri tre aggiungono uno o due punti ipotetici sulle scorciatoie, arrivando a 26 o 27 siti; non ripristinano le identità eliminate.', '',
             'Copertura pedonale potenziale entro **10 minuti**, caso senza nuovi punti:', '',
             '| Comune | Prima | Dopo | Differenza in punti percentuali |',
             '|---|---:|---:|---:|']
    for code, name in joint['municipality_names'].items():
        before = 100 * float(Fraction(joint['baseline_potential_access_fraction'][code]['10']))
        after = 100 * float(Fraction(c['potential_access_fraction'][code]['10']))
        lines.append(f'| {name} | {before:.2f}% | {after:.2f}% | {after-before:+.2f} pp |')
    lines += ['', 'Nei due casi con punto aggiuntivo ovest, La Valletta Brianza recupera quasi tutta la piccola perdita. '
              'Le perdite maggiori restano pressoché identiche nei quattro testimoni: circa **−19,7 pp Brivio, −12,1 pp Calco, −3,9 pp Santa Maria Hoè**. '
              'Le percentuali non sono passeggeri o domanda: includono le ipotesi sulle fermate non autorizzate e sui connettori pedonali. '
              'I JSON espongono anche soglie 5/8 minuti e perdita lorda dei nuclei precedentemente coperti, non soltanto il saldo.', '',
              '## Orario e risorse del testimone illustrato', '',
              '39 corse d’ala al giorno: **20 ovest B + 19 est A**. Prima partenza FS 06:35 ovest / 06:40 est, ultime partenze 19:40. '
              'La fascia di disponibilità passeggeri 06:30–19:40 non è una promessa di prima/ultima salita identica in ogni sito.', '',
              'Punte comuni confrontate: **06:50–08:50 e 16:35–18:35**; H60 nel resto. Sono vincoli di attesa massima modellata, '
              'non ancora un orario pubblico perfettamente cadenzato. Nessuna H90/H120 introdotta.', '',
              'Tutti e quattro i testimoni: **quattro mezzi nominali**, fino a **cinque** nella griglia di stress. '
              'Disponibilità mezzi, turni, deposito e affidabilità osservata non sono certificati. '
              'I treni restano quelli congelati del 3 settembre 2026, con primo obiettivo AM 07:26 e ultimo arrivo PM 19:32; '
              'l’obiettivo 20:32 del confronto più lungo non è incluso.', '',
              '## Tracciato reale del confronto, non una proposta scelta', '',
              '![Estremo di minimo costo: territori persi evidenziati](../outputs/phase2/rt031_line8_local_shortcuts_v3/combined_edits_diagnostic.png)', '',
              'La mappa mostra il caso senza nuovi punti, scelto solo per illustrare le esclusioni senza sovrapporre alternative di fermata. '
              'Grigio: percorso precedente; verde: ovest B/est A effettivamente usati; croci rosse: quattro siti originari non serviti. '
              'Olgiate sud e San Zeno rimangono distinti e presenti, con collegamenti locali brevi nei due versi.', '',
              '## Come usare questo risultato', '',
              '**Non proseguire a combinare queste stesse scorciatoie sperando di trovare 111.419 km:** nelle condizioni dichiarate il limite è dimostrato. '
              'Questo non prova l’impossibilità su altre geometrie, ordini di fermate, finestre di punta, calendari o fasce. '
              'Il risultato non autorizza un aumento del budget, né una perdita territoriale. Non esiste qui un vincitore da inviare come proposta finale.', '',
              '[Chiusura macchina del dominio](../outputs/phase2/rt031_line8_local_shortcuts_v3/combined_edits_closure.json) · '
              '[Limiti sui 41 gruppi](../outputs/phase2/rt031_line8_local_shortcuts_v3/combined_edits_timing_bounds.json) · '
              '[Quattro orari e copertura ricalcolata](../outputs/phase2/rt031_line8_local_shortcuts_v3/combined_edits_joint_diagnostics.json) · '
              '[GeoJSON del testimone illustrato](../outputs/phase2/rt031_line8_local_shortcuts_v3/combined_edits_diagnostic.geojson)', '',
              'Percorribilità autobus, restrizioni dipendenti dall’intera storia del percorso, paline e continuità passeggeri restano condizionali. '
              '`network_selected`, `primary_selection_authorised`, `runner_up_selection_authorised` restano `false`; '
              'budget decisionale, banda d’incertezza, aumento approvato e km operativi totali non sono scelti o noti.']
    return '\n'.join(lines) + '\n'


def geometry(joint, pool, reference, graph_dir):
    from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import inputs
    from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
    from scripts.phase2_audit_rt031_south_road_probe_v3 import rows, VIRTUAL, FS
    from scripts.phase2_export_rt031_line8_inclusive_shape_v3 import NORTH
    paths = inputs(graph_dir)
    edges, nodes, _, attachments = build_graph(paths)
    coords = {n: [float(r['lon']), float(r['lat'])] for n, r in nodes.items()}
    south = next(r for r in rows(paths['candidates_normalized_newlines']) if r['candidate_id'] == 'P2V2S_0031')
    coords[VIRTUAL] = [float(south['lon']), float(south['lat'])]
    lookup = {c['choice_id']: c for cs in pool.values() for c in cs}
    c = next(c for c in joint['cases'] if c['west_choice_id'].endswith('__no_new_stop') and c['east_choice_id'].endswith('__no_new_stop'))
    family = combine_family(reference, lookup[c['west_choice_id']], lookup[c['east_choice_id']])
    patterns = {t['loop'] for t in c['trips']}
    features = []
    for label, f in (('reference', reference), ('diagnostic', family)):
        for p in sorted(patterns):
            loop = f['loops'][p]
            vertices = [edges[loop['edge_ids'][0]]['u_node_id']] + [edges[e]['v_node_id'] for e in loop['edge_ids']]
            features.append({'type': 'Feature', 'properties': {'case': label, 'pattern': p, 'distance_m': loop['distance_m']},
                             'geometry': {'type': 'LineString', 'coordinates': [coords[v] for v in vertices]}})
    locations = {FS: (attachments[FS]['graph_node_id'], 'Olgiate FS')}
    for f in (reference, family):
        for loop in f['loops'].values():
            for event in loop['events']:
                locations[event['stop_place_id']] = (edges[event['incoming_edge']]['v_node_id'], event['name'])
    for sid, (node, name) in locations.items():
        features.append({'type': 'Feature', 'properties': {'site_id': sid, 'name': name,
            'lost': sid in c['lost_original_site_ids'], 'priority': sid in (FS, VIRTUAL, NORTH), 'boarding_authorised': False},
            'geometry': {'type': 'Point', 'coordinates': coords[node]}})
    shape = {'type': 'FeatureCollection', 'properties': {**{k: False for k in FLAGS},
        'diagnostic_choice_ids': [c['west_choice_id'], c['east_choice_id']], 'semantics': 'Extreme minimum-resource diagnostic with severe territorial loss; not selected or recommended.'}, 'features': features}
    return shape, coords, edges


def render(shape, coords, edges):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    fig, ax = plt.subplots(figsize=(12, 7), constrained_layout=True)
    ax.add_collection(LineCollection([(coords[e['u_node_id']], coords[e['v_node_id']]) for e in edges.values()], colors='#dce2e5', linewidths=.6))
    lines = [f for f in shape['features'] if f['geometry']['type'] == 'LineString']
    points = [f for f in shape['features'] if f['geometry']['type'] == 'Point']
    for f in lines:
        old = f['properties']['case'] == 'reference'
        ax.plot(*zip(*f['geometry']['coordinates']), color='#969da3' if old else '#087e8b', lw=4.5 if old else 1.9, alpha=.65 if old else 1,
                label=('Percorso precedente' if old else 'Testimone con esclusioni') if f['properties']['pattern'] == 'east_A' else None)
    for f in points:
        p = f['properties']; xy = f['geometry']['coordinates']
        ax.scatter(*xy, s=85 if p['lost'] else 45 if p['priority'] else 15, marker='x' if p['lost'] else 'D' if p['priority'] else 'o',
                   color='#ba284c' if p['lost'] else '#49316f' if p['priority'] else '#333333', zorder=8)
        if p['lost'] or p['priority']:
            name = p['name']
            if 'Cantina' in name: name = 'Arlate — sito escluso'
            if 'Bergamo' in name: name = 'Brivio Via Bergamo — escluso'
            right_edge = 'Bergamo' in p['name']
            ax.annotate(name, xy, xytext=(-10, 8) if right_edge else (7, 8), ha='right' if right_edge else 'left', textcoords='offset points', fontsize=9,
                        bbox={'facecolor': 'white', 'alpha': .85, 'edgecolor': 'none'}, zorder=9)
    extent = [p for f in lines for p in f['geometry']['coordinates']]
    ax.set_xlim(min(p[0] for p in extent)-.004, max(p[0] for p in extent)+.008)
    ax.set_ylim(min(p[1] for p in extent)-.004, max(p[1] for p in extent)+.004)
    ax.set_aspect(1/.7); ax.set_xticks([]); ax.set_yticks([]); ax.legend(loc='lower right')
    fig.suptitle('Minimo nel dominio dei tagli combinati: 121.341 km/anno\nH30/H60 — quattro siti originari esclusi — NON è la proposta raccomandata', fontsize=13)
    fig.supxlabel('Geometria del grafo congelato. Siti e percorribilità autobus non autorizzati; deposito e riposizionamenti esclusi.', fontsize=9)
    fig.savefig(BASE / 'combined_edits_diagnostic.png', dpi=150, bbox_inches='tight', pad_inches=.15); plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--graph_dir', type=Path, required=True)
    args = parser.parse_args()
    screen = json.loads(SCREEN.read_text(encoding='utf-8'))
    retention = json.loads(RETENTION.read_text(encoding='utf-8'))
    bounds = json.loads(BOUNDS.read_text(encoding='utf-8'))
    joint = json.loads(JOINT.read_text(encoding='utf-8'))
    pool = choices(screen, retention)
    reference = next(f for f in family_inputs(load_sources()) if f['name'] == 'fast_local_both_directions')
    closure = close(bounds, joint, pool, reference)
    (BASE / 'combined_edits_closure.json').write_text(json.dumps(closure, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    DOC.write_text(report(closure, joint), encoding='utf-8')
    shape, coords, edges = geometry(joint, pool, reference, args.graph_dir)
    (BASE / 'combined_edits_diagnostic.geojson').write_text(json.dumps(shape, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    render(shape, coords, edges)
