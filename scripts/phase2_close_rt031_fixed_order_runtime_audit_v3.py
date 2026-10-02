"""Close the fixed-order road-runtime question, not the operating approval.

Compare distance and modeled moving-time minima, preserving every ordered
service node and the agreed street exclusions. Disclose the AM phase tradeoff
instead of silently prioritising one rail flow or selecting a robustness band.
"""
import argparse
import copy
import difflib
import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from scripts.phase2_strengthen_rt031_fixed_design_v3 import (
    BASE,DESIGN,SOURCE,RAIL,HANDOFF,CALENDAR,OUTPUT as STRENGTHENING,
    canonical_sha256,handoff_build,complete_case,am_phase_bound,splice_one_event,
)
from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import inputs,FS
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
from scripts.phase2_probe_rt031_line8_calco_through_path_v3 import through_path,refresh_events
from scripts.phase2_audit_rt031_line8_caller_streets_v3 import excluded_ways
from scripts.phase2_audit_rt031_confirmed_route_fieldwork_v3 import audit_path
from scripts.phase2_audit_rt031_internal_transfer_margins_v3 import compare,shifted_schedule
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter

OUTPUT=BASE/'fixed_order_runtime_closure_20261002.json'
SHAPE=BASE/'fixed_order_runtime_comparison_20261002.geojson'
BRIEF=ROOT/'docs/RT031_LINEA8_LIMITE_TEMPO_E_SCELTA_AM_2026_10_02.md'
HELPER=ROOT/'scripts/phase2_probe_rt031_line8_calco_through_path_v3.py'


def reconstruct_loop(old,edges,adapter,fs,policy,objective):
    if policy not in ('all_incoming','local_incoming','node_only'):
        raise ValueError('Undeclared service occurrence protection policy')
    ordered=sorted(old['events'],key=lambda e:(e['path_node_index'],e['stop_place_id']))
    checkpoints=[]
    for event in ordered:
        incoming=event['incoming_edge']
        required=incoming if policy=='all_incoming' or (
            policy=='local_incoming' and event['stop_place_id']=='PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE') else None
        checkpoints.append((edges[incoming]['v_node_id'],required))
    answer=through_path(edges,adapter,old['edge_ids'][0],old['edge_ids'][-1],checkpoints,{fs},objective=objective)
    if not answer['reachable']:
        return None
    path=[old['edge_ids'][0],*answer['edge_ids'],old['edge_ids'][-1]]
    events=[];progress=0
    for index,eid in enumerate(path,1):
        while progress<len(checkpoints):
            node,required=checkpoints[progress]
            if edges[eid]['v_node_id']!=node or (required is not None and required!=eid):
                break
            event=copy.deepcopy(ordered[progress])
            event.update(path_node_index=index,service_node_hypothesis=node,
                physical_boarding_authorised=False,physical_passenger_continuity_certified=False)
            events.append(event);progress+=1
    if progress!=len(checkpoints):
        raise ValueError('Fixed ordered service-event reconstruction failed')
    loop={**copy.deepcopy(old),'edge_ids':path,'events':events}
    refresh_events(loop,edges,'east_A')
    if [e['stop_place_id'] for e in events]!=[e['stop_place_id'] for e in ordered]:
        raise ValueError('Ordered stop identity drift')
    if policy=='all_incoming' and [e['incoming_edge'] for e in events]!=[e['incoming_edge'] for e in ordered]:
        raise ValueError('Directional service occurrence changed in strict domain')
    if len({e['path_node_index'] for e in events})!=14:
        raise ValueError('Hypothetical dwell events merged or duplicated')
    return loop


