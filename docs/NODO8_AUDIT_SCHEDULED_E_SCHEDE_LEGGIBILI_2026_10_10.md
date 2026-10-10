# Audit scheduled D184/D185 e schede leggibili

Revisione `20261010e`, 10 ottobre 2026. Due subagent hanno svolto separatamente l'audit delle animazioni e la correzione delle schede; integrazione, verifica browser e pubblicazione sono gestite nel task principale.

## Risposta sulla fedeltà agli orari

L'animazione D184/D185 **non è esatta rispetto a tutti gli orari scheduled alle proprie fermate**. La distinzione non dipende dall'assenza di GPS.

- Sono incluse tutte le 34 corse del giorno storico verificato, 28 aprile 2026: 15 D184 e 19 D185.
- 374 dei 422 eventi conservano l'orario GTFS originale, inclusi tutti gli estremi di corsa.
- 48 eventi intermedi usano un orario stimato esclusivamente per l'animazione. Scarto massimo: 213,068 secondi, circa 3 min 33 s.
- Esempio reale: D185, corsa `A2013327-0036-50214`, fermata `300482` Caprino–Roccolino, seconda occorrenza: fonte **14:11:10**, visualizzazione **14:14:43**.
- Fra due fermate, anche quando entrambi gli orari sono conservati, la posizione è interpolata per distanza lungo la shape ufficiale. Non è una posizione certificata al secondo.
- 410 occorrenze si allineano entro 1,891 metri dalle coordinate palina. Dodici ritorni FS utilizzano l'estremità della shape vicino alla stazione, anziché la coordinata sorgente distante circa 500 metri. Dieci partenze FS restano sulla Statale.
- Non sono aggiunte soste: in questa fonte arrivo e partenza coincidono. La soglia di 90 km/h del modello è un controllo grafico, non un limite o una velocità reale certificata.

Nessun dato o orario della fonte è stato modificato in questa revisione. Per avere un modello fedele a tutti gli orari di fermata, occorre riconciliare una fonte completa e coerente, non dichiarare esatte queste 48 stime. Il pannello tecnico del sito ora esplicita sia questa non-esattezza scheduled, sia lo scarto massimo. Il confronto della frequenza 2026/27 rimane distinto dall'animazione storica 2025/26.

## Correzione delle schede

La causa del verde scuro su sfondo scuro era la regola globale iniettata da `journey-explore-prelude.js`, che imponeva sfondo e padding con `!important`. Il foglio delle nuove schede aveva colori per una superficie chiara, ma quella superficie veniva sovrascritta.

La correzione è limitata a `.nodo8-map-popup`:

- Fondo crema completamente opaco, senza trasparenza o filtro; testo primario verde scuro e secondario ad alto contrasto.
- Contrasto teorico 10,73:1 primario e 5,87:1 secondario contro il fondo.
- Titolo più chiaro, tabella compatta a 13 px, ordinale e descrizione della ripetizione nella stessa riga.
- Due occorrenze di San Zeno e Olgiate sud preservate, con tempi in minuti e secondi; nessuna fusione di eventi o inferenza di un viaggio garantito.
- Pulsante orari pieno verde, chiusura 44×44 px, focus visibile e metodo chiuso fino a richiesta.
- Frecce della scheda coerenti con il fondo chiaro e dimensioni contenute nella finestra.
- Anche le durate nelle schede dettagli della pagina principale usano ora minuti e secondi, invece dei residui minuti decimali. I valori sorgente sono identici.

## Verifiche prima della pubblicazione

97 test Node, 44 test Python e 8 sottotest superati. Test aggiunto per l'override dello sfondo iniettato, contrasto, pulsante orari e dichiarazione scheduled.

Browser desktop, San Zeno: sfondo calcolato `rgb(245,242,233)`, titolo `rgb(21,61,52)`, padding 16 px, due righe e metodo chiuso. Scheda circa 253×347 px, contro la precedente presentazione molto più alta e a basso contrasto. Il pulsante apre il sito `PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE` nella pagina principale e mostra i 16 giri con entrambe le occorrenze.

Browser a 375 px: scheda di San Zeno interamente contenuta nella finestra (x 61–315, y 276–623), entrambe le righe presenti e nessun overflow orizzontale. Nella verifica mobile è emerso anche il footer del racconto dipinto sopra la mappa: footer e indicatori di capitolo ora vengono nascosti soltanto in modalità Esplora, senza cambiare il layout o rimuoverli dal racconto.

Verificata anche Olgiate sud a 375 px: entrambe le occorrenze 15/28 presenti, fondo chiaro e nessun overflow. Su smartphone, mentre una scheda Nodo8 è aperta, i controlli dell'esplorazione vengono temporaneamente nascosti per non coprirne la parte inferiore. Chiudere la scheda restituisce gli stessi controlli e non cambia orologio, linee o selezione.

FS nel livello cartografico e OSM tenue della precedente revisione sono mantenuti. Nessuna modifica a fonti, percorso, fermate, chilometri, calendario, autorizzazioni o risultati della proposta. I file non tracciati estranei restano esclusi.
