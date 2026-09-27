"""Export the illustrative 10-16/H120 comparison, not a selected timetable."""
import copy
import json
from collections import Counter

from scripts.phase2_compare_rt031_line8_deep_offpeak_v3 import OUTPUT, build_problem
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import BASE, FLAGS, verify, events_by_site
from scripts.phase2_probe_rt031_line8_stop_relocation_v3 import digest

LEDGER = BASE/'deep_offpeak_witness.json'


def build():
    result = json.loads(OUTPUT.read_text(encoding='utf-8'))
    if any(result[k] for k in FLAGS) or result['window_selection_authorised']:
        raise ValueError('comparison must not authorise selection')
    case = next(c for c in result['cases'] if c['case_id']=='10_16_h120')
    problem = build_problem(case['midday_window_comparison_min'],case['midday_wait_comparison_min'])
    if verify(problem,case['trips'],case['comparison_peak_windows'],4)!=case['conditional_scenarios']:
        raise ValueError('scenario ledger drift')
    nominal=problem['adjusted'][1.1,.5]
    trips=[]
    for i,t in enumerate(case['trips']):
        loop=nominal[t['loop']]
        trips.append({**t,'trip_index':i,'service_km':problem['family']['loops'][t['loop']]['distance_m']/1000,
                      'fs_return_nominal_min':t['departure_min']+loop['road_minutes'],
                      'events_nominal':[{**e,'departure_min':t['departure_min']+e['offset_from_wing_origin_min']}
                                        for e in loop['events']]})
    if abs(sum(t['service_km'] for t in trips)*260-case['annual_service_km'])>1e-5:
        raise ValueError('annual service ledger mismatch')
    counts=Counter(t['loop'] for t in trips)
    sites={e['stop_place_id'] for t in trips for e in t['events_nominal']}|{'FROZEN::L00407'}
    pool_path=BASE/'partial_services_pool.json'
    pool=json.loads(pool_path.read_text(encoding='utf-8'))
    if sites!=set(pool['reference_site_ids']):raise ValueError('sites changed')
    for name in counts:
        if pool['family']['loops'][name]!=problem['family']['loops'][name]:
            raise ValueError('road geometry source differs from timetable')
    shape_path=BASE/'partial_services_pool.geojson'
    source_shape=json.loads(shape_path.read_text(encoding='utf-8'))
    features=[]
    for feature in source_shape['features']:
        f=copy.deepcopy(feature)
        if f['geometry']['type']=='LineString':
            name=f['properties']['pattern']
            if name not in counts:continue
            f['properties']['daily_trip_count']=counts[name]
        elif f['properties']['site_id'] not in sites:continue
        features.append(f)
    metadata={'contract':'RT031_LINE8_DEEP_OFFPEAK_ILLUSTRATIVE_WITNESS_V3',
              'case_id':case['case_id'],'annual_service_km':case['annual_service_km'],
              'site_count_including_fs':len(sites),'patterns_used':dict(counts),
              'comparison_peak_windows':case['comparison_peak_windows'],
              'offpeak_wait_windows_comparison':case['offpeak_wait_windows_comparison'],
              'source_sha256_normalized_newlines':{'comparison':digest(OUTPUT,True),
                  'pool':digest(pool_path,True),'pool_geojson':digest(shape_path,True)},
              'semantics':'Illustrative least-service-km case among four full-pattern comparisons, not a primary selection. Nominal events x1.1 moving/0.5 minute dwell. Ordered occurrences and local last-occurrence boarding retained; no physical boarding or passenger continuity approval. Same potential walking catchments, reduced midday temporal access. Frozen train targets, not current railway certification.',
              **{k:False for k in FLAGS},'window_selection_authorised':False,
              'actual_timetable_certified':False,'decision_budget_km':None,
              'uncertainty_band_min':None,'approved_uplift_percent':None,'total_operating_km':None}
    row={**metadata,'trips':trips,'nominal_boarding_opportunities':[
        {'site_id':sid,'direction':direction,'opportunities':events}
        for (sid,direction),events in sorted(events_by_site(case['trips'],nominal).items())]}
    return row,{'type':'FeatureCollection','properties':metadata,'features':features}


def export():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    row,shape=build()
    for suffix,data in [('json',row),('geojson',shape)]:
        LEDGER.with_suffix('.'+suffix).write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
    fig,ax=plt.subplots(figsize=(11,7),constrained_layout=True)
    labels={'FROZEN::L00407':'Olgiate FS','RT031::P2V2S_0031_PROJECTED_ROAD_POINT':'Olgiate sud',
            'PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE':'San Zeno / Via Cantu',
            'ASF::CALCO_VIA_GARIBALDI':'Calco','FROZEN::300063':'Brivio / Via Bergamo',
            'ASF::ARLATE_CANTINA_PIROVANO':'Arlate','FROZEN::300398':'Beverate',
            'FROZEN::300782':'Santa Maria','FROZEN::300879':'Rovagnate','ASF::PEREGO_VIA_STATALE_79':'Perego'}
    for f in shape['features']:
        p,g=f['properties'],f['geometry']
        if g['type']=='LineString':
            west=p['pattern'].startswith('west')
            ax.plot(*zip(*g['coordinates']),color='#087e8b' if west else '#aa3c13',lw=1.6,
                    label=('Ovest' if west else 'Est')+f": {p['daily_trip_count']} corse complete")
        else:
            x,y=g['coordinates'];sid=p['site_id']
            ax.scatter(x,y,color='#38275c',s=20,zorder=5)
            if sid in labels:
                ax.annotate(labels[sid],(x,y),xytext=(-140,8) if sid=='FROZEN::300063' else (5,6),
                            textcoords='offset points',fontsize=9,bbox={'facecolor':'white','alpha':.8,'edgecolor':'none'})
    ax.set_aspect(1/.7);ax.margins(.13);ax.set_xticks([]);ax.set_yticks([]);ax.legend(loc='lower left')
    fig.suptitle('Stesso tracciato, 28 siti: 122.340 km/anno di servizio\nH30 in punta; H120 solo 10-16; H60 altrove — confronto non adottato',fontsize=13)
    fig.supxlabel('Geometrie del grafo congelato, non segmenti tra fermate. Paline e manovre autobus da validare.\nRiduzione delle opportunita a meta giornata, non dei bacini pedonali.',fontsize=9)
    fig.savefig(LEDGER.with_suffix('.png'),dpi=150,bbox_inches='tight');plt.close(fig)


if __name__=='__main__':export()
