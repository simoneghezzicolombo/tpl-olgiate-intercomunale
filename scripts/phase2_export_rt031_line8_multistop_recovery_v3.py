"""Diagnostic map: actual shorter graph path, omitted sites, six hypothetical replacements."""
import json
from scripts.phase2_probe_rt031_line8_multistop_recovery_v3 import OUTPUT, FS, VIRTUAL, NORTH
from scripts.phase2_check_rt031_line8_multistop_recovery_v3 import OUTPUT as TIMETABLE


def export():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    r=json.loads(OUTPUT.read_text(encoding='utf-8'))
    t=json.loads(TIMETABLE.read_text(encoding='utf-8'))['case']
    shape=json.loads(OUTPUT.with_suffix('.geojson').read_text(encoding='utf-8'))
    fig,ax=plt.subplots(figsize=(11,7),constrained_layout=True)
    names={FS:'Olgiate FS',VIRTUAL:'Olgiate sud',NORTH:'San Zeno / Via Cantu',
           'FROZEN::300063':'Brivio / Via Bergamo', 'ASF::ARLATE_CANTINA_PIROVANO':'Arlate',
           'ASF::CALCO_VIA_GARIBALDI':'Calco', 'FROZEN::300782':'S. Maria Hoe',
           'FROZEN::300873':'Hoe', 'ASF::PEREGO_VIA_STATALE_79':'Perego'}
    for f in shape['features']:
        p,g=f['properties'],f['geometry']
        if g['type']=='LineString' and p['pattern'] in ('west_B','east_A'):
            west=p['pattern'].startswith('west')
            ax.plot(*zip(*g['coordinates']),color='#087e8b' if west else '#aa3c13',lw=1.7,
                    label='Ovest: geometria accorciata' if west else 'Est: geometria accorciata')
    kinds=set()
    for f in shape['features']:
        p,g=f['properties'],f['geometry']
        if g['type']!='Point':continue
        x,y=g['coordinates']
        if 'new_road_node' in p:
            kind='Nuovo punto ipotetico';marker='s';color='#0059c7';size=42
            label='N'+str(r['added_road_nodes'].index(p['new_road_node'])+1)
            offset=(5,-13)
        else:
            kept=p['retained'];kind='Sito mantenuto' if kept else 'Sito escluso'
            marker='o' if kept else 'x';color='#38275c' if kept else '#c40036';size=22 if kept else 65
            label=names.get(p['site_id'],'');offset=(-115,5) if p['site_id'] in ('FROZEN::300782','FROZEN::300063') else (5,5)
        ax.scatter(x,y,marker=marker,color=color,s=size,zorder=5,label=kind if kind not in kinds else None)
        kinds.add(kind)
        if label:
            ax.annotate(label,(x,y),xytext=offset,textcoords='offset points',fontsize=8,color=color,
                        bbox={'facecolor':'white','alpha':.8,'edgecolor':'none'})
    ax.set_aspect(1/.7);ax.margins(.13);ax.set_xticks([]);ax.set_yticks([]);ax.legend(loc='lower left',fontsize=8)
    fig.suptitle(f"Sei fermate ipotetiche sulla scorciatoia: {t['annual_service_km']:,.0f} km/anno\n"
                 'H30/H60 ricalcolati; copertura ancora penalizzata — confronto NON adottato',fontsize=13)
    fig.supxlabel('Geometrie effettive del grafo congelato. Nessuna autorizzazione di paline o manovre.\n'
                  'I nuovi punti non sostituiscono integralmente i bacini pedonali dei siti esclusi.',fontsize=9)
    fig.savefig(OUTPUT.with_suffix('.png'),dpi=150,bbox_inches='tight');plt.close(fig)


if __name__=='__main__':export()
