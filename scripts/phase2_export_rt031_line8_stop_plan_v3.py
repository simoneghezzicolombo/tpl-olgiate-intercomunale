"""Publish a numbered stop plan, critical manoeuvres and few study examples."""
from fractions import Fraction
import argparse
import json
from pathlib import Path

from scripts.phase2_audit_rt031_line8_stop_plan_v3 import read_result,SHAPE
from scripts.phase2_close_rt031_line8_31_trips_v3 import ROOT,OUTPUT as TIMETABLE,digest

DOC=ROOT/'docs/RT031_LINEA8_PIANO_FERMATE_E_MANOVRE_V3.md'
TEMPLATE=ROOT/'scripts/templates/rt031-stop-plan-map.html'


def gain_total(c):
    # An explicitly named spatial axis for examples, not a passenger score.
    return sum(c['gain_weight_vector'][2::3])


def study_examples(r):
    ids={group[0] for group in r['pair_representative_groups']}
    candidates=[c for c in r['single_additions'] if c['candidate_id'] in ids]
    examples=[]
    for pattern in ('west_B','east_A'):
        own=[c for c in candidates if c['patterns']==[pattern]]
        if own:examples.append(sorted(own,key=lambda c:(-gain_total(c),c['candidate_id']))[0])
    return examples


