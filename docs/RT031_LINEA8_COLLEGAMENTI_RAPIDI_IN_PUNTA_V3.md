# Linea 8 — collegamenti rapidi nelle direzioni delle punte

## Risultato concreto del confronto

**115.800,435 km/anno di servizio: +4.381,435 km, pari a +3,93% rispetto a 111.419.** Nessuna località eliminata e nessun nuovo percorso inventato. Il conto assume ancora 260 giorni; deposito e riposizionamenti sono esclusi e non stimati. L'apertura dell'utente a un piccolo sforamento autorizza il confronto, non la modifica automatica del tetto.

Si riprende il cambio di senso del testimone originario, invece di mantenere il senso fisso tutto il giorno. Si aggiunge **una sola corsa mattutina per ala**, alle 06:12. Le precedenti 34 corse non sono né spostate né modificate: diventano 36, cioè 18 per ala. Rispetto al caso originario 109k l'aggiunta vale 6.514,446 km/anno; rispetto al tetto lo sforamento è invece 4.381,435. I due confronti non vanno confusi.

| Località | Mattina: località → FS | Resto della giornata: FS → località |
|---|---:|---:|
| Olgiate sud | **4,1 min** | **4,3 min** |
| San Zeno / Via Cantù | **2,6 min** | **2,5 min** |

Tempi a bordo nel modello con marcia +10% e 30 secondi di sosta a ogni nodo di fermata distinto. Non includono accesso o attesa. Le posizioni e i lati di fermata sono ancora ipotetici.

**Questo migliora l'andata mattutina e il ritorno, non entrambi i versi tutto il giorno.** Da FS verso queste località al mattino rimangono circa 31–32 minuti; dalle località verso FS dopo il cambio di senso rimangono circa 31 minuti. Per rendere rapido anche il controflusso serve un diverso intervento sul servizio o sul percorso: non è una proprietà di questa proposta.

## Orario costruito, senza corse nascoste

Le due ali partono da FS agli stessi minuti:

| Periodo | Partenze da FS | Sensi |
|---|---|---|
| Prima punta: cinque corse | **06:12**, 06:42, 07:12, 07:42, 08:12 | Ovest A / est B, arrivo rapido in stazione da Olgiate sud e San Zeno |
| Morbida: otto corse | 08:40, 09:40, 10:40, 11:40, 12:40, 13:40, 14:40, 15:40 | Ovest B / est A, uscita rapida dalla stazione verso i due quartieri |
| Seconda punta: cinque corse | 16:40, 17:10, 17:40, 18:10, 18:40 | Ovest B / est A |

Prima–ultima partenza: **12 ore e 28 minuti**, non una promessa di 13–14 ore. Gli ultimi giri rientrano a FS intorno alle 19:14–19:16 nel modello.

Ogni occorrenza di fermata dei sensi di punta ha cinque passaggi distanziati di 30 minuti: due ore tra primo e quinto. Le fasce locali si spostano con il percorso. Per esempio, Olgiate sud verso FS ha i cinque passaggi circa alle **06:43, 07:13, 07:43, 08:13, 08:43**. Non sono una promessa simultanea 07–09 in tutti i luoghi.

Nel caso di marcia/sosta sopra indicato, l'intervallo massimo fra opportunità della stessa identità rimane 60 minuti anche al cambio di senso. Questo controllo è ottimistico: presume accessibili i diversi lati/occorrenze. Non certifica un unico marciapiede utilizzabile in entrambi i sensi. I controlli più severi sulle finestre orarie comuni sono conservati nell'artefatto e continuano a segnalare fallimenti: non sono stati eliminati per dichiarare H30 valido ovunque e in qualsiasi finestra.

## Coincidenze e mezzi: cosa regge e cosa resta condizionato

- Sul giorno ferroviario congelato **3 settembre 2026**, le cinque corse mattutine arrivano a FS circa 06:47, 07:17, 07:47, 08:17 e 08:47. Con tre minuti di trasferimento, raggiungono i cinque S8 per Milano **06:56–08:56**, con circa 5,5 minuti di margine residuo nel modello.
- Le partenze pomeridiane raggiungono nel modello i cinque arrivi da Milano **16:32–18:32**, lasciando cinque minuti dopo il trasferimento ipotizzato.
- Con marcia +10% e soste di 30 secondi, la copertura condizionata richiede **quattro mezzi**, sia con 5, sia con 10, sia con 15 minuti di recupero per ala. Non sono ancora turni autisti con deposito.
- **Non è robusta su tutta la sensibilità.** Con marcia +10%, un minuto per fermata e 15 minuti di recupero, la copertura arriva a cinque mezzi. Gli intervalli ottimistici possono salire a 66,13 minuti e i treni mattutini nominali non vengono mantenuti. Sono controesempi deterministici, non probabilità di perdere la coincidenza. Servono tempi osservati per stabilire quale scenario sia realistico e per correggere l'orario definitivo.

Gli orari ferroviari congelati non sono una verifica del servizio attuale. Non si dichiara una coincidenza affidabile al 100%.

## Tracciato e siti

![Tracciato stradale delle due ali, geometria invariata e non ancora validata per esercizio](../outputs/phase2/rt031_line8_local_shortcuts_v3/full_retention_context.png)

Rimangono **28 identità/siti includendo FS**, non 28 paline autorizzate. Olgiate sud e San Zeno/Via Cantù rimangono distinti. La copertura pedonale potenziale già calcolata non cambia perché non cambiano i siti: Brivio 89,09%, Calco 68,21%, Olgiate 84,56%, Santa Maria Hoè 95,75%, La Valletta Brianza 67,85%, totale 79,16% a 10 minuti. Non equivale a copertura temporale o domanda passeggeri certificata.

## Confine della proposta

Questa è un'alternativa concreta al senso fisso, non una selezione finale: privilegia le direzioni utili all'andata mattutina e al ritorno conservando i territori, con un +3,93% **dei soli km di servizio**. Per un giudizio sullo sforamento totale mancano deposito e riposizionamenti; per l'esercibilità mancano verifiche di fermate, autobus, restrizioni complete, tempi, calendario, costi e turni.

Fonte riproducibile: `outputs/phase2/rt031_line8_local_shortcuts_v3/peak_direction_18_trips.json`. Contiene tutte le corse e le occorrenze ordinate, i tempi di viaggio anche nel verso sfavorevole, la sensibilità e i confronti H30 più severi.

`reference_cap_changed=false`; `approved_uplift_percent=null`; `actual_timetable_certified=false`; `network_selected=false`; `primary_selection_authorised=false`; `runner_up_selection_authorised=false`; `decision_budget_km=null`; `uncertainty_band_min=null`.
