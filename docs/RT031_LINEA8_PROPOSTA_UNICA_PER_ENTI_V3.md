# Linea 8 — proposta unica per il tavolo con Agenzia e operatore

**24 settembre 2026 · indirizzo di progetto, non autorizzazione all'esercizio.**

## Proposta

Una sola linea pubblica riconoscibile, con **Olgiate-Calco-Brivio FS** come
cerniera fra due ali e servizio progettato nei due versi:

- **Ovest:** FS → Monticello/Scarpone e area Mondonico → Rovagnate → Perego
  → Santa Maria Hoè e Tremonte/Via Trento → **Olgiate residenziale a sud
  della SS342** → FS.
- **Est:** FS → Calco Cornello/centro e Via Nazionale, con verifica di Calco alta → Arlate
  → Brivio centro → Beverate, includendo Quattro Strade e Cariplo →
  **San Zeno/Via Cantù** → FS.

Olgiate sud e San Zeno/Via Cantù sono **due aree diverse**. Il progetto deve
assegnare a entrambe punti di salita realmente accessibili e viaggi utili
verso e dalla stazione. Mondonico, Cornello, Calco alta e altri nomi di
frazione non si considerano serviti finché una fermata e un evento di corsa
non lo dimostrano. Crescenzaga/Pianezzo e Cassina sono opportunità da
confrontare con il costo di deviazione; Cassina richiede prima
un'identificazione geografica univoca. La conservazione delle fermate
attuali è una preferenza da misurare, non un veto automatico. **In questa
fase la variante inclusiva 11/11 e tutti i luoghi richiesti restano nel
perimetro**: nessuna fermata viene tolta preventivamente per il cap.

## Servizio da progettare

La richiesta è un orario prevedibile, con buona copertura della giornata e
coincidenze S8 verso Milano e Lecco. La proposta conserva **l'intero
itinerario desiderato**, con entrambe le ali e i due sensi da verificare,
e chiede corse e viaggi utili per ogni località. La fascia 06–22 e il
rinforzo dei picchi 07–09 e 17–19 sono obiettivi; **H30 di punta/H60 di
morbida non è ancora un orario approvato** né un obbligo di percorrere
sempre tutto l'8 a ogni corsa. Il cap di 111.419 bus-km/anno è il
riferimento di confronto, non una ragione per tagliare adesso frazioni o
fermate. Verificare separatamente il sabato. La classe H60 richiede una
decisione esplicita rispetto alla policy vigente. A FS va dichiarato se
il passeggero resta sulla stessa corsa o cambia, con quale attesa. Nessuna
fase S8 è ancora selezionata.

### Il limite quantitativo della promessa di servizio

L'[audit riproducibile del servizio](../outputs/phase2/rt031_line8_service_promise_v3/audit.json)
conta solo traversate **complete** delle due ali nei due versi sul
riferimento inclusivo 11/11; non presume fermate autorizzate, orario,
coincidenze o mezzi disponibili. Con 260 giorni ipotetici, ciascuna coppia
giornaliera dei due versi aggiunge 52,208 km/giorno. Il cap attuale di
111.419 bus-km/anno ne contiene al massimo **otto al giorno**, per
108.592 km/anno prima dei riposizionamenti e di qualunque altro servizio.

| Promessa su tutte le località e i due versi, se ogni corsa fa l'intero 8 | Coppie complete/giorno | Km/anno prima degli extra | Rapporto col cap |
| --- | ---: | ---: | --- |
| H60 per 8 ore | 8 | 108.592 | Entro, con margine di soli 2.827 km |
| H60 per 10 ore | 10 | 135.740 | Oltre di 24.321 km |
| H60 per 16 ore | 16 | 217.184 | Oltre di 105.765 km |
| H30 per 4 ore più H60 nelle altre 12 | 20 | 271.480 | Oltre di 160.061 km |

Quindi **non è sostenibile promettere ora H60 06–22 su tutta la Linea 8
inclusiva entro quel cap**. Distribuire gli otto passaggi per verso sulle
16 ore darebbe in media un passaggio ogni due ore, non H60; quattro ore di
H30 consumerebbero già tutti e otto i passaggi di ciascun verso. Nessuno
di questi conteggi è un orario da pubblicare: il cap copre produzione
stradale modellata e non include km di deposito, sabato o variabilità dei
tempi. La geometria inclusiva resta il riferimento. Un esercizio con corse
parziali, rinforzi mirati o diversa produzione annua va costruito con
eventi passeggeri e chilometri propri: non può ereditare automaticamente
la copertura né la continuità della traversata completa. Solo dopo tale
verifica si può decidere esplicitamente se chiedere più risorse o quale
promessa di frequenza/span modificare.