def path_changes(old,new,edges,ways,nodes):
    rows=[];features=[]
    def xy(ids):
        vertices=[edges[ids[0]]['u_node_id']]+[edges[e]['v_node_id'] for e in ids]
        return [[float(nodes[n]['lon']),float(nodes[n]['lat'])] for n in vertices]
    for tag,lo,hi,start,end in difflib.SequenceMatcher(a=old,b=new,autojunk=False).get_opcodes():
        if tag=='equal':
            continue
        before,after=old[lo:hi],new[start:end]
        if not before or not after:
            raise ValueError('Unexpected non-local path edit; inspect before publishing')
        row=dict(original_edge_slice=[lo,hi],replacement_edge_slice=[start,end])
        for label,ids in [('original',before),('replacement',after)]:
            used=list(dict.fromkeys(edges[e]['osm_way_id'] for e in ids))
            row[label]=dict(edge_ids=ids,distance_m=sum(float(edges[e]['length_m']) for e in ids),
                running_minutes_model=sum(float(edges[e]['running_minutes_model']) for e in ids),
                osm_ways=[dict(osm_way_id=w,tags=ways[w]) for w in used])
            features.append(dict(type='Feature',properties=dict(role='CHANGED_SECTION',variant=label),
                geometry=dict(type='LineString',coordinates=xy(ids))))
        rows.append(row)
    return rows,features


def readable_case(case):
    return {key:case[key] for key in (
        'east_am_advance_min','west_trips_9_to_15_delay_min',
        'event_readiness_and_complete_trip_checks_pass','readiness_violation',
        'maximum_model_vehicles','additional_full_trip_service_min_per_day',
        'exact_fs_departure_pairs_min','bank_margins_assumed_3min_walk',
        'lost_previous_all_nine_case_bus_to_rail','maximum_increase_in_nominal_rail_to_bus_wait_min',
        'rail_flow_changes')}


