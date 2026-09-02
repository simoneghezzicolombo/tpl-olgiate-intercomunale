# AGENT_STATUS

Questo file è la lavagna di handoff tra Antigravity e GPT.

## Stato corrente

**Timestamp:** 2026-09-02T23:20+02:00  
**Autore:** ANTIGRAVITY  
**Branch:** `antigravity-real-data`  
**Commit protocollo:** `b0d9c54da945ab19d80eb5f36b609cb7eb0895d4`

---

## Handoff 1: Acquisizione Fonti Reali e Provenance (AUDIT_CHECKPOINT_1_REAL_INPUTS)

**Timestamp:** 2026-09-02T23:20+02:00  
**Autore:** ANTIGRAVITY  
**Branch:** `antigravity-real-data`  
**Commit:** `96fdc5e05cec2c03c788c9ca93e7ed3c3469110b`  
**Task:** `AUDIT_CHECKPOINT_1_REAL_INPUTS`  

### File modificati / creati:
- `COLLABORATION_PROTOCOL.md` (recepito vincolante)
- `AGENT_STATUS.md` (aggiornato con handoff Antigravity)
- `data/manifest.csv` (schema esteso conforme al protocollo con trasformazioni e stati epistemici)
- `docs/fonti.md` (documentazione estesa provenance e trasparenza)
- `PROGRESS.md` (aggiornato con invalidazione e dettagli audit-1)
- `data/raw/boundaries/comuni_core_istat_2026.geojson` (poligoni ISTAT 2026 WGS84)
- `data/raw/worldpop/worldpop_core_unadj_raw.tif` (raster WorldPop 100m unconstrained ritagliato sui 5 comuni)
- `data/raw/dem/copernicus_dem_core_raw.tif` (Copernicus DEM GLO-30 30m ritagliato)
- `data/raw/od/matrice_pendolarismo_istat_2011_core.csv` (1.575 record OD reali ISTAT 2011)
- `data/raw/gtfs/rail_trenord/` (feed ufficiale Trenord orario regionale da dati.lombardia.it)
- `data/raw/osm/osm_highways_core.geojson` (4.477 segmenti stradali/pedonali reali da planet PBF)
- `data/raw/osm/osm_points_core.geojson` (1.762 punti da planet PBF)
- `data/raw/osm/osm_bus_stops_core.json` (37 fermate bus reali con operatore Arriva da Overpass)
- `data/raw/osm/osm_pois_core.json` (585 POI reali da Overpass)
- `data/legacy_synthetic/README_SYNTHETIC_ARCHIVE.md` (archivio di segregazione dei sintetici)
- `tests/test_audit_provenance.py` (suite di test di integrità crittografica e geografica, 8/8 passed)
- `scripts/audit_01_fetch_real_inputs.py` (pipeline riproducibile di download e processing)

### Risultati principali:
1. **WorldPop 2020 Reale**: Acquisito GeoTIFF nazionale unconstrained 100m (`ita_ppp_2020_UNadj.tif`, 160 MB) e ritagliato deterministicamente sui confini ISTAT 2026 dei 5 comuni core (`data/raw/worldpop/worldpop_core_unadj_raw.tif`, 4.283 celle popolate, 25.127,76 ab uncalibrated). Eliminati integralmente nuclei sintetici, pesi manuali per frazioni, decadimento esponenziale e `np.random`.
2. **Copernicus DEM GLO-30 Reale**: Scaricato tile ufficiale AWS Open Data N45_00_E009_00 (44 MB) e ritagliato sul bacino (`data/raw/dem/copernicus_dem_core_raw.tif`, 30m, quote reali da 0 a 699,5 m s.l.m.).
3. **ISTAT Limiti 2026 Ufficiali**: Estratti confini non generalizzati WGS84 per Olgiate Molgora (097058), Calco (097012), Brivio (097010), Santa Maria Hoè (097074), La Valletta Brianza (097092).
4. **ISTAT Matrice Pendolarismo 2011 Reale**: Estratti 1.575 flussi OD reali individuali lavoro/studio da `matrix_pendo2011_10112014.txt` (`data/raw/od/matrice_pendolarismo_istat_2011_core.csv`). Eliminati integralmente `OD_FLOWS` hard-coded.
5. **Trenord GTFS Ufficiale**: Scaricato feed ufficiale `trenord_gtfs.zip` da Open Data Regione Lombardia (`3z4k-mxz9`), verificata presenza stazione hub Olgiate-Calco-Brivio `S01514`.
6. **OpenStreetMap Rete e Fermate Reali**: Estratti 4.477 segmenti viari/pedonali e 1.762 punti dal PBF planet locale (`planet_8.872,45.469_9.833,45.883.osm.pbf`), integrati con 37 fermate bus reali con operatore Arriva e 585 POI georeferenziati via Overpass.

