"""Mix original and corrected wings without crediting slow local journeys."""
import argparse
import copy
import json
from pathlib import Path

from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import inputs, FS, VIRTUAL, digest
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
from scripts.phase2_probe_rt031_line8_stop_relocation_v3 import validate_paths
from scripts.phase2_audit_rt031_line8_occurrence_service_v3 import occurrences
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import (
    BASE, FLAGS, GRID, LOCAL_SITES, family_inputs, load_sources, adjusted_loops, prepare, verify)
from scripts.phase2_solve_rt031_line8_partial_services_v3 import solve_lazy
from scripts.phase2_compare_rt031_line8_shorter_span_v3 import SPANS

OUTPUT = BASE / 'mixed_local_comparison.json'


def local_rides(loop, sid, dwell):
    events = [e for e in loop['events'] if e['stop_place_id'] == sid]
    return {'from_fs': min(e['offset_from_wing_origin_min'] - dwell for e in events),
            'to_fs': loop['road_minutes'] - max(e['offset_from_wing_origin_min'] for e in events)}


def qualify(loops, reference):
    """No new minute cutoff: no worse than the reference fast envelope in EVERY case."""
    adjusted = {key: adjusted_loops(loops, *key) for key in GRID}
    ref = {key: adjusted_loops(reference, *key) for key in GRID}
    envelope = {key: {sid: {direction: max(local_rides(loop, sid, key[1])[direction]
                             for loop in rows.values() if any(e['stop_place_id'] == sid for e in loop['events']))
                           for direction in ('to_fs', 'from_fs')} for sid in LOCAL_SITES}
                for key, rows in ref.items()}
    result, audit = copy.deepcopy(loops), []
    for name, loop in result.items():
        loop['local_service_directions'] = {}
        for sid in sorted({e['stop_place_id'] for e in loop['events']} & set(LOCAL_SITES)):
            eligible = []
            for direction in ('to_fs', 'from_fs'):
                details = [{'moving_multiplier': m, 'dwell_min': d,
                            'ride_min': local_rides(adjusted[m, d][name], sid, d)[direction],
                            'reference_envelope_min': envelope[m, d][sid][direction]}
                           for m, d in GRID]
                allowed = all(r['ride_min'] <= r['reference_envelope_min'] + 1e-8 for r in details)
                if allowed:
                    eligible.append(direction)
                audit.append({'pattern': name, 'site_id': sid, 'direction': direction,
                              'eligible_for_fast_local_service': allowed, 'scenarios': details})
            loop['local_service_directions'][sid] = eligible
    return result, audit


def build_pool(graph_dir):
    source_path = BASE / 'partial_services_pool.json'
    pool = json.loads(source_path.read_text(encoding='utf-8'))
    if pool['contract'] != 'RT031_LINE8_PREFIX_SUFFIX_PARTIAL_POOL_V3' or any(pool[k] is not False for k in FLAGS):
        raise ValueError('unsupported or decisional source pool')
    sources = load_sources()
    original, corrected = family_inputs(sources)
    if any(pool['family']['loops'][p] != l for p, l in corrected['loops'].items()):
        raise ValueError('corrected pool reference drift')
    loops = copy.deepcopy(pool['family']['loops'])
    for pattern, loop in original['loops'].items():
        loops[pattern + '_original'] = copy.deepcopy(loop)
    paths = inputs(graph_dir)
    edges, nodes, rules, attachments = build_graph(paths)
    fs = attachments[FS]['graph_node_id']
    sites = {FS: {'node': fs, 'name': 'Olgiate FS', 'status': 'INVENTORY_NOT_APPROVED'}}
    for loop in corrected['loops'].values():
        for e in loop['events']:
            sites[e['stop_place_id']] = {'node': edges[e['incoming_edge']]['v_node_id'],
                                         'name': e['name'], 'status': e['site_status']}
    # Original events retain whole-figure-eight indices. Rebind them to each
    # actual wing path; do not relabel those indices as valid local occurrences.
    for pattern in original['loops']:
        loop = loops[pattern + '_original']
        actual = occurrences(loop['edge_ids'], edges, sites, fs, pattern + '_original')
        loop['events'] = [{**e, 'offset_from_wing_origin_min': e['offset_road_minutes']}
                          for e in actual if e['stop_place_id'] != FS]
        loop['distance_m'] = sum(float(edges[e]['length_m']) for e in loop['edge_ids'])
        loop['road_minutes'] = sum(float(edges[e]['running_minutes_model']) for e in loop['edge_ids'])
    adapter = FrozenRT017ViaNodeAdapter(edges.values(), rules, unresolved_external_via_way_count=2)
    validate_paths({'mixed': [{'loops': loops}]}, edges, adapter, attachments[FS]['graph_node_id'])
    joins = {a + '>' + b: adapter.decision((la['edge_ids'][-1],), lb['edge_ids'][0])['allowed'] is True
             for a, la in loops.items() for b, lb in loops.items()}
    if not all(joins.values()):
        raise ValueError('incompatible represented station joins')
    loops, audit = qualify(loops, corrected['loops'])
    family = {**pool['family'], 'name': 'mixed_original_corrected_partial_with_qualified_local_events',
              'loops': loops, 'joins': joins, 'all_patterns_fast_local': False,
              'local_direction_contract': 'REFERENCE_FAST_RIDE_ENVELOPE_V3'}
    return family, audit, {'partial_pool': digest(source_path, True),
                          'road_sources': {k: digest(v, k.endswith('normalized_newlines')) for k, v in paths.items()}}, edges, nodes