def build(graph_dir):
    source,design,rail,handoff,calendar,strengthening=[json.loads(p.read_text(encoding='utf-8'))
        for p in (SOURCE,DESIGN,RAIL,HANDOFF,CALENDAR,STRENGTHENING)]
    if canonical_sha256(handoff)!=canonical_sha256(handoff_build()):
        raise ValueError('Authoritative fixed design drift')
    for path,value in zip((SOURCE,DESIGN,RAIL,HANDOFF,CALENDAR),(source,design,rail,handoff,calendar)):
        if strengthening['source_canonical_sha256'][path.name]!=canonical_sha256(value):
            raise ValueError('Previous strengthening source drift')
    paths=inputs(graph_dir)
    for key in ('edges','nodes','rules','attachments'):
        if hashlib.sha256(paths[key].read_bytes()).hexdigest()!=design['road_graph_inputs_sha256'][key]:
            raise ValueError('Frozen road input drift')
    raw,nodes,rules,attachments=build_graph(paths)
    all_edges={k:v for k,v in raw.items() if not(k+'::IN' in raw and k+'::OUT' in raw)}
    osm_path=graph_dir/'rt017/frozen_osm_snapshot.json.gz'
    if hashlib.sha256(osm_path.read_bytes()).hexdigest()!=strengthening['road_comparison']['source_osm_snapshot_sha256']:
        raise ValueError('Frozen road tags drift')
    osm=json.loads(gzip.decompress(osm_path.read_bytes()))
    ways={str(w['id']):w.get('tags',{}) for w in osm['elements'] if w['type']=='way'}
    exclusions=excluded_ways(osm['elements'],design['adopted_development_street_exclusions'])
    edges={k:v for k,v in all_edges.items() if v['osm_way_id'] not in exclusions}
    adapter=FrozenRT017ViaNodeAdapter(edges.values(),rules,unresolved_external_via_way_count=2)
    fs=attachments[FS]['graph_node_id']
    cases=[];witnesses={};loops_by_witness={}
    for policy in ('all_incoming','local_incoming','node_only'):
        for objective in ('distance','minutes'):
            loop=reconstruct_loop(design['loops']['east_A'],edges,adapter,fs,policy,objective)
            if loop is None:
                raise ValueError('Baseline-containing fixed-order domain became unreachable')
            key=canonical_sha256(loop['edge_ids'])
            loops_by_witness[key]=loop
            witnesses.setdefault(key,dict(edge_ids=loop['edge_ids'],ordered_service_events=loop['events'],
                distance_m=loop['distance_m'],moving_minutes_model=loop['road_minutes']))
            cases.append(dict(incoming_protection_policy=policy,objective=objective,reachable=True,
                witness_id=key,all_14_ordered_service_nodes_preserved=True,
                all_directional_incoming_edges_preserved=[e['incoming_edge'] for e in loop['events']]==
                    [e['incoming_edge'] for e in sorted(design['loops']['east_A']['events'],key=lambda e:(e['path_node_index'],e['stop_place_id']))],
                distance_m=loop['distance_m'],moving_minutes_model=loop['road_minutes']))
    strict=next(c for c in cases if c['incoming_protection_policy']=='all_incoming' and c['objective']=='minutes')
    relaxed=next(c for c in cases if c['incoming_protection_policy']=='node_only' and c['objective']=='minutes')
    fastest=loops_by_witness[strict['witness_id']]
    # This is an objective-specific witness, never an overall network winner.
    if strict['moving_minutes_model']<relaxed['moving_minutes_model']-1e-8:
        raise ValueError('Relaxed search domain contradicts strict-domain minimum')
    same_minimum=abs(strict['moving_minutes_model']-relaxed['moving_minutes_model'])<=1e-8
    coupled=copy.deepcopy(design['loops'])
    coupled['east_A']=fastest
    scarpone=strengthening['road_comparison'];run=scarpone['original_service_slice']
    coupled['west_B']=splice_one_event(coupled['west_B'],run['first_edge_index_zero_based'],
        run['last_edge_index_zero_based']+1,scarpone['bypass_edge_ids'],
        scarpone['evaluated_attachment_hypothesis']['node_id'],all_edges,'west_B')
    path_audit=audit_path(coupled,all_edges,fs,nodes)
    combined=coupled['east_A']['edge_ids']+coupled['west_B']['edge_ids']
    whole_adapter=FrozenRT017ViaNodeAdapter(all_edges.values(),rules,unresolved_external_via_way_count=2)
    if path_audit['immediate_edge_reversals'] or any(
        whole_adapter.decision((combined[i-1],),eid)['allowed'] is not True for i,eid in enumerate(combined)):
        raise ValueError('Runtime comparison violates represented route/boundary transitions')
    days=calendar['weekday_base_day_count_before_local_exceptions'];reference=calendar['reference_published_pdb_annual_km']
    sample=complete_case('example_AM_minus2_PM_plus2_Scarpone_confirmed_east_geometry',
        shifted_schedule(source,am_advance=2,west_delay=2),
        {'east_A':design['loops']['east_A'],'west_B':coupled['west_B']},
        source,design['loops'],rail,days,reference)
    faster_case=complete_case('minimum_modeled_east_runtime_PM_plus2_Scarpone_no_AM_phase_change',
        shifted_schedule(source,west_delay=2),coupled,source,design['loops'],rail,days,reference)
    baseline=strengthening['completed_comparisons'][0]
    nominal_key=lambda c:(c['moving_multiplier'],c['dwell_min'],c['terminal_recovery_min'])==(1.1,.5,10)
    baseline_nominal=next(c for c in baseline['all_27_complete_vehicle_blocks'] if nominal_key(c))
    for completed in (sample,faster_case):
        nominal=next(c for c in completed['all_27_complete_vehicle_blocks'] if nominal_key(c))
        delta=nominal['total_service_min_per_day']-baseline_nominal['total_service_min_per_day']
        completed['additional_nominal_service_min_per_day_vs_confirmed']=delta
        completed['additional_nominal_service_hours_2027_vs_confirmed']=delta*days/60
    fixed_phase_grid=[readable_case(compare(source,design,rail,a,2)) for a in range(5)]
    changes,features=path_changes(design['loops']['east_A']['edge_ids'],fastest['edge_ids'],all_edges,ways,nodes)
    # Include complete routes, not just schematic local segments. Geometry
    # uses pinned nodes, with the projected south node from confirmed GeoJSON.
    original_geo=json.loads(DESIGN.with_suffix('.geojson').read_text(encoding='utf-8'))
    coordinates={n:[float(v['lon']),float(v['lat'])] for n,v in nodes.items()}
    for feature in original_geo['features']:
        if feature['geometry']['type']=='Point':
            coordinates.setdefault(feature['properties']['site_id'],feature['geometry']['coordinates'])
    for variant,loops in [('confirmed',design['loops']),('runtime_and_scarpone_hypothesis',coupled)]:
        for wing,loop in loops.items():
            ids=loop['edge_ids'];verts=[all_edges[ids[0]]['u_node_id']]+[all_edges[e]['v_node_id'] for e in ids]
            features.append(dict(type='Feature',properties=dict(role='FULL_ROUTE',variant=variant,wing=wing,adopted=False),
                geometry=dict(type='LineString',coordinates=[coordinates[n] for n in verts])))
    for feature in original_geo['features']:
        if feature['geometry']['type']=='Point':
            copied=copy.deepcopy(feature)
            copied['properties']['variant']='confirmed'
            features.append(copied)
    features.append(dict(type='Feature',properties=dict(role='HYPOTHETICAL_ATTACHMENT',
        variant='runtime_and_scarpone_hypothesis',site_id='ASF::OLGIATE_MOLGORA_SCARPONE',
        physical_boarding_authorised=False,adopted=False),
        geometry=dict(type='Point',coordinates=scarpone['evaluated_attachment_hypothesis']['coordinates_lon_lat'])))
    bounds=[]
    for f in features:
        if f['properties'].get('role')=='CHANGED_SECTION':bounds.extend(f['geometry']['coordinates'])
    source_nodes={n['id']:[n['lon'],n['lat']] for n in osm['elements'] if n['type']=='node'}
    extent=[min(c[0] for c in bounds)-.001,min(c[1] for c in bounds)-.001,
        max(c[0] for c in bounds)+.001,max(c[1] for c in bounds)+.001]
    for w in osm['elements']:
        if w['type']!='way' or not w.get('tags',{}).get('highway') or any(n not in source_nodes for n in w.get('nodes',[])):
            continue
        xy=[source_nodes[n] for n in w['nodes']]
        if any(extent[0]<=x<=extent[2] and extent[1]<=y<=extent[3] for x,y in xy):
            features.append(dict(type='Feature',properties=dict(role='BASEMAP_ROAD',osm_way_id=str(w['id']),name=w['tags'].get('name','')),
                geometry=dict(type='LineString',coordinates=xy)))
    result=dict(contract='RT031_FIXED_ORDER_RUNTIME_AND_AM_PRIORITY_CLOSURE_V3',recorded_on='2026-10-02',
        source_canonical_sha256={p.name:canonical_sha256(v) for p,v in zip(
            (SOURCE,DESIGN,RAIL,HANDOFF,CALENDAR,STRENGTHENING),(source,design,rail,handoff,calendar,strengthening))},
        generator_code_sha256={p.name:hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in (Path(__file__),HELPER)},
        search_domain=dict(wing='east_A',ordered_service_occurrences=14,
            fixed_fs_incoming_outgoing_edges=[design['loops']['east_A']['edge_ids'][0],design['loops']['east_A']['edge_ids'][-1]],
            excluded_exact_street_names=design['adopted_development_street_exclusions'],
            internal_fs_visits_allowed=False,immediate_edge_reversals_allowed=False,
            restriction_semantics='FROZEN_REPRESENTED_VIA_NODE_ONLY',full_history_legal_domain_certified=False),
        objective_extreme_cases=cases,distinct_path_witnesses=witnesses,
        relaxed_direction_domain_has_same_minimum_modeled_time=same_minimum,
        minimum_modeled_runtime_distance_change_m=fastest['distance_m']-design['loops']['east_A']['distance_m'],
        minimum_modeled_runtime_change_min=fastest['road_minutes']-design['loops']['east_A']['road_minutes'],
        changed_road_sections=changes,
        baseline_paired_flow_bound=am_phase_bound(source,design['loops'],rail),
        minimum_runtime_paired_flow_bound=am_phase_bound(source,coupled,rail),
        complete_runtime_comparison=faster_case,complete_AM_minus2_comparison=sample,
        fixed_geometry_AM_phase_comparisons_with_PM_plus2=fixed_phase_grid,
        coupled_runtime_scarpone_route_audit=path_audit,
        internal_bounded_road_time_question_closed=True,
        all_order_or_all_graph_optimality_claimed=False,complete_pareto_frontier_claimed=False,
        remaining_caller_choice='AM_OUTBOUND_RAIL_MARGIN_VS_IMMEDIATE_INBOUND_RAIL_CONNECTION',
        actual_operator_implementation_ready=False,design_engineering_solidification_complete=False,
        am_phase_change_adopted=False,runtime_route_change_adopted=False,normative_rail_priority_adopted=False,
        rail_2027_certified=False,physical_boarding_authorised=False,
        physical_passenger_continuity_certified=False,network_selected=False,
        primary_selection_authorised=False,runner_up_selection_authorised=False,
        decision_budget_km=None,uncertainty_band_min=None,missed_connection_probability=None,
        demand_weighted_gjt_improvement_min=None,
        semantics='Two objective extrema under three incoming-edge protection domains, not a complete weighted/Pareto tournament or a global route optimum. Costs are frozen moving-time proxies, not observed bus performance or measured transfer time. All original service nodes/order retained; physical permissions remain unknown. AM minus two is a fully rebuilt example whose reverse-flow cost is disclosed, not a silently adopted threshold or railway priority.')
    return result,dict(type='FeatureCollection',features=features)


