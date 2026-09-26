"""Static map of the contextual road witness, not an approved service plan."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def render(shape_path, roads_path, output):
    shape = json.loads(shape_path.read_text(encoding='utf-8'))
    if shape['properties']['network_selected'] is not False:
        raise ValueError('non-decisional shape required')
    fig, ax = plt.subplots(figsize=(11, 9), constrained_layout=True)
    for f in json.loads(roads_path.read_text(encoding='utf-8'))['features']:
        g = f['geometry']
        segments = [g['coordinates']] if g['type'] == 'LineString' else g['coordinates'] if g['type'] == 'MultiLineString' else []
        for pts in segments:
            ax.plot(*zip(*[(p[0], p[1]) for p in pts]), color='#dde2e6', lw=.5, zorder=1)
    all_points = []
    for f in shape['features']:
        if f['geometry']['type'] != 'LineString':
            continue
        pts = f['geometry']['coordinates']
        all_points.extend(pts)
        forward = f['properties']['direction'] == 'forward'
        ax.plot(*zip(*pts), color='#147d92' if forward else '#a54c12',
                lw=2 if forward else 1.5, linestyle='-' if forward else '--',
                label='Orientamento A: 24,52 km' if forward else 'Orientamento B: 25,16 km', zorder=3)
    labeled = set()
    for f in shape['features']:
        if f['geometry']['type'] != 'Point':
            continue
        p = f['properties']; x, y = f['geometry']['coordinates']
        new = p['status'] == 'NEW_STOP_NEED_NOT_APPROVED'
        fs = p['stop_place_id'] == 'FROZEN::L00407'
        gain = p['stop_place_id'] == 'ASF::VACCAREZZA_CARTELLO_PAESE'
        label = 'Esigenza di nuova fermata (sito da validare)' if new else 'Identità di fermata incontrata sul grafo'
        ax.scatter(x, y, s=50 if new or fs else 25, marker='D' if new else 's' if fs else 'o',
                   facecolor='white' if new else '#215e36' if fs or gain else '#333333',
                   edgecolor='#703c8d' if new else 'white', linewidth=1, zorder=5,
                   label=label if label not in labeled else None)
        labeled.add(label)
        name = p['name']
        if fs or new or gain or p['stop_place_id'] in ('FROZEN::300063',):
            label_name = 'Olgiate FS' if fs else 'Brivio / Via Bergamo' if p['stop_place_id'] == 'FROZEN::300063' else name
            ax.annotate(label_name, (x,y), xytext=(-100 if p['stop_place_id'] == 'FROZEN::300063' else 7, 10 if fs else -15),
                        textcoords='offset points', fontsize=9, zorder=6,
                        bbox=dict(facecolor='white', edgecolor='none', alpha=.85, pad=1))
    # Labels use coordinates of actual inventory points, never invented town centres.
    for token in ('PEREGO', 'ROVAGNATE', 'SANTA MARIA', 'CALCO', 'ARLATE', 'BEVERATE', 'MONDONICO'):
        candidates = [f for f in shape['features'] if f['geometry']['type'] == 'Point'
                      and token in f['properties']['name'].upper()]
        if candidates:
            f = candidates[0]
            ax.annotate(token.title(), f['geometry']['coordinates'], xytext=(6, 7),
                        textcoords='offset points', fontsize=9,
                        bbox=dict(facecolor='white', edgecolor='none', alpha=.8, pad=1))
    ax.set_xlim(min(p[0] for p in all_points)-.003, max(p[0] for p in all_points)+.005)
    ax.set_ylim(min(p[1] for p in all_points)-.003, max(p[1] for p in all_points)+.003)
    ax.set_aspect(1/.7); ax.set_xticks([]); ax.set_yticks([])
    ax.set_title('Linea 8: percorso con tutte le 25 identità del riferimento + Vaccarezza\n'
                 'Cammino su grafo: fermate, orario e idoneità autobus non approvati', loc='left', fontsize=12)
    ax.legend(loc='lower left', fontsize=9)
    fig.savefig(output, dpi=170, bbox_inches='tight'); plt.close(fig)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for key in ('shape', 'roads', 'output'):
        p.add_argument('--'+key, required=True, type=Path)
    a = p.parse_args(); render(a.shape, a.roads, a.output)
