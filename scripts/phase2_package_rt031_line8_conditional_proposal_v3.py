"""One coherent conditional delivery example, explicitly not a network selection.

Consolidates the previously disclosed 17-trip east-first example. It does not
rank networks, adopt stop exclusions, infer a budget, or publish a timetable.
"""
import gzip
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path

from scripts.phase2_probe_rt031_line8_paired_cuts_v3 import OUTPUT as CUTS, SHAPE as ALL_SHAPES
from scripts.phase2_close_rt031_line8_maximum_hold_v3 import OUTPUT as HOLD
from scripts.phase2_probe_rt031_line8_variable_fs_hold_v3 import ordered_stop_ledger
from scripts.phase2_rebuild_rt031_uniform_complete_line_v3 import inputs, source_fingerprints

ROOT=Path(__file__).resolve().parents[1]
OUT=CUTS.parent/'conditional_proposal_17_trips.json'
SHAPE=CUTS.parent/'conditional_proposal_17_trips.geojson'
MAP=CUTS.parent/'conditional_proposal_17_trips.png'
DOC=ROOT/'docs/RT031_LINEA8_SCHEDA_UNICA_CONDIZIONATA_V3.md'
FS='FROZEN::L00407'
OMITTED=['FROZEN::300634','FROZEN::300873']


def read(path):
    raw=path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix=='.gz' else raw),raw


def clock(minute):
    seconds=round(minute*60)
    return f'{seconds//3600:02d}:{seconds//60%60:02d}:{seconds%60:02d}'


