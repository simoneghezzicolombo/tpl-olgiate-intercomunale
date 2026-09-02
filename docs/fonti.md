# Repertorio Ufficiale delle Fonti Dati e Provenance (Audit Checkpoint 1 - Gate A)

Il presente documento attesta e documenta in modo esaustivo l'origine, la licenza, l'autenticità e l'integrità crittografica (SHA256) di tutte le fonti dati primarie e derivate utilizzate nello studio, a seguito della revisione metodologica e del soddisfacimento integrale dei requisiti di **GATE A**.

Tutte le fonti, i checksum SHA256 e le trasformazioni sono formalmente registrati in [`data/manifest.csv`](file:///d:/linea_8_olgiate/data/manifest.csv).

---

## 1. Confini Amministrativi Ufficiali dei Comuni (ISTAT 2026)
- **Ente**: ISTAT (Istituto Nazionale di Statistica)
- **Dataset**: *Limiti delle unità amministrative a fini statistici al 1° gennaio 2026 (non generalizzati)*
- **URL Ufficiale**: `https://www.istat.it/storage/cartografia/confini_amministrativi/non_generalizzati/2026/Limiti01012026.zip`
- **File Locale Estratto**: `data/raw/boundaries/comuni_core_istat_2026.geojson` (e `.shp`)
- **Licenza**: Creative Commons Attribution 3.0 IT (CC BY 3.0 IT)
- **Entità estratte (5 comuni core del bacino Olgiate)**:
  1. `097010`: Brivio
  2. `097012`: Calco
  3. `097058`: Olgiate Molgora
  4. `097074`: Santa Maria Hoè
  5. `097092`: La Valletta Brianza
- **SHA256 GeoJSON**: `7008e5380b28c865bf2e503b605700700a6d2959925f91fdde2b1435e00033f9`
- **Stato Epistemico**: `FACT` (con trasformazione deterministica documentata di filtro per codice ISTAT).
- **Utilizzo**: Maschera geometrica vettoriale per il clipping rigoroso e deterministico di WorldPop, DEM ed estrazione della rete.

---

## 2. Popolazione Territoriale Raster (WorldPop 2020 Reale 100m)
- **Ente**: WorldPop (School of Geography and Environmental Science, University of Southampton)
- **Dataset**: *Italy 100m Population Count (unconstrained, UN-adjusted, 2020)*
- **Serie Ufficiale**: `Global_2000_2020` (dataset nominale 100m)
- **URL Ufficiale**: `https://data.worldpop.org/GIS/Population/Global_2000_2020/2020/ITA/ita_ppp_2020_UNadj.tif`
- **File Nazionale Originale**: `data/raw/worldpop/ita_ppp_2020_UNadj.tif` (160.705.122 bytes)
  - **SHA256 Nazionale**: `a9f9743a08f73e714722ecd54db5e9bb4968bec4a9f88d8f1782c6f7ba1dcea8`
- **File Locale Ritagliato (Core 5 Comuni)**: `data/raw/worldpop/worldpop_core_unadj_raw.tif` (56.293 bytes)
  - **SHA256 Ritaglio**: `a441578ca49c2e55fba8e6c474301cb91e78e3bf6bc0aca97cf425e698ea3db2`
- **Licenza**: Creative Commons Attribution 4.0 International (CC BY 4.0)
- **Risoluzione Angolare**: `0.0008333333` gradi (~3 arc-seconds).
- **Risoluzione a Terra**: ~64,6 metri (lon) x ~92,6 metri (lat), corrispondente a cella nominale 100 metri a 45,7°N.
- **Proprietà del Ritaglio**: 4.283 celle popolate reali all'interno dei confini ISTAT, somma grezza non calibrata: 25.127,76 ab.
- **Stato Epistemico**: Raster grezzo `FACT`, raster ritagliato `DERIVED`.
- **Garanzia Metodologica**: Nessun generatore artificiale, nessun decadimento esponenziale sintetico o peso manuale assegnato a frazioni.

---

## 3. Modello Digitale di Elevazione (Copernicus DEM GLO-30)
- **Ente**: European Space Agency (ESA) / Unione Europea (Programma Copernicus)
- **Dataset**: *Copernicus Global 30m Digital Elevation Model (GLO-30) - Tile COG N45_00_E009_00*
- **URL Ufficiale**: `https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N45_00_E009_00_DEM/Copernicus_DSM_COG_10_N45_00_E009_00_DEM.tif`
- **File Tile Originale**: `data/raw/dem/Copernicus_DSM_COG_10_N45_00_E009_00_DEM.tif` (44.155.932 bytes)
  - **SHA256 Tile**: `fb357e36d4f0ebea0c96cec7793c686506bb6aaeb34b92d464b46f05889f824d`
- **File Locale Ritagliato (Core 5 Comuni)**: `data/raw/dem/copernicus_dem_core_raw.tif` (491.980 bytes)
  - **SHA256 Ritaglio**: `14bbb5eb6cca940426f27bd65732600f20a911418237e890b3677d6ff8186398`
- **Licenza e Attribuzione**: Copernicus Sentinel data / Copernicus DEM Licence (Accesso libero e gratuito; Obbligo di attribuzione: *"Produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPE-GSP-EOPG-TN-15-0005"*).
- **Proprietà**: Risoluzione 30 metri. Elevazione reale compresa tra quota minima 0,0m (mascheratura idrografica e limiti) e 699,5 m s.l.m. (rilievi collinari del Parco di Montevecchia e del Curone / Colle Brianza). Utilizzato per campionare pendenze reali ed evitare gradienti pedonali inaccessibili (funzione di Tobler).
- **Stato Epistemico**: Tile grezzo `FACT`, raster ritagliato `DERIVED`.

---

## 4. Matrice Reale del Pendolarismo (ISTAT 2011)
- **Ente**: ISTAT (15° Censimento Generale della Popolazione e delle Abitazioni)
- **Dataset**: *Matrice del pendolarismo per motivi di lavoro e studio (file a tracciato fisso `matrix_pendo2011_10112014.txt`)*
- **URL Ufficiale**: `https://www.istat.it/storage/cartografia/matrici_pendolarismo/matrici_pendolarismo_2011.zip`
- **File Locale Estratto**: `data/raw/od/matrice_pendolarismo_istat_2011_core.csv` (94.380 bytes)
- **SHA256**: `131cc7e5070aecb7c362eb241c1d3454d72b161a899b5d80ac72f55bb4413075`
- **Licenza**: Italian Open Data License 2.0 (IODL 2.0)
- **Contenuto**: 1.575 record OD reali individuali di tipo 'S' per spostamenti sistematici con origine o destinazione nei 5 comuni core verso qualunque comune italiano.
  - Totale pendolari in uscita/interni (anno 2011 esplicito): Brivio 2.567, Calco 3.020, Olgiate Molgora 3.329, La Valletta Brianza (Perego+Rovagnate) 2.235, Santa Maria Hoè 1.282.
- **Stato Epistemico**: `FACT`.
- **Garanzia Metodologica**: Nessun valore OD sintetico o proporzione forzata nel modello.

---

## 5. Rete Ferroviaria Regionale (Trenord GTFS Ufficiale)
- **Ente**: Regione Lombardia (D.G. Trasporti e Mobilità Sostenibile) / Trenord S.r.l.
- **Dataset**: *Orario Ferroviario Regionale GTFS (dataset identificativo `3z4k-mxz9`)*
- **URL Ufficiale**: `https://dati.lombardia.it/Mobilit-e-trasporti/Orario-Ferroviario-Regionale-Gtfs/3z4k-mxz9` (Download diretto: `https://dati.lombardia.it/download/3z4k-mxz9/application%2Fzip`)
- **File Locale**: `data/raw/gtfs/rail_trenord/trenord_gtfs.zip` (1.660.043 bytes)
- **SHA256**: `b4296f145b42ccb35c26085470ff4b3fd5dffe533251c0aab312312a73820ad6`
- **Licenza**: Creative Commons Attribution 4.0 (CC BY 4.0)
- **Tabelle Estratte**: `agency.txt`, `routes.txt`, `trips.txt`, `stops.txt`, `stop_times.txt`, `calendar_dates.txt`.
- **Stazione Hub**: `S01514` - `Olgiate-Calco-Brivio` (lat 45.729188, lon 9.403663), asse portante della linea ferroviaria S8 Milano Porta Garibaldi - Monza - Carnate - Lecco.
- **Stato Epistemico**: `FACT`.

---

## 6. GTFS Ufficiale Agenzia TPL Como-Lecco-Varese (Orario Invernale 2025-2026)
- **Ente**: Agenzia per il Trasporto Pubblico Locale del Bacino di Como, Lecco e Varese
- **Pagina Ufficiale Open Data**: [File GTFS - orario invernale ed estivo 2025-2026](https://www.tplcomoleccovarese.it/atpcolc/zf/index.php/servizi-aggiuntivi/index/index/idtesto/172)
- **Licenza**: `licenza non specificata / accesso pubblico` (download pubblico diretto sul portale istituzionale dell'Agenzia TPL).

### Feed 1: Arriva Italia S.r.l. e Addabus (Bacino Lecchese / Meratese)
- **URL Ufficiale**: `https://www.tplcomoleccovarese.it/atpcolc/images/File%20GTFS%20inv.%202025-2026/GTFS%20invernale%202025-2026%20-%20Arriva%20Italia%20e%20Addabus.zip`
- **File Locale**: `data/raw/gtfs/agency_arriva/GTFS_invernale_2025-2026_-_Arriva_Italia_e_Addabus.zip` (4.484.693 bytes)
- **SHA256**: `f890c393b909a40ae9500ab5acba71166cdfc5af3d42be92f55a92d92927553b`
- **Linee Core Identificate nel Feed**:
  - `D184`: *Olgiate Molgora F.S. - Ravellino*
  - `D185`: *Celana - Olgiate F.S.*
  - `D150`: *Lecco - Brivio - Lomagna*
  - `D170`: *Arlate - Vimercate*
- **Articolazione Dati Core**:
  - 201 corse (`trips.txt`) per le linee core
  - 2.392 passaggi orari (`stop_times.txt`)
  - 59.021 punti di tracciato vettoriale (`shapes.txt`)
  - 56 fermate ufficiali (`stops.txt`) con coordinate GPS nel perimetro dei 5 comuni core
- **Stato Epistemico**: `FACT`.

### Feed 2: Linee Lecco (Rete Urbana e Contermine)
- **URL Ufficiale**: `https://www.tplcomoleccovarese.it/atpcolc/images/File%20GTFS%20inv.%202025-2026/GTFS%20invernale%202025-2026%20Linee%20Lecco.zip`
- **File Locale**: `data/raw/gtfs/agency_lineelecco/GTFS_invernale_2025-2026_Linee_Lecco.zip` (2.510.002 bytes)
- **SHA256**: `f9b902807a2b213caea8e97c7501bdbfcbe1f3fe6d97f21f947ac2ecc6063271`
- **Stato Epistemico**: `FACT`.

---

## 7. Rete Stradale, Pedonale e Punti OpenStreetMap (OSM)
- **Ente**: OpenStreetMap contributors
- **Provider & Endpoint Ufficiale**: `https://overpass-api.de/api/interpreter` (FOSSGIS e.V. / OpenStreetMap Foundation)
- **Estrazione Primaria Raw XML**: Query Overpass per bounding box core `[45.710°N, 9.355°E, 45.760°N, 9.460°E]`
  - **File Raw XML**: `data/raw/osm/osm_core_bbox.osm` (24.347.485 bytes)
  - **SHA256**: `cff22a10740b049cd847095748706024821ff47579d6788af54c592f4fbe8582`
  - **Stato Epistemico**: `FACT`.
- **Layer Estratti Deterministici con pyogrio (Bbox Core 45.71-45.76 N, 9.355-9.460 E)**:
  1. `data/raw/osm/osm_highways_core.geojson`: 4.506 segmenti stradali e pedonali reali con geometrie WGS84 e attributi (2.752.693 bytes, SHA256: `2a1082b10f5a6560bdf69e8dc344541d3a892f751054316ea582fef32fe6b4c4`). Stato: `DERIVED`.
  2. `data/raw/osm/osm_points_core.geojson`: 1.875 punti reali (fermate bus, scuole, farmacie, servizi) (697.238 bytes, SHA256: `897b8351af5fcf9b7fab9187b43adbe9bc043a635a035e9aa54c4a59ff1fb004`). Stato: `DERIVED`.
- **Layer Overpass API Complementari**:
  - `data/raw/osm/osm_bus_stops_core.json`: 37 fermate e piazzole bus georeferenziate su OSM (10.079 bytes, SHA256: `464c818c08e73ea06607afc696a34bb940dc6f25010165c6ccfa6ab215bb4748`). Stato: `FACT_OSM_OBSERVATION`.
    - *Nota di gerarchia*: La fonte primaria istituzionale per le fermate TPL è il file `stops.txt` del GTFS ufficiale Arriva; le fermate OSM sono osservazioni reali utilizzate per cross-check geometrico e verifica accessibilità pedonale su banchina.
  - `data/raw/osm/osm_pois_core.json`: 585 generatori di domanda georeferenziati (scuole, municipi, sanità, sport, commercio) (175.482 bytes, SHA256: `df5369b5f96d1c245b07db921d2cd364fa8489292dfe8dc217d92d323efd2696`). Stato: `FACT`.
- **Licenza**: Open Database License 1.0 (ODbL 1.0).

---

## 8. Statistiche Demografiche ISTAT (POSAS 2025)
- **Ente**: ISTAT (Istituto Nazionale di Statistica)
- **Dataset**: *Popolazione residente per età, sesso e stato civile al 1° gennaio 2025 (Provincia di Lecco - 097)*
- **URL Ufficiale**: `https://demo.istat.it/app/?l=it&a=2025&i=POS` (e `https://www.istat.it/it/archivio/295287`)
- **File Locale**: `data/raw/istat/POSAS_2025_it_097_Lecco.csv` (479.315 bytes)
- **SHA256**: `3756f20b9b1b9633ee0fc68f1c7a42d9c2d436e181141236675f24de94074132`
- **Licenza**: Italian Open Data License 2.0 (IODL 2.0)
- **Popolazione Legale al 01/01/2025 nei 5 Comuni Core**:
  - Olgiate Molgora: 6.332 ab.
  - Calco: 5.460 ab.
  - Brivio: 4.357 ab.
  - La Valletta Brianza: 4.656 ab.
  - Santa Maria Hoè: 2.109 ab.
  - **Totale Core**: 22.914 residenti legali
- **Stato Epistemico**: `FACT`.

---

## 9. Frequentazione Ferroviaria SFR (Serie Storica 2015-2025)
- **Ente Fonte Primaria**: Regione Lombardia (Direzione Generale Trasporti e Mobilità Sostenibile) / Trenord S.r.l.
- **Dataset Istituzionale**: Rilevazioni ufficiali di frequentazione stazioni SFR, campagne di monitoraggio contrattuale novembre feriale 2015-2025 (portale Open Data Regione Lombardia: `https://dati.lombardia.it/Mobilit-e-trasporti/Frequentazione-stazioni-SFR/`)
- **Origine ed Elaborazione Upstream**: Serie storica passeggeri saliti/giorno feriale elaborata e documentata nel repository correlato `s8-analisi`, acquisita in questo studio per l'analisi di interscambio con la linea ferroviaria S8.
- **File Locale**: `data/raw/sfr/stazioni_s8_indice_2015_2025.csv` (11.877 bytes)
- **SHA256**: `0f66710b0d1b3cc0928e57dfc945df17e84f39a39bc2a461f09dc404bf8e452c`
- **Licenza**: Italian Open Data License 2.0 (IODL 2.0)
- **Dato Stazione Hub (Olgiate-Calco-Brivio FS)**:
  - Saliti feriale 2019: 1.420 saliti/giorno
  - Saliti feriale 2025: 2.400 saliti/giorno (+69% rispetto al 2019)
- **Stato Epistemico**: `DERIVED`.

---

## 10. Programma di Bacino Ufficiale (PdB Agenzia TPL Como-Lecco-Varese - Rev. 7.2)
- **Ente**: Agenzia per il Trasporto Pubblico Locale del Bacino di Como, Lecco e Varese
- **Dataset**: *Programma di Bacino del Trasporto Pubblico Locale - Revisione 7.2* (approvato con Delibera dell'Assemblea di Bacino)
- **Licenza**: Atto Pubblico di Pianificazione Territoriale e Trasportistica

### Documento 1: Relazione Generale di Progetto (Rev. 7.2)
- **URL Ufficiale**: `https://www.tplcomoleccovarese.it/atpcolc/images/Programma%20di%20Bacino/Rev7.2/programma%20di%20bacino%20del%20trasporto%20pubblico%20locale%20-%20v7.2_def.pdf`
- **File Locale**: `data/raw/pdb/PdB_Como_Lecco_Varese_Relazione_v7.2.pdf` (6.128.753 bytes)
- **SHA256**: `aedff739f2e55defac8c4db16aef42ebecedd331817316de03a337123fbd2e48`
- **Stato Epistemico**: `FACT`.

### Documento 2: Scheda d'Ambito 3.4 Meratese (Rev. 7.2)
- **URL Ufficiale**: `https://www.tplcomoleccovarese.it/atpcolc/images/Programma%20di%20Bacino/Rev7.2/Allegato3.4_PdB_SchedaAmbito_Meratese.pdf`
- **File Locale**: `data/raw/pdb/PdB_Allegato3.4_Meratese.pdf` (10.583.241 bytes)
- **SHA256**: `e0657cb4e8a078ddf99f28e1ebbde4a67ee36bb9b7a92fcd488e2539a948079a`
- **Contenuto**: Scheda di dettaglio per l'ambito del Meratese con standard di servizio, fabbisogni e specifiche delle linee contermini D184 (52.560 km/anno) e D185 (58.859 km/anno).
- **Stato Epistemico**: `FACT`.
