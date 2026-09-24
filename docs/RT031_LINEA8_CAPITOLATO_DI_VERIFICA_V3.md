# Linea 8 — capitolato minimo di verifica per Agenzia e operatore

**24 settembre 2026.** Oggetto: un'unica linea riconoscibile con Olgiate FS
come cerniera; ala ovest via Monticello/Rovagnate/Perego/Santa Maria Hoè e
quartiere residenziale a sud della SS342; ala est via Calco/Arlate/Brivio/
Beverate e San Zeno–Via Cantù. I due versi sono parte della proposta.

La [scheda di indirizzo](RT031_LINEA8_PROPOSTA_UNICA_PER_ENTI_V3.md) è il
brief politico-tecnico. La variante che incontra 10/11 identità attuali è
la **base da verificare**, non una rete selezionata. Quella 11/11 è
l'alternativa di conservazione delle fermate da confrontare sullo stesso
substrato. Nessuno dei punti nuovi è una fermata autorizzata.

## Cosa consegnare

1. **Percorso e fermate per verso.** Polilinea diretta e ordinata,
   autorizzazioni/restrizioni di svolta con storia sufficiente, idoneità del
   bus e manovre a FS; per ogni fermata: ID, posizione, lato, direzione,
   accesso pedonale, spazio e sicurezza, stato autorizzativo. Verificare
   esplicitamente `P2V2S_0031` su Via Aldo Moro e il sito ancora da
   identificare su Via Cantù. Un nodo stradale incontrato non vale come
   evento di salita. Se una delle 24 identità esistenti modellate non è
   servibile, ricalcolare accessibilità e retention; non conservare le
   percentuali precedenti.
2. **Eventi di servizio.** Per ogni pattern/corsa e giorno tipo, fornire
   sequenza ordinata degli eventi di arrivo, partenza, salita e discesa;
   identità di linea e corsa, direzione, fermata e occorrenza. A Olgiate FS
   dichiarare se il passeggero rimane sulla stessa corsa o cambia, con
   piattaforma e attesa. La continuità del veicolo non prova continuità
   del servizio passeggeri. Per ogni località rappresentativa, produrre
   viaggio verso FS e da FS nei due versi, comprensivo di cammino, attesa,
   sosta e tempi di corsa: i [minuti stradali](../outputs/phase2/rt031_current_stop_repair_v3/road_options.json)
   non sono un sostituto.
3. **Orario e risorse.** Presentare prima un orario feriale credibile entro
   111.419 bus-km/anno, cercando fascia 06–22 e rinforzo nelle punte
   07–09 e 17–19. H30/H60 è una preferenza di servizio da verificare,
   **non** un obbligo di 40 giri completi dell'8 ogni giorno. Specificare
   frequenza effettiva per **località, ala e verso** e il tempo verso FS;
   presentare separatamente sabato e altri giorni di
   esercizio. Misurare tempi con sosta, recupero e traffico; fornire
   blocchi veicolo, mezzi necessari, chilometri di servizio e di
   riposizionamento, calendario annuo e margini di robustezza. Verificare
   coincidenze S8 per Milano e Lecco, bus→treno e treno→bus, su eventi
   effettivi, senza convertirne gli esiti deterministici in probabilità.
4. **Conto e confronto.** Il primo conto è il servizio progettato entro
   il cap, se fattibile. Se non rende utili i viaggi da tutte le aree
   richieste, presentare un'alternativa con il **minimo incremento di km
   motivato** o una modifica fisica del percorso, esplicitando che cosa
   migliora e che cosa peggiora. Per le alternative esporre 5/8/10 minuti
   di accesso pedonale nei cinque comuni e
   nelle aree Olgiate sud/San Zeno, fermate attuali perse o conservate,
   tempo verso FS per località, span, frequenza, coincidenze, mezzi e
   chilometri. Confrontare anche la variante 11/11. La classe H60/mista
   richiede un'eccezione motivata rispetto alla policy di frequenza; non
   diventa approvata per il solo fatto di essere stata simulata.

## Criterio di lettura e decisione

Il [conto condizionale](../outputs/phase2/rt031_line8_service_envelope_v3/envelope.json)
indica circa **256.254 km/anno** soltanto per uno stress test che impone
20 giri completi **in ciascun verso** su 260 giorni ipotetici. Non è
il target di spesa né una richiesta di budget. La stessa variante 10/11
costerebbe nel modello circa 102.502 km con 16 giri completi totali al
giorno o 128.127 km con 20, ma nessuno dei due conteggi prova un orario
utile. Separare le ali a FS senza ridurre la produzione non risolve il
divario. Corse limitate sono
ammissibili come alternativa da analizzare, ma non ereditano automaticamente
copertura, direttezza o continuità dell'intero 8.
Se si mantenessero **20 giri completi totali al giorno** per 260 giorni,
il cap imporrebbe una lunghezza media non superiore a **21,427 km/giro**
prima di ogni riposizionamento; la variante 10/11 è a circa **24,640 km**.
Servirebbe quindi togliere almeno **3,213 km/giro** al modello, oppure
ottenere risorse ulteriori. È un obiettivo di ridisegno *condizionato a
quei 20 giri*, non la prova che esista un percorso equivalente più corto.

La decisione di esercizio resta **NON PRONUNCIABILE** se mancano percorso
legale completo, fermate nei versi necessari, eventi passeggeri, orario
congiunto, blocchi e km annui inclusivi dei riposizionamenti, oppure il
confronto territoriale ricalcolato sul servizio effettivamente offerto.
Se il servizio utile supera il cap, occorre una **delibera esplicita di
risorse** sul fabbisogno minimo motivato; se il cap non cambia, occorre
dichiarare precisamente la promessa ridotta e valutarla contro i benchmark
e il servizio attuale. Nessun dato mancante
si sostituisce con OD comunale non disaggregata, GJT pesata inventata o
probabilità empiriche di mancata coincidenza.

Questo capitolato non valorizza `decision_budget_km` o
`uncertainty_band_min`. `network_selected=false`;
`primary_selection_authorised=false`;
`runner_up_selection_authorised=false`.
