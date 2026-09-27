"""Actual road/event witness for the completed partial-service phase search."""
import copy
import json

from scripts.phase2_solve_rt031_line8_partial_services_v3 import BASE, POOL, FLAGS, digest
from scripts.phase2_compare_rt031_line8_shorter_span_v3 import SPANS
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import prepare, verify, events_by_site, family_inputs
from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import load_sources

SOURCE = BASE / 'partial_services_phase_closure.json'


def build():
    pool = json.loads(POOL.read_text(encoding='utf-8'))
    result = json.loads(SOURCE.read_text(encoding='utf-8'))
    if result['source_sha256_normalized_newlines'] != {
            'pool': digest(POOL), 'reference': digest(BASE / 'shorter_span_comparison.json')} or any(result[k] for k in FLAGS):
        raise ValueError('phase closure source drift or selection')
    family = pool['family']
    case = result['case']
    kwargs = dict(ready_span=(390, 1180), pm_arrivals=SPANS['last_fs_1940']['pm_arrivals'])
    original = next(f for f in family_inputs(load_sources()) if f['name'] == 'fast_local_both_directions')
    ceiling = prepare(original, 60, False, **kwargs)['wait_ceiling']
    problem = prepare(family, 60, False, **kwargs, am_wait_ceiling_comparison_min=ceiling)
    verified = verify(problem, case['trips'], case['comparison_peak_windows'], 4)
    if verified != case['conditional_scenarios']:
        raise ValueError('phase closure scenario ledger drift')
    nominal = problem['adjusted'][1.1, .5]
    departures = events_by_site(case['trips'], nominal)
    ledger = []
    for i, trip in enumerate(case['trips']):
        loop = nominal[trip['loop']]
        ledger.append({**trip, 'trip_index': i, 'service_km': family['loops'][trip['loop']]['distance_m'] / 1000,
                       'fs_return_nominal_min': trip['departure_min'] + loop['road_minutes'],
                       'partial_service': 'partial' in trip['loop'],
                       'site_ids': sorted({e['stop_place_id'] for e in loop['events']}),
                       'events_nominal': [{**e, 'departure_min': trip['departure_min'] + e['offset_from_wing_origin_min']}
                                          for e in loop['events']]})
    if abs(sum(t['service_km'] for t in ledger) * 260 - case['annual_service_km']) > 1e-5:
        raise ValueError('witness annual km ledger mismatch')
    used = set(case['patterns_used'])
    full_ids = set(pool['reference_site_ids'])
    served = {sid for trip in ledger for sid in trip['site_ids']} | {'FROZEN::L00407'}
    if served != full_ids:
        raise ValueError('reference sites lost or added in witness')
    row = {'contract': 'RT031_LINE8_PARTIAL_PHASE_WITNESS_LEDGER_V3',
           'source_sha256_normalized_newlines': {'pool': digest(POOL), 'phase_closure': digest(SOURCE),
                                               'pool_geojson': digest(BASE / 'partial_services_pool.geojson')},
           'annual_service_km': case['annual_service_km'],
           'minimum_proven_in_declared_domain': case['optimality_proven_in_this_domain'],
           'annual_service_km_lower_bound_in_domain': case['annual_service_km_lower_bound_in_domain'],
           'saved_service_km_vs_reference': case['saved_service_km_vs_reference'],
           'site_count_including_fs': len(served), 'trips': ledger,
           'nominal_boarding_opportunities': [{'site_id': sid, 'direction': direction,
                                              'opportunities': [{'trip_index': i, 'departure_min': t} for i, t in times]}
                                             for (sid, direction), times in sorted(departures.items())],
           'comparison_peak_windows': case['comparison_peak_windows'], 'patterns_used': case['patterns_used'],
           'semantics': 'Actual witness only, not every candidate combined into a line. Nominal events use moving x1.1 and 0.5-minute dwell. Local to-FS opportunities use the last occurrence only. Different occurrences/platforms remain conditional; no transfers or cross-trip passenger continuity certified. Exact nine-case frequency/rail and nominal fleet rechecks do not establish empirical reliability or authorise the service.',
           **{k: False for k in FLAGS}, 'actual_timetable_certified': False,
           'decision_budget_km': None, 'uncertainty_band_min': None, 'total_operating_km': None}
    pool_shape = json.loads((BASE / 'partial_services_pool.geojson').read_text(encoding='utf-8'))
    features = []
    for f in pool_shape['features']:
        if f['geometry']['type'] == 'LineString':
            if f['properties']['pattern'] not in used:
                continue
            f = copy.deepcopy(f)
            f['properties']['daily_trip_count'] = case['patterns_used'][f['properties']['pattern']]
            f['properties']['partial_service'] = 'partial' in f['properties']['pattern']
        features.append(f)
    shape = {'type': 'FeatureCollection', 'properties': {k: False for k in FLAGS}, 'features': features}
    return row, shape


