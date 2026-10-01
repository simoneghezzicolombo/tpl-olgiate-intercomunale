# Linea 8 — scheda di verifica per Agenzia e operatore, 1 ottobre 2026

**Oggetto da verificare:** la [proposta unica consolidata](RT031_LINEA8_PROPOSTA_UNICA_CONSOLIDATA_2026_10_01.md), senza cambiarne tacitamente percorso, fermate o orario. Una Linea 8, 16 giri completi identici al giorno, 27 siti di progetto inclusa FS, 28 occorrenze non-FS per giro. Lunghezza 27,123508 km/giro; 112.833,793 km commerciali solo nell'esempio a 260 giorni. [Geometria GeoJSON](../outputs/phase2/rt031_line8_local_shortcuts_v3/calco_centre_adopted_design.geojson) · [orario completo e eventi](../outputs/phase2/rt031_line8_local_shortcuts_v3/caller_confirmed_design_handoff_20261001.json).

## Correzione del piano manovre storico

Sul percorso **attuale** il controllo del grafo diretto congelato ha ricostruito **1.435 archi** e controllato **1.435 transizioni**, incluso il passaggio est→ovest a FS e il rientro al giro successivo. **Non risultano inversioni immediate dello stesso arco.** Le sei inversioni M1–M6 e le relative alternative chilometriche dei documenti storici appartengono a geometrie precedenti: non vanno sommate ai 27,123508 km né presentate come sei problemi ancora presenti. [Audit e sequenza completa dei nodi](../outputs/phase2/rt031_line8_local_shortcuts_v3/caller_confirmed_route_fieldwork_20261001.json).

Questo controllo non stabilisce raggi di svolta, ingombri, restrizioni dipendenti dalla storia completa, larghezza e accesso per autobus. L'accesso nel grafo è genericamente `generic_access` per tutti gli archi del giro; la larghezza e i limiti di altezza/peso/larghezza mancano nei tag per tutti i 1.435 archi. Sono assenze del dato OSM, non prove che le strade siano inadatte.

**Punto stradale specifico da guardare:** sull'ala ovest c'è un tratto contiguo di **85,68 m classificato `highway=service`** nei way OSM `1207059930` e `1207059929`, attraversato vicino all'occorrenza **Olgiate Molgora – Scarpone**. Occorre verificare accesso, larghezza utile, ostacoli, incroci e traiettoria del mezzo previsto. La classificazione OSM non dice da sola se il bus possa o non possa transitare.

## Verifiche da chiudere sul progetto già scelto

| Tema | Chi può rispondere | Evidenza richiesta | Esito da registrare |
|---|---|---|---|
| Percorso completo | Operatore ed enti stradali | Percorrenza di prova con il tipo di bus proposto; svolte e raggi reali, larghezze, accessi, eventuali restrizioni condizionate dal percorso, passaggio e sosta a FS. Controllare in particolare il tratto `service` presso Scarpone. | Percorso confermato oppure criticità localizzata con modifica proposta e sua nuova lunghezza. |
| 27 siti e 28 occorrenze | Operatore ed enti competenti per le fermate | Per ogni evento: lato e punto fisico di accosto, spazio di salita accessibile, attraversamento, visibilità, sicurezza, permesso di salita/discesa. Verificare separatamente i due passaggi di Olgiate sud e di San Zeno. | Identificativo e coordinate della fermata utilizzabile per ciascuna occorrenza, oppure evento non esercibile. |
| Quattro nuovi punti | Operatore e comuni/enti stradali | Sopralluogo per Olgiate sud, San Zeno/Via Cantù, Arlate N1212 e Calco Centro–Municipio in Via Italia. | Sito e lato approvati con eventuali lavori necessari, oppure posizione alternativa da ricalcolare. |
| Orario e mezzo continuo | Operatore | Tempi osservati per fascia e svolte, fermate e recupero, 3 minuti pedonali FS da misurare, possibilità reale di restare a bordo a FS, turni mezzi/autisti, deposito, km a vuoto. | Orario a 16 giri eseguibile con blocchi di mezzi e turni espliciti, oppure scostamenti esatti da ricontrollare su treni e attese. |
| Calendario e finanziamento | Agenzia e operatore, con scelta del committente | Giorni scolastici/non scolastici, weekend e festività, costo di personale e mezzi, km commerciali e non commerciali, copertura finanziaria. | Piano annuo completo; i 260 giorni restano un confronto finché non vengono scelti. |

Il [registro macchina per i 27 siti](../outputs/phase2/rt031_line8_local_shortcuts_v3/caller_confirmed_route_fieldwork_20261001.json) riporta coordinate, occorrenze e campi di sopralluogo lasciati `null`/`PENDING`. Per FS elenca separatamente partenza, passaggio intermedio e arrivo. È compilabile con osservazioni, ma non contiene approvazioni presunte.

## Cosa già sappiamo sull'orario e cosa una modifica comporta

Le quattro banche H30 di punta sono sfalsate; la finestra di attesa centrale del confronto termina alle 16:20. I 74 treni del 1 ottobre 2026 sono stati riconciliati con l'orario RFI vigente per quel giorno; rimangono tre vecchi obiettivi ferroviari deboli, descritti nella proposta. Il fabbisogno di 3/4 mezzi nei 27 scenari è una verifica ingegneristica condizionata, non disponibilità della flotta. Una variazione di percorso, fermata, tempo di sosta o possibilità di restare a bordo richiede ricalcolo di km, eventi di fermata, corrispondenze e blocchi dei mezzi prima di chiamare equivalente la nuova soluzione.

**Stato:** scheda pronta per confronto tecnico. `physical_bus_operation_authorised=false`; `all_stops_authorised=false`; `full_history_legality_certified=false`; `network_selected=false`; `primary_selection_authorised=false`; `runner_up_selection_authorised=false`; `decision_budget_km=null`; `uncertainty_band_min=null`.
