"""Static road comparison; the shorter geometry is diagnostic, not a bus proposal."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

from scripts.phase2_audit_rt031_south_road_probe_v3 import rows
from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import BASE, FS, NORTH, VIRTUAL, inputs

OUTPUT = BASE / 'free_boundary_road_comparison.png'


def render(graph_dir, output=OUTPUT):
    graph = inputs(graph_dir)
    audit = json.loads((BASE / 'free_boundary_road_comparison.json').read_text(encoding='utf-8'))
    shape = json.loads((BASE / 'free_boundary_road_comparison.geojson').read_text(encoding='utf-8'))
    current = json.loads((BASE / 'local_counterflow.geojson').read_text(encoding='utf-8'))
    if audit['network_selected'] or audit['both_local_directional_occurrence_guarantees_preserved']:
        raise ValueError('expected non-decisional road minimum that loses directional occurrence guarantees')
    from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import digest
    for key in ('edges', 'nodes'):
        if digest(graph[key]) != audit['road_source_sha256'][key]:
            raise ValueError('map road source drift: ' + key)
    nodes = {n['node_id']: (float(n['lon']), float(n['lat'])) for n in rows(graph['nodes'])}
    road_segments = [(nodes[e['u_node_id']], nodes[e['v_node_id']]) for e in rows(graph['edges'])]
    stop_points = {f['properties']['site_id']: f['geometry']['coordinates']
                   for f in shape['features'] if f['geometry']['type'] == 'Point'
                   and f['properties'].get('site_id')}
    if len(stop_points) != 29:
        raise ValueError('map lacks project stop identities')
    bounds = [p for p in stop_points.values()]
    xmin, xmax = min(p[0] for p in bounds) - .003, max(p[0] for p in bounds) + .003
    ymin, ymax = min(p[1] for p in bounds) - .003, max(p[1] for p in bounds) + .003
    fig, axes = plt.subplots(1, 2, figsize=(16, 5.2), constrained_layout=True)
    route_sets = [
        {f['properties']['pattern'].split('_')[0]: f for f in current['features']
         if f['geometry']['type'] == 'LineString' and f['properties'].get('case') == 'both'
         and f['properties'].get('pattern') in ('west_B', 'east_A')},
        {f['properties']['wing']: f for f in shape['features']
         if f['geometry']['type'] == 'LineString'},
    ]
    key_labels = {FS: ('Olgiate FS', (5, -12)), VIRTUAL: ('Olgiate sud', (5, -16)),
                  NORTH: ('San Zeno', (5, 8)),
                  'ASF::SANTA_MARIA_HOE_VIA_COMO': ('Santa Maria', (4, 6)),
                  'ASF::PEREGO_VIA_STATALE_79': ('Perego', (4, 6)),
                  'ASF::BRIVIO_BAR_CRISTALLO': ('Brivio', (5, 6)),
                  'ASF::CALCO_VIA_GARIBALDI': ('Calco', (5, -12)),
                  'PROXY::RT031_ADDITIONAL::n:534398.29:5063851.64': ('Arlate N1212', (5, 6))}
    colors = {'west': '#087e8b', 'east': '#b25b00'}
    for panel, (ax, routes) in enumerate(zip(axes, route_sets)):
        ax.add_collection(LineCollection(road_segments, colors='#d9dee2', linewidths=.45, zorder=1))
        for wing in ('west', 'east'):
            line = routes[wing]['geometry']['coordinates']
            ax.plot(*zip(*line), color=colors[wing], lw=2.5, zorder=3,
                    label='Ala ovest' if wing == 'west' else 'Ala est')
        for sid, (x, y) in stop_points.items():
            ax.scatter(x, y, s=25 if sid in key_labels else 9,
                       c='#282b31', marker='s' if sid == FS else 'o',
                       edgecolors='white', linewidths=.5, zorder=4)
        for sid, (label, offset) in key_labels.items():
            ax.annotate(label, stop_points[sid], xytext=offset, textcoords='offset points',
                        fontsize=8.3, color='#20242a', zorder=7,
                        bbox={'facecolor': 'white', 'edgecolor': 'none', 'alpha': .78, 'pad': 1})
        if panel == 1:
            reversals = [f for f in shape['features'] if f['properties'].get('immediate_reversal')]
            for f in reversals:
                x, y = f['geometry']['coordinates']
                ax.scatter(x, y, s=115, marker='x', c='#c32128', lw=2.4, zorder=8)
            ax.scatter([], [], s=90, marker='x', c='#c32128', lw=2.4,
                       label='Inversione non autorizzata')
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.set_aspect(1 / .698)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(('Tracciato confermato · 27,679 km' if panel == 0 else
                      'Minimo stradale diagnostico · 24,517 km'), fontsize=13, loc='left')
        ax.legend(loc='lower left', frameon=True, fontsize=8)
    fig.suptitle('Linea 8 unica: stessi 29 siti, servizio non equivalente', fontsize=15)
    fig.supxlabel('Il percorso a destra perde un passaggio rapido per ciascuno tra Olgiate sud e San Zeno e include 4 inversioni da verificare. '
                 'Non è una rete selezionata.', fontsize=9)
    fig.savefig(output, dpi=170, bbox_inches='tight')
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--graph_dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    render(args.graph_dir, args.output)
