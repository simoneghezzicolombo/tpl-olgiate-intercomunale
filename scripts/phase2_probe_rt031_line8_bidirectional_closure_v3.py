"""Bounded two-direction comparison on retained ordered service sites, not selection."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from scripts.phase2_probe_rt031_line8_no_reverse_all_orders_v3 import OUTPUT as ROAD
from scripts.phase2_probe_rt031_line8_calco_through_path_v3 import OUTPUT as CALCO
from scripts.phase2_probe_rt031_line8_order_neighbourhood_v3 import reconstruct, access_vector
from scripts.phase2_probe_rt031_line8_manoeuvre_cycles_v3 import split_only_edges
from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import inputs, FS
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter

OUTPUT=ROAD.parent/'bidirectional_closure.json.gz'
SHAPE=ROAD.parent/'bidirectional_closure.geojson'
MAP=ROAD.parent/'bidirectional_closure.png'


def build(graph_dir):
    paths=inputs(graph_dir)
    raw,nodes,rules,attachments=build_graph(paths)
    edges=split_only_edges(raw)
    adapter=FrozenRT017ViaNodeAdapter(edges.values(),rules,unresolved_external_via_way_count=2)
    fs=attachments[FS]['graph_node_id']
    source=json.loads(gzip.decompress(ROAD.read_bytes()))
    calco=next(c for c in json.loads(gzip.decompress(CALCO.read_bytes()))['cases'] if c['reachable'])
    variants={
        'all_29':calco['whole_wing_fixed_order_without_reversals']['loops'],
        'hoe_omission_28_not_adopted':source['hoe_omission_fixed_event_order_comparison_not_adopted']['loops'],
    }
    cases=[]
    for name,forward in variants.items():
        reverse={}
        for wing,loop in forward.items():
            ordered=sorted(loop['events'],key=lambda e:e['path_node_index'],reverse=True)
            reverse[wing]=reconstruct(loop,ordered,edges,adapter,fs,
                calco['candidate_service_node'],False,wing)
        reachable=all(l is not None for l in reverse.values())
        cases.append({'case_id':name,'forward_loops':forward,'reverse_loops':reverse,
            'reverse_reachable_in_represented_graph':reachable,
            'forward_distance_m':sum(l['distance_m'] for l in forward.values()),
            'reverse_distance_m':sum(l['distance_m'] for l in reverse.values()) if reachable else None,
            'forward_access_nominal_by_site':access_vector(forward),
            'reverse_access_nominal_by_site':access_vector(reverse) if reachable else None,
            'same_public_line_comparison':True,'directional_service_variants_adopted':False,
            'physical_platform_sides_certified':False,'full_history_legality_certified':False})
        print(name,reachable,cases[-1]['forward_distance_m'],cases[-1]['reverse_distance_m'],flush=True)
    coordinates={n:[float(r['lon']),float(r['lat'])] for n,r in nodes.items()}
    register=json.loads(gzip.decompress((ROAD.parent/'stop_plan_and_additions.json.gz').read_bytes()))
    coordinates.update({r['graph_node_id']:r['road_coordinates'] for r in register['register']})
    features=[]
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import math
    fig,axes=plt.subplots(1,2,figsize=(14,6))
    for ax,c in zip(axes,cases):
        for direction,key,color,style in [('F','forward_loops','#e57c22','-'),('R','reverse_loops','#157da4','--')]:
            for wing,loop in c[key].items():
                if loop is None:continue
                path=loop['edge_ids']
                xy=[coordinates[edges[path[0]]['u_node_id']]]+[
                    coordinates[edges[e]['v_node_id']] for e in path]
                features.append({'type':'Feature','properties':{'case_id':c['case_id'],
                    'direction':direction,'wing':wing,'public_line_count':1,'adopted':False},
                    'geometry':{'type':'LineString','coordinates':xy}})
                ax.plot(*zip(*xy),color=color,ls=style,lw=1.4,
                    label=direction if wing=='west_B' else None)
                if direction=='F':
                    pts=[xy[e['path_node_index']] for e in loop['events']]
                    ax.scatter(*zip(*pts),s=10,color='#333333',zorder=3)
        ax.scatter(*coordinates[fs],color='red',s=25,zorder=4)
        ax.annotate('Olgiate FS',coordinates[fs],xytext=(5,5),textcoords='offset points',fontsize=8)
        ax.set_title(('29 siti, Hoè conservata' if c['case_id']=='all_29' else '28 siti, sola Hoè esclusa — non adottato')+
            f"\nF {c['forward_distance_m']/1000:.3f} km · R {c['reverse_distance_m']/1000:.3f} km")
        ax.set_aspect(1/math.cos(math.radians(45.73)));ax.legend()
    fig.suptitle('Una Linea 8, confronto dei due versi ricostruiti sul grafo\nAccosti, manovra FS e idoneità autobus non certificati')
    fig.tight_layout();fig.savefig(MAP,dpi=150);plt.close(fig)
    SHAPE.write_text(json.dumps({'type':'FeatureCollection','features':features},sort_keys=True)+'\n',encoding='utf-8')
    return {'contract':'RT031_LINE8_BIDIRECTIONAL_CLOSURE_DIAGNOSTIC_V3',
        'road_source_sha256':hashlib.sha256(ROAD.read_bytes()).hexdigest(),
        'calco_source_sha256':hashlib.sha256(CALCO.read_bytes()).hexdigest(),
        'cases':cases,
        'semantics':'Reconstruct reversed ordered service-event visits on the directed represented '
            'graph, not reverse a polyline. Same FS boundary directed edges, no internal FS, '
            'no immediate reversals, Calco19m unadopted hypothesis. Both local occurrences '
            'remain distinct. Inventory coordinates do not certify opposite boarding sides. '
            'Two full-route directions are a newly authorised comparison, not caller adoption. '
            'No demand inference, empirical connection probability or primary selection.',
        'network_selected':False,'primary_selection_authorised':False,
        'runner_up_selection_authorised':False,'decision_budget_km':None,'uncertainty_band_min':None}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--graph_dir',type=Path,required=True)
    a=p.parse_args();r=build(a.graph_dir)
    OUTPUT.write_bytes(gzip.compress((json.dumps(r,ensure_ascii=False,sort_keys=True,
        separators=(',',':'))+'\n').encode('utf-8'),mtime=0))