### Prova di downgrade dell'esercizio, senza cancellare la geografia

Il [probe stradale condizionale](../outputs/phase2/rt031_line8_peak_core_v3/probe.json)
ha anche il [tracciato GeoJSON ispezionabile](../outputs/phase2/rt031_line8_peak_core_v3/road_options.geojson) dei sei anelli modellati; nessuno è ancora una linea TPL o un piano fermate approvato. Il probe
ha composto sullo stesso grafo un anello breve **FS → Olgiate sud → FS →
San Zeno → FS**: 4,737 km e 12,372 minuti di sola marcia modellata. Non
incontra alcuna fermata d'inventario oltre FS: funziona come proposta di
servizio soltanto se i due nuovi punti diventano fermate sicure, servite
nei versi utili, e le manovre e il passaggio a FS sono verificati. Nessun
H30 o blocco veicolo è certificato da questa distanza.

Come puro conto di produzione su 260 giorni, **sette** coppie giornaliere
complete dei due versi della 11/11 più **otto** anelli brevi aggiuntivi
fanno circa **104.871 km/anno**, lasciando 6.548 km prima dei
riposizionamenti e degli altri servizi. Con **otto** coppie complete,
invece, diventano **118.445 km/anno**, oltre il cap già prima degli extra.
La 10/11 con otto coppie complete e otto anelli brevi arriva a circa
112.355 km/anno, ancora oltre il cap e con la perdita locale pedonale
descritta sopra. Otto anelli brevi potrebbero formare H30 per quattro
ore *solo se* orario, eventi di fermata e mezzi lo consentono. Questo
esperimento dimostra soltanto che H30 mirato è una famiglia da verificare;
sette coppie complete distribuite su una giornata lunga possono lasciare
attese eccessive nelle località esterne. **Non è ancora la proposta di
esercizio.**

Una prova aggiuntiva inserisce fermate d'inventario vicine a FS nello
stesso anello breve, mantenendo Olgiate sud e San Zeno come punti da
verificare. Con sette coppie complete 11/11 e otto anelli brevi al giorno,
il cammino più corto fra gli ordini provati misura **5,988 km** passando
per Via Statale a Olgiate e Via Virgilio a Calco: **107.473 km/anno**
prima degli extra, con tre identità esistenti incontrate incluso FS.
Passando invece anche per Via della Salute e Via Virgilio misura
**7,432 km** e **110.477 km/anno**, con quattro identità esistenti incluso
FS. Sono inserimenti di waypoint sul grafo, non prove di fermata o di
H30 effettivo. Il margine al cap del secondo caso è inferiore a
1.000 km/anno prima di deposito e sabato; non va presentato come
esercizio finanziato. Il primo caso lascia comunque soltanto sette
traversate complete per verso al giorno per i luoghi esterni, da
valutare come servizio temporale reale, non solo come percentuale
pedonale invariata.

## Riscontro tecnico già disponibile

**Tracciato controllabile, non ancora itinerario TPL approvato.** La
[polilinea GeoJSON dei due versi](../outputs/phase2/rt031_line8_inclusive_shape_v3/line8_inclusive_model.geojson)
materializza gli archi ordinati del grafo stradale congelato per la
variante inclusiva 11/11; una
[vista statica](../outputs/phase2/rt031_line8_inclusive_shape_v3/line8_inclusive_preview.png)
li sovrappone alla rete stradale e ai 25 punti esistenti incontrati e ai
due nuovi bisogni di fermata. Le lunghezze esportate sono esattamente
26,455 km nel verso ovest→est e 25,753 km nel verso opposto. Questo
permette finalmente un controllo strada per strada della geometria che
genera i chilometri. **Non dimostra** idoneità del bus, fermate in entrambi
i sensi, restrizioni dipendenti dall'intero cammino, orario o continuità
di servizio a FS. Le due stelle nuove non sono fermate certificate. La
forma del tracciato va esaminata criticamente per deviazioni e ritorni
prima di trattarlo come proposta operativa.

Una [prova stradale fissata e riprodotta in CI](../outputs/phase2/rt031_unique_line_road_screen_v3/screen.json)
ha confrontato sei modi di collocare Olgiate sud e San Zeno nelle ali,
usando gli stessi punti rappresentativi. **Sud a ovest, San Zeno a est** è
il più corto: 23,853 km per giro completo ovest→est e 23,451 km nel verso
opposto. La seconda assegnazione più corta media 25,09 km, contro 23,65 km
per questa. Nel grafo le quattro giunzioni a FS condividono il nodo e non
violano svolte *via-node* rappresentate. Il sito sud `P2V2S_0031` è ancora
`FIELD_CHECK_PENDING`; a San Zeno è stato usato un nodo di Via Cantù vicino
all'ancora provvisoria, **non una fermata**. Percorso completo, restrizioni
dipendenti dalla storia, idoneità stradale e continuità passeggeri restano da
validare.

