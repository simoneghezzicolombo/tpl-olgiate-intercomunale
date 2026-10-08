# Nodo8: testi brevi e schemi circolari

## Correzione richiesta dal committente: release 20261008i

I nomi delle località sono ora centrati dentro i punti circolari stessi, non semplicemente all’interno degli anelli. Ogni nodo ha raggio 82 unità SVG; nomi bianchi centrati e, dove necessario, su due righe. Verificati nel browser tutti gli undici nomi: il rettangolo del testo è contenuto nel relativo punto.

«Fermate» sostituisce «passaggi» nei riepiloghi, negli schemi e nei controlli. Il riepilogo dichiara 27 fermate inclusa FS; San Zeno e Olgiate sud restano due visite allo stesso luogo. «Primo passaggio» e «Secondo passaggio» sono mantenuti nelle sole colonne necessarie a distinguere quelle visite. Numerazione, identità, ordine e dati del registro restano invariati. 40 test Python e 31 test Node verdi.

Pubblicazione i verificata: sorgente `0c828f0acad57ad45d1a9605686c7ca6db095ca8`, Pages `684003d8e6abdbf216e96040408522725450add7`, pipeline [37825380259](https://github.com/simoneghezzicolombo/tpl-olgiate-intercomunale/actions/runs/37825380259) verde. Tutti i 71 file HTTP corrispondono al manifest. Nel browser pubblico: undici nodi con undici nomi al centro, riepilogo 27 fermate, nessun errore console osservato. Anteprima `nodo8-nomi-dentro-punti-published-20261008i.png` salvata nella cache.

Release `20261008h`, presentazione soltanto. Percorso, fermate, orari, copertura e autorità del progetto invariati.

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

Ultima rifinitura visiva: «Santa Maria Hoè» su due righe, separata da «Perego» nello schema concettuale. Verificato un margine di 45 px tra le due etichette nella vista desktop compatta.

## Pubblicazione verificata

Sorgente finale `035a2419eee4e44d62a9d161467e503fb2e3cb58`, revisione Pages `5093112c78b88915c5e6a4f382cb32a264e7aae4`. Pipeline [37824239649](https://github.com/simoneghezzicolombo/tpl-olgiate-intercomunale/actions/runs/37824239649) completata con successo. Tutti i 71 file pubblici confrontati con gli SHA-256 del manifest; esattamente due pagine HTML. Nel browser pubblico: un favicon, nessun em dash, due cerchi concettuali e nome Santa Maria Hoè su due righe. Anteprima salvata in cache come `nodo8-localita-circolari-published-20261008h.png`.
