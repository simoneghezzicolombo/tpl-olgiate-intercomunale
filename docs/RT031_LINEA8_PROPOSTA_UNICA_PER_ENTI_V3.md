# Linea 8 — proposta unica per il tavolo con Agenzia e operatore

**24 settembre 2026 · indirizzo di progetto, non autorizzazione all'esercizio.**

## Proposta

Una sola linea pubblica riconoscibile, con **Olgiate-Calco-Brivio FS** come
cerniera fra due ali e servizio progettato nei due versi:

- **Ovest:** FS → Monticello/Scarpone e area Mondonico → Rovagnate → Perego
  → Santa Maria Hoè → **Olgiate residenziale a sud della SS342** → FS.
- **Est:** FS → Calco Cornello/centro, con verifica di Calco alta → Arlate
  → Brivio centro → Beverate → **San Zeno/Via Cantù** → FS.

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
trova 16 identità di fermata esistente i cui nodi sono incontrati dal
percorso in entrambi i versi. Se diventassero tutte eventi di salita, e se
i due punti nuovi fossero sicuri e serviti, la quota di popolazione con
una fermata entro **10 minuti a piedi** sarebbe:

| Brivio | Calco | Olgiate | Santa Maria Hoè | La Valletta | Totale |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 76,14% | 62,81% | 72,86% | 76,63% | 67,85% | 70,42% |

Queste percentuali sono **condizionali**: i 16 nodi non sono ancora un
orario con fermate effettive, i due nuovi punti non sono approvati e la
matrice misura accesso pedonale, non viaggio verso FS o domanda osservata.
Per confronto, usando solo le fermate rappresentative già nominate nel
percorso, Calco è al 47,97% e Olgiate al 31,26%: la scelta degli eventi di
fermata cambia materialmente la proposta.
Solo **5 delle 11 identità di fermata attuali** del sottoinsieme RT031 sono
incontrate nei due versi: il confronto pedonale individua perdite locali
anche dove la percentuale comunale cresce. In particolare Brivio passa
condizionalmente dal 78,38% al 76,14% a 10 minuti. La conservazione delle
fermate resta una preferenza da trattare con soluzioni locali motivate.

Il cap vigente è **111.419 bus-km/anno**. Con 260 giorni ipotetici, dieci
giri completi per verso al giorno produrrebbero circa **122.991 km/anno**
già nel modello; perfino il limite inferiore stradale ottimistico è
**118.563 km/anno**. Se H30/H60 sulla fascia 06–22 significa nominalmente
20 giri completi **per ciascun verso**, il conto sale a circa **245.982
km/anno** nel modello. Sono scenari aritmetici, senza riposizionamenti né
orario o calendario approvati. Venti giri *totali* ripartiti fra i due versi
non darebbero H30/H60 per verso. Non si deve usare il cap come
`decision_budget_km` del finalizzatore.

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