La [verifica pedonale sul substrato comune](../outputs/phase2/rt031_unique_line_walk_access_v3/access.json)
individua i nodi di 16 fermate esistenti sul percorso iniziale. Una
[riparazione mirata](../outputs/phase2/rt031_current_stop_repair_v3/road_options.json)
attraverso Tremonte, Calco Via Nazionale e due fermate attuali di Beverate/Brivio porta a
**24 identità incontrate nei due versi e 10/11 identità attuali**, senza
perdere le 16 precedenti. Se diventassero tutte eventi di salita, e se
i due punti nuovi fossero sicuri e serviti, la quota di popolazione con
una fermata entro **10 minuti a piedi** sarebbe:

| Variante di studio | Brivio | Calco | Olgiate | Santa Maria Hoè | La Valletta | Totale |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 10/11, confronto più corto | 81,88% | 68,21% | 84,56% | 93,43% | 67,85% | 77,58% |
| 11/11, riferimento inclusivo | 81,88% | 68,21% | 84,56% | 95,75% | 67,85% | 77,79% |

Queste percentuali sono **condizionali**: i 24/25 nodi non sono ancora un
orario con fermate effettive, i due nuovi punti non sono approvati e la
matrice misura accesso pedonale, non viaggio verso FS o domanda osservata.
Per confronto, usando solo le fermate rappresentative già nominate nel
percorso, Calco è al 47,97% e Olgiate al 31,26%: la scelta degli eventi di
fermata cambia materialmente la proposta.
La riparazione recupera Brivio rispetto al sottoinsieme attuale a 10 minuti
(78,38% → 81,88%) e annulla nel controfattuale le perdite di accesso già
coperto a Calco; resta il 2,32% della popolazione di Santa Maria.
Includere anche l'ultima identità attuale a Santa Maria Hoè porta a
**25 nodi esistenti, 11/11 identità e 77,79%** nel totale dei cinque comuni,
ma aggiunge **1,464 km per giro completo** rispetto alla versione a 10/11.
La 11/11 è ora il **riferimento inclusivo da verificare per primo**, non
una rete automaticamente selezionata: l'effetto su tempi, risorse e
viaggi verso FS va misurato. La 10/11 resta il confronto di efficienza,
non un taglio già deciso.

**Guardrail per il downgrade.** La differenza di soli 0,21 punti
percentuali nel totale a 10 minuti non rende la 10/11 un taglio
territorialmente neutro. Eliminare lo sperone per la fermata “Hoè” riduce
la quota potenziale di Santa Maria Hoè da **72,88% a 64,21% entro 5
minuti** (−8,67 punti), da **94,83% a 88,60% entro 8 minuti** (−6,22)
e da **95,75% a 93,43% entro 10 minuti** (−2,32). Nel totale dei cinque
comuni le perdite corrispondenti sono 0,80/0,57/0,21 punti. Questi sono
risultati condizionali di accesso pedonale, non passeggeri persi. La
variante 9/11 senza Calco Via Nazionale scende invece al 62,81% a
10 minuti a Calco, contro 68,21% nella 11/11; non è un taglio innocuo.
Un downgrade si giudica quindi su **tutte le quote 5/8/10 minuti per
comune** e sugli eventi di servizio effettivi, non sul solo totale a
10 minuti. H30 nelle punte e copertura geografica sono dimensioni
diverse: diminuire la frequenza può lasciare invariata la percentuale
pedonale ma peggiorare i viaggi realmente utili verso FS.

### Direttezza verso FS: perché servono davvero i due sensi

Nel [percorso 10/11 modellato](../outputs/phase2/rt031_current_stop_repair_v3/road_options.json),
i minuti di **sola marcia stradale dal punto rappresentativo al successivo
passaggio a FS** cambiano molto con il senso del giro:

| Punto rappresentativo | Senso nell'ordine sopra | Senso inverso |
| --- | ---: | ---: |
| Monticello/Scarpone | 19,6 | 3,6 |
| Rovagnate | 15,5 | 7,7 |
| Santa Maria Hoè | 11,4 | 11,7 |
| Olgiate sud | 3,8 | 19,2 |
| Calco/Via Garibaldi | 25,5 | 1,9 |
| Arlate | 19,5 | 7,9 |
| Brivio centro | 14,0 | 12,1 |
| Beverate | 9,1 | 16,9 |
| San Zeno/Via Cantù | 2,4 | 24,4 |

