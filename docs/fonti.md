# Repertorio delle fonti e provenance — Gate A

Questo documento descrive le fonti attive del progetto `tpl-olgiate-intercomunale`.
**Gate A è PASS** sulla base della clean acquisition indipendente registrata nel run GitHub Actions
`33695160621`. Il documento non sostituisce `data/manifest.csv`, che resta il registro
machine-readable di URL, checksum, dimensioni, stato epistemico e trasformazioni.

## Regole epistemiche

- `FACT`: copia o snapshot di una fonte primaria identificabile.
- `DERIVED`: output ottenuto con una trasformazione deterministica documentata.
- `FACT_OSM_OBSERVATION`: osservazione OSM utile per cross-check, non fonte istituzionale TPL.
- I dati sintetici precedenti restano `INVALIDATED` e non possono alimentare risultati validati.

## 1. Confini amministrativi ISTAT 2026

- Fonte: ISTAT, limiti amministrativi non generalizzati al 1° gennaio 2026.
- URL: `https://www.istat.it/storage/cartografia/confini_amministrativi/non_generalizzati/2026/Limiti01012026.zip`
- Output attivo: `data/raw/boundaries/comuni_core_istat_2026.geojson`
- Trasformazione: filtro sui codici `097010`, `097012`, `097058`, `097074`, `097092`.
- Stato: `FACT` con estrazione deterministica.
- Licenza registrata: CC BY 3.0 IT.

## 2. WorldPop 2020

- Fonte: WorldPop, serie `Global_2000_2020`, raster `ita_ppp_2020_UNadj.tif`.
- URL: `https://data.worldpop.org/GIS/Population/Global_2000_2020/2020/ITA/ita_ppp_2020_UNadj.tif`
- Raster nazionale: `FACT`.
- Ritaglio sui cinque comuni: `DERIVED`.
- Risoluzione: circa 3 arc-second, nominalmente 100 m.
- Licenza: CC BY 4.0.
- Nessun peso manuale o generatore sintetico è ammesso.

## 3. Copernicus DEM GLO-30

- Fonte: Copernicus DEM GLO-30, tile `N45_00_E009_00`.
- URL diretto: `https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N45_00_E009_00_DEM/Copernicus_DSM_COG_10_N45_00_E009_00_DEM.tif`
- Tile: `FACT`; ritaglio: `DERIVED`.
- Licenza: Copernicus DEM Licence con attribuzione applicabile.
- Nota: è un DSM, non un DTM bare-earth. Questa distinzione va mantenuta nei Gate spaziali successivi.

## 4. Pendolarismo ISTAT 2011

- Fonte: matrice del pendolarismo del 15° Censimento.
- URL: `https://www.istat.it/storage/cartografia/matrici_pendolarismo/matrici_pendolarismo_2011.zip`
- Output: `data/raw/od/matrice_pendolarismo_istat_2011_core.csv`.
- Trasformazione: record di tipo `S` con origine o destinazione nei comuni core.
- Stato: `FACT`.
- Anno 2011 sempre esplicito, senza presentare il dato come mobilità corrente.

## 5. GTFS ferroviario Trenord

- Fonte: Regione Lombardia / Trenord, dataset `3z4k-mxz9`.
- Permalink: `https://dati.lombardia.it/Mobilit-e-trasporti/Orario-Ferroviario-Regionale-Gtfs/3z4k-mxz9`
- Download: `https://dati.lombardia.it/download/3z4k-mxz9/application%2Fzip`
- Stato: `FACT`.
- La stazione `S01514` Olgiate-Calco-Brivio è verificata nei file GTFS.

## 6. GTFS Agenzia TPL Como-Lecco-Varese

Feed invernali 2025-2026 pubblicati dall'Agenzia:

- Arriva Italia / Addabus:
  `https://www.tplcomoleccovarese.it/atpcolc/images/File%20GTFS%20inv.%202025-2026/GTFS%20invernale%202025-2026%20-%20Arriva%20Italia%20e%20Addabus.zip`
- Linee Lecco:
  `https://www.tplcomoleccovarese.it/atpcolc/images/File%20GTFS%20inv.%202025-2026/GTFS%20invernale%202025-2026%20Linee%20Lecco.zip`

Stato: `FACT`. Nel feed Arriva sono verificate `D184`, `D185`, `D150`, `D170`.
Per le fermate TPL, `stops.txt` è la fonte istituzionale primaria.
La licenza formale non è dichiarata nel materiale acquisito, quindi il manifest usa
`licenza non specificata / accesso pubblico` senza implicare una licenza Open Data non verificata.

## 7. OpenStreetMap

- Provider operativo: Overpass API con endpoint primario `overpass.private.coffee` e fallback pubblici `overpass-api.de` e `maps.mail.ru`.
- Funzione riproducibile: `fetch_osm_xml()`.
- Bounding box core: sud 45.710, ovest 9.355, nord 45.760, est 9.460.
- Snapshot raw corrente: `data/raw/osm/osm_core_bbox.osm`, `FACT`.
- Layer `lines` e `points`: `DERIVED` con pyogrio.
- Fermate OSM: `FACT_OSM_OBSERVATION`, solo cross-check rispetto al GTFS.
- Licenza: ODbL 1.0.

