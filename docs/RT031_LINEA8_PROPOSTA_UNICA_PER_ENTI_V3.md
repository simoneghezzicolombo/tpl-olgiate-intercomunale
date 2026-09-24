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
coincidenze S8 verso Milano e Lecco. Lo scenario di lavoro è 06–22 nei
feriali, **H30 07–09 e 17–19, H60 nelle altre ore**, con frequenza dichiarata
**per ala e per verso** e verifica separata del sabato. La classe H60 richiede
una decisione esplicita rispetto alla policy vigente. Il passaggio intermedio
a FS deve dire se il passeggero prosegue sulla stessa corsa o deve cambiare,
e con quale attesa. Nessuna fase oraria ferroviaria è ancora selezionata.

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

Il cap vigente è **111.419 bus-km/anno**. Con 260 giorni ipotetici, dieci
giri completi per verso al giorno produrrebbero circa **122.991 km/anno**
già nel modello; perfino il limite inferiore stradale ottimistico è
**118.563 km/anno**. Se H30/H60 sulla fascia 06–22 significa nominalmente
20 giri completi **per ciascun verso**, il conto sale a circa **245.982
km/anno** nel modello. Sono scenari aritmetici, senza riposizionamenti né
orario o calendario approvati. Venti giri *totali* ripartiti fra i due versi
non darebbero H30/H60 per verso. Non si deve usare il cap come
`decision_budget_km` del finalizzatore.
La riparazione mirata a 10/11 aggiunge circa **0,988 km per giro completo** nella
sequenza stradale più corta: il corrispondente scenario nominale H30/H60
per verso sarebbe circa **256.254 km/anno**, ancora senza dwell o
riposizionamenti. L'ordine opposto delle due fermate di Beverate aumenta
leggermente la distanza ma migliora un poco l'accesso a 5 minuti a Brivio;
la scelta precisa richiede sopralluogo e orario.

### La scelta di risorse, resa esplicita

Il [conto riproducibile delle percorrenze complete](../outputs/phase2/rt031_line8_service_envelope_v3/envelope.json)
usa il cap approvato e **260 giorni ipotetici**. Una coppia giornaliera
significa un giro completo ovest+est per ciascuno dei due versi; non è
una semplice coppia di partenze FS↔una frazione.

| Variante | Km per coppia di giri | Massimo intero di coppie/giorno entro il cap, prima di altri km | H60 per 10 ore in entrambi i versi | H60 per 16 ore | H30 per 4 ore + H60 per 12 ore |
| --- | ---: | ---: | ---: | ---: | ---: |
| 10/11 fermate attuali | 49,280 | 8 | 128.127 km/anno | 205.003 km/anno | 256.254 km/anno |
| 11/11 fermate attuali | 52,208 | 8 | 135.740 km/anno | 217.184 km/anno | 271.480 km/anno |

Già **H60 per sole 10 ore nei due versi supera il cap** di 111.419
km/anno, se ogni corsa percorre tutto l'8. Otto coppie al giorno della
variante 10/11 consumano 102.502 km/anno e lasciano appena 8.917 km
per ogni altra percorrenza; non sono un orario proposto. Il calcolo non
esclude esercizi con corse limitate, interlinee o calendari differenti,
ma questi richiedono una nuova descrizione degli eventi passeggeri e
non possono ereditare automaticamente le quote di accesso dell'8 intero.
La separazione delle due ali a FS **non crea da sola risparmio**: nella
versione 10/11 una coppia di giri dell'ovest vale 24,014 km e una
dell'est 25,265 km, che sommano agli stessi 49,280 km. Se il cap resta
fisso, l'allocazione diventa uno scambio territoriale: 8 coppie quotidiane
ovest e 9 est sono aritmeticamente entro il tetto, così come 10 ovest e
7 est, ma nessuna delle due promette H60 per 10 ore su **entrambe** le ali.
Sono conteggi di percorrenze, non orari con corse passeggeri o coincidenze.
Per le 16 ore H30/H60 richieste, il solo modello 10/11 supera il cap
di circa **144.835 km/anno**, prima di riposizionamenti e di qualsiasi
servizio non contato nei 260 giorni ipotizzati.

La richiesta politica al tavolo è quindi precisa: **quantificare e deliberare
le risorse per il servizio completo desiderato**, oppure dichiarare quale
parte della promessa cambia e ricalcolare accessibilità, tempi e
coincidenze per quella versione. Il conto non seleziona da sé una frequenza
ridotta né autorizza la variante 10/11 come rete in esercizio.

## Richiesta al tavolo

1. Verificare su strada il percorso e i punti di salita nei due versi,
   soprattutto Olgiate sud e Via Cantù, inclusi spazio bus, attraversamenti
   e accesso pedonale. Misurare i tempi con sosta e recupero.
2. Costruire **un orario congiunto** dei due versi e dei passaggi a FS,
   indicando tempi frazione↔FS, coincidenze S8, mezzi e tutti i chilometri,
   inclusi riposizionamenti. Confrontare la copertura 5/8/10 minuti nei
   cinque comuni e nelle due aree di Olgiate con i benchmark già pubblicati.
3. Presentare **due contabilità esplicite**: le risorse necessarie per la
   frequenza richiesta e il servizio realmente ottenibile mantenendo il cap
   vigente. La raccomandazione di progetto privilegia il servizio utile al
   passeggero e porta il maggiore fabbisogno a decisione pubblica; non
   approva qui un nuovo budget o una frequenza ridotta.

Questa scheda fissa **un solo concept** e un confronto finito. La decisione
di esercizio segue le verifiche sopra. `network_selected=false`;
`primary_selection_authorised=false`;
`runner_up_selection_authorised=false`.

Dettagli, fonti e limiti nella [proposta conclusiva](RT031_PROPOSTA_CONCLUSIVA_DI_INDIRIZZO_V3.md).
