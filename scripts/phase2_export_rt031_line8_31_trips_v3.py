"""Readable 31-trip design proposal and date-bound railway connection ledger."""
from itertools import zip_longest
import json

from scripts.phase2_close_rt031_line8_31_trips_v3 import (
    AUTH, OUTPUT, BASE, ROOT, RAIL, CONFIRMATION, FLAGS, digest, sources, verify_schedule)
from scripts.phase2_export_rt031_line8_working_timetable_v3 import connection_ledger, clock

CONNECTIONS=BASE/'approved_31_trip_rail_connections.json'
DOC=ROOT/'docs/RT031_LINEA8_ORARIO_31_CORSE_V3.md'


def build():
    r=json.loads(OUTPUT.read_text(encoding='utf-8'));p=sources()
    expected={'authority':digest(AUTH),'geometry_confirmation':digest(CONFIRMATION),
              'reference_34':digest(BASE/'fixed_geometry_timetable.json'),'rail':digest(RAIL)}
    if r['source_sha256_normalized_newlines']!=expected or any(r[k] for k in FLAGS):
        raise ValueError('source drift or unauthorised selection')
    audit=verify_schedule(p,r['trips'],r['wait_limit_min_by_pattern'],True)
    for key,value in audit.items():
        if r[key]!=value: raise ValueError(f'independent recheck differs: {key}')
    nominal=p['adjusted'][1.1,.5]
    for i,(t,row) in enumerate(zip(r['trips'],r['trip_ledger'],strict=True)):
        expected_row={**t,'trip_index':i,'service_km':p['family']['loops'][t['loop']]['distance_m']/1000,
                      'fs_return_nominal_min':t['departure_min']+nominal[t['loop']]['road_minutes'],
                      'events_nominal':[{**e,'departure_min':t['departure_min']+e['offset_from_wing_origin_min']}
                                        for e in nominal[t['loop']]['events']]}
        if row!=expected_row: raise ValueError('ordered event ledger drift')
    return r,{'contract':'RT031_CALLER_31_TRIP_DATED_RAIL_LEDGER_V3',
              'source_sha256_normalized_newlines':{'timetable':digest(OUTPUT),'rail':digest(RAIL)},
              'service_date':p['rail']['service_date'],'connections':connection_ledger(r,p['rail'],p),
              'semantics':'Nearest compatible dated S8 train in each direction, 3-minute assumed transfer, worst bus grid for onward train. No empirical missed-connection probability, every-train guarantee, annual calendar or through-service certification.',
              'actual_timetable_certified':False,**{k:False for k in FLAGS}}