def write_example_proofs(r,graph_dir):
    from scripts.phase2_audit_rt031_line8_stop_plan_v3 import example_proofs,EXAMPLES
    from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import inputs
    from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
    from scripts.phase2_close_rt031_line8_31_trips_v3 import sources,PATTERNS
    p=sources();edges,_,_,_=build_graph(inputs(graph_dir))
    loops={pat:p['family']['loops'][pat] for pat in PATTERNS}
    timetable=json.loads(TIMETABLE.read_text(encoding='utf-8'))
    proofs=example_proofs(r,loops,edges,p,timetable,[c['candidate_id'] for c in study_examples(r)])
    EXAMPLES.write_text(json.dumps(proofs,sort_keys=True,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def label(c):
    street=' / '.join(c['street_names_in_snapshot']) or 'Strada senza nome nello snapshot'
    return street+' — zona '+c['nearest_reference_site_name']


def changes(r,c):
    return {m:{t:100*float(Fraction(c['potential_access_fraction'][m][t])-Fraction(r['baseline_potential_access_fraction'][m][t]))
               for t in ('5','8','10')} for m in r['municipality_names']}


def report(r):
    passing=sum(c['timing']['fixed_31_timetable_pass'] for c in r['single_additions'])
    examples=study_examples(r)
    lines=['# Linea 8 — piano fermate e manovre sulla proposta a 31 corse','',
           '**Precisazione sul servizio:** si corregge l’interpretazione della richiesta del committente: '
           'ogni corsa sull’intero percorso, come aveva sempre inteso. Il conteggio storico a corse d’ala '
           'non è la proposta finale. [Percorso unico completo](RT031_LINEA8_PERCORSO_UNICO_COMPLETO_V3.md). '
           'Il registro dei siti e le scelte sulle due aggiunte restano utili; non autorizzano corse parziali.','',
           '**Aggiornamento successivo del committente:** N1212 nell’area di Arlate è accolta '
           'come fermata di progetto; N0655 in Via Indipendenza è esclusa per la segnalazione del cavalcavia. '
           'Non si cerca automaticamente una palina poco prima o dopo. La base corrente diventa '
           '**29 siti di progetto**, mentre i 28 qui numerati sono il registro precedente. '
           'Olgiate sud e San Zeno rimangono inclusi. '
           '[Scelte e continuità intercomunale](RT031_LINEA8_CONTINUITA_INTERCOMUNALE_V3.md). '
           'Le comparazioni sotto restano evidenza storica dell’audit, non revocano queste scelte.','',
           '**Ambito dell’audit storico sotto: geometria e orario allora invariati, nessuna aggiunta automatica.** '
           'Questo documento rende verificabili i 28 siti, i diversi passaggi e le sei inversioni; '
           'esamina inoltre zero, una o due aggiunte come confronto circoscritto.','',
           '## Cosa sappiamo sulle fermate','',
           '- **26 siti d’inventario, compresa FS**, e **due punti locali proposti: Olgiate sud e San Zeno/Via Cantù**. '
           'Sito non significa una singola palina: non sappiamo ancora quanti impianti direzionali saranno necessari.',
           '- I siti d’inventario non sono tutti fermate delle sole D184/D185: sono conservate le famiglie sorgente e le linee note. '
           'La presenza nell’inventario non dimostra utilizzabilità da questo preciso percorso.',
           '- Coordinate d’inventario e nodo stradale di aggancio rimangono distinti. '
           'Lato strada, marciapiede, attraversamento accessibile e autorizzazione non vengono inventati.',
           '- Per Olgiate sud e San Zeno il primo passaggio serve a scendere arrivando da FS; l’ultimo a salire verso FS. '
           'Sono occorrenze diverse, non una sola garanzia ottenuta dal nome della fermata. '
           'Gli archi di ingresso/uscita sono registrati; il lato fisico della palina resta da accertare.','',
           '**Limite ereditato:** per gli altri siti già presenti, i controlli di servizio conservano '
           'l’unione ottimistica delle occorrenze del modello. Non equivale a una garanzia di salita '
           'da una palina fisica autorizzata. Il registro consente di correggere questo punto '
           'quando saranno noti lati e accessi; non lo dichiara già risolto.','',
           '## Registro numerato','',
           'Le coordinate qui sono del **nodo stradale nel modello**, non il progetto esecutivo della palina. '
           'Il JSON conserva anche le coordinate originali d’inventario, la distanza di aggancio e ogni occorrenza ordinata.','',
           '| N. | Sito | Comune | Natura | Passaggi nel giro d’ala | Latitudine, longitudine del nodo |',
           '|---|---|---|---|---|---|']
    for s in r['register']:
        visits='FS: origine/fine delle due ali' if not s['occurrences'] else ', '.join(f"{pat}: {sum(e['pattern']==pat for e in s['occurrences'])}" for pat in sorted({e['pattern'] for e in s['occurrences']}))
        nature='Proposto, non autorizzato' if s['status'].startswith('PROPOSED') else 'Inventario, lato da verificare'
        lon,lat=s['road_coordinates']
        lines.append(f"| {s['number']} | {s['name']} | {s['municipality']} | {nature} | {visits} | {lat:.6f}, {lon:.6f} |")
    lines+=['','Per ogni sito servono una fotografia/planimetria con il **lato di accosto**, '
            'verifica del percorso pedonale e dell’attraversamento, spazio accessibile di attesa e salita, '
            'ed effettiva compatibilità del mezzo. La fonte stradale non certifica queste condizioni. '
            'Non si applica una soglia arbitraria per dichiararle sicure.','',
            '## Sei punti di manovra, localizzati','',
            'Nel grafo, il bus torna immediatamente sul tratto appena percorso. '
            'Il fatto che le restrizioni rappresentate non vietino la transizione **non dimostra** che un autobus possa girare.','',
            '| Punto | Ala | Riferimento | Via nello snapshot | Nodo / coordinate | Stato |',
            '|---|---|---|---|---|---|']
    lookup={s['number']:s for s in r['register']}
    for m in r['manoeuvres']:
        names=', '.join(f"{i}: {lookup[i]['name']}" for i in m['site_numbers']) or 'Non coincide con un sito di fermata'
        lon,lat=m['coordinates'];street=m['street_name_in_snapshot'] or f"OSM way {m['osm_way_id']}"
        lines.append(f"| {m['id']} | {'Ovest' if m['pattern']=='west_B' else 'Est'} | {names} | {street} | {lat:.6f}, {lon:.6f} | Spazio e traiettoria del mezzo da verificare |")
    lines+=['','**Priorità di verifica fisica:** i ritorni ai due punti nuovi, Olgiate sud e San Zeno, '
            'e la manovra non associata a una fermata sono particolarmente importanti per capire come '
            'tradurre il tracciato in esercizio. È una priorità istruttoria, non un giudizio di pericolosità misurata. '
            'Nessuna delle sei è approvata: servono spazio reale, traiettoria d’ingombro del mezzo e condizioni di accesso. '
            'Se una fallisce, si corregge quel punto e si ricontrollano i tempi; non si riapre automaticamente tutta la rete.','',
            '## Poche nuove fermate: confronto lungo la linea, non nuove deviazioni','',
            f"Esaminati **{r['candidate_node_count']} nodi attualmente non serviti lungo le due ali**. "
            f"**{passing}** conservano il calendario di 31 partenze nei controlli effettuati; "
            'questo comprende anche punti senza beneficio territoriale. Tutti i risultati, anche quelli negativi, sono conservati.',
            '',
            'Una fermata aggiuntiva su un arco già percorso aggiunge **0 km di servizio**, ma non zero tempo: '
            '30 secondi per visita nel nominale e fino a un minuto nella griglia di stress. '
            'Una posizione ripetuta due volte paga entrambe le soste. H30, gli intervalli centrali, '
            'i treni richiesti e i quattro mezzi nominali sono ricontrollati con i tempi aggiornati. '
            'Per i nuovi siti ripetuti viene usata l’ultima occorrenza per salire verso FS, non un passaggio anticipato seguito da un giro lungo.',
            '',
            f"**{len(r['single_addition_spatial_dwell_frontier_ids'])} posizioni** restano non dominate sulle sole "
            '15 dimensioni territoriali (cinque comuni × 5/8/10 minuti) e sulle soste aggiunte per ala, '
            'fra quelle che passano l’orario invariato. Sono alternative di posizione, **non altrettante fermate da costruire**. '
            'Sicurezza, marciapiedi, costo delle opere e domanda passeggeri non sono certificati da questa frontiera.',
            '',
            '### Due esempi da approfondire, non una selezione di nuove paline','',
            'Per mostrare casi concreti prendiamo, separatamente per ala, un rappresentante con il maggiore '
            'incremento di accesso territoriale a **10 minuti** fra i gruppi analizzati. '
            'È un criterio descrittivo dichiarato: non una classifica complessiva né una preferenza nascosta '
            'fra comuni. Gli altri miglioramenti a 5 e 8 minuti restano disponibili.',
            '',
            '| Ipotesi | Localizzazione indicativa | Coordinate | Beneficio a 10 minuti per comune, punti percentuali | Sosta nominale aggiunta nell’ala |',
            '|---|---|---|---|---|']
    for c in examples:
        delta=changes(r,c);benefits='; '.join(f"{r['municipality_names'][m]} +{v['10']:.2f} pp" for m,v in delta.items() if v['10']>0) or 'Nessun incremento a 10 minuti; vedere 5/8'
        lon,lat=c['coordinates'];dwell=sum(c['timing']['extra_nominal_running_and_dwell_min'].values())
        lines.append(f"| {c['candidate_id']} | {label(c)} | {lat:.6f}, {lon:.6f} | {benefits} | {dwell:g} min |")
    if len(examples)==2:
        selected={c['candidate_id'] for c in examples}
        pair=next((c for c in r['pair_comparisons'] if set(c['candidate_ids'])==selected),None)
        if pair:
            lines+=['',f"**Insieme:** {'i due esempi passano' if pair['timing']['fixed_31_timetable_pass'] else 'i due esempi NON passano'} i controlli dell’orario invariato. "
                    'I benefici combinati sono ricalcolati sull’unione delle aree, non sommati contando due volte gli stessi residenti.']
            lines+=['','| Comune | Base: accesso a piedi entro 10 minuti | Con entrambe le ipotesi |',
                    '|---|---|---|']
            for m,name in r['municipality_names'].items():
                before=100*float(Fraction(r['baseline_potential_access_fraction'][m]['10']))
                after=100*float(Fraction(pair['potential_access_fraction'][m]['10']))
                lines.append(f'| {name} | {before:.2f}% | {after:.2f}% |')
            margin=pair['timing']['smallest_AM_residual_min_after_3min_transfer']
            lines+=['',f'**Margine da non nascondere:** nel caso più severo della griglia, il minimo residuo mattutino '
                    f'oltre i 3 minuti ipotizzati per il cambio è **{margin*60:.0f} secondi**. '
                    'Superare il controllo deterministico non dimostra affidabilità empirica. '
                    'In particolare Via Nuova Provinciale richiede una verifica fisica di accosto e attraversamento; '
                    'il guadagno di copertura non dimostra sicurezza o fattibilità della palina.']
    lines+=['','Le coordinate sono sul grafo stradale: una palina reale potrà richiedere uno spostamento locale '
            'o risultare impraticabile. Prima di aggiungere un punto vicino a una fermata esistente, '
            'va valutato se sia invece uno **spostamento della palina**, ricontrollando anche eventuali perdite '
            'per gli utenti già coperti. Questo confronto non autorizza sostituzioni.',
            '',
            f"Sono state controllate **{len(r['pair_comparisons'])} coppie** di rappresentanti. "
            'La riduzione a rappresentanti vale solo per il confronto: siti con gli stessi abitanti raggiunti '
            'non sono automaticamente equivalenti per sicurezza o tempi. Un esito negativo riguarda '
            'queste esatte 31 partenze, non prova che nessun altro orario possa funzionare.',
            '',
            '## Cosa resta fermo','',
            '31 corse, **111.460,883 km/anno** nel calendario ipotetico da 260 giorni, stessa geometria. '
            '**Zero nuove aggiunte adottate in questo audit.** I due punti locali precedenti rimangono già inclusi '
            'nei 28 siti della base. Le eventuali 1–2 aggiunte qui studiate non sono conteggiate come fermate approvate.',
            '',
            'La copertura è potenziale e spaziale: nessuna trasformazione di popolazione in passeggeri, '
            'nessun OD municipale attribuito alle corse, nessuna probabilità empirica di coincidenza. '
            'Le restrizioni stradali complete e l’accessibilità fisica restano da verificare.',
            '',
            'I [tre ricontrolli riproducibili](../outputs/phase2/rt031_line8_local_shortcuts_v3/stop_addition_examples.json) '
            'conservano gli eventi aggiunti separatamente per ala: ciascuna ipotesi da sola e le due insieme. '
            'La griglia completa di 27 combinazioni corsa/sosta/recupero resta a quattro mezzi nel nominale '
            'e fino a sei negli stress. Non sono turni autista o approvazione della flotta.',
            '',
            '## Riproduzione','',
            'Con i pacchetti stradale e pedonale fissati dagli hash delle fonti:',
            '',
            '```text',
            'python -m scripts.phase2_audit_rt031_line8_stop_plan_v3 --graph_dir <pacchetto-stradale> --walk_dir <pacchetto-pedonale>',
            'python -m scripts.phase2_export_rt031_line8_stop_plan_v3 --examples_graph_dir <pacchetto-stradale> --visual_path <mappa.html>',
            'python -m unittest discover -s tests -p test_phase2_rt031_line8_stop_plan_v3.py',
            '```',
            '',
            'Impostare `PYTHONPATH` su radice repository e `src` come nella CI. '
            'Le prove su eventi e scenari pubblicati non richiedono i pacchetti esterni; '
            'rigenerare l’intero censimento spaziale invece sì.',
            '',
            '[Registro e tutti i confronti (JSON gzip)](../outputs/phase2/rt031_line8_local_shortcuts_v3/stop_plan_and_additions.json.gz) · '
            '[Eventi dei due esempi e 27 scenari mezzi](../outputs/phase2/rt031_line8_local_shortcuts_v3/stop_addition_examples.json) · '
            '[Mappa georeferenziata GeoJSON](../outputs/phase2/rt031_line8_local_shortcuts_v3/stop_plan_and_additions.geojson) · '
            '[Orario corrente](RT031_LINEA8_ORARIO_31_CORSE_V3.md)']
    return '\n'.join(lines)+'\n'


def visualization(r,shape):
    examples=study_examples(r);ids={c['candidate_id'] for c in examples};features=[]
    for f in shape['features']:
        p=f['properties'];kind=p['kind'];props={'kind':kind}
        if kind=='route':props['pattern']=p['pattern']
        elif kind=='site':
            props.update(key='S'+str(p['number']),short=str(p['number']),label=f"{p['number']}. {p['name']}",
                         proposed=p['status'].startswith('PROPOSED'),
                         detail=f"{p['name']} · {p['municipality']} · {'Punto proposto' if p['status'].startswith('PROPOSED') else 'Sito in inventario'} · lato di salita e accesso pedonale da verificare")
        elif kind=='manoeuvre':
            props.update(key=p['id'],short=p['id'],label=p['id']+' · '+(p['street_name_in_snapshot'] or 'Inversione sul grafo'),
                         detail=f"{p['id']} · {p['street_name_in_snapshot'] or ('OSM way '+p['osm_way_id'])} · inversione immediata nel grafo · manovra autobus NON autorizzata")
        elif kind=='candidate':
            if p['candidate_id'] not in ids:continue
            c=next(c for c in examples if c['candidate_id']==p['candidate_id']);delta=changes(r,c)
            gain='; '.join(f"{r['municipality_names'][m]} +{v['10']:.2f} pp a 10 min" for m,v in delta.items() if v['10']>0)
            props.update(key=c['candidate_id'],short=c['candidate_id'],label=c['candidate_id']+' · '+label(c),
                         detail=label(c)+' · '+gain+' · 0 km aggiuntivi · ipotesi, non palina approvata')
        geom=f['geometry']
        if geom['type']=='LineString':geom={'type':'LineString','coordinates':[[round(x,6),round(y,6)] for x,y in geom['coordinates']]}
        features.append({'type':'Feature','properties':props,'geometry':geom})
    fragment=TEMPLATE.read_text(encoding='utf-8').replace('__DATA__',json.dumps({'features':features},ensure_ascii=False,separators=(',',':')).replace('</',r'<\/'))
    if len(fragment.encode('utf-8'))>=1000000:raise ValueError('inline map exceeds 1 MB')
    return fragment


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--visual_path',type=Path)
    parser.add_argument('--examples_graph_dir',type=Path)
    args=parser.parse_args()
    r=read_result();shape=json.loads(SHAPE.read_text(encoding='utf-8'))
    if r['source_sha256_normalized_newlines']['timetable']!=digest(TIMETABLE):raise ValueError('timetable source drift')
    if args.examples_graph_dir:write_example_proofs(r,args.examples_graph_dir)
    DOC.write_text(report(r),encoding='utf-8')
    if args.visual_path:
        args.visual_path.parent.mkdir(parents=True,exist_ok=True)
        args.visual_path.write_text(visualization(r,shape),encoding='utf-8')
