# Linea 8 — rafforzamento interno, non chiusura di carta

La base confermata resta una linea unica, 16 giri completi, 27 siti e 28 eventi non-FS; calendario feriale 2027 di 254 giorni. Nessuna modifica sotto è adottata tacitamente.

## Correzioni verificate da un capo all’altro

| Confronto | Km commerciali feriali 2027 | Margine su riferimento 111.419 | Massimo mezzi nei 27 casi | Minuti servizio nominale aggiunti/giorno |
|---|---:|---:|---:|---:|
| confirmed_baseline | 110229.936 | 1189.064 | 4 | 0.000 |
| evening_plus2_same_geometry | 110229.936 | 1189.064 | 4 | 14.000 |
| scarpone_bypass_evening_plus2 | 110334.948 | 1084.052 | 4 | 11.006 |

Sono soli km commerciali della base lunedì–venerdì, esclusi festivi nazionali; non comprendono sabato, km a vuoto o costo completo. 111.419 è il riferimento produttivo pubblicato, non un finanziamento certificato.

Ogni confronto ricostruisce e valida i 16 giri × 31 eventi per ciascuno dei nove casi marcia/dwell. Sono salvati i ledger nominale/lento, i loro hash e i 27 blocchi completi. Si ricalcolano tutte le 74 chiamate ferroviarie del 1 ottobre 2026: 148 righe e 296 flussi, Lecco/Milano e arrivo/partenza. Mezzo continuo non significa autorizzazione a restare a bordo.

**Sera +2 minuti:** cambia solo la partenza FS intermedia dei giri 9–15. La banca ovest diventa 17:37–19:37 ogni 30 minuti, margine dopo cammino assunto di 3 minuti da zero a due minuti. Nessuna precedente compatibilità bus→treno nei nove casi persa sullo stesso tracciato; alcune attese aumentano due minuti. Il servizio aumenta 14 minuti/giorno, 59,27 ore sui 254 giorni: stessi km non significa stesso costo.

**Scarpone:** Via Pilata → rotatoria → Via Como evita il tratto classificato service. Nessuna classificazione OSM prova da sola divieto o sicurezza. Il punto originale non è raggiungibile senza service nel dominio verificato; non viene dichiarato magicamente conservato.

La deviazione aggiunge **25.839 m/giro**; l’ipotesi di attacco più vicina fra i nodi del bypass dista **17.891 m** dal vecchio nodo. È un punto del grafo su Via Como, non una palina approvata. Il percorso completo resta senza inversioni immediate e supera tutte le transizioni via-node rappresentate; restrizioni a storia completa, sagoma e accosto non sono certificati.

## Copertura ricalcolata, non trasferita per nome

| Comune/codice | Variazione punti % a 5 min | a 8 min | a 10 min |
|---|---:|---:|---:|
| Brivio | +0.0000 | +0.0000 | +0.0000 |
| Calco | +0.0000 | +0.0000 | +0.0000 |
| Olgiate Molgora | +0.0000 | +0.0000 | +0.0000 |
| Santa Maria Hoe | +0.0000 | +0.0000 | +0.0000 |
| La Valletta Brianza | +0.0000 | +0.0000 | +0.0000 |
| Totale | +0.0000 | +0.0000 | +0.0000 |

Anche le perdite e i guadagni lordi sono ricalcolati e salvati per comune e soglia: zero in questo specifico modello, non uno scambio nascosto di abitanti dietro la stessa percentuale.

## Partenze del confronto serale, non nuovo orario adottato

| Giro completo | FS inizio est, invariata | FS intermedia ovest, base | FS intermedia ovest, confronto |
|---:|---|---|---|
| 1 | 06:05:00 | 07:00:00 | 07:00:00 |
| 2 | 06:35:00 | 07:30:00 | 07:30:00 |
| 3 | 07:05:00 | 08:00:00 | 08:00:00 |
| 4 | 07:35:00 | 08:30:00 | 08:30:00 |
| 5 | 08:05:00 | 09:00:00 | 09:00:00 |
| 6 | 09:00:00 | 09:55:00 | 09:55:00 |
| 7 | 10:00:00 | 10:50:00 | 10:50:00 |
| 8 | 11:55:00 | 12:50:00 | 12:50:00 |
| 9 | 13:40:00 | 14:35:00 | 14:37:00 |
| 10 | 15:40:00 | 16:35:00 | 16:37:00 |
| 11 | 16:40:00 | 17:35:00 | 17:37:00 |
| 12 | 17:10:00 | 18:05:00 | 18:07:00 |
| 13 | 17:40:00 | 18:35:00 | 18:37:00 |
| 14 | 18:10:00 | 19:05:00 | 19:07:00 |
| 15 | 18:40:00 | 19:35:00 | 19:37:00 |
| 16 | 19:40:00 | 20:30:00 | 20:30:00 |

Copertura potenziale con stessi abitanti e grafo pedonale RT028, non domanda o accessibilità fisicamente approvata. Non si pretende che 18 metri preservino una percentuale senza ricalcolarla.

## Il problema mattutino è ora circoscritto e dimostrato

Per gli stessi cinque treni che arrivano da Milano (:02) e i cinque verso Milano (:56), la fase della stessa corsa est deve stare in un intervallo largo soltanto **13.4 secondi**, nel caso più lento ereditato e con 3 minuti assunti per ogni trasferimento. Anche una fase continua bilanciata potrebbe offrire al massimo **6.7 secondi per lato**. Non è una soglia adottata o una prova di impossibilità globale.

Anticipare di quattro minuti aumenta il margine verso Milano ma perde il bus immediato per chi arriva dal treno :02. Non è rafforzamento senza contropartite. Qui serve ridurre e misurare il tempo est effettivo, oppure dichiarare esplicitamente quale collegamento accettare di peggiorare: non basta rietichettare il margine.

## Chiusura onesta

Sono chiusi i ricalcoli di questi interventi locali, non l’intero esercizio. Rimangono la fragilità AM, la verifica fisica del punto Scarpone e degli altri accosti, tempi reali/turni/deposito, treni 2027, finanziamento e sabato separato. Nessun modulo per l’operatore elimina questi buchi. Non vengono aggiunti pesi, budget o banda di incertezza.

[Evidenza macchina e registri completi](../outputs/phase2/rt031_line8_local_shortcuts_v3/fixed_design_strengthening_20261002.json). [Geometrie Scarpone](../outputs/phase2/rt031_line8_local_shortcuts_v3/scarpone_main_road_comparison_20261002.geojson).