Il migliore dei due sensi è entro circa 12,1 minuti per tutti i waypoint
di questa versione: è il vantaggio potenziale della forma a otto, **non
una garanzia di viaggio**. La tabella omette attesa, sosta e cammino;
i punti stradali non sono fermate certificate e i due sensi non hanno
ancora eventi di salita e orari verificati. Offrire soltanto il senso
lungo, o orariare quello rapido in modo inutilizzabile per S8, annullerebbe
gran parte del beneficio. La verifica dell'operatore deve quindi mostrare
per ciascun punto i tempi **porta/fermata→FS in entrambi i sensi**, insieme
alle partenze effettive, non solo la lunghezza dell'intera linea.

Il cap vigente è **111.419 bus-km/anno**. L'ordine opposto delle due
fermate di Beverate aumenta leggermente la distanza ma migliora un poco
l'accesso a 5 minuti a Brivio; la scelta precisa richiede sopralluogo e
orario. Non si deve usare il cap come `decision_budget_km` del finalizzatore.

### Diagnosi del numero «256 mila»

Il [conto riproducibile delle percorrenze complete](../outputs/phase2/rt031_line8_service_envelope_v3/envelope.json)
usa il cap approvato e **260 giorni ipotetici**. Qui un «giro completo»
attraversa entrambe le ali e torna a FS. Per la variante 10/11:

| Ipotesi puramente aritmetica | Giri completi/giorno | Bus-km/anno modellati |
| --- | ---: | ---: |
| 8 giri in ciascun verso | 16 | 102.502 |
| 10 giri in ciascun verso | 20 | 128.127 |
| H30/H60 **su tutto l'8 in ciascun verso** | 40 | 256.254 |

Il terzo rigo è **uno stress test della specifica eccessiva, non una
proposta di spesa**. Nemmeno i primi due sono orari raccomandati: 16–20
giri totali distribuiti su 16 ore non darebbero automaticamente frequenza
utile nel senso rapido per ogni località, e mancano riposizionamenti e
calendario approvato. La separazione delle ali a FS non fa risparmiare
km a parità di corse: ovest ed est sommano comunque. Corse limitate,
interlinee, percorso più corto o una diversa distribuzione temporale
possono cambiare la produzione, **ma devono essere valutati come servizi
effettivi**, con accessibilità, tempi verso FS e coincidenze ricalcolati.

La richiesta politica non è «finanziare 256 mila km» né «tagliare subito
3,213 km». È **verificare il concept inclusivo** e ricevere un progetto
di esercizio che esponga trasparentemente servizio e risorse necessari.
Il confronto con il cap viene dopo la verifica della funzione passeggeri;
non si sceglie una frequenza ridotta solo dividendo un numero di giri.

## Richiesta al tavolo

1. Verificare su strada il percorso e i punti di salita nei due versi,
   soprattutto Olgiate sud e Via Cantù, inclusi spazio bus, attraversamenti
   e accesso pedonale. Misurare i tempi con sosta e recupero.
2. Costruire **un orario congiunto** dei due versi e dei passaggi a FS,
   indicando tempi frazione↔FS, coincidenze S8, mezzi e tutti i chilometri,
   inclusi riposizionamenti. Confrontare la copertura 5/8/10 minuti nei
   cinque comuni e nelle due aree di Olgiate con i benchmark già pubblicati.
3. Consegnare lo schema inclusivo verificato, dichiarando per ogni
   località le frequenze nel senso utile, span e tempi verso FS, insieme
   a km e mezzi necessari. Confrontarlo **poi** con il cap e con una
   variante di efficienza, senza eliminare oggi fermate o frazioni.
   Nessun nuovo budget o orario è approvato qui.

Questa scheda fissa **un solo concept** e un confronto finito. La decisione
di esercizio segue le verifiche sopra. `network_selected=false`;
`primary_selection_authorised=false`;
`runner_up_selection_authorised=false`.

La [lista verificabile delle consegne richieste](RT031_LINEA8_CAPITOLATO_DI_VERIFICA_V3.md)
accompagna la proposta. La precedente bozza di email non è stata inviata
e va aggiornata soltanto dopo che la proposta tecnica sarà chiusa.
Dettagli, fonti e limiti nella
[proposta conclusiva](RT031_PROPOSTA_CONCLUSIVA_DI_INDIRIZZO_V3.md).
