# Gate A — Provenance: PASS

**Verdetto:** PASS
**Data:** 2026-09-03
**Branch:** `antigravity-real-data`
**Functional fix:** `bcdb9713fdb984c1754ca881ece67357542d6a9a`
**Validated commit:** `019a12806af09d744f6f22032d980441ae60dc06`
**Finalization trigger:** `dcaf3c9cdd7f8a27866fca8babc6dfe7046cfcfe`
**GitHub Actions run:** `33695160621`
**Job:** `100462353597`

## Evidenza di validazione

Il Gate A non è stato approvato sulla base della sola presenza dei file nel repository. La validazione è stata eseguita su un runner Ubuntu pulito e ha richiesto alla pipeline di ricostruire il workspace a partire dal clone.

Risultati osservati nel run `33695160621`:

- compilazione di `scripts/audit_01_fetch_real_inputs.py`: PASS;
- test deterministici di rebuild POSAS e SFR: 2/2 PASS;
- `python scripts/audit_01_fetch_real_inputs.py` da clone pulito: PASS;
- manifest prodotto: 18 dataset attivi;
- suite Gate A offline dopo l'acquisizione: **16/16 PASS**;
- clean acquisition POSAS da ISTAT: PASS;
- clean acquisition SFR dai due dataset Regione Lombardia: PASS;
- clean acquisition OSM da Overpass: PASS;
- test di rete complessivi: **3/3 PASS, nessuno skip**.

## Provenance risolta

### ISTAT POSAS 2025

La provincia di Lecco viene ricostruita automaticamente dall'archivio ufficiale:
`https://demo.istat.it/data/posas/POSAS_2025_it_Comuni.zip`.
Il file provinciale di progetto è quindi `DERIVED`, non una dipendenza manuale.

### Frequentazione SFR 2015-2025

La serie deriva da due dataset ufficiali Regione Lombardia:

- `m2u2-frtq`, storico 2015-2023;
- `ut63-s688`, recente 2024-2025.

Per il 2015-2023 la fonte è già riferita al giorno feriale medio. Dal 2024 il tipo di giorno è presente nel dataset e la pipeline filtra esplicitamente il feriale. La documentazione regionale segnala inoltre una discontinuità metodologica con l'introduzione dei contatori automatici dal 2023: confronti temporali che attraversano il cambio di metodo devono essere interpretati con cautela.

### OpenStreetMap

L'acquisizione usa query Overpass esplicite e mirror pubblici con fallback. Un fetch live OSM è per natura time-varying, quindi la riproducibilità non viene definita come identità eterna del risultato live, ma come combinazione di query/processo documentati, data di accesso e checksum dello snapshot raw utilizzato nell'audit. Le fermate OSM restano un cross-check; `stops.txt` del GTFS Agenzia è la fonte istituzionale primaria per il TPL.

## Conseguenza

**Gate B — real spatial integrity è sbloccato.** Nessun risultato di routing o raccomandazione viene tuttavia promosso finché non supererà i Gate B, C, D ed E applicabili.