def build():
    paths=dict(cuts=CUTS,maximum_hold=HOLD,all_shapes=ALL_SHAPES,
        register=CUTS.parent/'stop_plan_and_additions.json.gz',
        authority=ROOT/'config/rt031_16_full_trips_authority_v3.json',
        requirements=ROOT/'config/rt031_requirements_audit_v3.json',
        localities=ROOT/'config/rt031_caller_locality_itinerary_preference_v3.json')
    data={};hashes={}
    for key,path in paths.items():
        data[key],raw=read(path);hashes[key]=hashlib.sha256(raw).hexdigest()
    for key in ('cuts','maximum_hold','authority'):
        if any(data[key][flag] for flag in ('network_selected','primary_selection_authorised','runner_up_selection_authorised')):
            raise ValueError('delivery example cannot silently overwrite upstream selection authority')
    if data['authority']['full_commercial_trips_per_day_adopted']!=16:
        raise ValueError('caller trip authority changed; review the conditional example')
    if data['maximum_hold']['cut_source_sha256']!=hashes['cuts']:
        raise ValueError('stale holding proof')
    index=next(i for i,c in enumerate(data['cuts']['cases']) if c['omitted_stop_ids']==OMITTED)
    candidate=data['cuts']['cases'][index]
    timing_index=next(i for i,t in enumerate(candidate['extra_trip_count_comparisons_not_adopted'])
                      if t['full_trip_count']==17 and t['first_wing']=='east_A')
    timing=candidate['extra_trip_count_comparisons_not_adopted'][timing_index]
    if not timing['witness_found'] or not timing['holding_objective_proven_optimal']:
        raise ValueError('disclosed 17-trip sum-holding example not supported')
    _,policy,_,_,_=inputs()
    if candidate['timetable_source_fingerprints']!=source_fingerprints(policy,candidate['loops']):
        raise ValueError('stale consumed timetable policy')
    proof_index=next(i for i,c in enumerate(data['maximum_hold']['cases']) if c['geometry_case_id']==candidate['case_id']
                     and c['first_wing']=='east_A')
    proof=data['maximum_hold']['cases'][proof_index]
    if not proof['maximum_holding_objective_proven_optimal']:
        raise ValueError('minimax proof absent; do not replace it with sum optimum')
    coords={f['properties']['wing']:f['geometry']['coordinates']
            for f in data['all_shapes']['features'] if f['properties']['case_id']==candidate['case_id']}
    if set(coords)!=set(candidate['loops']):raise ValueError('incomplete graph shape')
    first,second='east_A','west_B'
    if coords[first][-1]!=coords[second][0] or coords[first][0]!=coords[second][-1]:
        raise ValueError('complete itinerary does not join at FS')
    registry={s['site_id']:s for s in data['register']['register']}
    sites={FS:dict(site_id=FS,name=registry[FS]['name'],municipality=registry[FS]['municipality'],
        coordinates_lon_lat=coords[first][0],kind='INVENTORY_HUB',ordered_occurrences=[],
        boarding_authorised=False,physical_platform_count=None)}
    for wing in (first,second):
        for e in sorted(candidate['loops'][wing]['events'],key=lambda e:e['path_node_index']):
            sid=e['stop_place_id'];source=registry.get(sid)
            if sid not in sites:
                name=source['name'] if source else 'Arlate — ipotesi N1212'
                sites[sid]=dict(site_id=sid,name=name.replace('Ho\ufffd','Hoè'),
                    source_name_raw=name,municipality=source['municipality'] if source else 'Calco',
                    coordinates_lon_lat=coords[wing][e['path_node_index']],
                    kind=('PROPOSED_ARLATE_N1212' if source is None else
                          'PROPOSED_LOCAL_SITE' if source['inventory_coordinates'] is None else 'INVENTORY_SITE'),
                    inventory_coordinates_lon_lat=source['inventory_coordinates'] if source else None,
                    nominal_fs_access_min=candidate['retained_access_nominal_by_site'][sid],
                    ordered_occurrences=[],boarding_authorised=False,physical_platform_count=None)
            sites[sid]['ordered_occurrences'].append(dict(wing=wing,**{k:e[k] for k in
                ('occurrence_id','path_node_index','incoming_edge','outgoing_edge')}))
    if len(sites)!=27 or any(s in sites for s in OMITTED):raise ValueError('wrong served-event set')
    ledger=ordered_stop_ledger(candidate['loops'],first,timing['full_trips'])
    for site in sites.values():
        if site['site_id']==FS:continue
        opportunities=[]
        for number,(trip,entry) in enumerate(zip(timing['full_trips'],ledger),1):
            visits=[e for e in entry['events'] if e.get('site_id')==site['site_id']]
            earliest=min(visits,key=lambda e:e['full_path_edge_index'])
            latest=max(visits,key=lambda e:e['full_path_edge_index'])
            origin=(trip['first_fs_min'] if earliest['wing']==first else trip['second_fs_min'])
            fs_arrival=(next(e['arrival_min'] for e in entry['events']
                           if e['role']=='INTERMEDIATE_FS_STAY_ONBOARD_DESIGN')
                        if latest['wing']==first else entry['events'][-1]['arrival_min'])
            opportunities.append(dict(full_trip_number=number,wing=earliest['wing'],
                from_fs_departure_min=origin,from_fs_alight_min=earliest['alight_event_min'],
                from_fs_alight_occurrence_id=earliest['occurrence_id'],
                to_fs_board_min=latest['board_event_min'],to_fs_arrival_min=fs_arrival,
                to_fs_board_occurrence_id=latest['occurrence_id'],
                physical_boarding_authorised=False))
        site['station_journey_opportunities_nominal']=opportunities
    public_shape=coords[first]+coords[second][1:]
    features=[dict(type='Feature',properties=dict(role='COMPLETE_PUBLIC_ITINERARY_EXAMPLE',
        public_route_name='Linea 8',adopted=False,full_history_legality_certified=False),
        geometry=dict(type='LineString',coordinates=public_shape))]
    for wing in (first,second):
        features.append(dict(type='Feature',properties=dict(role='WING_OF_SAME_LINE',wing=wing,adopted=False),
            geometry=dict(type='LineString',coordinates=coords[wing])))
    for site in sites.values():
        features.append(dict(type='Feature',properties=dict(role='DESIGN_SITE',site_id=site['site_id'],
            name=site['name'],kind=site['kind'],boarding_authorised=False,
            physical_platform_count=None,ordered_occurrences=site['ordered_occurrences']),
            geometry=dict(type='Point',coordinates=site['coordinates_lon_lat'])))
    case_pointer=f'/cases/{index}/extra_trip_count_comparisons_not_adopted/{timing_index}'
    statuses={
        'railway_interchange':('MODEL_SUPPORTED_CURRENT_TRAINS_UNVERIFIED','cuts',case_pointer,
            '20 archived bindings;17/22 old targets compatible; not all original targets or current trains certified.'),
        'peak_service':('MODEL_SUPPORTED_PHASES_NOT_ADOPTED','cuts',case_pointer,
            'Four H30 banks of five trains, with east/west phases explicitly different.'),
        'deep_offpeak':('COMPARISON_NOT_ADOPTED','cuts',case_pointer,'H120 only10-16; H60 readiness outside, not constant all-day headway.'),
        'territorial_service':('LOSSES_EXPLICIT_ACCEPTANCE_PENDING','cuts',f'/cases/{index}',
            'Conditional 5/8/10-minute walk coverage in all five municipalities; no permissible loss threshold invented.'),
        'local_districts':('ORDERED_POINT_EVENTS_SUPPORTED_DISTRICTS_UNVERIFIED','cuts',f'/cases/{index}/loops',
            'Olgiate south and San Zeno each have two ordered events; whole areas and platforms not certified.'),
        'recognisable_line':('ONE_COMPLETE_PATH_EXAMPLE_OPERATION_UNVERIFIED','cuts',case_pointer,
            'One line, both wings every trip, same path/event sequence; FS onboard continuity remains a design assumption.'),
        'budget':('EXCEEDS_REFERENCE_AND_SPECIFIC_COMPARISON_NOT_ADOPTED','cuts',case_pointer,
            '120323.896 service km on260 assumed days; not a declared cap or financed service.'),
        'service_span':('NOMINAL_EXAMPLE_SUPPORTED','cuts',case_pointer,
            'First root06:05, last root19:40, final FS about21:09; each site has its own first/last events.'),
        'calendar':('NOT_ADOPTED','authority','/annual_service_days_comparison','260 identical days, no dated calendar or double weekend deduction.'),
        'fleet':('CONDITIONAL_MODEL_AVAILABILITY_UNVERIFIED','cuts',case_pointer,
            'At most four in27 deterministic scenarios; no vehicle availability, depot or driver-duty approval.'),
        'runtime_dwell_recovery':('DETERMINISTIC_NOT_EMPIRICAL','cuts',case_pointer,
            '9 runtime/dwell and3 recovery values; neither probability nor observed reliability.'),
        'rail_margins':('ASSUMPTIONS_UNVERIFIED_ON_FIELD','cuts',case_pointer,
            'AM transfer3min and inherited wait ceiling; PM departures3-8min after train; margins not measured.'),
        'road_and_boarding':('VALIDATION_PENDING','cuts',f'/cases/{index}/loops',
            'Directed frozen graph, represented via-node rules, no immediate reversal within wings; not full-history/bus/platform certification.'),
    }
    reqs=[]
    for req in data['requirements']['requirements']:
        status,key,pointer,semantics=statuses[req['id']]
        reqs.append(dict(requirement_id=req['id'],classification=req['classification'],status=status,
            source_path=str(paths[key].relative_to(ROOT)).replace('\\','/'),source_sha256=hashes[key],
            source_json_pointer=pointer,semantics=semantics,
            authority_context_source_path=str(paths['authority'].relative_to(ROOT)).replace('\\','/'),
            authority_context_sha256=hashes['authority']))
    omitted=[dict(site_id=s,name=registry[s]['name'],municipality=registry[s]['municipality'],
                  coordinates_lon_lat=registry[s]['road_coordinates'],omission_adopted=False) for s in OMITTED]
    return dict(contract='RT031_LINE8_CONDITIONAL_SINGLE_DELIVERY_EXAMPLE_V3',
        status='CONSOLIDATED_CONDITIONAL_EXAMPLE_NOT_SELECTED_OR_APPROVED',
        documented_example_reason='Consolidate the previously disclosed east-first17-trip example; no new ranking or normative selection.',
        source_sha256=hashes,source_paths={k:str(p.relative_to(ROOT)).replace('\\','/') for k,p in paths.items()},
        timetable_source_json_pointer=case_pointer,public_route_name='Linea 8',
        minimum_hold_source_json_pointer=f'/cases/{proof_index}',
        wing_sequence=[first,second],full_trips_per_comparison_day=17,
        caller_adopted_full_trips_per_day=data['authority']['full_commercial_trips_per_day_adopted'],
        full_trip_count_change_adopted=False,stop_omissions_adopted=False,
        inventory_site_count_including_fs=sum(s['kind'].startswith('INVENTORY') for s in sites.values()),
        proposed_site_count=sum(s['kind'].startswith('PROPOSED') for s in sites.values()),
        served_design_site_count_including_fs=len(sites),
        physical_platform_count=None,served_sites=list(sites.values()),omitted_sites=omitted,
        nonhub_ordered_occurrence_count_per_trip=sum(len(l['events']) for l in candidate['loops'].values()),
        loops=candidate['loops'],ordered_stop_event_ledger_nominal=ledger,
        full_trips=timing['full_trips'],selected_train_banks_example_not_adopted=timing['selected_real_train_banks_not_adopted'],
        old_rail_objective_compatibility=timing['original_22_target_compatibility_full_timetable'],
        coverage_fraction=candidate['potential_walking_access_fraction'],
        coverage_loss_percentage_points=candidate['potential_walking_access_loss_percentage_points'],
        municipality_names=data['cuts']['municipality_names'],requirements=reqs,
        desired_localities_not_automatically_certified=data['localities']['desired_sequence'],
        annual_service_km_260_day_comparison=timing['annual_service_km_260_day_comparison'],
        annual_service_days_comparison=260,calendar_adopted=False,
        readiness_windows_min=[[timing['ready_start_min'],600,60],[600,960,120],[960,1180,60]],
        annual_noncommercial_km=None,complete_operator_cost=None,
        delta_km_vs_reference=timing['annual_service_km_260_day_comparison']-111419,
        delta_percent_vs_reference=(timing['annual_service_km_260_day_comparison']/111419-1)*100,
        maximum_intermediate_fs_hold_nominal_min=timing['maximum_intermediate_fs_onboard_wait_nominal_min'],
        minimum_possible_maximum_hold_over_nine_scenarios_min=proof['maximum_fs_onboard_hold_over_nine_scenarios_min'],
        vehicle_cases_conditional=timing['vehicle_cases_conditional'],
        final_nominal_return_min=ledger[-1]['events'][-1]['arrival_min'],
        complete_historical_conversation_audit_claimed=False,
        ready_for_final_recommendation=False,ready_for_public_timetable=False,
        physical_passenger_continuity_certified=False,full_history_legality_certified=False,
        physical_boarding_authorised=False,demand_weighted_gjt_improvement_min=None,
        missed_connection_probability=None,decision_budget_km=None,uncertainty_band_min=None,
        unsupported_metric_semantics=dict(
            demand_weighted_gjt_improvement_min='Municipal work OD not spatially downscaled to routes/passengers; no inferred demand weights.',
            missed_connection_probability='Stage E RT001 V3 engineering retention and deterministic stress misses are not empirical missed-connection probability.'),
        network_selected=False,primary_selection_authorised=False,runner_up_selection_authorised=False),dict(type='FeatureCollection',features=features)


