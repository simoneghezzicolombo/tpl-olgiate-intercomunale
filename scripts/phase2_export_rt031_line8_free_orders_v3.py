"""Render graph paths and explicitly unapproved reversal points; no basemap claims."""
import json

from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import BASE, FS, VIRTUAL, NORTH


def export():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    shape = json.loads((BASE / 'free_order_road_comparison.geojson').read_text(encoding='utf-8'))
    chosen = {'west_B_free_order', 'east_A_free_order'}
    fig, ax = plt.subplots(figsize=(11, 8), constrained_layout=True)
    for f in shape['features']:
        p, g = f['properties'], f['geometry']
        if g['type'] == 'LineString' and p['pattern'] in chosen:
            west = p['pattern'].startswith('west')
            ax.plot(*zip(*g['coordinates']), color='#087e8b' if west else '#aa3c13', lw=1.5,
                    label='Ala ovest 14,163 km' if west else 'Ala est 13,516 km')
    labels = {FS: 'Olgiate FS', VIRTUAL: 'Olgiate sud', NORTH: 'San Zeno / Via Cantu',
              'FROZEN::300063': 'Brivio', 'ASF::ARLATE_CANTINA_PIROVANO': 'Arlate',
              'ASF::CALCO_VIA_GARIBALDI': 'Calco', 'FROZEN::300782': 'Santa Maria',
              'ASF::PEREGO_VIA_STATALE_79': 'Perego'}
    for f in shape['features']:
        p, g = f['properties'], f['geometry']
        if g['type'] == 'Point' and 'site_id' in p:
            x, y = g['coordinates']
            ax.scatter(x, y, color='#38275c', s=20, zorder=4)
            if p['site_id'] in labels:
                offset = (-65, 8) if p['site_id'] == 'FROZEN::300063' else (6, 7)
                ax.annotate(labels[p['site_id']], (x, y), xytext=offset, textcoords='offset points',
                            fontsize=9, bbox={'facecolor': 'white', 'alpha': .8, 'edgecolor': 'none'})
    counter = 0
    for f in shape['features']:
        p, g = f['properties'], f['geometry']
        if p.get('immediate_reversal') and p['pattern'] in chosen:
            counter += 1
            x, y = g['coordinates']
            ax.scatter(x, y, s=110, facecolors='none', edgecolors='#da0040', linewidths=1.5, zorder=6,
                       label='Inversioni nel grafo: da validare' if counter == 1 else None)
            ax.annotate(str(counter), (x, y), xytext=(-14, -14), textcoords='offset points',
                        color='#b00030', weight='bold', fontsize=10)
    assert counter == 6
    ax.set_aspect(1 / .7); ax.margins(.13); ax.set_xticks([]); ax.set_yticks([])
    ax.legend(loc='lower left', fontsize=9)
    fig.suptitle('Ordine libero delle fermate: stessi percorsi minimi delle ali gia usate\n'
                 'Nessun risparmio sulle ali complete attuali; sei inversioni da verificare', fontsize=13)
    fig.supxlabel('Tracciati del grafo congelato, non autorizzazione TPL. Collegamenti FS-locali mantenuti.\n'
                  'Punti viola: siti ipotetici. Cerchi rossi: ritorno immediato sul tratto appena percorso.', fontsize=9)
    fig.savefig(BASE / 'free_order_road_comparison.png', dpi=150, bbox_inches='tight')
    plt.close(fig)


if __name__ == '__main__':
    export()
