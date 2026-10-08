# Nodo8: testi brevi e schemi circolari

Release `20261008g`, presentazione soltanto. Percorso, fermate, orari, copertura e autorità del progetto invariati.

- Un solo favicon Nodo8 condiviso dalle due pagine, incluso nell’artefatto pubblico. Rimossa la vecchia icona inserita dinamicamente dal racconto.
- Nessun em dash nel testo delle due pagine. La punteggiatura dei nomi upstream viene pulita solo nella visualizzazione, non modificando i dati.
- Testo visibile ridotto: circa un terzo nella vetrina e un quarto nel racconto. Metodo, calendario, costi e altre precisazioni restano in approfondimenti apribili. Player e popup usano un italiano meno tecnico.
- Primo schema: due cerchi con tutti i 28 passaggi fuori FS, numero e selezione della fermata, ordine del registro conservato. FS conserva partenza, sosta intermedia e arrivo. Download SVG autonomo e lista accessibile mantenuti.
- Secondo schema: due cerchi concettuali, nomi all’interno, FS al centro e un solo raccordo verso San Zeno e Canova/Beolco. Cerchio superiore antiorario con Beverate, Vaccarezza, Brivio, Arlate e Calco. Cerchio inferiore con Monticello, Santa Maria Hoè, Perego e Rovagnate.
- Nel secondo schema i nomi sono riferimenti territoriali, non nuove fermate o copertura certificata. Il registro attuale non contiene fermate denominate Beolco o Monticello. La disposizione inferiore richiesta non sostituisce l’ordine reale: nessuna freccia di servizio inferiore o numerazione inventata. L’ordine esatto resta nel primo schema e nella lista.

## Verifiche

40 test Python con otto subtest e 31 test Node. I nuovi test controllano il favicon condiviso, l’assenza di em dash, tutti i passaggi interattivi, cerchi/raccordi/etichette interne, ordine e ruoli FS, esportazioni SVG con stili e pulizia della punteggiatura senza mutazione della sorgente.

Proiezione dati confrontata con tutte e quattro le fonti confermate. Asset storici e vendor preservati. Verifiche browser a 1280 px e 390 px: schemi, dettagli apribili, favicon unico, assenza di overflow della pagina ed errori console nei casi controllati. La mappa degli schemi può scorrere orizzontalmente su telefono per mantenere leggibili i nomi.

Pubblicazione finale limitata alle due pagine e 71 file allowlisted. Le pagine ritirate restano nel repository.