def report(r,connections):
    west=[t for t in r['trips'] if t['loop']=='west_B'];east=[t for t in r['trips'] if t['loop']=='east_A']
    midday=[]
    for name,trips in (('Ovest',west),('Est',east)):
        times=[t['departure_min'] for t in trips]
        left=max(t for t in times if t<=545)
        middle=[t for t in times if left<=t<=995]
        gaps=[b-a for a,b in zip(middle,middle[1:])]
        midday.append(f"- **{name}:** "+' → '.join(clock(t) for t in middle)+': intervalli di **'+', '.join(str(g) for g in gaps)+' minuti**.')
    lines=['# Linea 8 — proposta di progetto a 31 corse','',
           '**Scelta del committente registrata: 31 corse e il lieve sforamento dello specifico scenario.** '
           'Questa è la proposta corrente; sostituisce l’orario da 34 corse e 122.340 km come base di lavoro. '
           'Geometria invariata. Non è un’autorizzazione all’esercizio né una copertura finanziaria.','',
           '## Quadro conclusivo','',
           '| Voce | Proposta |','|---|---|',
           '| Produzione | **111.460,883 km di servizio/anno**, con 260 giorni identici ipotizzati |',
           '| Scostamento dal riferimento di 111.419 | **+41,883 km/anno, +0,0376%**; questo specifico scostamento è accettato |',
           '| Corse | **15 ovest + 16 est = 31 al giorno**; ciascuna è un giro completo della propria ala, non un intero otto |',
           '| Geometria | Stesse ali ovest B / est A; stessi 28 siti, inclusi FS e i due punti locali provvisori |',
           '| H30 passeggeri nelle punte | **07–09 e 16:55–18:55**, in entrambi i sensi di viaggio nel modello |',
           '| Prime / ultime partenze FS | **06:30 ovest, 06:35 est / 19:40 entrambe** |',
           '| Massima attesa modellata | **155 minuti ovest; 120 minuti est**; non H120 ovunque e non H60 in tutta la morbida |',
           '| Mezzi | **4 nominali, fino a 6 negli stress**; non sono turni autista o disponibilità certificata |','',
           'Il calendario annuale non è ancora adottato. Km di deposito e riposizionamento, costo monetario, '
           'paline e manovre non sono compresi nell’approvazione dello scenario chilometrico. '
           'La scelta di 31 corse non equivale all’accettazione preventiva di ogni minuto della tabella.','',
           '## Partenze da Olgiate FS','',
           'Le colonne sono elenchi indipendenti: una riga **non** indica lo stesso autobus o una coincidenza '
           'fra ali. Non è garantita la permanenza a bordo attraverso FS.','',
           '| N. nell’ala | Ovest: Olgiate sud, La Valletta, Santa Maria | Est: San Zeno, Calco, Arlate, Brivio |',
           '|---|---:|---:|']
    for i,(w,e) in enumerate(zip_longest(west,east),1):
        lines.append(f"| {i} | {clock(w['departure_min']) if w else '—'} | {clock(e['departure_min']) if e else '—'} |")
    lines+=['','## Il compromesso centrale, senza nasconderlo','',*midday,
            '- Prime partenze, punte e ultima partenza non vengono anticipate o accorciate. '
            'H60 è ricontrollato nella fascia iniziale 06:30–07 e dopo la punta serale 18:55–19:40.',
            '- Questi intervalli sono tra partenze FS; la verifica aggiuntiva usa gli eventi di ciascun sito '
            'verso/dalla stazione e tutti i nove scenari. Il massimo non è un’attesa media né una probabilità di affidabilità.',
            '- La precedente regola «H120 solo 10–16, H60 nel resto» **non vale più**: la riduzione interessa '
            'anche la transizione dopo la punta mattutina e prima di quella pomeridiana. '
            'Le violazioni di quella vecchia regola sono registrate per sito, direzione e scenario nel file macchina.','',
            'I buchi di tre ore dell’esempio ottenuto cancellando corse sono quindi ridotti a **2h35 ovest '
            'e 2h est**, agli stessi 111.460,883 km. La copertura geografica resta invariata; '
            'l’accessibilità temporale peggiora rispetto alle 34 corse. Non dichiariamo trascurabile la domanda centrale.','',
            '### Regolarità e prova di limite','',
            'Mattino: ovest **:00/:30**, est **:05/:35**. Dalle 10 entrambe usano **:05/:35**; '
            'l’ultima partenza **19:40** è l’eccezione esplicita. Non tutti gli slot sono serviti.',
            '',
            'Nel dominio verificato (partenze ogni cinque minuti, 15/16 corse, stessi percorsi, prime/ultime, '
            'punte, treni e quattro mezzi nominali) il minimo indipendente del peggior intervallo è '
            '**155 minuti ovest e 115 est**. I due minimi sono raggiungibili insieme. '
            'Imponendo i minuti regolari della proposta, i minimi diventano **155 e 120** e sono ancora '
            'raggiungibili insieme. Quindi la leggibilità costa **5 minuti sul peggior intervallo est**, '
            'nessun km e nessun peggioramento ovest. Entrambe le prove sono conservate, senza pesi territoriali '
            'né dichiarare unica la tabella scelta. Non è un ottimo su ogni calendario o su partenze continue.','',
            '## Coincidenze ferroviarie','',
            'Conservati tutti i **297 controlli per sito**: treni verso Milano **07:26, 07:56, 08:26, '
            '08:56, 09:26**; arrivi da Milano **16:32, 17:02, 17:32, 18:02, 18:32, 19:32**. '
            '**06:56 non è fra gli obiettivi garantiti dal modello.**',
            '',
            'Fonte: [GTFS ufficiale Regione Lombardia/Trenord](https://dati.lombardia.it/download/3z4k-mxz9/application%2Fzip), '
            'riscaricato il 27 settembre, eventi attivi del 28 settembre 2026 e minuti confrontati fino al 2 ottobre. '
            'Tre minuti di trasferimento sono un’ipotesi ingegneristica, non una garanzia su ritardi reali '
            'o sul calendario dell’anno. Le altre coincidenze sono descritte, non tutte promesse.','',
            '| Partenza centrale FS | Ultimo arrivo da Milano utilizzabile | Attesa treno→bus | Rientro FS nominale | Primo treno verso Milano dopo il giro in tutta la griglia |',
            '|---|---:|---:|---:|---:|']
    for i,t in enumerate(r['trips']):
        if not 600<=t['departure_min']<990:continue
        out=next(c for c in connections if c['trip_index']==i and c['rail_direction']=='LECCO')
        inward=next(c for c in connections if c['trip_index']==i and c['rail_direction']=='MILANO')
        prev=out['previous_train_for_outward_bus'];nxt=inward['next_train_after_bus_return_all_grid']
        wait=out['train_to_bus_wait_including_transfer_min']
        lines.append(f"| {'Ovest' if t['loop']=='west_B' else 'Est'} {clock(t['departure_min'])} | {clock(prev['arrival_min']) if prev else '—'} | {wait:g} min | {clock(inward['fs_return_nominal_min'])} | {clock(nxt['departure_min']) if nxt else '—'} |")
    lines+=['','## Territorio e tracciato: nessun nuovo taglio','',
            'Bacini pedonali potenziali a 10 minuti invariati: **Olgiate 84,56%; Calco 68,21%; '
            'Brivio 89,09%; Santa Maria Hoè 95,75%; La Valletta Brianza 67,85%**. '
            'Sono le metriche territoriali ereditate della stessa geometria, non percentuali di passeggeri '
            'o di servizio disponibile a ogni ora. I 28 siti comprendono due punti locali ipotetici: '
            'non sono 28 paline già autorizzate. Olgiate sud e San Zeno restano distinti.',
            '',
            '![Tracciato confermato, invariato](../outputs/phase2/rt031_line8_local_shortcuts_v3/deep_offpeak_witness.png)',
            '',
            '## Stato da conservare per una futura presentazione','',
            '**Definito come base di progetto:** geometria confermata, 31 corse, specifico scostamento '
            'chilometrico accettato, tabella completa e controlli riproducibili. Nessun contatto con Agenzia o operatore effettuato.',
            '',
            '**Esplicito compromesso della tabella proposta:** massimo 155 minuti ovest e 120 est, '
            'con orario centrale più diradato anche fuori dal precedente intervallo 10–16. '
            'La scelta di conservare i minuti regolari rispetto al caso est da 115 minuti è esposta, non nascosta.',
            '',
            '**Prima dell’attivazione, non motivo per riaprire ora tutto il progetto:** calendario effettivo, '
            'tempi osservati, turni/flotta/deposito, sei manovre, restrizioni complete, paline e interscambio fisico, '
            'copertura economica e aggiornamento ferroviario alla data d’avvio. Nessuna garanzia empirica di affidabilità '
            'o di permanenza a bordo fra corse. Le limitazioni di viaggio della geometria accettata restano note.',
            '',
            '[Decisione del committente](../config/rt031_31_trip_service_authorisation_v3.json) · '
            '[Orario, prove e registro eventi](../outputs/phase2/rt031_line8_local_shortcuts_v3/approved_31_trip_timetable.json) · '
            '[Coincidenze per tutte le corse](../outputs/phase2/rt031_line8_local_shortcuts_v3/approved_31_trip_rail_connections.json) · '
            '[Precedente confronto a 34 corse](RT031_LINEA8_ORARIO_DI_PROGETTO_V3.md)']
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    r,c=build()
    CONNECTIONS.write_text(json.dumps(c,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    DOC.write_text(report(r,c['connections']),encoding='utf-8')
