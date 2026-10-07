# Linea 8 — accessi distinti ai binari, senza cambiare la proposta

**Correzione del 7 ottobre:** recuperata la fonte RT028 originale e incluso il passaggio binario 2 → scala → sottopasso → scala → binario 1 segnalato dal committente. Il precedente giro esterno da 251 m è superato e non viene più usato per le coincidenze. Percorso bus, fermate, 16 giri, calendario feriale 2027 e km restano invariati.

Il committente ha poi confermato esplicitamente il tragitto mostrato, in base alla propria esperienza locale. È un riscontro sulla topologia del percorso, non un cronometraggio, un rilievo delle coordinate o un’approvazione degli accosti/tempi alle porte.

## Evidenza recuperata dal quadro ferroviario già salvato

Il campo RFI «Binario programmato» è riconciliato per numero treno e partenza con tutte le 74 chiamate del 1 ottobre 2026: Milano binario 2, Lecco binario 1. È un binario di partenza programmato, non quello reale né una certificazione del binario di arrivo o del 2027.

L’accosto di progetto FS deriva da L00407, non dal diverso record 300407: la coordinata 45,733710 del vecchio spot-check non è quella usata dalla Linea 8. Non occorre spostare il tracciato per correggere quel confronto.

## Correzione topologica: il sottopasso esisteva già nella fonte

Le scale OSM 1193795237 e 1193795239 raggiungono il sottopasso 784178060. Le loro estremità superiori sono dentro le aree delle banchine, non sul bordo: il controllo precedente le ignorava. Sono esclusi come obiettivi i nodi sotterranei che ricadono nella proiezione della stessa banchina. Non si inventa un attraversamento dei binari a raso.

Dal punto bus all’accesso di superficie della banchina 1: **108.2 m**; banchina 2: **76.2 m**. Il primo passa per la banchina 2, le due scale e il sottopasso. Solo **5.93 m** di cammino interno alla banchina 2 sono un’inferenza geometrica esplicita, interamente contenuta nel poligono OSM e senza intersezione con i binari in superficie; tutti gli altri archi sono highways OSM. Quel tratto non viene spacciato per un arco OSM originale o un rilievo di agibilità.

Il grafo RT028 certificato e il suo digest non cambiano: il raccordo di superficie è un modello locale separato per la stazione. L’artefatto originale 9991182904/run 34039162932 è stato recuperato in `cache/rt028-certified-34039162932`; il checksum coincide con quello certificato. Non dipende più dalla cartella temporanea eliminata.

Il proxy pianeggiante ereditato di 80 m/min restituisce rispettivamente **1.35 e 0.95 minuti**, ma omette rallentamenti sulle scale, cammino lungo banchina, discesa/salita e chiusura porte. Non li si adotta come nuovi tempi di trasferimento.

La sensibilità senza archi “steps” non trova un accesso a questi ingressi nel grafo. **Non dimostra che una soluzione senza scale sia fisicamente impossibile.** La [scheda ufficiale RFI](https://www.rfi.it/it/stazioni/olgiate-calco-brivio.html), verificata anche nel browser il 2 ottobre (aggiornamento visualizzato 13:05), indica accessi in piano/rampa a entrambi i binari, senza ascensore e senza servizio di assistenza. Il grafo non ne ricostruisce il collegamento: è incompleto per quella prova. La disponibilità dall’ingresso della stazione non certifica il percorso dall’accosto bus, il tempo o la porta del treno. Nessun attraversamento dei binari o rampa viene inventato.

## Cosa cambia nella conclusione mattutina

L’audit precedente restava valido nell’ipotesi di 3 minuti per ciascun verso. Non dimostrava però che anticipare il bus perdendo la coincidenza da Milano fosse l’unica scelta reale: i due cammini sono diversi e non sono misurati.

Usando la geometria corretta come diagnostica, il bus base delle 06:05 ha residuo ingresso **1.648 min** e uscita **2.271 min** nello stress est massimo, dopo il solo proxy di cammino. **Entrambi sono positivi**: il vecchio conflitto dovuto al giro esterno non è una ragione per spostare l’orario confermato. Non sono però riserve garantite: mancano scale, porte, ritardi e misure effettive.

Per ciascuna delle cinque coppie mattutine il giro est stressato vale 47,7766 minuti. La prima coppia è arrivo da Milano 06:02 / partenza verso Milano 06:56. I seguenti sono **budget temporali da misurare**, non un orario nuovo:

| Partenza bus est ipotetica | Trasferimento treno→bus + ritardo treno massimo | Trasferimento bus→treno + ritardo bus aggiuntivo massimo |
|---|---:|---:|
| 06:05, base confermata | 3 min | 3 min 13,4 s |
| 06:06, confronto non adottato | 4 min | 2 min 13,4 s |
| 06:07, confronto non adottato | 5 min | 1 min 13,4 s |

Il budget in uscita è ciò che resta **dopo** il tempo est massimo del modello; una riserva positiva desiderata e la chiusura porte vanno sottratte. Nessuna banda viene scelta. Questa tabella è un bilancio locale, non un’approvazione dell’orario. Il successivo [confronto AM completo](RT031_LINEA8_FASI_AM_COMPLETE_2026_10_02.md) ricostruisce ledger, cap, blocchi e tutti i flussi delle ipotesi +1/+2: entrambe rispettano i controlli di corsa completa, ma i trasferimenti reali restano da misurare e nessuna fase è adottata.

Ricontrollati tutti i 296 flussi dell’orario invariato con i due accessi distinti. I cinque arrivi AM da Milano hanno ora il bus est a 3 minuti nel proxy corretto, non 33/58; anche il gap serale ovest di 3 minuti non è più superato dal solo accesso al binario 1. Questa compatibilità geometrica non garantisce porte, accessibilità o ritardi e non autorizza +1/+2.

**Prossima prova decisiva: misurare separatamente binario 1→bus e bus→binario 2**, includendo scale, posizione porte e accessibilità, insieme al giro est in punta. Se i budget sono rispettati con una riserva dichiarata, si può valutare una fase che mantenga entrambe le coincidenze; se non lo sono, il trade-off ferroviario torna da decidere. Non si forza ora una priorità normativa.

[Audit macchina](../outputs/phase2/rt031_line8_local_shortcuts_v3/station_platform_transfer_audit_20261002.json) · [Percorsi pedonali sorgente](../outputs/phase2/rt031_line8_local_shortcuts_v3/station_platform_transfer_paths_20261002.geojson)

`physical_operation_ready=false`; `rail_2027_certified=false`; nessuna modifica adottata; `decision_budget_km=null`; `uncertainty_band_min=null`.

Riproduzione dalla fonte recuperata: `PYTHONPATH=.;src python -m scripts.phase2_audit_rt031_station_platform_access_v3` (in PowerShell impostare prima `$env:PYTHONPATH=".;src"`). Un percorso esplicito assente o con checksum diverso continua a fallire chiuso.