def document(r):
    lines=['# Linea 8 — scheda unica di proposta condizionata','',
        'Una sola scheda consolida il confronto già mostrato: **17 corse complete al giorno, 27 siti di progetto, 120.324 km/anno su 260 giorni ipotizzati (+8%)**. Non è una rete selezionata, un aumento di budget autorizzato o un orario pubblicabile. L\'esempio est→ovest non è un nuovo vincitore Pareto; l\'alternativa ovest→est resta nei confronti sorgente.','',
        '![Tracciato della stessa Linea 8](../outputs/phase2/rt031_line8_local_shortcuts_v3/conditional_proposal_17_trips.png)','',
        '## Servizio proposto nell’esempio','',
        'Un solo nome pubblico: **Linea 8**. Ogni corsa parte da FS, percorre l’ala est, richiama FS con prosecuzione progettata a bordo, percorre l’ala ovest e torna a FS. Stesso percorso e stesse occorrenze per tutte le 17 corse; nessuna corsa limitata a una sola ala. Le ali non sono due linee. Continuità fisica/operativa e manovra in stazione restano da verificare.','',
        'H30 per quattro gruppi ferroviari di cinque treni, con finestre diverse fra le ali; H60 come cap di readiness nelle spalle, H120 solo10–16. Non significa H30 per tutto il giorno, H30 comune alle stesse ore in tutte le frazioni o intervalli esattamente60 minuti per tutta la morbida. I treni sono quelli congelati del modello, non orari odierni verificati.','',
        'Finestre di readiness dell’esempio: 06:50–10:00 limite 60 min, 10:00–16:00 limite 120 min, 16:00–19:40 limite 60 min. Per chi è pronto a partire in queste fasce, il modello verifica un’opportunità di viaggio entro quel limite. Sono assunzioni ingegneristiche esplicite, non la fascia di salita identica a ogni fermata.','',
        '| Gruppo | Treni archiviati | Partenze dell’ala da FS |','|---|---|---|']
    for bank in r['selected_train_banks_example_not_adopted']:
        label=('Est' if bank['wing']=='east_A' else 'Ovest')+(' → Milano' if bank['kind']=='bus_to_rail' else ' ← Milano')
        lines.append(f"| {label} | {clock(bank['rail_minutes'][0])[:5]}–{clock(bank['rail_minutes'][-1])[:5]} | "+', '.join(clock(t)[:5] for t in bank['bus_departures_min'])+' |')
    lines+=['','## Tutti i27 siti, non27 paline approvate','',
        '24 identità di inventario inclusa FS e tre punti proposti: Olgiate sud, San Zeno/Via Cantù e Arlate N1212. I due punti locali hanno ciascuno due occorrenze ordinate per corsa. Posizione/lato di accosto, numero di paline e accessibilità reale sono ancora non approvati. Tempi relativi nominali del passaggio più favorevole, esclusi cammino e attesa iniziale; ledger completo nel JSON.','',
        '| Sito | Comune da inventario | Tipo | FS→sito min | Sito→FS min |','|---|---|---|---:|---:|']
    for s in r['served_sites']:
        a=s.get('nominal_fs_access_min');out=f"{a['from_fs_min']:.2f}" if a else '—';back=f"{a['to_fs_min']:.2f}" if a else '—'
        kind='Nuovo punto ipotizzato' if s['kind'].startswith('PROPOSED') else 'Inventario'
        lines.append(f"| {s['name']} | {s['municipality']} | {kind} | {out} | {back} |")
    lines+=['','**Due esclusioni soltanto nell’esempio, non adottate:** Hoè (`FROZEN::300873`) e Calco–via Nazionale (`FROZEN::300634`). La fermata Via Nazionale/Peugeot è una diversa identità conservata; il suo comune è quello dell’inventario, non dedotto dal nome.','',
        '## Copertura potenziale dei cinque comuni','',
        '| Comune | Entro5min | Entro8min | Entro10min | Perdita5/8/10min, punti percentuali |',
        '|---|---:|---:|---:|---|']
    for code in (*r['municipality_names'],'TOTAL'):
        row=r['coverage_fraction'][code];loss=r['coverage_loss_percentage_points'][code]
        values=[f'{float(Fraction(row[k]))*100:.2f}%' for k in ('5','8','10')]
        lines.append('| '+r['municipality_names'].get(code,'Totale')+' | '+' | '.join(values)+' | '+
                     '/'.join(f'{loss[k]:.2f}' for k in ('5','8','10'))+' |')
    lines+=['','Conteggi geografici su substrato pedonale congelato; non OD, domanda passeggeri o accessibilità fisica certificata. Il punto Olgiate sud non certifica l’intero perimetro provvisorio. Monticello/Mondonico, Calco alta/Cornello, Cassina, Crescenzaga, oratorio e Casa di Comunità mantengono le associazioni non certificate del dossier precedente.','',
        '## Orario nominale completo, non per pubblicazione','',
        '| Corsa completa | FS verso est | FS intermedia verso ovest | Ritorno finale FS |','|---:|---|---|---|']
    for i,(trip,ledger) in enumerate(zip(r['full_trips'],r['ordered_stop_event_ledger_nominal']),1):
        lines.append(f"| {i} | {clock(trip['first_fs_min'])} | {clock(trip['second_fs_min'])} | {clock(ledger['events'][-1]['arrival_min'])} |")
    lines+=['','Ogni sito ha eventi di salita/discesa e prima/ultima opportunità propri nel ledger; la fascia alla radice FS non viene attribuita identica a tutte le fermate. Sono compatibili 17 dei 22 vecchi obiettivi ferroviari; i cinque non compatibili sono espliciti qui sotto.','',
        '| Ala | Obiettivo originario non coperto | Ora del treno archiviato |','|---|---|---|']
    for missing in r['old_rail_objective_compatibility']['missing']:
        lines.append('| '+('Est' if missing['wing']=='east' else 'Ovest')+' | '+
            ('Bus → treno Milano' if missing['kind']=='bus_to_rail' else 'Treno da Milano → bus')+
            ' | '+clock(missing['rail_min'])[:5]+' |')
    lines+=['',
        '### Prima e ultima opportunità per sito','',
        'Da FS: partenza alla stazione verso il sito. Per FS: salita al sito nell’occorrenza ordinata più vicina al successivo arrivo in stazione. Non si confondono i due passaggi di un punto locale. Orari nominali, non coincidenze ferroviarie garantite.','',
        '| Sito | Partenza da FS: prima–ultima | Salita al sito per FS: prima–ultima |','|---|---|---|']
    for site in r['served_sites']:
        if site['site_id']==FS:continue
        opp=site['station_journey_opportunities_nominal'];a,b=opp[0],opp[-1]
        lines.append(f"| {site['name']} | {clock(a['from_fs_departure_min'])}–{clock(b['from_fs_departure_min'])} | {clock(a['to_fs_board_min'])}–{clock(b['to_fs_board_min'])} |")
    lines+=['',
        '## Risorse e limiti che restano aperti','',
        f"- {r['annual_service_km_260_day_comparison']:.3f} km commerciali, {r['delta_km_vs_reference']:.3f} sopra111.419.260 giorni non sono un calendario adottato; km non commerciali e costi completi non disponibili.",
        '- I17 giri non sostituiscono formalmente i16 adottati. Nessun finanziamento o incremento generale di budget è dichiarato.',
        '- Quattro mezzi al massimo nei27 scenari deterministici dell’esempio, non prova di disponibilità o turni operatore.',
        f"- Sosta massima nominale FS {r['maximum_intermediate_fs_hold_nominal_min']:.2f}min; minimo possibile della massima nei nove scenari {r['minimum_possible_maximum_hold_over_nine_scenarios_min']:.2f}min nel dominio verificato. Non probabilità o garanzia reale.",
        '- Restano viaggi lunghi: Scarpone→FS circa30,24min, Beverate/Cariplo31,10 e Peugeot32,56. Nessuna soglia inventata per dichiararli buoni.',
        '- Regole via-node rappresentate e assenza di inversioni immediate dentro le ali non certificano idoneità autobus, manovra FS, restrizioni a storia completa o paline.',
        '','## Stato della consegna','',
        '**Scheda consolidata pronta per confronto istruttorio; non proposta finale approvata né orario per l’utenza.** Il JSON collega tutti i13 requisiti dell’audit vigente alla fonte consumata e alla semantica, senza dichiarare una certificazione di tutte le chat storiche.','',
        'Restano da decidere i17 giri, i due tagli e le perdite, il costo aggiuntivo specifico, le fasi ferroviarie e l’accettabilità dei tempi. Poi servono calendario, turni e verifiche stradali/di fermata. Questa scheda non invia email, non sceglie PRIMARY/RUNNER-UP e non nasconde quei punti sotto la parola “finale”.','',
        '`network_selected=false`; `primary_selection_authorised=false`; `runner_up_selection_authorised=false`; `decision_budget_km=null`; `uncertainty_band_min=null`.','',
        '[Scheda machine-readable con ledger integrale](../outputs/phase2/rt031_line8_local_shortcuts_v3/conditional_proposal_17_trips.json) · [Tracciato e27 punti GeoJSON](../outputs/phase2/rt031_line8_local_shortcuts_v3/conditional_proposal_17_trips.geojson) · [Confronti e prove](RT031_LINEA8_ESITO_TAGLI_E_17_GIRI_V3.md).','']
    return '\n'.join(lines)


