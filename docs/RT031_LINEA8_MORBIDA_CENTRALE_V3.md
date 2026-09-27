# Linea 8 — H90/H120 nelle sole ore centrali

## Risultato

La nuova flessibilità autorizzata dall'utente permette un confronto da **122.339,721 km/anno**, senza eliminare siti e mantenendo H30 nelle punte e gli obiettivi ferroviari congelati. Rimangono **10.920,721 km (+9,80%)** oltre il riferimento di 111.419, prima dei trasferimenti da/per deposito. Non è ancora una proposta esercibile certificata o un aumento di budget approvato.

| Politica centrale confrontata | Km di servizio/anno | Corse d'ala/giorno | Eccedenza su 111.419 |
|---|---:|---:|---:|
| Riferimento H60 fuori punta | 143.929,084 | 40 | +29,18% |
| H90 solo 11–15 | 129.536,175 | 36 | +16,26% |
| H120 solo 11–15 | 129.536,175 | 36 | +16,26% |
| H90 solo 10–16 | 129.536,175 | 36 | +16,26% |
| H120 solo 10–16 | 122.339,721 | 34 | +9,80% |

Fuori dalla finestra centrale resta H60; H30 nelle punte prevale sempre. Sono limiti all'attesa del passeggero pronto a partire, non necessariamente partenze a minuti fissi. Anche i confini delle finestre sono verificati: alle 09:59 non si può attribuire automaticamente il limite di 120 minuti previsto dalle 10.

Tutti i cinque minimi sono provati **nel dominio dei quattro percorsi completi corretti**, con 49 combinazioni delle fasi di punta, partenze candidate ogni cinque minuti e quattro mezzi nominali. Non è un minimo su qualsiasi rete, orario o servizio parziale. Il precedente 141.065 includeva un diverso dominio di 64 percorsi, con corse parziali: non è il riferimento omogeneo per attribuire tutto il risparmio a questo solo cambiamento.

H120 11–15 non dà risparmi ulteriori rispetto a H90 11–15; nemmeno estendere H90 a 10–16 riduce i km. Questo rende H90 11–15 preferibile su queste sole dimensioni aggregate, ma non prova dominanza su ogni tempo di viaggio o ogni singola coincidenza. Nessun vincitore selezionato.

## Cosa rimane uguale e cosa peggiora

- Stessi percorsi stradali, **28 siti inclusa FS**: 26 siti d'inventario e due punti locali ipotetici, non 28 paline autorizzate.
- Stessi bacini di accessibilità pedonale potenziale. A 10 minuti: Brivio **89,09%**, Calco **68,21%**, Olgiate **84,56%**, Santa Maria Hoè **95,75%**, La Valletta Brianza **67,85%**. Non sono quote di passeggeri o copertura temporale invariata.
- Olgiate sud e San Zeno/Via Cantù restano distinti; viaggi locali nominali verso/dalla stazione circa 2,5–4,3 minuti, alle occorrenze appropriate.
- Stessi **297 controlli ferroviari per sito** e nove scenari deterministici di marcia/sosta; nessuna probabilità empirica di coincidenza inferita.
- Stessa ipotesi di 260 giorni identici e fascia di disponibilità 06:30–19:40. Non è un calendario adottato, né una certificazione delle prime/ultime salite in ciascun punto.
- **Peggiora l'accessibilità temporale centrale**: si possono attendere fino a 90/120 minuti. Non abbiamo dimostrato che le ore 10–16 siano tutte a domanda debole. Google Popular Times non dimostra domanda di linea o irrilevanza dei viaggi scolastici, lavorativi e sanitari.

## Esempio concreto 10–16 / H120

17 corse complete ovest B e 17 est A, nessuna corsa parziale. Finestre H30 comuni nel modello: **07–09 e 16:55–18:55**. Le partenze FS iniziano prima delle finestre perché occorre servire anche i viaggi verso FS dalle altre località.

| Ala | Partenze da FS del testimone, non orario pubblico |
|---|---|
| Ovest B | 06:30, 07:00, 07:30, 08:00, 08:30, 09:00, 10:00, 12:00, 13:55, 15:55, 16:35, 17:05, 17:35, 18:05, 18:35, 19:05, 19:40 |
| Est A | 06:35, 07:05, 07:35, 08:05, 08:35, 09:05, 10:05, 12:05, 14:05, 16:05, 16:40, 17:10, 17:40, 18:10, 18:40, 19:00, 19:40 |

Le due ali hanno 14,163015494 e 13,515654413 km. Contabilità riproducibile: **17 × (14,163015494 + 13,515654413) × 260 = 122.339,721 km/anno**. I risparmi vengono da sei corse complete in meno al giorno rispetto al riferimento di 40, non dalla semplice traslazione degli orari.

Quattro mezzi nel caso nominale, fino a sei nella griglia di stress con recuperi più lunghi: il risparmio di km **non** risolve la disponibilità dei mezzi nelle punte.

![Cammini effettivi del confronto](../outputs/phase2/rt031_line8_local_shortcuts_v3/deep_offpeak_witness.png)

## Requisiti dell'utente e ipotesi tecniche

Il [registro leggibile dalla macchina](../config/rt031_requirements_audit_v3.json) distingue 13 voci. Ferrovia, H30 nelle punte, servizio intercomunale e i due quartieri restano esigenze dell'utente. Le precise finestre comuni di due ore, la griglia delle fasi, i 260 giorni, i quattro mezzi nominali, i margini di trasferimento e le posizioni puntuali dei proxy sono rappresentazioni tecniche, non tutte decisioni irrevocabili dell'utente. Non sono state allentate in questo confronto.

L'autorizzazione nuova riguarda H90/H120 nella morbida pesante e il **confronto** delle due finestre, non l'adozione di una di esse o H120 in tutta la morbida. Questa registrazione aggiorna le precedenti note storiche «H90 non approvato» esclusivamente per il nuovo ambito.

## Limiti e conclusione utilizzabile

L'obiettivo ferroviario è protetto attraverso lo stesso elenco di treni del modello, ma la fonte è congelata al 3 settembre 2026 e non certifica l'orario oggi applicabile. I treni centrali da privilegiare non sono ancora definiti: il confronto non garantisce tutte le coincidenze della giornata. Restano da validare sei inversioni immediate, idoneità autobus, restrizioni complete dipendenti dalla storia, paline e interscambio fisico.

La scelta concreta emersa è **meno attese centrali (H90 11–15, 129.536 km)** contro **meno km (H120 10–16, 122.340 km)**, a parità dei siti e degli altri controlli qui mantenuti. Prima di trasformarla in proposta finale va verificato il servizio ferroviario applicabile e il piano operativo: non occorre inventare altri tagli territoriali per nascondere questi due problemi. Non è autorizzato scegliere un nuovo tetto chilometrico.

Fonti: [cinque confronti e verifiche](../outputs/phase2/rt031_line8_local_shortcuts_v3/deep_offpeak_comparison.json), [registro corse ed eventi](../outputs/phase2/rt031_line8_local_shortcuts_v3/deep_offpeak_witness.json), [tracciato GeoJSON](../outputs/phase2/rt031_line8_local_shortcuts_v3/deep_offpeak_witness.geojson). `network_selected`, `primary_selection_authorised`, `runner_up_selection_authorised` restano `false`; `decision_budget_km`, `uncertainty_band_min` e `total_operating_km` restano `null`.
