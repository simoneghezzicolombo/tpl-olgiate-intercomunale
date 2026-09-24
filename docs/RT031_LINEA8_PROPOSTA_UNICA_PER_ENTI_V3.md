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
attuali è una preferenza da misurare, non un veto automatico.

## Servizio da progettare

La richiesta è un orario prevedibile, con buona copertura della giornata e
coincidenze S8 verso Milano e Lecco. **Prima consegna dell'operatore:** una
proposta per **una sola Linea 8** che parta dal cap vigente di 111.419
bus-km/anno e mostri per ogni località le partenze e i viaggi utili verso
e dalla stazione, per ala e per verso. Si cerchi la fascia 06–22 e si
dia priorità ai picchi 07–09 e 17–19, ma **H30 di punta/H60 di morbida
non è un obbligo simultaneo su tutto l'8 in entrambi i sensi**. Se un
servizio utile non sta nel cap, l'operatore deve mostrare la modifica
minima verificabile di percorso, orario o risorse, con le perdite esplicite;
non un preventivo implicito di 256 mila km. Verificare separatamente il
sabato. La classe H60 richiede una decisione esplicita rispetto alla
policy vigente. A FS va dichiarato se il passeggero resta sulla stessa
corsa o cambia, con quale attesa. Nessuna fase S8 è ancora selezionata.

## Riscontro tecnico già disponibile

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

| Brivio | Calco | Olgiate | Santa Maria Hoè | La Valletta | Totale |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 81,88% | 68,21% | 84,56% | 93,43% | 67,85% | 77,58% |

Queste percentuali sono **condizionali**: i 24 nodi non sono ancora un
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
È un'alternativa esplicita di conservazione delle fermate, non una scelta
automatica: l'effetto su tempi, risorse e viaggi verso FS va verificato.

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

La richiesta politica non è «finanziare 256 mila km». È ricevere **una
proposta unica credibile entro il cap**, insieme alla quantificazione del
più piccolo incremento eventualmente indispensabile per non sacrificare
la funzione dei cinque comuni e delle due zone di Olgiate. Non si sceglie
una frequenza ridotta solo dividendo un numero di giri.

## Richiesta al tavolo

1. Verificare su strada il percorso e i punti di salita nei due versi,
   soprattutto Olgiate sud e Via Cantù, inclusi spazio bus, attraversamenti
   e accesso pedonale. Misurare i tempi con sosta e recupero.
2. Costruire **un orario congiunto** dei due versi e dei passaggi a FS,
   indicando tempi frazione↔FS, coincidenze S8, mezzi e tutti i chilometri,
   inclusi riposizionamenti. Confrontare la copertura 5/8/10 minuti nei
   cinque comuni e nelle due aree di Olgiate con i benchmark già pubblicati.
3. Consegnare **prima** uno schema verificabile entro il cap,
   dichiarando per ogni località le frequenze nel senso utile, span e
   tempi verso FS. Se non soddisfa il brief territoriale, indicare il
   minimo incremento di risorse o la modifica di tracciato necessari e
   quantificarne l'effetto. Nessun nuovo budget o orario è approvato qui.

Questa scheda fissa **un solo concept** e un confronto finito. La decisione
di esercizio segue le verifiche sopra. `network_selected=false`;
`primary_selection_authorised=false`;
`runner_up_selection_authorised=false`.

La [bozza di comunicazione](RT031_EMAIL_A_AGENZIA_OPERATORE_V3.md) e la
[lista verificabile delle consegne richieste](RT031_LINEA8_CAPITOLATO_DI_VERIFICA_V3.md)
sono pronte per Agenzia e operatore; la comunicazione non è stata inviata.
Dettagli, fonti e limiti nella
[proposta conclusiva](RT031_PROPOSTA_CONCLUSIVA_DI_INDIRIZZO_V3.md).
