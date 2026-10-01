"""Single traceable delivery packet; no implied political or operational approval."""
import gzip
import hashlib
import json
from pathlib import Path

from scripts.phase2_probe_rt031_line8_no_reverse_all_orders_v3 import OUTPUT as ROAD
from scripts.phase2_close_rt031_line8_fixed_order_timetable_v3 import OUTPUT as CLOSURE
from scripts.phase2_probe_rt031_line8_order_neighbourhood_v3 import access_vector

ROOT=Path(__file__).resolve().parents[1]
OUT=ROAD.parent/'delivery_readiness_fixed_order.json'
DOC=ROOT/'docs/RT031_LINEA8_DOSSIER_UNICO_ISTRUTTORIO_V3.md'
FS='FROZEN::L00407'


def read(path):
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_text(encoding='utf-8'))


def build():
    paths={'road':ROAD,'closure':CLOSURE,'register':ROAD.parent/'stop_plan_and_additions.json.gz',
        'walk':ROAD.parent/'no_reverse_omission_walking.json',
        'shape':ROAD.parent/'no_reverse_all_orders.geojson',
        'authority':ROOT/'config/rt031_16_full_trips_authority_v3.json',
        'requirements':ROOT/'config/rt031_requirements_audit_v3.json',
        'localities':ROOT/'config/rt031_caller_locality_itinerary_preference_v3.json'}
    road,register,walk,shape,auth,requirements=(read(paths[k]) for k in
        ('road','register','walk','shape','authority','requirements'))
    fixed=road['hoe_omission_fixed_event_order_comparison_not_adopted']
    timetable=fixed['timetable_comparison_not_adopted']
    if read(CLOSURE)['road_source_sha256']!=hashlib.sha256(ROAD.read_bytes()).hexdigest():
        raise ValueError('stale timetable closure')
    if walk['road_source_sha256']!=hashlib.sha256(ROAD.read_bytes()).hexdigest():
        raise ValueError('stale walking assessment')
    by_id={s['site_id']:s for s in register['register']}
    coords={f['properties']['wing']:f['geometry']['coordinates'] for f in shape['features']
            if f['properties'].get('comparison')=='hoe_omission_fixed_event_order'}
    access=access_vector(fixed['loops'])
    sites=[{'site_id':FS,'name':by_id[FS]['name'],'municipality':by_id[FS]['municipality'],
        'coordinates_lon_lat':by_id[FS]['road_coordinates'],'kind':'INVENTORY_HUB',
        'boarding_authorised':False,'physical_platform_count':None,'ordered_occurrences':[]}]
    for wing in ('west_B','east_A'):
        loop=fixed['loops'][wing]
        for e in sorted(loop['events'],key=lambda e:e['path_node_index']):
            sid=e['stop_place_id']
            row=next((s for s in sites if s['site_id']==sid),None)
            if row is None:
                source=by_id.get(sid)
                kind=('PROPOSED_ADDITION_N1212' if source is None else
                      'PROPOSED_LOCAL_SITE' if source['inventory_coordinates'] is None else
                      'INVENTORY_SITE_WITH_NEW_CALCO_ACCOSTO_HYPOTHESIS' if sid=='FROZEN::300634'
                      else 'INVENTORY_SITE')
                row={'site_id':sid,'name':source['name'] if source else 'Arlate — ipotesi N1212',
                    'municipality':source['municipality'] if source else 'Calco',
                    'kind':kind,'coordinates_lon_lat':coords[wing][e['path_node_index']],
                    'inventory_coordinates_lon_lat':source['inventory_coordinates'] if source else None,
                    'boarding_authorised':False,'physical_platform_count':None,
                    'nominal_fs_access_min':access[sid], 'ordered_occurrences':[]}
                sites.append(row)
            row['ordered_occurrences'].append({k:e[k] for k in
                ('occurrence_id','path_node_index','incoming_edge','outgoing_edge') }|{'wing':wing})
    if len(sites)!=28 or any(s['site_id']=='FROZEN::300873' for s in sites):
        raise ValueError('unexpected served-site set')
    assessments={
        'railway_interchange':('PARTIAL_UNACCEPTED', 'road', '20 actual archived bindings; 18/22 old objectives compatible, four missing. Current trains and station transfer unverified.'),
        'peak_service':('MODEL_SUPPORTED_NOT_ADOPTED','road','Five consecutive H30 rail-bound opportunities per wing and peak, with different bank phases. Not a continuous all-day H30 claim.'),
        'deep_offpeak':('COMPARISON_NOT_ADOPTED','road','H120 10-16 compared; final quiet-hour policy not adopted.'),
        'territorial_service':('TRADEOFF_REQUIRES_CALLER_PREFERENCE','walk','Five municipal potential walk metrics supported; Hoe omission and local loss not accepted.'),
        'local_districts':('POINT_EVENTS_SUPPORTED_AREA_UNVERIFIED','road','Two ordered local events at Olgiate south and San Zeno; proxies do not certify entire districts.'),
        'recognisable_line':('MODEL_SUPPORTED_OPERATION_UNVERIFIED','road','Same complete eight each trip; intermediate FS onboard continuity designed, not physically certified.'),
        'budget':('EXCEEDS_SPECIFIC_ACCEPTED_COMPARISON','authority','116411.944 exceeds accepted specific 115143.267; no general budget declared.'),
        'service_span':('NOMINAL_TIMETABLE_SUPPORTED','road','Root 06:05 to last full return about21:13. Not identical first/last boarding at each stop.'),
        'calendar':('NOT_ADOPTED','authority','260 identical days are a comparison, not a dated calendar; no further weekend deduction.'),
        'fleet':('ENGINEERING_SUPPORTED_AVAILABILITY_UNVERIFIED','road','Four nominal; worst deterministic scenario five, not an approved fleet or probability.'),
        'runtime_dwell_recovery':('DETERMINISTIC_ONLY','road','9 moving/dwell combinations and 3 recovery values; no empirical reliability distribution.'),
        'rail_margins':('ENGINEERING_ASSUMPTIONS_UNVERIFIED','closure','Inherited 3-minute transfer margin and PM 3-8-minute wait; not observed field values.'),
        'road_and_boarding':('FIELD_AND_FULL_HISTORY_VALIDATION_PENDING','road','No immediate reversals inside wings; FS manoeuvre, full-history legality, bus suitability and platforms not certified.'),
    }
    mapped=[]
    for req in requirements['requirements']:
        status,source,semantics=assessments[req['id']]
        mapped.append({'requirement_id':req['id'],'original_classification':req['classification'],
            'status':status,'upstream_source':str(paths[source].relative_to(ROOT)).replace('\\','/'),
            'semantics':semantics})
    coverage=walk['hoe_fixed_event_order_comparison_not_adopted']
    return {'contract':'RT031_LINE8_SINGLE_DELIVERY_READINESS_NON_DECISIONAL_V3',
        'source_sha256':{k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()},
        'served_design_site_count_including_fs':len(sites),'physical_platform_count':None,
        'served_sites':sites,'ordered_stop_event_ledger_nominal':timetable['ordered_stop_event_ledger_nominal'],
        'requirements':mapped,'desired_localities_not_automatically_certified':read(paths['localities'])['desired_sequence'],
        'coverage':coverage,'full_trips':timetable['full_trips'],
        'annual_service_km_260_day_comparison':fixed['annual_service_km_16_trips_260_days'],
        'extra_km_above_specific_accepted_comparison':fixed['annual_service_km_16_trips_260_days']-auth['specific_annual_service_km_comparison_accepted'],
        'old_rail_objectives_incompatible':timetable['original_22_target_compatibility_full_timetable']['missing'],
        'journey_quality_illustrative_examples_not_admissibility_threshold':[
            {'site_id':s['site_id'],'name':s['name'],'nominal_fs_access_min':s['nominal_fs_access_min']}
            for s in sites if s['site_id'] in ('ASF::OLGIATE_MOLGORA_SCARPONE',
                'FROZEN::300086','FROZEN::300398','FROZEN::300956')],
        'ready_for_final_recommendation':False,'ready_for_public_timetable':False,
        'complete_historical_conversation_audit_claimed':False,
        'demand_weighted_gjt_improvement_min':None,'missed_connection_probability':None,
        'decision_budget_km':None,'uncertainty_band_min':None,
        'network_selected':False,'primary_selection_authorised':False,'runner_up_selection_authorised':False}