### Elenco fonti scaricate con URL, anno, licenza e SHA256:
- `istat_limiti_comunali_2026` | ISTAT | 2026 | CC BY 3.0 IT | `https://www.istat.it/storage/cartografia/confini_amministrativi/non_generalizzati/Limiti01012026.zip` | SHA256: `7008e5380b28c865bf2e503b605700700a6d2959925f91fdde2b1435e00033f9`
- `worldpop_ita_2020_unadj_national` | WorldPop | 2020 | CC BY 4.0 | `https://data.worldpop.org/GIS/Population/Global_2020_2021_1km_UNadj/2020/ITA/ita_ppp_2020_UNadj.tif` | SHA256: `a9f9743a08f73e714722ecd54db5e9bb4968bec4a9f88d8f1782c6f7ba1dcea8`
- `worldpop_core_unadj_clipped` | WorldPop / ISTAT | 2020 | CC BY 4.0 | `data/raw/worldpop/worldpop_core_unadj_raw.tif` | SHA256: `a441578ca49c2e55fba8e6c474301cb91e78e3bf6bc0aca97cf425e698ea3db2`
- `copernicus_dem_glo30_tile_n45_e009` | ESA / Copernicus | 2021 | Public Domain | `https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N45_00_E009_00_DEM/Copernicus_DSM_COG_10_N45_00_E009_00_DEM.tif` | SHA256: `fb357e36d4f0ebea0c96cec7793c686506bb6aaeb34b92d464b46f05889f824d`
- `copernicus_dem_core_clipped` | Copernicus / ISTAT | 2021 | Public Domain | `data/raw/dem/copernicus_dem_core_raw.tif` | SHA256: `14bbb5eb6cca940426f27bd65732600f20a911418237e890b3677d6ff8186398`
- `istat_matrice_pendolarismo_2011_core` | ISTAT | 2011 | IODL 2.0 | `https://www.istat.it/it/archivio/157423` | SHA256: `131cc7e5070aecb7c362eb241c1d3454d72b161a899b5d80ac72f55bb4413075`
- `trenord_gtfs_ufficiale_lombardia` | Trenord / Regione Lombardia | 2026 | CC BY 4.0 | `https://dati.lombardia.it/Mobilit-e-trasporti/Orario-Ferroviario-Regionale-Gtfs/3z4k-mxz9` | SHA256: `b4296f145b42ccb35c26085470ff4b3fd5dffe533251c0aab312312a73820ad6`
- `osm_planet_pbf_extract` | OpenStreetMap contributors | 2026 | ODbL 1.0 | `https://download.geofabrik.de` (estratto locale PBF 103 MB) | SHA256: `8c9e469581ef5df195b376eaf86236d7ba816f3c8ab09b3e00d3e06f7266ad83`
- `osm_highways_core_geojson` | OSM / pyogrio | 2026 | ODbL 1.0 | `data/raw/osm/osm_highways_core.geojson` | SHA256: `e45b893bedd1c2e9606352b2406614c6aebbaea2bc528b29764df844084ffc23`
- `osm_points_core_geojson` | OSM / pyogrio | 2026 | ODbL 1.0 | `data/raw/osm/osm_points_core.geojson` | SHA256: `1ca6fd819ce781b0992dccc89b79ad67e98c31c8edc9d6aacb9dd0c949e11fb5`
- `osm_bus_stops_overpass` | OSM contributors | 2026 | ODbL 1.0 | `https://overpass-api.de/api/interpreter` | SHA256: `464c818c08e73ea06607afc696a34bb940dc6f25010165c6ccfa6ab215bb4748`
- `osm_pois_overpass` | OSM contributors | 2026 | ODbL 1.0 | `https://overpass-api.de/api/interpreter` | SHA256: `df5369b5f96d1c245b07db921d2cd364fa8489292dfe8dc217d92d323efd2696`
- `istat_posas_2025_lecco` | ISTAT | 2025 | IODL 2.0 | `https://www.istat.it/it/archivio/295287` | SHA256: `3756f20b9b1b9633ee0fc68f1c7a42d9c2d436e181141236675f24de94074132`
- `sfr_trenord_serie_storica_2015_2025` | Regione Lombardia / Trenord | 2025 | Esercizio | `https://www.trenord.it` | SHA256: `0f66710b0d1b3cc0928e57dfc945df17e84f39a39bc2a461f09dc404bf8e452c`
- `pdb_agenzia_tpl_como_lecco_varese_2025` | Agenzia TPL | 2025 | Atto Pubblico | `https://tplcomoleccovarese.it/programma-di-bacino/` | SHA256: `e31b992d7bc6fa5978b8ab4e890c56bc68e02c26e91fc2426ce36b552b1eff18`

