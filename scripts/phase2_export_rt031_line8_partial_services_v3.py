"""Export domain/verified-witness distinction, not a newly selected service."""
import json

from scripts.phase2_solve_rt031_line8_partial_services_v3 import BASE, FLAGS, OUTPUT, POOL, digest


def export():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    pool = json.loads(POOL.read_text(encoding='utf-8'))
    fixed = json.loads(OUTPUT.read_text(encoding='utf-8'))
    flex_path = BASE / 'partial_services_flexible_peaks.json'
    flex = json.loads(flex_path.read_text(encoding='utf-8'))
    for result in (fixed, flex):
        if result['source_sha256_normalized_newlines']['pool'] != digest(POOL) or any(result[k] for k in FLAGS):
            raise ValueError('partial-service export source drift or selection')
    summary = {'contract': 'RT031_LINE8_PARTIAL_SERVICES_FINDINGS_V3',
               'pattern_count': len(pool['family']['loops']), 'requested_road_variants': len(pool['requests']),
               'reference_site_count': len(pool['reference_site_ids']),
               'comparisons': [], 'source_sha256_normalized_newlines': {
                   'pool': digest(POOL), 'fixed': digest(OUTPUT), 'flexible': digest(flex_path)},
               **{k: False for k in FLAGS}, 'actual_timetable_certified': False,
               'decision_budget_km': None, 'uncertainty_band_min': None,
               'total_operating_km': None, 'approved_uplift_percent': None}
    for name, result in (('fixed_peaks', fixed), ('flexible_peaks', flex)):
        case = result['case']
        lower, upper = case['annual_service_km_lower_bound_in_domain'], case['annual_service_km']
        if lower > upper + 1e-4:
            raise ValueError('inconsistent lower bound and witness')
        summary['comparisons'].append({'comparison': name, 'annual_service_km_lower_bound': lower,
                                       'verified_witness_annual_service_km': upper,
                                       'reference_111419_excluded_in_declared_domain': lower > 111419 + 1e-4,
                                       'minimum_proven': case['optimality_proven_in_this_domain'],
                                       'verified_witness_partial_trip_count': sum(n for p, n in case['patterns_used'].items() if 'partial' in p),
                                       'witness_patterns_used': case['patterns_used']})
    (BASE / 'partial_services_findings.json').write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')

    shape = json.loads((BASE / 'partial_services_pool.geojson').read_text(encoding='utf-8'))
    lines = [f for f in shape['features'] if f['geometry']['type'] == 'LineString']
    points = [f for f in shape['features'] if f['geometry']['type'] == 'Point']
    fig, axes = plt.subplots(1, 2, figsize=(14, 7), constrained_layout=True)
    for ax, wing, color in zip(axes, ('west', 'east'), ('#087e8b', '#aa3c13')):
        own = [f for f in lines if f['properties']['pattern'].startswith(wing)]
        for f in own:
            if 'partial' in f['properties']['pattern']:
                ax.plot(*zip(*f['geometry']['coordinates']), color=color, lw=1, alpha=.20)
        witness = 'west_B' if wing == 'west' else 'east_A'
        f = next(f for f in own if f['properties']['pattern'] == witness)
        ax.plot(*zip(*f['geometry']['coordinates']), color='#252525', lw=1.7)
        site_ids = {e['stop_place_id'] for name, loop in pool['family']['loops'].items() if name.startswith(wing) for e in loop['events']}
        for point in points:
            sid = point['properties']['site_id']
            if sid not in site_ids and sid != 'FROZEN::L00407':
                continue
            x, y = point['geometry']['coordinates']
            ax.scatter(x, y, color='#38275c', s=18, zorder=5)
            if sid in ('FROZEN::L00407', 'RT031::P2V2S_0031_PROJECTED_ROAD_POINT', 'PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE'):
                label = {'FROZEN::L00407': 'Olgiate FS', 'RT031::P2V2S_0031_PROJECTED_ROAD_POINT': 'Olgiate sud',
                         'PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE': 'San Zeno / Via Cantu'}[sid]
                ax.annotate(label, (x, y), xytext=(5, 6), textcoords='offset points', fontsize=9,
                            bbox={'facecolor': 'white', 'edgecolor': 'none', 'alpha': .8})
        ax.set_title(f'{"Ovest" if wing == "west" else "Est"}: {len(own)} cammini distinti')
        ax.set_aspect(1 / .7)
        ax.margins(.12)
        ax.set_xticks([]); ax.set_yticks([])
        ax.legend(handles=[Line2D([0], [0], color=color, alpha=.5, label='Alternative corte esaminate, NON adottate'),
                           Line2D([0], [0], color='#252525', label='Ala completa del testimone verificato')], loc='lower left', fontsize=8)
    fig.suptitle('Corse parziali: dominio stradale esaminato, non una nuova linea\n'
                 '28 siti mantenuti nel servizio; le alternative non sono tutte corse da esercire', fontsize=13)
    fig.supxlabel('Grafo congelato: svolte via-node controllate. Paline, manovre autobus e restrizioni complete non certificate.', fontsize=9)
    fig.savefig(BASE / 'partial_services_domain.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(json.dumps(summary['comparisons']), flush=True)


if __name__ == '__main__':
    export()
