"""Publish one working timetable and explicit dated rail connection ledger."""
import json
from scripts.phase2_close_rt031_line8_fixed_geometry_timetable_v3 import OUTPUT,BASE,CONFIRMATION,digest
from scripts.phase2_refresh_rt031_s8_service_date_v3 import OUTPUT as RAIL,ROOT
from scripts.phase2_compare_rt031_line8_deep_offpeak_v3 import build_problem
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import verify,FLAGS

CONNECTIONS=BASE/'fixed_geometry_rail_connections.json'
DOC=ROOT/'docs/RT031_LINEA8_ORARIO_DI_PROGETTO_V3.md'


def clock(value):
    total=int(round(value));return f'{total//60:02d}:{total%60:02d}'


def connection_ledger(r,rail,p):
    rows=[]
    for index,t in enumerate(r['trips']):
        arrivals=[t['departure_min']+loops[t['loop']]['road_minutes'] for loops in p['adjusted'].values()]
        nominal=t['departure_min']+p['adjusted'][1.1,.5][t['loop']]['road_minutes']
        for direction in ('MILANO','LECCO'):
            trains=[e for e in rail['events'] if e['direction']==direction]
            onward=next((e for e in trains if e['departure_min']>=max(arrivals)+3-1e-8),None)
            inbound=[e for e in trains if e['arrival_min']<=t['departure_min']-3+1e-8]
            preceding=max(inbound,key=lambda e:e['arrival_min']) if inbound else None
            rows.append({'trip_index':index,'pattern':t['loop'],'fs_departure_min':t['departure_min'],
                         'fs_return_nominal_min':nominal,'fs_return_grid_min_range':[min(arrivals),max(arrivals)],
                         'rail_direction':direction,
                         'previous_train_for_outward_bus':preceding,
                         'train_to_bus_wait_including_transfer_min':None if preceding is None else t['departure_min']-preceding['arrival_min'],
                         'next_train_after_bus_return_all_grid':onward,
                         'bus_to_train_wait_nominal_including_transfer_min':None if onward is None else onward['departure_min']-nominal,
                         'bus_to_train_wait_grid_including_transfer_min_range':None if onward is None else [onward['departure_min']-max(arrivals),onward['departure_min']-min(arrivals)],
                         'transfer_walk_comparison_min':3,'passenger_connection_certified':False})
    return rows