def export():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    row, shape = build()
    for suffix, data in (('json', row), ('geojson', shape)):
        (BASE / f'partial_services_phase_witness.{suffix}').write_text(
            json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    fig, ax = plt.subplots(figsize=(11, 6), constrained_layout=True)
    for f in shape['features']:
        if f['geometry']['type'] != 'LineString':
            continue
        p = f['properties']
        partial = p['partial_service']
        color = '#087e8b' if p['pattern'].startswith('west') else '#aa3c13'
        label = ('Ovest' if p['pattern'].startswith('west') else 'Est') + (' corta' if partial else ' completa')
        count = p['daily_trip_count']
        ax.plot(*zip(*f['geometry']['coordinates']), color=color, lw=2 if partial else 1.2,
                ls='--' if partial else '-', alpha=1 if partial else .6,
                label=f'{label}: {count} {"corsa" if count == 1 else "corse"}')
    labels = {'FROZEN::L00407': 'Olgiate FS', 'RT031::P2V2S_0031_PROJECTED_ROAD_POINT': 'Olgiate sud',
              'PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE': 'San Zeno / Via Cantu',
              'ASF::CALCO_VIA_GARIBALDI': 'Calco', 'FROZEN::300063': 'Brivio / Via Bergamo',
              'ASF::ARLATE_CANTINA_PIROVANO': 'Arlate', 'FROZEN::300398': 'Beverate',
              'FROZEN::300782': 'Santa Maria', 'FROZEN::300879': 'Rovagnate',
              'ASF::PEREGO_VIA_STATALE_79': 'Perego'}
    for f in shape['features']:
        if f['geometry']['type'] != 'Point':
            continue
        x, y = f['geometry']['coordinates']; sid = f['properties']['site_id']
        ax.scatter(x, y, color='#38275c', s=22, zorder=5)
        if sid in labels:
            offset = (-140, 8) if sid == 'FROZEN::300063' else (5, 6)
            ax.annotate(labels[sid], (x, y), xytext=offset, textcoords='offset points', fontsize=9,
                        bbox={'facecolor': 'white', 'alpha': .85, 'edgecolor': 'none'})
    ax.set_aspect(1 / .7); ax.margins(.12); ax.set_xticks([]); ax.set_yticks([])
    ax.legend(loc='lower left', fontsize=8)
    fig.suptitle(f'Orario verificato nel modello: {row["annual_service_km"]:,.0f} km/anno di servizio\n'
                 '28 siti conservati, H30/H60 — confronto non adottato', fontsize=14)
    fig.supxlabel('Solo i cammini effettivamente usati. Grafo congelato; paline e percorribilita autobus da validare.', fontsize=9)
    fig.savefig(BASE / 'partial_services_phase_witness.png', dpi=150, bbox_inches='tight'); plt.close(fig)
    print(json.dumps({k: row[k] for k in ('annual_service_km', 'saved_service_km_vs_reference', 'patterns_used')}), flush=True)


if __name__ == '__main__':
    export()
