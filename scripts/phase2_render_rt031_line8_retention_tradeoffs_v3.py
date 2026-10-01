"""Geographic witness of a bounded retention comparison, not a selected line."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from scripts.phase2_audit_rt031_south_road_probe_v3 import rows, digest, FS, VIRTUAL
from scripts.phase2_export_rt031_line8_inclusive_shape_v3 import NORTH
from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import BASE, inputs


def render(graph_dir,output,case_id=None):
    a=json.loads((BASE/'retention_tradeoffs.json').read_text(encoding='utf-8'))
    if a['network_selected']:
        raise ValueError('non-decisional source required')
    cid=case_id or a['minimum_distance_case_id']
    case=next(c for c in a['cases'] if c['case_id']==cid)
    shape=json.loads((BASE/'retention_tradeoffs.geojson').read_text(encoding='utf-8'))
    baseline=json.loads((BASE/'local_counterflow.geojson').read_text(encoding='utf-8'))
    paths=inputs(graph_dir)
    for k in ('nodes','edges'):
        if digest(paths[k])!=a['source_sha256'][k]:
            raise ValueError('map source drift')
    nodes={r['node_id']:(float(r['lon']),float(r['lat'])) for r in rows(paths['nodes'])}
    road_segments=[(nodes[r['u_node_id']],nodes[r['v_node_id']]) for r in rows(paths['edges'])]
    fig,ax=plt.subplots(figsize=(12,7.5),constrained_layout=True)
    ax.add_collection(LineCollection(road_segments,colors='#e1e5e8',linewidths=.5,zorder=1))
    old=[f for f in baseline['features'] if f['geometry']['type']=='LineString' and f['properties']['case']=='both']
    for i,f in enumerate(old):
        ax.plot(*zip(*f['geometry']['coordinates']),color='#92999e',lw=5,alpha=.55,
                label='Correzione completa prima dei tagli' if i==0 else None,zorder=2)
    lines=[f for f in shape['features'] if f['geometry']['type']=='LineString' and f['properties']['case_id']==cid]
    if len(lines)!=4:
        raise ValueError('requested case geometry not exported')
    for f in lines:
        pattern=f['properties']['pattern']; west=pattern.startswith('west'); am=pattern in ('west_A','east_B')
        ax.plot(*zip(*f['geometry']['coordinates']),color='#087e8b' if west else '#a93f13',
                ls='-' if am else '--',lw=2,label=('Ovest' if west else 'Est')+(' mattina' if am else ' resto'),zorder=3)
    gained=set(case['gained_inventory_site_ids'])
    points=[f for f in shape['features'] if f['geometry']['type']=='Point'
            and (f['properties'].get('original_reference_site',True) or f['properties']['site_id'] in gained)]
    lost=set(case['lost_original_site_ids'])
    labels={FS:'Olgiate FS',VIRTUAL:'Olgiate sud',NORTH:'San Zeno / Via Cantù',
            'FROZEN::300063':'Brivio / Via Bergamo','FROZEN::300398':'Beverate',
            'ASF::CALCO_VIA_GARIBALDI':'Calco','ASF::ARLATE_CANTINA_PIROVANO':'Arlate',
            'FROZEN::300879':'Rovagnate','ASF::PEREGO_VIA_STATALE_79':'Perego','FROZEN::300782':'Santa Maria Hoè'}
    for f in points:
        x,y=f['geometry']['coordinates']; sid=f['properties']['site_id']; missing=sid in lost
        ax.scatter(x,y,marker='x' if missing else '+' if sid in gained else 's' if sid==FS else 'D' if sid in (NORTH,VIRTUAL) else 'o',
                   color='#c22d2d' if missing else '#c77400' if sid in gained else '#3b315c' if sid in (FS,NORTH,VIRTUAL) else '#404040',
                   s=80 if missing else 45 if sid in (FS,NORTH,VIRTUAL) else 15,zorder=5)
        if missing or sid in labels or sid in gained:
            label=('ESCLUSO: '+f['properties']['name']) if missing else ('ALTRO SITO: '+f['properties']['name']) if sid in gained else labels[sid]
            if missing:
                label=label.replace('Santa Maria Hoè - ','S. Maria: ').replace('Brivio - ','Brivio: ')
            offset=(-150,12) if sid=='FROZEN::300063' else (6,-16) if sid in (FS,'ASF::CALCO_VIA_GARIBALDI') else (6,8)
            ax.annotate(label,(x,y),xytext=offset,textcoords='offset points',fontsize=9,
                color='#a32121' if missing else '#222222',bbox=dict(facecolor='white',alpha=.88,edgecolor='none',pad=1),zorder=6)
    xy=[f['geometry']['coordinates'] for f in points]
    ax.set_xlim(min(p[0] for p in xy)-.003,max(p[0] for p in xy)+.004)
    ax.set_ylim(min(p[1] for p in xy)-.003,max(p[1] for p in xy)+.003)
    ax.set_aspect(1/.7); ax.set_xticks([]); ax.set_yticks([])
    km=case['annual_service_km']; pct=(km/a['reference_cap_unchanged']-1)*100
    ax.set_title(f'Confronto con esclusioni limitate — {km:,.0f} km/anno ({pct:+.1f}%)\n'
                 f'{case["retained_site_count"]} siti iniziali su 28 + {len(gained)} altri; minimo km del dominio, NON linea selezionata',loc='left',fontsize=12)
    ax.legend(loc='lower left',fontsize=9)
    fig.supxlabel('Grafo congelato; paline e idoneità autobus da validare. I km escludono deposito e riposizionamenti.',fontsize=10)
    fig.savefig(output,dpi=150,bbox_inches='tight'); plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--graph_dir',type=Path,required=True)
    p.add_argument('--case_id'); p.add_argument('--output',type=Path,default=BASE/'retention_tradeoffs.png')
    a=p.parse_args(); render(a.graph_dir,a.output,a.case_id)
