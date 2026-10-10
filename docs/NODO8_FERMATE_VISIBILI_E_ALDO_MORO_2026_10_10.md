# Nodo8: fermate visibili e nome pubblico Olgiate Aldo Moro

## Cambiamenti della presentazione

- D184/D185: la riproduzione intercetta gli istanti di tutte le chiamate del modello della linea attiva. A ciascun istante il tempo condiviso resta fermo per 600 millisecondi reali; l'icona è sul punto di fermata ricostruito e ha stato `stop`. Gli eventi simultanei condividono la stessa pausa.
- Questo è un accorgimento della riproduzione accelerata, non una sosta operativa di 600 ms o una sosta simulata aggiunta al servizio. Durante la pausa anche Nodo8 e S8 rimangono sul medesimo istante. Nessun clock GTFS, profilo derivato, velocità del modello o durata di servizio viene modificato.
- Trascinamento, pausa, ripartenza, cambio velocità e disattivazione della linea non introducono nuove soste o clock indipendenti. Nessun timer aggiuntivo: viene usato il ciclo di animazione esistente.
- Restano 34 corse, 422 chiamate, 374 clock conservati e 48 intermedi stimati. Non si dichiara esattezza rispetto a tutti gli orari ufficiali, GPS o dwell certificato.
- Il nome pubblico del sito `RT031::P2V2S_0031_PROJECTED_ROAD_POINT` è **Olgiate Aldo Moro**, inclusi eventi 15 e 28, schemi, popup, ricerca, orari e due documenti della proposta pubblicati. Identità e coordinate non cambiano. Nei dataset congelati e nelle evidenze storiche resta il nome originale; non vengono riscritte le fonti certificate per un cambio editoriale.
- FS rimane scritto dentro il punto geografico della stazione, con livelli cartografici, non un'etichetta HTML mobile. OSM in Esplora resta a opacità 0,16 e luminosità massima 0,38.
- La correzione di contrasto dei popup è condivisa da tutte le fermate Nodo8, non è specifica di San Zeno.

## Verifica locale

- 100 test Node superati.
- 44 test Python e 8 subtest superati.
- Verifiche dei builder: dati e modelli congelati invariati.
- Browser, Esplora, entrambe le D attive a ×300: osservati 38 fotogrammi fermi alle 08:10:00, circa 611 ms, con icone ferme e clock condiviso; nessun errore console osservato.
- Popup Olgiate Aldo Moro: entrambe le occorrenze presenti, sfondo `rgb(245,242,233)`, testo `rgb(21,61,52)`; verificato anche il fondo cartografico tenue.

La proposta e le autorizzazioni operative non sono modificate da questa revisione.