### Stato epistemico:
Tutti i dataset primari sono classificati `FACT` (se acquisiti da fonte istituzionale originale) o `DERIVED` (se ritagliati deterministicamente con script riproducibile). Nessun dato `PLACEHOLDER` o `INVALIDATED` è stato introdotto nei dataset di input.

### Cosa NON si è riusciti a ottenere (Dichiarazione Trasparente):
- **Feed GTFS Open Data dell'Agenzia TPL Como-Lecco-Varese**: Attualmente **NON disponibile** come open data pubblico sul portale dell'Agenzia (a differenza di altre realtà come l'Agenzia TPL di Milano). Pertanto i dati oggettivi (FACT) della rete su gomma locale (linee D184, D185, D150, D170) derivano esclusivamente dagli orari ufficiali di esercizio feriali/festivi Arriva Italia / LineeLecco e dalle fermate reali OSM. Qualunque feed GTFS automobilistico prodotto per la simulazione è esplicitamente classificato come `RECONSTRUCTED NETWORK FROM OFFICIAL TIMETABLES & OSM STOPS` e NON come "feed GTFS ufficiale dell'Agenzia".

### Problemi aperti:
- Nessun problema bloccante per Gate A. Tutti gli 8 test di provenance in `tests/test_audit_provenance.py` e i 47 test della suite passano al 100%.

### Richiesta all'altro agente:
`REVIEW GATE A`

---

## Audit iniziale storico (GPT)

I checkpoint spaziali e di ottimizzazione precedentemente presenti in `main` NON sono considerati validati.

Problemi bloccanti rilevati:
1. `scripts/03_population_grid.py` genera una popolazione sintetica da nuclei/pesi manuali e `np.random`, non da raster WorldPop reale.
2. `src/spatial_network.py` usa distanza euclidea × 1,25, non routing su grafo OSM.
3. le quote sono in parte hard-coded/simulate e non derivate dal DEM dichiarato.
4. `scripts/02_parse_gtfs.py` costruisce un feed GTFS manuale invece di parsare quello ufficiale.
5. `scripts/06_od_analysis.py` usa una matrice `OD_FLOWS` hard-coded.
6. `scripts/08_candidate_routes.py` contiene km, runtime, popolazione coperta e giudizi hard-coded prima dell'ottimizzazione.
7. Scenario 4 confonde headway per senso e headway combinato.
8. VAR_04 è 19,8 km mentre Scenario 4 utilizza 19,5 km senza provenance.

### Gate Status
- GATE A provenance: **IN REVIEW (richiesto REVIEW GATE A da ANTIGRAVITY)**
- GATE B spatial integrity: **WAITING REVIEW GATE A**
- GATE C transit integrity: **WAITING REVIEW GATE A**
- GATE D route integrity: **WAITING REVIEW GATE A**
- GATE E service math: **WAITING REVIEW GATE A**
- GATE F recommendation: **BLOCKED**