def document(r):
    lines=['# Linea 8 — dossier unico istruttorio, non raccomandazione finale','',
        'Un solo documento riunisce la variante a ordine conservato: **28 siti di progetto inclusa FS, 16 giri completi, 116.412 km/anno su 260 giorni ipotizzati**. Non sono 28 paline certificate. Hoè è esclusa soltanto in questo confronto; nessuna scelta finale è adottata.','',
        '![Tracciato](../outputs/phase2/rt031_line8_local_shortcuts_v3/no_reverse_hoe_omission.png)','',
        '## Tutti i punti di servizio','',
        'Tempi nominali ingegneristici del passaggio più favorevole FS↔punto, senza attesa iniziale o cammino. Non garantiscono lo stesso tempo da ogni occorrenza; eventi completi e coordinate sono nel JSON. Le nuove posizioni sono ipotesi da verificare, non paline approvate.','',
        '| # | Sito | Comune | Stato posizione | FS → sito (min) | Sito → FS (min) |',
        '|---:|---|---|---|---:|---:|']
    labels={'INVENTORY_HUB':'Inventario FS','INVENTORY_SITE':'Inventario',
        'PROPOSED_LOCAL_SITE':'Nuovo punto ipotizzato','PROPOSED_ADDITION_N1212':'Nuovo punto Arlate N1212',
        'INVENTORY_SITE_WITH_NEW_CALCO_ACCOSTO_HYPOTHESIS':'Accosto Calco spostato ~19 m, ipotesi'}
    for i,s in enumerate(r['served_sites'],1):
        a=s.get('nominal_fs_access_min')
        out=f"{a['from_fs_min']:.2f}" if a else '—'
        back=f"{a['to_fs_min']:.2f}" if a else '—'
        lines.append(f"| {i} | {s['name']} | {s['municipality']} | {labels[s['kind']]} | {out} | {back} |")
    lines+=['','## Cosa manca per chiamarla proposta finale','',
        '- Preferenza esplicita sul taglio Hoè: a Santa Maria Hoè perdita di 8,67/6,22/2,32 punti percentuali di copertura pedonale potenziale a 5/8/10 minuti; altri quattro comuni invariati.',
        '- 116.412 km supera di circa **1.269 km** il confronto specifico già accettato da 115.143, non soltanto il riferimento 111.419. Non è un aumento generale autorizzato.',
        '- H70 nelle spalle, H120 nella morbida 10–16 e quattro vecchi obiettivi ferroviari non coperti richiedono una scelta esplicita. [Chiusura dei 14 confronti d’orario](RT031_LINEA8_CHIUSURA_ORARIO_ORDINE_CONSERVATO_V3.md).',
        '- **Conservare i tempi precedenti non significa che siano buoni:** Scarpone → FS circa 30 minuti, Beverate Cariplo → FS circa 34,5 e Beverate paese → FS circa 32,5. È un problema di direzionalità del servizio che i soli km e la copertura pedonale non descrivono. Non viene inventata una soglia generale di accettabilità.',
        '- Paline/accosti, attraversamenti, manovra FS, idoneità bus e restrizioni dipendenti dalla storia completa non sono verificati.',
        '- Calendario reale, disponibilità mezzi, costi operatore e km non commerciali non sono approvati.',
        '- Monticello/Mondonico, Calco alta/Cornello, Cassina, Crescenzaga, oratorio e Casa di Comunità non diventano serviti perché nominati o vicini alla geometria: gli abbinamenti località→fermata restano quelli non certificati del contratto sorgente. Neppure un singolo punto Olgiate sud certifica l’intero quartiere.',
        '- La linea è geometricamente unica, ma la sosta FS fino a 15,81 minuti e i viaggi intercomunali devono essere valutati sul ledger. Non c’è OD passeggeri downscalata, GJT demand-weighted o probabilità empirica di coincidenza.',
        '','## Stato conclusivo','',
        '**Pronto come dossier istruttorio tracciabile; non pronto come raccomandazione finale o orario al pubblico.** Le best practices storiche sono riferimenti di progetto, non autorizzazione a inventare utility/probabilità mancanti o selezionare PRIMARY. Il JSON mappa tutti i 13 requisiti dell’audit vigente alle fonti e riporta le 18 località desiderate; non afferma di aver certificato tutte le conversazioni storiche.','',
        '[Dossier machine-readable](../outputs/phase2/rt031_line8_local_shortcuts_v3/delivery_readiness_fixed_order.json) · [Copertura dei cinque comuni](RT031_LINEA8_COMPROMESSO_HOE_V3.md)','',
        '`network_selected=false`; `primary_selection_authorised=false`; `runner_up_selection_authorised=false`; `decision_budget_km=null`; `uncertainty_band_min=null`.','']
    return '\n'.join(lines)


if __name__=='__main__':
    result=build()
    OUT.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    DOC.write_text(document(result),encoding='utf-8')
