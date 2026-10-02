# Linea 8 — rafforzamento delle evidenze e residui di chiusura

La base confermata resta una sola Linea 8, 16 giri completi, 27 siti e 28 eventi non-FS ordinati. Nessuna modifica di tracciato, orario, priorità ferroviaria o selezione finale. Il calendario feriale 2027 resta 254 giorni e 110.229,936 km commerciali; non è un costo completo o un finanziamento acquisito.

## Risultato verificato

**16 dei 25 fallimenti iniziali risolti.** La suite offline nello stesso ambiente Python, ora inclusi i test PDF, termina con **1.283 passati, 9 falliti, 3 test di rete esclusi e 78 subtest passati**. Non si dichiara l'intero repository verde.

Riesame finale mirato: **127 test passati**, incluse proposta corrente, sorgenti certificate, red-team, avvisi storici, PDF e sei prove avversariali.

- Ripristinati 31 file che differivano dai blob Git certificati soltanto per LF/CRLF. Nessun hash atteso o contenuto semantico cambiato; regole Git mirate impediscono la riconversione al prossimo checkout.
- Recuperate tre fonti dai commit già locali: Stage F, riferimento del servizio attuale V3 e audit Stage E vecchio/nuovo. Tutti e tre i digest coincidono con il certificato precedente. Una cache alterata o un percorso esplicito assente vengono rifiutati, non sostituiti silenziosamente.
- Red-team verificato: due soli validatori di riepiloghi ammessi per hash completo del codice. Qualsiasi modifica revoca l'eccezione. Lettori sconosciuti restano bloccati; tutti i 16.495 contesti storici sono preservati, senza pruning o graduatoria implicita.
- I generatori conservano gli avvisi già pubblicati sui documenti storici di best practice e fermate/manovre. Non trapiantano numeri, corse d'ala o inversioni storiche nella proposta corrente.
- Aggiunta la dipendenza PDF effettivamente usata dal codice e sei test avversariali su integrità, recupero di fonti e revoca delle eccezioni.

## I nove fallimenti rimasti, senza occultarli

Otto riguardano prerequisiti storici assenti: raster WorldPop nazionale e tile Copernicus originali, metadati di acquisizione OSM e output Gate B non materializzati nel clone. I ritagli disponibili non vengono ribattezzati originali; un nuovo download OSM non ricostruirebbe automaticamente l'acquisizione storica.

Il nono riguarda l'esperimento non tracciato `inventory_alternatives`: dichiara nove casi controllati e `all_cases_checked=false`. È preservato e non adottato. Questi residui non vengono rimossi dalla suite né convertiti in PASS.

## Ciò che manca alla proposta implementabile

La regressione dei file è una verifica distinta dalle prove di esercizio. Restano: scelta o riscontro misurato sul compromesso AM, restrizioni a storia completa e sagoma/accosti/accessi, permanenza a bordo a FS, tempi reali di marcia e trasferimento, turni/deposito e costo completo; orari ferroviari applicabili al 2027, eccezioni locali e sabato separato. I limiti di copertura delle località restano quelli già dichiarati, non vengono cancellati da test verdi.

**Nessuna adozione tacita dell'anticipo AM di due minuti.** L'orario confermato rimane la base; il [confronto ferroviario](RT031_LINEA8_LIMITE_TEMPO_E_SCELTA_AM_2026_10_02.md) rende espliciti beneficio e perdita del bus immediato dai treni in arrivo.

`actual_operator_implementation_ready=false`; PRIMARY/RUNNER-UP non autorizzati; `decision_budget_km=null`; `uncertainty_band_min=null`. Stress deterministico non significa probabilità empirica; accessibilità potenziale non significa domanda passeggeri.

[Matrice dei 25 controlli, fonti e condizioni residue](../outputs/phase2/rt031_line8_local_shortcuts_v3/closure_integrity_assessment_20261002.json) · [Prova dei ripristini di soli fine riga](../outputs/phase2/rt031_line8_local_shortcuts_v3/certified_checkout_bytes_20261002.json) · [Proposta unica consolidata](RT031_LINEA8_PROPOSTA_UNICA_CONSOLIDATA_2026_10_01.md)
