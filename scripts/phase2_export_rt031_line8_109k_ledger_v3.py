"""Freeze and explain the 17x2 witness without changing its trips or semantics."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops


def clock(minute):
    seconds=int(round(minute*60))
    return f'{seconds//3600:02d}:{seconds//60%60:02d}:{seconds%60:02d}'


def build(wings,joint,comparison):
    if wings['contract']!='RT031_LINE8_INDEPENDENT_WINGS_DIAGNOSTIC_V3' or joint['contract']!='RT031_LINE8_JOINT_PHASE_FEASIBILITY_V3':
        raise ValueError('wrong source contract')
    if comparison['contract']!='RT031_LINE8_REBUILT_PEAK_WINDOW_COMPARISON_V3':
        raise ValueError('wrong comparison contract')
    for source in (wings,joint,comparison):
        if any(source[k] for k in ('network_selected','primary_selection_authorised','runner_up_selection_authorised')):
            raise ValueError('source became decisional')
    w=joint['illustrative_witness']
    adjusted=adjusted_loops(wings['loops'],w['runtime_multiplier'],w['dwell_min_assumption'])
    trips=[]; events=[]; counts=Counter()
    for t in sorted(w['trips'],key=lambda t:(t['departure_min'],t['loop'])):
        wing=t['loop'].split('_')[0]; counts[wing]+=1
        tid=('O' if wing=='west' else 'E')+f'{counts[wing]:02d}'
        loop=adjusted[t['loop']]
        arrival=t['departure_min']+loop['road_minutes']
        trips.append({'trip_id':tid,'wing':wing,'pattern':t['loop'],'departure_min':t['departure_min'],
            'departure':clock(t['departure_min']),'fs_arrival_min':round(arrival,6),'fs_arrival':clock(arrival),
            'distance_m':wings['loops'][t['loop']]['distance_m'],
            'hypothetical_stop_node_occurrences':len({e['path_node_index'] for e in loop['events']})})
        for e in loop['events']:
            dep=t['departure_min']+e['offset_from_wing_origin_min']
            events.append({'trip_id':tid,'wing':wing,'pattern':t['loop'],
                'occurrence_id':tid+':'+e['occurrence_id'],'stop_place_id':e['stop_place_id'],
                'name':e['name'],'status':e['site_status'],'path_node_index':e['path_node_index'],
                'arrival_min':round(dep-w['dwell_min_assumption'],6),'departure_min':round(dep,6),
                'fs_arrival_min':round(arrival,6),'boarding_authorised':False})
    if counts!={'west':17,'east':17}:
        raise ValueError('17x2 witness drift')
    daily=sum(t['distance_m'] for t in trips)/1000
    if abs(daily*260-w['annual_km_before_extras'])>.001:
        raise ValueError('distance ledger fails reconciliation')
    by_site=defaultdict(list)
    for e in events:
        by_site[e['stop_place_id']].append(e)
    for values in by_site.values():
        values.sort(key=lambda e:(e['departure_min'],e['occurrence_id']))
        for i,e in enumerate(values):
            e['gap_since_previous_encounter_min']=round(e['departure_min']-values[i-1]['departure_min'],6) if i else None
            e['different_pattern_from_previous']=i>0 and e['pattern']!=values[i-1]['pattern']
    new=next(c for c in comparison['comparisons'] if c['peak_window_advance_min']==15)
    before=Counter(t['pattern'] for t in trips); after=Counter(t['loop'] for t in new['trip_witness'])
    bridge=[{'pattern':p,'distance_m':v['distance_m'],'old_daily_count':before[p],'comparison_daily_count':after[p],
        'annual_km_delta':round((after[p]-before[p])*v['distance_m']/1000*260,6)} for p,v in wings['loops'].items()]
    return {'contract':'RT031_LINE8_FROZEN_109K_TRIP_LEDGER_V3','witness_id':'JOINT_PHASE_18_20_17_TRIPS_PER_WING',
        'trips':trips,'events_by_site':dict(sorted(by_site.items())),
        'annual_service_days_assumption':260,'daily_service_km':round(daily,9),
        'annual_service_km':round(daily*260,6),'source_reported_annual_km':w['annual_km_before_extras'],
        'moving_time_multiplier_assumption':w['runtime_multiplier'],'dwell_per_node_min_assumption':w['dwell_min_assumption'],
        'historical_comparison_only':{'source_contract':comparison['contract'],'pattern_count_bridge':bridge,
            'annual_km_before_extras':new['annual_km_before_extras'],'current_witness_changed':False},
        'gap_semantics':'Chronological gap between encountered identity occurrences, not a certified directional passenger headway. Repeated occurrences within one trip stay separate; no substitution of stop identity for a guaranteed service event.',
        'network_selected':False,'primary_selection_authorised':False,'runner_up_selection_authorised':False,
        'actual_timetable_certified':False,'decision_budget_km':None,'uncertainty_band_min':None}


def markdown(a,main_path,stops_path):
    lines=['# Le 17 corse per ala: conto fermo del candidato da 109 mila km','',
        '**Questo documento non modifica nessuna corsa.** Fissa il testimone `JOINT_PHASE_18_20_17_TRIPS_PER_WING` già pubblicato, non una nuova proposta approvata.',
        '', '## Come leggere gli orari','',
        'Orari calcolati, non orario al pubblico: marcia +10%, sosta ipotetica di 30 secondi a ogni nodo di fermata distinto. I secondi servono a rendere verificabili i conti, non indicano precisione osservata. Il rientro a FS comprende le soste intermedie ma non il recupero successivo. Le fermate e le piattaforme restano da autorizzare.',
        '', '## Tutte le corse, senza aggiunte','',
        '| Corse | Partenza FS | Ovest: rientro FS | Ovest km | Est: rientro FS | Est km |',
        '|---|---|---|---:|---|---:|']
    west=[t for t in a['trips'] if t['wing']=='west']; east=[t for t in a['trips'] if t['wing']=='east']
    for x,y in zip(west,east):
        if x['departure']!=y['departure']:
            raise ValueError('paired display requires same departures')
        lines.append(f'| {x["trip_id"]} / {y["trip_id"]} | {x["departure"]} | {x["fs_arrival"]} | {x["distance_m"]/1000:.3f} | {y["fs_arrival"]} | {y["distance_m"]/1000:.3f} |')
    lines += ['',f'**34 corse d’ala/giorno = {a["daily_service_km"]:.6f} km/giorno.**',
        f'**× 260 giorni ipotetici = {a["annual_service_km"]:.3f} km/anno.** Deposito e riposizionamenti esclusi.',
        'I km in tabella sono arrotondati; il totale utilizza le distanze non arrotondate. Cambiare soltanto l’ora di una di queste corse lascia invariato questo totale.',
        '', 'Le prime quattro corse sono ovest A/est B. Dalla quinta diventano ovest B/est A. I sensi hanno distanze leggermente diverse: questa differenza è esplicita nel conto.',
        '', '## Passaggi nei luoghi e intervalli','',
        '[Tabella completa di tutti i passaggi, luogo per luogo](RT031_LINEA8_109K_PASSAGGI_PER_LOCALITA_V3.md). Ogni riga ha corsa, occorrenza, arrivo, partenza, rientro FS e intervallo dal passaggio precedente. I cambi di senso sono segnalati.',
        '', 'Un intervallo fra identità incontrate non prova che il passeggero possa usare entrambi i lati: la tabella non autorizza le fermate. Il [controllo delle punte](RT031_LINEA8_SCHEDA_CONCLUSIVA_DI_AVANZAMENTO_V3.md) mostra dove la promessa H30 del testimone non è soddisfatta per l’intera finestra. Non cambiamo il significato di H30 per dichiararlo valido.',
        '', '## Perché un confronto precedente risultava da 121 mila km','',
        '**Era un altro insieme di corse, non il medesimo orario traslato.** Questo è solo il ponte contabile con quel risultato storico, non una modifica del candidato sopra.',
        '', '| Giro d’ala | Corse/giorno qui | Corse/giorno nel confronto | Variazione km/anno |','|---|---:|---:|---:|']
    for r in a['historical_comparison_only']['pattern_count_bridge']:
        lines.append(f'| {r["pattern"]} | {r["old_daily_count"]} | {r["comparison_daily_count"]} | {r["annual_km_delta"]:+.3f} |')
    south=a['events_by_site']['RT031::P2V2S_0031_PROJECTED_ROAD_POINT']
    transition=[next(e for e in south if e['trip_id']==tid) for tid in ('O04','O05','O06')]
    lines += ['', 'Totale: **34 → 38 corse d’ala/giorno**, oltre alla diversa composizione dei sensi. La differenza non è causata dai minuti sull’orologio.',
        '', '## Un problema concreto da risolvere, senza cambiare i conti', '',
        'A Olgiate sud le corse O04, O05 e O06 passano rispettivamente alle **'+', '.join(clock(e['departure_min']) for e in transition)+'**. Il cambio di senso concentra due passaggi a circa un minuto e mezzo di distanza, seguiti da un intervallo di un’ora. Sono passaggi modellati, non una garanzia di salita su entrambi i lati.',
        '', 'Questo esempio localizza una transizione punta/morbida da verificare; da solo non dimostra né che basti traslare le corse né che servano necessariamente più km. Prima di dichiarare conclusa la proposta occorre verificare H30/H60 lungo l’intera finestra di servizio di ogni località, in relazione ai treni e al senso utile al passeggero. Ogni correzione dovrà riportare separatamente le corse spostate e quelle eventualmente aggiunte o modificate.',
        '', '## Cosa è dimostrato e cosa no','',
        'Dimostrati nel modello: elenco delle corse, somma dei km, tempi ottenuti dalle ipotesi dichiarate. Non dimostrati: servizio H30 completo nelle punte, fermate autorizzate, coincidenze affidabili, costi e km di deposito, calendario reale. Nessuna selezione PRIMARY/RUNNER-UP è autorizzata.',
        '', 'Il prossimo eventuale cambiamento va registrato come spostamento, aggiunta, soppressione o modifica del percorso, con variazione chilometrica separata. Questa tabella resta il riferimento invariato.']
    main_path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    out=['# Passaggi del candidato 109k, luogo per luogo','',
        'Fonte unica: `frozen_109k_trip_ledger.json`. O=ala ovest, E=ala est. Orari ipotetici comprensivi delle soste dichiarate; non orario pubblico approvato. Intervallo = differenza tra passaggi cronologici della stessa identità, non garanzia direzionale. Occorrenze ripetute restano distinte.',
        '', '[Conto delle 34 corse e dei chilometri](RT031_LINEA8_109K_CONTO_CORSE_V3.md).']
    for sid,values in a['events_by_site'].items():
        out += ['', '## '+values[0]['name'],'',f'Identità: `{sid}`. Stato: `{values[0]["status"]}`. Salita non autorizzata da questo modello.',
            '', '| Corsa / nodo progressivo | Arrivo | Partenza | Rientro FS | Intervallo precedente (min) | Cambio di schema |',
            '|---|---|---|---|---:|---|']
        for e in values:
            gap='—' if e['gap_since_previous_encounter_min'] is None else f'{e["gap_since_previous_encounter_min"]:.2f}'
            out.append(f'| {e["trip_id"]} / {e["path_node_index"]} | {clock(e["arrival_min"])} | {clock(e["departure_min"])} | {clock(e["fs_arrival_min"])} | {gap} | '+('Sì' if e['different_pattern_from_previous'] else '—')+' |')
    stops_path.write_text('\n'.join(out)+'\n',encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('wings','joint','comparison','output','main_report','stops_report'):
        p.add_argument('--'+k,required=True,type=Path)
    a=p.parse_args(); result=build(*(json.loads(getattr(a,k).read_text(encoding='utf-8')) for k in ('wings','joint','comparison')))
    result['source_sha256']={k:hashlib.sha256(getattr(a,k).read_bytes().replace(b'\r\n',b'\n')).hexdigest() for k in ('wings','joint','comparison')}
    a.output.write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    markdown(result,a.main_report,a.stops_report)