def run(graph_dir, time_limit, checkpoint):
    family, audit, hashes, edges, nodes = build_pool(graph_dir)
    reference_path = BASE / 'partial_services_phase_closure.json'
    reference = json.loads(reference_path.read_text(encoding='utf-8'))['case']
    baseline = family_inputs(load_sources())[1]
    kwargs = dict(ready_span=(390, 1180), pm_arrivals=SPANS['last_fs_1940']['pm_arrivals'])
    ceiling = prepare(baseline, 60, False, **kwargs)['wait_ceiling']
    problem = prepare(family, 60, False, **kwargs, am_wait_ceiling_comparison_min=ceiling)
    verify(problem, reference['trips'], reference['comparison_peak_windows'], 4)
    print(json.dumps({'patterns': len(family['loops']), 'trips': len(problem['trips']), 'anchors': len(problem['anchors'])}), flush=True)
    case = solve_lazy(problem, reference, time_limit, flexible_peaks=True, strengthen=True, checkpoint_path=checkpoint)
    hashes['reference'] = digest(reference_path, True)
    result = {'contract': 'RT031_LINE8_MIXED_LOCAL_SERVICE_COMPARISON_V3', 'family': family,
              'local_direction_audit': audit, 'case': case, 'source_sha256': hashes,
              'semantics': '68 existing graph paths: 64 corrected/partial plus four original wings. Local H30/H60 and frozen rail opportunities count only directions no slower than the reference fast-local ride envelope in all nine timing cases. Nonlocal sites retain per-site service and rail controls. No transfer inferred; no new normative travel-time threshold. Same 260 days, 06:30-19:40 ready span, four nominal vehicles, 49 peak combinations. Not a full road-network optimum or physically approved service. Inversions and full-history restrictions remain unresolved.',
              **{k: False for k in FLAGS}, 'actual_timetable_certified': False,
              'decision_budget_km': None, 'uncertainty_band_min': None, 'total_operating_km': None}
    prior = json.loads((BASE / 'local_counterflow.geojson').read_text(encoding='utf-8'))
    coords = {n: [float(row['lon']), float(row['lat'])] for n, row in nodes.items()}
    coords[VIRTUAL] = next(f['geometry']['coordinates'] for f in prior['features'] if f['geometry']['type'] == 'Point' and f['properties']['site_id'] == VIRTUAL)
    features = [f for f in prior['features'] if f['geometry']['type'] == 'Point']
    for pattern, count in case['patterns_used'].items():
        path = family['loops'][pattern]['edge_ids']
        vertex = [edges[path[0]]['u_node_id']] + [edges[e]['v_node_id'] for e in path]
        features.append({'type': 'Feature', 'properties': {'pattern': pattern, 'daily_trip_count': count,
                         'local_service_directions': family['loops'][pattern]['local_service_directions'], 'boarding_authorised': False},
                         'geometry': {'type': 'LineString', 'coordinates': [coords[n] for n in vertex]}})
    return result, {'type': 'FeatureCollection', 'properties': {k: False for k in FLAGS}, 'features': features}


def export_map(result, shape):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(11, 6), constrained_layout=True)
    labels = {FS: 'Olgiate FS', VIRTUAL: 'Olgiate sud', LOCAL_SITES[1]: 'San Zeno / Via Cantu',
              'FROZEN::300063': 'Brivio', 'ASF::ARLATE_CANTINA_PIROVANO': 'Arlate',
              'ASF::CALCO_VIA_GARIBALDI': 'Calco', 'FROZEN::300782': 'Santa Maria',
              'ASF::PEREGO_VIA_STATALE_79': 'Perego'}
    for f in shape['features']:
        p, g = f['properties'], f['geometry']
        if g['type'] == 'LineString':
            name = p['pattern']
            ax.plot(*zip(*g['coordinates']), color='#087e8b' if name.startswith('west') else '#aa3c13',
                    lw=1.4, alpha=.8, ls='--' if name.endswith('_original') else ':' if 'partial' in name else '-',
                    label=f"{name}: {p['daily_trip_count']} corse")
        elif g['type'] == 'Point':
            x, y = g['coordinates']; sid = p['site_id']
            ax.scatter(x, y, color='#38275c', s=20, zorder=4)
            if sid in labels:
                ax.annotate(labels[sid], (x, y), xytext=(-65, 8) if sid == 'FROZEN::300063' else (5, 6),
                            textcoords='offset points', fontsize=8,
                            bbox={'facecolor': 'white', 'alpha': .8, 'edgecolor': 'none'})
    ax.set_aspect(1/.7); ax.margins(.12); ax.set_xticks([]); ax.set_yticks([])
    ax.legend(loc='lower left', fontsize=7)
    fig.suptitle(f"Combinazione percorsi e servizio locale: {result['case']['annual_service_km']:,.0f} km/anno\n"
                 'Solo il testimone verificato, non i risultati intermedi incompleti', fontsize=13)
    fig.supxlabel('28 siti; H30/H60 con opportunita locali rapide distinte per verso.\n'
                  'Grafo congelato: inversioni, idoneita autobus e paline non autorizzate.', fontsize=9)
    fig.savefig(OUTPUT.with_suffix('.png'), dpi=150, bbox_inches='tight'); plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--graph_dir', type=Path, required=True)
    parser.add_argument('--time_limit', type=float, default=180)
    parser.add_argument('--checkpoint', type=Path)
    args = parser.parse_args()
    result, shape = run(args.graph_dir, args.time_limit, args.checkpoint)
    for path, data in ((OUTPUT, result), (OUTPUT.with_suffix('.geojson'), shape)):
        path.write_text(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    export_map(result, shape)
    print(json.dumps({k: result['case'][k] for k in ('annual_service_km', 'annual_service_km_lower_bound_in_domain', 'patterns_used', 'optimality_proven_in_this_domain')}), flush=True)
