# Prompt Gemini / Google Maps — verifica fermate residue V3

Usa la tua integrazione diretta con **Google Maps** e, se accessibile dal browser, anche il portale ufficiale **Linee e Fermate ASF** `https://fermate.asfautolinee.it/public/fermate/`.

Sto costruendo un inventario rigoroso delle fermate di trasporto pubblico nei comuni di Calco, La Valletta Brianza, Santa Maria Hoè e Brivio. L'esistenza delle fermate elencate sotto è già supportata da orari o schemi linea ufficiali. **Non devi decidere se esistono per somiglianza del nome**. Devi soltanto risolvere con precisione la loro posizione e l'eventuale identità con fermate già presenti su Google Maps.

Per ciascun caso restituisci una riga con queste colonne:

`verification_id | nome_esatto_google_maps | latitudine | longitudine | linee_mostrate_da_maps | codice_fermata_se_visibile | lato/direzione_se_deducibile | palina_o_pensilina_visibile_streetview | note_identita`

Regole obbligatorie:

1. usa **il pin della fermata del trasporto pubblico**, non il centro del paese, un indirizzo vicino, un distributore, un bar o una località;
2. se Google Maps mostra due pin sui due lati della strada, restituisci **due righe separate** e descrivi la relazione;
3. non inventare coordinate. Se non c'è un pin preciso, scrivi `NON_RISOLTO`;
4. Street View serve soltanto per dire se si vede materialmente una palina, pensilina o area di attesa. Se non è chiaro, scrivi `unknown`;
5. non assumere che due fermate con nomi simili siano la stessa. Segnala invece distanza e relazione;
6. se il portale ASF mostra un codice o una posizione, riportalo separatamente e indicane la provenienza;
7. restituisci le coordinate con almeno 6 cifre decimali.

## Casi ad alta priorità

### MAP001 — Calco - Largo Pomea / Largo Pomeo
- comune: Calco
- linee ufficialmente osservate: ASF C146 e Arriva D148
- indizio: il Comune di Calco usa ufficialmente l'indirizzo `Largo Pomeo`; fonti di servizio usano anche `Largo Pomea` / `Largo Pomeo (gelateria)`.
- domanda: qual è il pin esatto della fermata? Esistono uno o due boarding point distinti sui lati della strada?

### MAP002 — Calco - Via Garibaldi
- comune: Calco
- linea: ASF C146
- codice secondario già osservato: `CALCOA05`
- domanda: trova il pin esatto e verifica se è distinto da `Calco - Via Virgilio (Pensilina ASF)` oppure se i due nomi descrivono boarding point diversi dello stesso stop place.

### MAP003 — Rovagnate - Strada Statale - AGIP
- comune: La Valletta Brianza
- linea: ASF C146; il nome/codice compare anche in dati correnti associati a D184
- codice secondario: `ROVAGA03`
- domanda: trova il pin esatto. Confrontalo con `Rovagnate - semaforo`, `Rovagnate - la pesa` e `Rovagnate - vinicola Ghezzi`, senza fonderli automaticamente.

### MAP004 — S. Maria Hoè - Tre Strade
- comune: Santa Maria Hoè
- linea ufficiale: Arriva D148
- indizio territoriale: località Tre Strade, area Via Papa Giovanni XXIII
- domanda: trova esclusivamente un vero pin di fermata bus corrispondente e restituisci coordinate/denominazione.

### MAP005 — Calco - Località Cornello
- comune: Calco
- linea ufficiale: Arriva D148
- indizio territoriale: località Cornello / area Via Trieste
- domanda: trova esclusivamente il pin esatto della fermata, non il centro della località Cornello.

### MAP006 — Brivio - Bar Cristallo
- comune: Brivio
- linea ufficiale: ASF C146
- indizio: corridoio Via Como / SS342dir
- domanda: trova il pin esatto e verifica se è distinto dalle fermate `Brivio - Via Como - Pensilina`, `Brivio - capolinea` o altre fermate vicine.

## Secondo giro, solo dopo i sei casi sopra

### MAP007 — S. Maria Hoè - Via Giovanni XXIII
- segnalata da dati secondari correnti C146, non ancora confermata da una fonte primaria specifica.
- verifica se Google Maps contiene realmente un pin con questo nome e quali linee mostra.

### MAP008 — Olgiate Molgora - Via Della Salute
- segnalata da dati secondari correnti C146.
- Google/Moovit la collocano apparentemente molto vicino a `Olgiate Molgora - Via Statale`.
- determina se Google Maps mostra un **pin distinto**, un boarding point sul lato opposto oppure soltanto un alias dello stesso luogo.

Alla fine aggiungi un breve riepilogo separato con:

- casi risolti con pin preciso;
- casi con due boarding point;
- casi che sembrano alias dello stesso stop place;
- casi non risolti.

Non fare nessuna stima o ricostruzione quando manca il dato cartografico: `NON_RISOLTO` è una risposta valida e preferibile a una coordinata dedotta.