La query nuova specifica esplicitamente highways, elementi public transport e categorie POI,
invece di acquisire indiscriminatamente tutti i nodi della bbox. Il checksum del raw snapshot
fissa la realizzazione usata nell'audit; un nuovo fetch live può differire perché OSM è aggiornato nel tempo.

## 8. ISTAT POSAS 2025

Il precedente percorso manuale è stato eliminato come requisito della pipeline.

- Pagina ufficiale: `https://demo.istat.it/app/?l=it&a=2025&i=POS`
- Archivio ufficiale Comuni:
  `https://demo.istat.it/data/posas/POSAS_2025_it_Comuni.zip`
- Funzione: `fetch_posas_lecco()`.
- Procedura: download ZIP ufficiale, lettura `POSAS_2025_it_Comuni.csv`, filtro deterministico
  dei codici provincia `097`, scrittura di `data/raw/istat/POSAS_2025_it_097_Lecco.csv`.
- Stato del file di progetto: `DERIVED`.
- Licenza registrata: IODL 2.0.

Il file già presente nel repository rimane una cache verificata dell'export ufficiale di Lecco.
La pipeline non dipende più dalla sua presenza: se manca, lo ricostruisce dalla fonte ISTAT.

## 9. Frequentazione stazioni SFR 2015-2025

La serie **non proviene da un singolo dataset**. La provenance corretta è sdoppiata:

1. storico 2015-2023, `Flussi Stazioni Ferroviarie`, Socrata `m2u2-frtq`;
2. recente 2024-2025, `Frequentazione delle stazioni del servizio ferroviario regionale`,
   Socrata `ut63-s688`.

Endpoint CSV usati dalla pipeline:

- `https://www.dati.lombardia.it/resource/m2u2-frtq.csv?$limit=5000000`
- `https://www.dati.lombardia.it/resource/ut63-s688.csv?$limit=5000000`

Pagina istituzionale di raccordo:
`https://dati.lombardia.it/stories/s/SFR-dati-di-frequentazione/52uy-dgwp/`

La funzione `fetch_sfr_from_socrata()` scarica entrambi. Per il dataset 2015-2023 usa le campagne
di novembre, che la documentazione regionale descrive già come media del giorno feriale; per
2024-2025 filtra esplicitamente `TipoGiorno = Feriale`. Poi armonizza i nomi stazione e
`Saliti24H`, aggrega per anno e calcola `Indice_2019_100`.
L'output `data/raw/sfr/stazioni_s8_indice_2015_2025.csv` è `DERIVED`.

Il cambio di sorgente e metodologia resta esplicito. Regione Lombardia segnala inoltre che dal 2023
la misurazione passa ai contatori automatici e i livelli non sono necessariamente confrontabili in
modo diretto con le precedenti rilevazioni manuali. Le variazioni 2019-2025 non vanno quindi lette
come pura crescita della domanda senza questa cautela metodologica.

## 10. Programma di Bacino Como-Lecco-Varese rev. 7.2

Relazione generale:
`https://www.tplcomoleccovarese.it/atpcolc/images/Programma%20di%20Bacino/Rev7.2/programma%20di%20bacino%20del%20trasporto%20pubblico%20locale%20-%20v7.2_def.pdf`

Allegato 3.4 Meratese:
`https://www.tplcomoleccovarese.it/atpcolc/images/Programma%20di%20Bacino/Rev7.2/Allegato3.4_PdB_SchedaAmbito_Meratese.pdf`

Entrambi sono `FACT` e vengono scaricati automaticamente se mancanti.

## Validazione Gate A

`tests/test_audit_provenance.py` verifica:

- esistenza, non-vuotezza e SHA256 di ogni riga attiva del manifest;
- WorldPop 100 m e assenza del vecchio URL 1 km;
- licenze/formulazioni GTFS e Copernicus;
- linee e tabelle GTFS core;
- snapshot e derivati OSM;
- fallimento esplicito su input attivo mancante;
- rebuild POSAS senza file locale, con test unitario;
- rebuild SFR che deve usare **entrambi** `m2u2-frtq` e `ut63-s688`, con test unitario;
- test `network` separati per OSM, POSAS e SFR che esercitano acquisizioni reali da directory temporanee.

Comando test offline:

`python -m pytest tests/test_audit_provenance.py -m "not network" -v`

Comando clean acquisition reale:

`python -m pytest tests/test_audit_provenance.py -m network -v`

### Esito

**PASS.** Run GitHub Actions `33695160621`, job `100462353597`: pipeline completa ricostruita da clone pulito, 16/16 test offline superati e 3/3 test di acquisizione reale via rete superati senza skip. Gate B è sbloccato; Gate C/D/E/F restano soggetti ai rispettivi checkpoint.
