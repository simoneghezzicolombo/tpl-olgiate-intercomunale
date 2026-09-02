# Repertorio Ufficiale delle Fonti Dati e Provenance (Audit Checkpoint 1)

Il presente documento attesta e documenta in modo esaustivo l'origine, la licenza, l'autenticità e l'integrità crittografica (SHA256) di tutte le fonti dati utilizzate nello studio, a seguito della revisione metodologica e della transizione integrale a fonti reali verificabili.

Tutte le fonti e i checksum sono registrati in [`data/manifest.csv`](file:///d:/linea_8_olgiate/data/manifest.csv).

---

## 1. Confini Amministrativi Ufficiali dei Comuni (ISTAT 2026)
- **Ente**: ISTAT (Istituto Nazionale di Statistica)
- **Dataset**: *Limiti delle unità amministrative a fini statistici al 1° gennaio 2026 (non generalizzati)*
- **URL Ufficiale**: `https://www.istat.it/storage/cartografia/confini_amministrativi/non_generalizzati/Limiti01012026.zip`
- **File Locale Estratto**: `data/raw/boundaries/comuni_core_istat_2026.geojson` (e `.shp`)
- **Licenza**: Creative Commons Attribution 3.0 IT (CC BY 3.0 IT)
- **Entità estratte (5 comuni core del bacino Olgiate)**:
  1. `097010`: Brivio
  2. `097012`: Calco
  3. `097058`: Olgiate Molgora
  4. `097074`: Santa Maria Hoè
  5. `097092`: La Valletta Brianza
- **SHA256 GeoJSON**: `7008e5380b28c865bf2e503b605700700a6d2959925f91fdde2b1435e00033f9`
- **Utilizzo**: Maschera geometrica vettoriale per il clipping rigoroso e non fittizio di WorldPop, DEM ed estrazione della rete.

---

## 2. Popolazione Territoriale Raster (WorldPop 2020 Reale)
- **Ente**: WorldPop (School of Geography and Environmental Science, University of Southampton)
- **Dataset**: *Italy 100m Population Count (unconstrained, UN-adjusted, 2020)*
- **URL Ufficiale**: `https://data.worldpop.org/GIS/Population/Global_2020_2021_1km_UNadj/2020/ITA/ita_ppp_2020_UNadj.tif`
- **File Originale Nazionale**: `D:/Utente/Downloads/ita_ppp_2020_UNadj.tif` (160.705.122 bytes)
  - **SHA256 Nazionale**: `a9f9743a08f73e714722ecd54db5e9bb4968bec4a9f88d8f1782c6f7ba1dcea8`
- **File Locale Ritagliato (Core 5 Comuni)**: `data/raw/worldpop/worldpop_core_unadj_raw.tif` (56.293 bytes)
  - **SHA256 Ritaglio**: `a441578ca49c2e55fba8e6c474301cb91e78e3bf6bc0aca97cf425e698ea3db2`
- **Licenza**: Creative Commons Attribution 4.0 International (CC BY 4.0)
- **Proprietà**: 4.283 celle popolate reali all'interno dei confini ISTAT, somma grezza non calibrata: 25.127,76 ab.
- **Risoluzione**: 3 arc-seconds (~100 metri a questa latitudine). Nessun generatore artificiale, nessun decadimento esponenziale sintetico o peso manuale assegnato a frazioni.

---

## 3. Modello Digitale di Elevazione (Copernicus DEM GLO-30)
- **Ente**: European Space Agency (ESA) / Unione Europea (Programma Copernicus)
- **Dataset**: *Copernicus Global 30m Digital Elevation Model (GLO-30) - Tile N45_00_E009_00*
- **URL Ufficiale**: `https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N45_00_E009_00_DEM/Copernicus_DSM_COG_10_N45_00_E009_00_DEM.tif`
- **File Tile Originale**: `data/raw/dem/Copernicus_DSM_COG_10_N45_00_E009_00_DEM.tif` (44.155.932 bytes)
  - **SHA256 Tile**: `fb357e36d4f0ebea0c96cec7793c686506bb6aaeb34b92d464b46f05889f824d`
- **File Locale Ritagliato (Core 5 Comuni)**: `data/raw/dem/copernicus_dem_core_raw.tif` (491.980 bytes)
  - **SHA256 Ritaglio**: `14bbb5eb6cca940426f27bd65732600f20a911418237e890b3677d6ff8186398`
- **Licenza**: Copernicus Open Access Policy / Public Domain
- **Proprietà**: Risoluzione 30 metri. Elevazione reale compresa tra quota minima 0m (mascheratura idrografica e limiti) e 699,5 m s.l.m. (rilievi collinari di Montevecchia/Colle Brianza). Utilizzato per campionare pendenze reali ed evitare gradienti pedonali inaccessibili.

---

## 4. Matrice Reale del Pendolarismo (ISTAT 2011)
- **Ente**: ISTAT (15° Censimento Generale della Popolazione e delle Abitazioni)
- **Dataset**: *Matrice del pendolarismo per motivi di lavoro e studio (file a tracciato fisso `matrix_pendo2011_10112014.txt`)*
- **URL Ufficiale**: `https://www.istat.it/it/archivio/157423`
- **File Locale Estratto**: `data/raw/od/matrice_pendolarismo_istat_2011_core.csv` (94.380 bytes)
- **SHA256**: `131cc7e5070aecb7c362eb241c1d3454d72b161a899b5d80ac72f55bb4413075`
- **Licenza**: Italian Open Data License 2.0 (IODL 2.0)
- **Contenuto**: 1.575 record OD reali individuali di tipo 'S' per spostamenti sistematici con origine o destinazione nei 5 comuni core verso qualunque comune italiano.
  - Totale pendolari in uscita/interni: Brivio 2.567 (1.807 lavoro, 760 studio), Calco 3.020 (2.123 lavoro, 897 studio), Olgiate Molgora 3.329 (2.289 lavoro, 1.040 studio), La Valletta Brianza / Perego-Rovagnate 2.235 (1.564 lavoro, 671 studio), Santa Maria Hoè 1.282 (896 lavoro, 386 studio).
  - Nessun valore OD sintetico hard-coded nel modello finale.

---

## 5. Rete Ferroviaria Regionale (Trenord GTFS Ufficiale)
- **Ente**: Regione Lombardia (D.G. Trasporti e Mobilità Sostenibile) / Trenord S.r.l.
- **Dataset**: *Orario Ferroviario Regionale GTFS (dataset identificativo `3z4k-mxz9`)*
- **URL Ufficiale**: `https://dati.lombardia.it/Mobilit-e-trasporti/Orario-Ferroviario-Regionale-Gtfs/3z4k-mxz9`
- **File Locale**: `data/raw/gtfs/rail_trenord/trenord_gtfs.zip` (1.660.043 bytes)
- **SHA256**: `b4296f145b42ccb35c26085470ff4b3fd5dffe533251c0aab312312a73820ad6`
- **Tabelle Estratte**: `agency.txt`, `routes.txt`, `trips.txt`, `stops.txt`, `stop_times.txt`, `calendar_dates.txt`.
- **Stazione Hub**: `S01514` - `Olgiate-Calco-Brivio` (lat 45.729188, lon 9.403663), asse portante della linea ferroviaria S8 Milano Porta Garibaldi - Monza - Carnate - Lecco.

---

## 6. Rete Stradale, Pedonale e Fermate OpenStreetMap (OSM)
- **Ente**: OpenStreetMap contributors
- **Dataset PBF Locale**: `D:/Utente/Downloads/planet_8.872,45.469_9.833,45.883.osm.pbf` (103.234.768 bytes)
  - **SHA256 PBF**: `8c9e469581ef5df195b376eaf86236d7ba816f3c8ab09b3e00d3e06f7266ad83`
- **Layer Estratti con pyogrio (Bbox Core 45.71-45.76 N, 9.355-9.460 E)**:
  1. `data/raw/osm/osm_highways_core.geojson`: 4.477 segmenti stradali e pedonali reali con geometria e attributi (SHA256: `e45b893bedd1c2e9606352b2406614c6aebbaea2bc528b29764df844084ffc23`).
  2. `data/raw/osm/osm_points_core.geojson`: 1.762 punti reali (fermate bus, scuole, farmacie, servizi) (SHA256: `1ca6fd819ce781b0992dccc89b79ad67e98c31c8edc9d6aacb9dd0c949e11fb5`).
- **Layer Overpass API**:
  - `data/raw/osm/osm_bus_stops_core.json`: 37 fermate e piazzole bus reali con operatore Arriva Italia (SHA256: `464c818c08e73ea06607afc696a34bb940dc6f25010165c6ccfa6ab215bb4748`).
  - `data/raw/osm/osm_pois_core.json`: 585 generatori di domanda georeferenziati (scuole, municipi, sanità, sport, commercio) (SHA256: `df5369b5f96d1c245b07db921d2cd364fa8489292dfe8dc217d92d323efd2696`).
- **Licenza**: Open Database License 1.0 (ODbL).

---

## 7. Stato Trasparente del Servizio TPL su Gomma e Distinzione Rigorosa dei Dati
- **Nota di Trasparenza Istituzionale**: L'Agenzia per il TPL del Bacino di Como, Lecco e Varese **non** pubblica attualmente un feed open data in formato GTFS sul proprio portale web (a differenza dell'Agenzia TPL di Milano).
- **Trattamento Metodologico**:
  1. **FACT (Dati Reali Verificati)**:
     - Orari di esercizio feriali e festivi ufficiali pubblicati da Arriva Italia S.r.l. e LineeLecco.
     - Posizione fisica e toponomastica delle fermate reali codificate in OpenStreetMap.
     - Dati chilometrici e di servizio del Programma di Bacino (PdB).
  2. **RECONSTRUCTED NETWORK (Rete Ricostruita)**:
     - La modellazione relazionale in tabelle GTFS per le linee automobilistiche locali (D184, D185, D150, D170) è esplicitamente etichettata come *rete ricostruita da orari ufficiali di esercizio e grafo OSM*, e non viene mai qualificata come "feed GTFS ufficiale dell'Agenzia".
  3. **Segregazione Emergenza Ponte di Brivio**:
     - `network_structural`: assetto ordinario con transito sul ponte Adda di Brivio.
     - `network_2026_emergency`: assetto contingente deviato per la chiusura straordinaria del ponte di Brivio.

---

## 8. Segregazione e Archiviazione Dati Sintetici Precedenti
Tutti i file generati nelle iterazioni preliminari mediante modelli sintetici (decadimento esponenziale teorico, pesi manuali per frazioni, distanze euclidee fisse, `OD_FLOWS` hard-coded) sono stati formalmente **INVALIDATI** dall'audit esterno e archiviati in:
[`data/legacy_synthetic/README_SYNTHETIC_ARCHIVE.md`](file:///d:/linea_8_olgiate/data/legacy_synthetic/README_SYNTHETIC_ARCHIVE.md)
con dicitura:
`SYNTHETIC PLACEHOLDER - DO NOT USE (INVALIDATED BY EXTERNAL AUDIT - SYNTHETIC INPUTS)`
al fine di preservare la tracciabilità storica senza inquinare la nuova pipeline scientifica.
