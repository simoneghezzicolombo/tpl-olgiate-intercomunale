"""Static geographic comparison from pinned road geometry, not a service map."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

from scripts.phase2_audit_rt031_south_road_probe_v3 import rows, FS, VIRTUAL, digest
from scripts.phase2_export_rt031_line8_inclusive_shape_v3 import NORTH
from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import inputs, BASE


def render(graph_dir, output):
    paths=inputs(graph_dir)
    shape=json.loads((BASE/'local_counterflow.geojson').read_text(encoding='utf-8'))
    audit=json.loads((BASE/'local_counterflow.json').read_text(encoding='utf-8'))
    if audit['network_selected'] or shape['properties']['network_selected']:
        raise ValueError('not a non-decisional comparison')
    for key in ('edges','nodes'):
        if digest(paths[key])!=audit['source_sha256'][key]:
            raise ValueError('map road source drift: '+key)
    nodes={n['node_id']:(float(n['lon']),float(n['lat'])) for n in rows(paths['nodes'])}
    roads=[(nodes[e['u_node_id']],nodes[e['v_node_id']]) for e in rows(paths['edges'])]
    lines=[f for f in shape['features'] if f['geometry']['type']=='LineString' and f['properties']['case']=='both']
    base=[f for f in shape['features'] if f['geometry']['type']=='LineString' and f['properties']['case']=='baseline']
    points=[f for f in shape['features'] if f['geometry']['type']=='Point']
    local=[f for f in points if f['properties']['site_id'] in (FS,VIRTUAL,NORTH)]
    fig,axes=plt.subplots(1,2,figsize=(14,6),gridspec_kw={'width_ratios':[1.9,1]},constrained_layout=True)
    for ax,focus,title in zip(axes,(points,local),('Tutti i territori conservati','Dettaglio: passaggi aggiuntivi vicino a FS')):
        coords=[f['geometry']['coordinates'] for f in focus]
        pad=.004 if ax==axes[0] else .003
        xlim=(min(p[0] for p in coords)-pad,max(p[0] for p in coords)+pad)
        ylim=(min(p[1] for p in coords)-pad,max(p[1] for p in coords)+pad)
        ax.add_collection(LineCollection(roads,colors='#e0e4e7',linewidths=.6,zorder=1))
        for i,f in enumerate(base):
            ax.plot(*zip(*f['geometry']['coordinates']),color='#8a9299',lw=5,alpha=.45,
                    label='Tracciati precedenti' if i==0 else None,zorder=2)
        for f in lines:
            p=f['properties']['pattern']; west=p.startswith('west'); morning=p in ('west_A','east_B')
            ax.plot(*zip(*f['geometry']['coordinates']),color='#087e8b' if west else '#aa3c13',
                    lw=1.8,ls='-' if morning else '--',label=f'{"Ovest" if west else "Est"}: {"mattina" if morning else "resto"}',zorder=3)
        for f in points:
            x,y=f['geometry']['coordinates']; sid=f['properties']['site_id']
            islocal=sid in (FS,VIRTUAL,NORTH)
            ax.scatter(x,y,s=48 if islocal else 14,marker='s' if sid==FS else 'D' if islocal else 'o',
                       color='#38275c' if islocal else '#454545',edgecolor='white',lw=.5,zorder=5)
            if islocal:
                name={FS:'Olgiate FS',VIRTUAL:'Olgiate sud',NORTH:'San Zeno / Via Cantù'}[sid]
                offset=(6,-17) if sid==FS else (-120,10) if sid==NORTH and ax==axes[1] else (6,8)
                ax.annotate(name,(x,y),xytext=offset,textcoords='offset points',fontsize=10,
                            bbox=dict(facecolor='white',alpha=.85,edgecolor='none',pad=1),zorder=6)
        if ax==axes[0]:
            labels=[('ASF::PEREGO_VIA_STATALE_79','Perego',(5,6)),
                    ('FROZEN::300879','Rovagnate',(5,6)),('FROZEN::300782','Santa Maria',(5,6)),
                    ('ASF::CALCO_VIA_GARIBALDI','Calco',(5,-14)),
                    ('ASF::ARLATE_CANTINA_PIROVANO','Arlate',(5,6)),
                    ('FROZEN::300398','Beverate',(-55,8)),('FROZEN::300063','Brivio / Via Bergamo',(-100,10))]
            for sid,label,offset in labels:
                matches=[f for f in points if f['properties']['site_id']==sid]
                if matches:
                    f=matches[0]
                    ax.annotate(label,f['geometry']['coordinates'],xytext=offset,textcoords='offset points',
                                fontsize=9,bbox=dict(facecolor='white',alpha=.85,edgecolor='none',pad=1))
        ax.set_xlim(*xlim); ax.set_ylim(*ylim); ax.set_aspect(1/.7)
        ax.set_xticks([]); ax.set_yticks([]); ax.set_title(title,loc='left',fontsize=12)
    axes[0].legend(loc='lower left',fontsize=9)
    fig.suptitle('Linea 8 — confronto con passaggi brevi in entrambi i versi\n'
                 '130.567 km/anno di servizio (+17,2%): confronto, non proposta adottata',fontsize=14)
    fig.supxlabel('Cammini del grafo congelato. 28 siti provvisori; paline, manovre e idoneità autobus non autorizzate.',fontsize=10)
    fig.savefig(output,dpi=150,bbox_inches='tight'); plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--graph_dir',type=Path,required=True)
    p.add_argument('--output',type=Path,default=BASE/'local_counterflow.png')
    a=p.parse_args(); render(a.graph_dir,a.output)