def report(r,connections):
    west=[t for t in r['trips'] if t['loop']=='west_B'];east=[t for t in r['trips'] if t['loop']=='east_A']
    lines=['# Linea 8 — un solo orario di progetto sulla geometria confermata','',
           '**Confronto storico a 34 corse. La base di lavoro corrente è la [proposta a 31 corse, con lo specifico lieve sforamento accettato dal committente](RT031_LINEA8_ORARIO_31_CORSE_V3.md). I risultati sotto restano evidenza del confronto precedente, non il budget attualmente proposto.**','',
           '**Geometria confermata dal committente. Orario proposto per chiudere la progettazione temporale, non ancora approvato per l’esercizio.**','',
           '## La proposta','',
           '- Stessi due percorsi completi e stessi 28 siti. Nessuna nuova variante o esclusione territoriale.',
           '- **H30 nelle punte 07–09 e 16:55–18:55**, verificato nei due sensi di viaggio di ciascun sito attraverso i nove scenari di marcia/sosta.',
           '- **H120 solo 10–16; H60 nel resto fuori punta.** Sono massimi di attesa del passeggero pronto a partire, non una promessa di collegamento con ogni treno.',
           '- Prime partenze FS **06:30 ovest / 06:35 est**; ultime **19:40 entrambe**. Le ultime corse arrivano ai siti e rientrano a FS dopo tale ora.',
           '- **17 corse per ala, 34 totali; 122.339,721 km/anno su 260 giorni ipotizzati**. Restano +10.920,721 km (+9,80%) sul riferimento, prima di deposito e altri extra. Nessun aumento approvato.',
           '- Quattro mezzi nel caso nominale con recuperi, fino a sei negli stress. Flotta e turni da validare con l’operatore.','',
           '## Partenze da Olgiate FS','',
           'La tabella affianca gli elenchi delle due ali: **una riga non indica lo stesso autobus né una coincidenza fra ali**. '
           'Nessuna permanenza a bordo attraverso FS è garantita da questa tabella.','',
           '| Corsa nell’ala | Ovest: Olgiate sud, La Valletta, Santa Maria | Est: San Zeno, Calco, Arlate, Brivio |','|---|---:|---:|']
    for i,(w,e) in enumerate(zip(west,east),1):lines.append(f"| {i} | {clock(w['departure_min'])} | {clock(e['departure_min'])} |")
    lines+=['','### Regola da ricordare','',
            'Al mattino ovest ai minuti **:00/:30**, est **:05/:35**. Dalle 10 entrambe usano **:05/:35**, '
            'con una sola eccezione ordinaria: **ovest 10:00**; ultime partenze **19:40** esplicitamente fuori schema. '
            'Nelle ore centrali non sono serviti tutti gli slot: valgono le partenze della tabella, non una frequenza semioraria continua.','',
            'Questa è la minima quantità di eccezioni nel dominio verificato, a stessi km, percorsi e finestre di punta. '
            'Non si pagano i 3.682 km aggiuntivi della precedente variante senza eccezioni ordinarie, né si anticipano le punte per far tornare i conti.','',
            '## Coincidenze: verifica datata, non soltanto il vecchio calendario','',
            'È stato riscaricato il [GTFS ufficiale Regione Lombardia/Trenord](https://dati.lombardia.it/download/3z4k-mxz9/application%2Fzip) '
            'il 27 settembre 2026. I **74 eventi S8** a Olgiate attivi il **28 settembre** hanno gli stessi minuti del vecchio '
            'giorno di confronto; la verifica dei cinque feriali fino al **2 ottobre** conferma lo stesso quadro. '
            'Gli identificativi di corsa sono quelli attivi nel nuovo periodo, non quelli scaduti il 14 settembre. '
            'Il fatto che lo ZIP abbia lo stesso hash non lo rende scaduto: contiene più periodi di servizio.','',
            'Confermati tutti i **297 controlli per sito** sugli obiettivi ereditati: cinque treni verso Milano, '
            '**07:26, 07:56, 08:26, 08:56, 09:26**, e sei arrivi da Milano/direzione Lecco, '
            '**16:32, 17:02, 17:32, 18:02, 18:32, 19:32**. '
            'Il treno 06:56 non fa parte di questi cinque obiettivi: non va promesso implicitamente.','',
            'I margini restano ipotesi ingegneristiche: tre minuti di trasferimento; per gli arrivi ferroviari di punta '
            'partenza bus tra tre e otto minuti dopo. Non sono garanzie rispetto ai ritardi reali. '
            'La verifica annuale, festiva e del sabato rimane distinta dai cinque feriali controllati.','',
            '### Corse centrali e serali: cosa offre ciascuna','',
            'La tabella mostra l’ultimo arrivo da Milano compatibile con almeno tre minuti di trasferimento '
            'e il primo treno verso Milano raggiungibile dopo il ritorno dell’ala in **tutti** gli scenari modellati. '
            'Non somma corse diverse per inventare un viaggio. In direzione Lecco il registro macchina contiene lo stesso controllo.','',
            '| Ala / partenza FS | Arrivo treno da Milano utilizzabile | Attesa treno→bus, min inclusi 3 di trasferimento | Rientro FS nominale | Treno verso Milano dopo il giro |','|---|---:|---:|---:|---:|']
    for i,t in enumerate(r['trips']):
        if t['departure_min']<600:continue
        outward=next(c for c in connections if c['trip_index']==i and c['rail_direction']=='LECCO')
        inward=next(c for c in connections if c['trip_index']==i and c['rail_direction']=='MILANO')
        prev=outward['previous_train_for_outward_bus'];nxt=inward['next_train_after_bus_return_all_grid']
        lines.append(f"| {'Ovest' if t['loop']=='west_B' else 'Est'} {clock(t['departure_min'])} | {clock(prev['arrival_min']) if prev else '—'} | {outward['train_to_bus_wait_including_transfer_min']:g} | {clock(inward['fs_return_nominal_min'])} | {clock(nxt['departure_min']) if nxt else '—'} |")
    lines+=['','## Cosa viene chiuso e cosa no','',
            '**Chiuso come base progettuale:** geometria attuale, nessuna ricerca generale di nuovi tracciati; '
            'un solo orario proposto, 34 corse con contabilità completa, punte non anticipate e regolarità con eccezioni dichiarate.','',
            '**Da accettare esplicitamente:** compromesso H120 10–16 e servizio da 122.340 km. '
            'La conferma della geometria non approva automaticamente questi due aspetti. '
            'Non dichiariamo che tutti i viaggi centrali siano poco importanti o che il tetto 111.419 sia rispettato.','',
            '**Prima dell’esercizio:** orari osservati/turni/flotta, paline e sei manovre, interscambio fisico, calendario reale, '
            'deposito e aggiornamenti ferroviari oltre le date controllate. Questi controlli possono richiedere aggiustamenti locali, '
            'non riaprono automaticamente tutta la geometria. I viaggi lunghi già riportati rimangono un limite noto della geometria accettata.','',
            '[Geometria confermata](../config/rt031_geometry_confirmation_and_timetable_closure_v3.json) · '
            '[Tracciato invariato](../outputs/phase2/rt031_line8_local_shortcuts_v3/deep_offpeak_witness.png) · '
            '[Orario, eventi e blocchi macchina](../outputs/phase2/rt031_line8_local_shortcuts_v3/fixed_geometry_timetable.json) · '
            '[Registro delle coincidenze](../outputs/phase2/rt031_line8_local_shortcuts_v3/fixed_geometry_rail_connections.json)']
    return '\n'.join(lines)+'\n'


def build():
    r=json.loads(OUTPUT.read_text(encoding='utf-8'));rail=json.loads(RAIL.read_text(encoding='utf-8'))
    expected={'reference':digest(BASE/'deep_offpeak_witness.json'),'rail':digest(RAIL),'confirmation':digest(CONFIRMATION)}
    if r['source_sha256_normalized_newlines']!=expected or any(r[k] for k in FLAGS):raise ValueError('source drift or automatic selection')
    p=build_problem((600,960),120)
    if verify(p,r['trips'],r['comparison_peak_windows'],4)!=r['conditional_scenarios']:raise ValueError('verification drift')
    rows=connection_ledger(r,rail,p)
    return r,{'contract':'RT031_FIXED_GEOMETRY_DATED_RAIL_CONNECTION_LEDGER_V3',
              'source_sha256_normalized_newlines':{'timetable':digest(OUTPUT),'rail':digest(RAIL)},
              'service_date':rail['service_date'],'connections':rows,
              'semantics':'Nearest compatible scheduled trains with 3-minute assumed transfer. No maximum-wait guarantee for every train, empirical reliability, cross-trip journey or annual calendar certification.',
              'actual_timetable_certified':False,**{k:False for k in FLAGS}}


if __name__=='__main__':
    r,connections=build()
    CONNECTIONS.write_text(json.dumps(connections,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    DOC.write_text(report(r,connections['connections']),encoding='utf-8')