def render_brief(r):
    from scripts.phase2_package_rt031_confirmed_design_handoff_v3 import clock
    sample=r['complete_AM_minus2_comparison'];fast=r['complete_runtime_comparison']
    old=r['baseline_paired_flow_bound']['pairs'][0];new=r['minimum_runtime_paired_flow_bound']['pairs'][0]
    lines=['# Linea 8 — chiusa la domanda sul tempo minimo, esplicita la scelta mattutina','',
        'La proposta unica confermata non è modificata: 16 giri completi, 27 siti, calendario feriale 2027 e H30 nelle banche di punta. Il controllo riguarda il residuo AM; non riapre il progetto intercomunale.','',
        '## Il grafo non nasconde una scorciatoia risolutiva','',
        'Verificati due obiettivi — distanza e marcia modellata — con tre livelli di protezione delle direzioni di arrivo: tutti gli archi entranti, solo San Zeno, oppure nodi soltanto. Stessi 14 eventi est ordinati, stessi archi FS, nessun passaggio FS interno, nessuna inversione immediata, Mirasole/Cartiglio/Tessitura esclusi. Le restrizioni a storia completa non sono certificate.','',
        f"Sei ricerche restituiscono {len(r['distinct_path_witnesses'])} tracciati distinti, su due coppie estreme di costo; la libertà di direzione cambia alcune occorrenze ma non migliora il costo minimo. Il minimo di distanza con direzioni protette riproduce la base. Il minimo di tempo aggiunge **{r['minimum_modeled_runtime_distance_change_m']:.2f} m** e riduce la marcia modellata di **{-r['minimum_modeled_runtime_change_min']*60:.2f} secondi** (circa {-r['minimum_modeled_runtime_change_min']*1.1*60:.2f} nello stress di marcia ×1,1). Anche il dominio con direzioni libere ha lo stesso minimo di tempo.",'',
        'Il tratto diverso è a Calco: invece di Via Trieste/Vittorio Veneto, Via San Vigilio → rotatoria → Via Cornello → Via Notaio Carlo Mandelli. Non aggiunge una fermata a Cornello e non ne certifica accesso o sicurezza. Non viene adottato: il piccolo guadagno del proxy non dimostra un vantaggio reale di esercizio.','',
        f"La finestra comune per servire con la stessa corsa i cinque arrivi da Milano a :02/:32 e le cinque partenze verso Milano a :26/:56 (54 minuti dopo il rispettivo arrivo) passa da **{old['available_common_phase_interval_min']*60:.2f} a {new['available_common_phase_interval_min']*60:.2f} secondi**. Anche con fase continua bilanciata il limite è {new['maximum_equal_residual_margin_by_retiming_only_min']*60:.2f} secondi per lato. Vale soltanto per questo ordine, grafo e modello: non è impossibilità generale né una probabilità.",'',
        f"Il confronto completo minimo-tempo + Scarpone + sera +2 verifica i nove ledger, 27 blocchi e tutti i 296 flussi; {fast['weekday_commercial_km']:.3f} km commerciali feriali 2027, massimo {fast['maximum_conditional_vehicles']} mezzi condizionali. Non crea una soluzione mattutina robusta per definizione.",'',
        '## Esempio completo di compromesso AM, non adottato','',
        'Sul tracciato confermato, con il bypass Scarpone già studiato e sera +2, è ricostruito il caso **prime cinque partenze est −2 minuti**: 06:03, 06:33, 07:03, 07:33, 08:03. FS intermedia conserva le partenze ovest; tutte le corse continuano a percorrere entrambe le ali.','',
        f"Conserva H30, cap di attesa e 16 giri, {sample['weekday_commercial_km']:.3f} km feriali 2027 e massimo {sample['maximum_conditional_vehicles']} mezzi nei 27 casi. Il margine minimo verso Milano aumenta da 0,223 a 2,223 minuti dopo i 3 minuti assunti di cammino. Non è una soglia di affidabilità adottata. Servizio nominale aggiunto rispetto alla base: {sample['additional_nominal_service_min_per_day_vs_confirmed']:.3f} minuti/giorno, {sample['additional_nominal_service_hours_2027_vs_confirmed']:.3f} ore sui 254 giorni; non sono turni autista né costo certificato.",'',
        '| Treno da Milano in arrivo FS | Bus est base | Bus est nel confronto | Attesa base → confronto |','|---|---|---|---|']
    for row in sample['rail_flow_changes']:
        if row['wing']=='east_A' and row['train_arrival_min'] in (362,392,422,452,482):
            before=row['old_rail_to_bus_wait_min'];after=row['new_rail_to_bus_wait_min']
            lines.append(f"| {clock(row['train_arrival_min'])} | {clock(row['train_arrival_min']+before)} | {clock(row['train_arrival_min']+after)} | {before:g} → {after:g} min |")
    lines += ['', 'L’aumento dell’attesa non è occultato dalla copertura geografica o dall’assenza di nuovi km. Sono salvati tutti gli altri flussi Lecco/Milano, nominali e stress dello stesso bus. Anticipare −1, −3 o −4 resta un confronto, non una soluzione scelta: gli effetti per treno sono nel JSON.','',
        '## Conclusione che non rimanda a un nuovo giro di ricerca','',
        '**Chiusa la verifica interna del tempo minimo nel dominio dichiarato.** La soluzione non può essere proclamata pronta nascondendo il compromesso AM. Il committente deve scegliere se prioritizzare le cinque coincidenze verso Milano, accettando la perdita del bus immediato dai cinque arrivi, oppure mantenere la fase confermata finché tempi osservati giustifichino un margine diverso. Nessuna scelta viene attribuita automaticamente al committente.','',
        'Restano prove fisiche e operative non sostituibili con file: accosti/sagoma, tempi reali e trasferimento, permanenza a bordo, turni/deposito e costo completo; treni 2027 e sabato separato. Le località e i quartieri non già certificati restano esplicitamente tali nel dossier. Non si dichiara che tutti gli obiettivi storici siano soddisfatti.','',
        '[Audit macchina e registri](../outputs/phase2/rt031_line8_local_shortcuts_v3/fixed_order_runtime_closure_20261002.json) · [Tracciati completi e tratto Calco](../outputs/phase2/rt031_line8_local_shortcuts_v3/fixed_order_runtime_comparison_20261002.geojson)','']
    return '\n'.join(lines)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--graph-dir',type=Path,required=True)
    args=parser.parse_args();result,geo=build(args.graph_dir)
    for p,value in ((OUTPUT,result),(SHAPE,geo)):
        p.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
    BRIEF.write_text(render_brief(result),encoding='utf-8')
    print(json.dumps(dict(search_cases=len(result['objective_extreme_cases']),paths=len(result['distinct_path_witnesses']),
        moving_delta_min=result['minimum_modeled_runtime_change_min'],distance_delta_m=result['minimum_modeled_runtime_distance_change_m'],
        am_example_vehicles=result['complete_AM_minus2_comparison']['maximum_conditional_vehicles'],
        am_example_km=result['complete_AM_minus2_comparison']['weekday_commercial_km']),ensure_ascii=False))
