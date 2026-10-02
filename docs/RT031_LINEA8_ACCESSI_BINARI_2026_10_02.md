# Linea 8 — accessi distinti ai binari, senza cambiare la proposta

Il controllo chiude la ricostruzione interna dei percorsi pedonali nel grafo congelato. Non chiude la misura reale delle coincidenze. Restano invariati percorso, fermate, 16 giri, calendario feriale 2027 e km.

## Evidenza recuperata dal quadro ferroviario già salvato

Il campo RFI «Binario programmato» è riconciliato per numero treno e partenza con tutte le 74 chiamate del 1 ottobre 2026: Milano binario 2, Lecco binario 1. È un binario di partenza programmato, non quello reale né una certificazione del binario di arrivo o del 2027.

L’accosto di progetto FS deriva da L00407, non dal diverso record 300407: la coordinata 45,733710 del vecchio spot-check non è quella usata dalla Linea 8. Non occorre spostare il tracciato per correggere quel confronto.

## Due percorsi, non un solo valore di cammino

Nel grafo RT028, dal punto bus all’ingresso connesso della banchina 1: **250.9 m**; banchina 2: **76.2 m**. Sono percorsi stradali/pedonali reali del grafo, non segmenti rettilinei verso il centro stazione. Entrambi includono scale.

Il proxy pianeggiante ereditato di 80 m/min restituisce rispettivamente **3.14 e 0.95 minuti**, ma omette rallentamenti sulle scale, cammino lungo banchina, discesa/salita e chiusura porte. Non li si adotta come nuovi tempi di trasferimento.

La sensibilità senza archi “steps” non trova un accesso a questi ingressi nel grafo. **Non dimostra che una soluzione senza scale sia fisicamente impossibile.** La [scheda ufficiale RFI](https://www.rfi.it/it/stazioni/olgiate-calco-brivio.html), verificata anche nel browser il 2 ottobre (aggiornamento visualizzato 13:05), indica accessi in piano/rampa a entrambi i binari, senza ascensore e senza servizio di assistenza. Il grafo non ne ricostruisce il collegamento: è incompleto per quella prova. La disponibilità dall’ingresso della stazione non certifica il percorso dall’accosto bus, il tempo o la porta del treno. Nessun attraversamento dei binari o rampa viene inventato.

## Cosa cambia nella conclusione mattutina

L’audit precedente restava valido nell’ipotesi di 3 minuti per ciascun verso. Non dimostrava però che anticipare il bus perdendo la coincidenza da Milano fosse l’unica scelta reale: i due cammini sono diversi e non sono misurati.

Usando soltanto gli accessi OSM come diagnostica, il bus base delle 06:05 ha residuo ingresso **-0.137 min** e uscita **2.271 min** nello stress est massimo. Il primo è negativo; non si presenta il bus immediato come una coincidenza garantita. Il secondo non include tutto il trasferimento effettivo.

Per ciascuna delle cinque coppie mattutine il giro est stressato vale 47,7766 minuti. La prima coppia è arrivo da Milano 06:02 / partenza verso Milano 06:56. I seguenti sono **budget temporali da misurare**, non un orario nuovo:

| Partenza bus est ipotetica | Trasferimento treno→bus + ritardo treno massimo | Trasferimento bus→treno + ritardo bus aggiuntivo massimo |
|---|---:|---:|
| 06:05, base confermata | 3 min | 3 min 13,4 s |
| 06:06, confronto non adottato | 4 min | 2 min 13,4 s |
| 06:07, confronto non adottato | 5 min | 1 min 13,4 s |

Il budget in uscita è ciò che resta **dopo** il tempo est massimo del modello; una riserva positiva desiderata e la chiusura porte vanno sottratte. Nessuna banda viene scelta. Questa tabella è un bilancio locale, non un’approvazione dell’orario. Il successivo [confronto AM completo](RT031_LINEA8_FASI_AM_COMPLETE_2026_10_02.md) ricostruisce ledger, cap, blocchi e tutti i flussi delle ipotesi +1/+2: entrambe rispettano i controlli di corsa completa, ma i trasferimenti reali restano da misurare e nessuna fase è adottata.

Ricontrollati tutti i 296 flussi dell’orario invariato con i due accessi distinti. Anche la sera ovest ha un gap treno→bus di 3 minuti: dal binario 1 il proxy di solo accesso lo eccede, prima di scale/porte. Il dato non è una probabilità e non autorizza automaticamente +2.

**Prossima prova decisiva: misurare separatamente binario 1→bus e bus→binario 2**, includendo scale, posizione porte e accessibilità, insieme al giro est in punta. Se i budget sono rispettati con una riserva dichiarata, si può valutare una fase che mantenga entrambe le coincidenze; se non lo sono, il trade-off ferroviario torna da decidere. Non si forza ora una priorità normativa.

[Audit macchina](../outputs/phase2/rt031_line8_local_shortcuts_v3/station_platform_transfer_audit_20261002.json) · [Percorsi pedonali sorgente](../outputs/phase2/rt031_line8_local_shortcuts_v3/station_platform_transfer_paths_20261002.geojson)

`physical_operation_ready=false`; `rail_2027_certified=false`; nessuna modifica adottata; `decision_budget_km=null`; `uncertainty_band_min=null`.
