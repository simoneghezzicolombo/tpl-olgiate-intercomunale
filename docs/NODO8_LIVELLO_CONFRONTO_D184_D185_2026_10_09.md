# Confronto D184/D185 nella mappa

## Seconda iterazione: corse animate su richiesta del committente

Il committente ha richiesto bus in movimento su un giorno a scelta.
Il riferimento adottato per la simulazione è **mercoledì 6 maggio 2026**,
un giorno feriale già verificato dalla baseline GTFS. La data è dichiarata
nel pannello e non viene presentata come il servizio più recente 2026/27.
Il feed ufficiale completo pubblicato dall'Agenzia è quello 2025/26:
https://www.tplcomoleccovarese.it/atpcolc/zf/index.php/servizi-aggiuntivi/index/index/idtesto/172

- 15 corse D184 e 19 D185 selezionate tramite `calendar.txt` e
  `calendar_dates.txt` dello stesso archivio, non tutte le colonne o tutti
  i giorni aggregati.
- Associazione di ogni corsa al proprio `shape_id` ufficiale. 17 tracciati
  distinti nel giorno, senza abbinamento euristico di PDF aggiornati ai
  vecchi percorsi.
- Ogni occorrenza mantiene ordine, nome, coordinate, arrivo, partenza,
  regole di salita/discesa e distanza sulla shape. Posizioni interpolate
  fra chiamate sui vertici GTFS; nessuna sosta Nodo8 di 30 secondi viene
  copiata sulle linee attuali.
- Le icone sono **corse**, non un conteggio o un'identità di mezzi reali.
  Nessun blocco veicolo, turno, posizionamento fuori servizio o GPS è
  ricostruito.
- Stesso orologio, cursore, pausa e Riproduci di Nodo8/S8. Nessun timer
  indipendente. Filtri D184/D185 applicati a tracciati datati, fermate e
  icone; uscita o spegnimento rimuovono tutto il livello animato.
- La simulazione datata usa i propri tracciati e fermate GTFS, non le
  geometrie KML strutturali come sostituti. Se l'asset manca, resta soltanto
  il confronto geografico con avviso, senza bus inventati.

Archivio congelato SHA256:
`f890c393b909a40ae9500ab5acba71166cdfc5af3d42be92f55a92d92927553b`.
Riproduzione: `python scripts/build_nodo8_current_simulation.py --check`.
Il confronto pubblico degli orari invernali 2026/27 resta separato e
collegato: questa animazione storica non lo sostituisce.

## Prima iterazione: solo geometria, storico

Pubblicazione animata verificata: implementazione
`3311a9246c4ca7bdea3896de32a5d16a13dfc32f`, Pages
`1bb85fae171c3d1e3d124d448eda4fc3313415a0`, CI `37940822281` verde,
versione `20261008s`. 43 test Python, 8 subtest e 50 test Node passati.
Entrambi i builder riproducono gli asset congelati. Verificati per SHA256
via HTTP tutti i 77 file pubblicati, soltanto due pagine HTML e nessuna
cancellazione di fonti storiche. Browser pubblico: alle 06:55 compaiono
D184 e D185, filtro per linea, riproduzione e uscita verificati.
Prova salvata in
`cache/nodo8-website-preview/nodo8-d184-d185-s8-published-20261008s.png`.

Il livello è disponibile sia accanto alla simulazione sia nella scheda
«Livelli e confronto». Può sovrapporsi a Nodo8 e S8 senza cambiare i loro
orari. È spento all'apertura e non dipende dall'orologio animato.

- D184 blu, D185 arancio, Nodo8 verde.
- Selezione entrambe, solo D184 o solo D185, applicata insieme a tracciati,
  fermate e aree cliccabili. Le fermate condivise restano nella selezione
  di entrambe le linee.
- «Inquadra» considera solo le reti effettivamente accese e la linea
  selezionata, non aggiunge le alternative storiche spente.
- Le 18 varianti KML ufficiali già congelate restano byte per byte quelle
  fornite: 7 D184 e 11 D185, 2.268 e 3.618 coordinate. Nessun ricalcolo
  stradale, semplificazione o collegamento inventato.
- Fermate: 44 gruppi fisici della baseline strutturale V4 derivata dal
  GTFS ufficiale **2025/26**. Non sono 44 accosti certificati attivi oggi.
- Deviazione temporanea del Ponte di Brivio esclusa da questo riferimento.

## Cosa significa «attuale»

Il livello mostra i percorsi delle linee esistenti, non la posizione di
un bus nell'ora simulata né un servizio live. Tutte le varianti geometriche
non sono tutte attive contemporaneamente.

Gli orari ufficiali invernali **2026/27**, D184 edizione 14 settembre e
D185 edizione 5 ottobre, sono collegati al confronto pubblico già
verificato. Non si usano i vecchi orari estivi o il GTFS 2025/26 per
fabbricare un'animazione del servizio attuale. Prima di animare ogni corsa
occorre un abbinamento verificato fra calendario, chiamate e variante
stradale; in mancanza, il livello rimane geometrico e la limitazione è
visibile nei dettagli e nei popup.

Nodo8, calendario 2027, fermate, corse e autorizzazioni restano invariati.