def render(r,shape):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(11,7))
    for f in shape['features']:
        if f['properties']['role']!='WING_OF_SAME_LINE':continue
        xy=f['geometry']['coordinates'];wing=f['properties']['wing']
        ax.plot(*zip(*xy),lw=2,color='#ee8128' if wing=='east_A' else '#2586d8',
                label='Prima ala: est' if wing=='east_A' else 'Seconda ala: ovest')
    for s in r['served_sites']:
        xy=s['coordinates_lon_lat'];new=s['kind'].startswith('PROPOSED')
        ax.scatter(*xy,s=24,marker='s' if new else 'o',color='red' if s['site_id']==FS else '#333333',zorder=4)
        if new or s['site_id']==FS:
            ax.annotate(s['name'],xy,xytext=(5,6),textcoords='offset points',fontsize=8)
    for s in r['omitted_sites']:
        xy=s['coordinates_lon_lat'];ax.scatter(*xy,marker='x',s=60,color='red',zorder=4)
        ax.annotate(s['name']+' · esclusa nel confronto',xy,xytext=(5,6),textcoords='offset points',fontsize=8)
    ax.set_aspect(1/math.cos(math.radians(45.73)));ax.legend()
    ax.set_title('Linea8 · proposta condizionata, NON selezionata\n'
                 '17 corse complete · 27 siti · 120.324 km/anno su260 giorni ipotizzati')
    fig.tight_layout();fig.savefig(MAP,dpi=150);plt.close(fig)


if __name__=='__main__':
    r,shape=build()
    OUT.write_text(json.dumps(r,sort_keys=True,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    SHAPE.write_text(json.dumps(shape,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf-8')
    DOC.write_text(document(r),encoding='utf-8')
    render(r,shape)
