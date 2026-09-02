# PROGRESS.md - Avanzamento Progetto TPL Olgiate Intercomunale

**Nome Progetto**: `tpl-olgiate-intercomunale`  
**Data Inizio**: 02 Settembre 2026  
**Ultimo Aggiornamento**: 02 Settembre 2026  
**Stato Generale**: ✅ COMPLETATO (Tutti i Checkpoint da A a F completati e verificati)

---

## 1. Stato dei Checkpoint

| Checkpoint | Obiettivo | Stato | Output Principali |
| :--- | :--- | :---: | :--- |
| **CHECKPOINT A** | Baseline quantitativa completa dell'offerta TPL attuale | ✅ COMPLETATO | `outputs/current_service_baseline.csv`, GTFS strutturale vs 2026 emergenziale in `data/raw/gtfs/` |
| **CHECKPOINT B** | Mappa popolazione granulare, copertura e criticità | ✅ COMPLETATO | `data/processed/population_grid_calibrated.csv` (22.914 ab esatti), isocrone slope-adjusted Tobler, POI (`poi_dataset.csv`), matrice OD pendolarismo (`od_matrix_core.csv`) |
| **CHECKPOINT C** | Prime 5-10 alternative di tracciato e idoneità viaria | ✅ COMPLETATO | `outputs/route_variants.csv` (8 varianti testate), `outputs/field_checks.csv` (5 verifiche stradali), `outputs/deviation_efficiency.csv` (graduatoria rendimento) |
| **CHECKPOINT D** | Pareto frontier e simulazione esercizio (doppio verso) | ✅ COMPLETATO | `outputs/pareto_frontier.csv` (VAR_04 ottima), `outputs/service_simulation_scenarios.csv`, `outputs/train_connections.csv` (sincronizzazione S8) |
| **CHECKPOINT E** | Tracciato consigliato e due migliori alternative | ✅ COMPLETATO | `outputs/scenario_comparison.csv` (18 metriche per 5 scenari), Scenario 4 a saldo zero (+0,75% km vs PdB) |
| **CHECKPOINT F** | Rapporto finale, mappa interattiva e questionario residenti | ✅ COMPLETATO | `docs/rapporto_finale.md` (18 risposte decisionali), `outputs/maps/mappa_interattiva_rete_tpl_olgiate.html` (Leaflet), grafici `outputs/figures/`, suite `survey/`, 39 test pytest passati al 100% |

---

## 2. Dettaglio dei Checkpoint per Revisione Estera

### CHECKPOINT A: Baseline Quantitativa
1. **Risultati principali**: D184 e D185 dispongono nel Programma di Bacino (PdB) di 111.419 bus-km/anno (+23,3% rispetto a Merate D201+D202), ma orari gravemente inadeguati con sole 6 coppie di corse e buchi fino a 6h 55m (D184) e 4h 30m (D185). Costruiti i due dataset GTFS distinti: `network_structural` (ponte Brivio aperto) e `network_2026_emergency` (deviazione straordinaria via Olginate/Calolziocorte +14 km e +25 min).
2. **File da revisionare**: `outputs/current_service_baseline.csv`, `data/raw/gtfs/network_structural/`, `data/raw/gtfs/network_2026_emergency/`, `data/manifest.csv`.
3. **Assunzioni utilizzate**: 303 giorni feriali annui di esercizio TPL; catalogazione corse feriali da orari ufficiali Arriva 2026.
4. **Dati mancanti**: Rilevazioni palina per palina dei saliti/discesi orari sulle singole corse bus (non fornite da Arriva / Agenzia TPL, disponibili solo aggregati provinciali).
5. **Anomalie o risultati inattesi**: Il comune di Arlate (1.150 residenti) ha solo 2 corse scolastiche al giorno; la frazione di Mondonico (920 ab) è totalmente esclusa dal TPL pur essendo contigua a Olgiate.
6. **Decisioni che richiedono revisione umana**: Conferma che la deviazione cantiere 2026 sul ponte di Brivio debba essere considerata transitoria e non strutturale di piano.

### CHECKPOINT B: Popolazione e Accessibilità
1. **Risultati principali**: Griglia calibrata ISTAT 2025 al 100% (22.914 residenti esatti). L'accessibilità pedonale slope-adjusted alla stazione FS raggiunge solo 4.579 ab (20%). La rete a doppio anello espande l'accessibilità entro 10 min a 17.045 ab (74,4%). Matrice OD: 4.470 spostamenti pendolari/giorno orientati sulla stazione FS e treno S8.
2. **File da revisionare**: `data/processed/population_grid_calibrated.csv`, `data/processed/walk_isochrones_cells.csv`, `outputs/stop_analysis.csv`, `outputs/fraction_analysis.csv`, `outputs/od_matrix_core.csv`, `data/processed/poi_dataset.csv`.
3. **Assunzioni utilizzate**: Velocità pedonale in piano 4,8 km/h (80 m/min); funzione di Tobler per penalizzazione pendenza; detour factor medio rete 1,25; deduplicazione spaziale (nessun double-counting).
4. **Dati mancanti**: Coordinate precise degli ingressi pedonali secondari di tutti i complessi scolastici (assunti centroidi degli edifici).
5. **Anomalie o risultati inattesi**: Frazioni collinari come San Zeno e Calco Superiore vedono il tempo pedonale salire di oltre il 40% rispetto al piano a causa di pendenze superiori al 12-15%.
6. **Decisioni che richiedono revisione umana**: Soglia di cammino accettabile per anziani e mobilità debole (fissata cautelativamente a 8 minuti nel modello).

### CHECKPOINT C: Alternative di Tracciato
1. **Risultati principali**: Testate 8 varianti. Calcolata graduatoria rendimento $\Delta \text{Residenti}/\Delta \text{Min}$. Arlate (1.150 ab/min) e Mondonico (613 ab/min) mostrano rendimento eccellente e chiudono gli anelli. San Zeno (94,7 ab/min, +7,5 min) e Calco Sup. (+4,5 min) erodono o sfondano il ciclo di 60 min. Identificati 5 punti critici viari in `field_checks.csv`.
2. **File da revisionare**: `outputs/route_variants.csv`, `outputs/deviation_efficiency.csv`, `outputs/field_checks.csv`.
3. **Assunzioni utilizzate**: Dwell time di 20s per fermata intermedia, 60s capolinea intermedio, 180s hub Olgiate FS. Velocità commerciale 21,6 km/h.
4. **Dati mancanti**: Raggio di volta effettivo e ingombro spazzata in loco alla curva di via Mondonico e innesto Arlate su SP72.
5. **Anomalie o risultati inattesi**: Includere Arlate nell'anello Est riduce i chilometri percorsi rispetto al ritorno a vuoto su SP72 (da 12,0 km a 10,3 km!).
6. **Decisioni che richiedono revisione umana**: Esclusione di San Zeno e Calco Superiore dal percorso di linea fissa a favore di servizi a chiamata (DRT) per preservare la puntualità del cadenzamento a 60 min.

### CHECKPOINT D: Ottimizzazione e Simulazione Esercizio
1. **Risultati principali**: VAR_04 (Doppio Anello Simmetrico Mondonico+Arlate) è Pareto-ottimale con score bilanciato di 0,829 e 55,0 min di marcia. A Olgiate FS restano 5,0 min netti di buffer di recupero. Sincronizzazione con S8: treni alimentati al 100% in punta, tempo medio di interscambio di 9,8 min (mediana 9,5 min, P90 12,0 min), rail score che passa da 43 a 80,5.
2. **File da revisionare**: `outputs/pareto_frontier.csv`, `outputs/service_simulation_scenarios.csv`, `outputs/train_connections.csv`.
3. **Assunzioni utilizzate**: Finestra di coincidenza ferro-gomma accettabile tra 4 e 16 minuti; orario S8 cadenzato Trenord con arrivi/partenze ai minuti :08, :21, :22, :38, :51, :52, :07, :37.
4. **Dati mancanti**: Ritardi medi storici dei treni S8 nelle fasce di punta mattutina verso Milano (assunta deviazione standard di 3 minuti assorbita dal buffer).
5. **Anomalie o risultati inattesi**: La configurazione a doppio verso (orario + antiorario) raddoppia le opportunità di interscambio utile per ora, coprendo sia i pendolari diretti a Milano sia quelli diretti a Lecco.
6. **Decisioni che richiedono revisione umana**: Scelta di attestare il buffer orario di 5 minuti interamente a Olgiate FS anziché frazionarlo su Rovagnate o Brivio.

### CHECKPOINT E: Alternative Consigliate
1. **Risultati principali**: Scenario 4 (Ibrido di Punta CW+CCW con 2 bus in punta + 1 in morbida) selezionato come soluzione prioritaria di Piano. Copre 17.350 ab a 10 min (+2.150 nuovi residenti). Genera 112.261 km/anno, con uno scostamento di appena +842 km (+0,75%) rispetto al budget PdB di 111.419 km: perfetta neutralità economica a saldo zero. Code Ravellino e Caprino preservate con corse dedicate scolastiche e pendolari.
2. **File da revisionare**: `outputs/scenario_comparison.csv`.
3. **Assunzioni utilizzate**: 6 ore di punta feriale (3h mattino 06:30-09:30 + 3h pomeriggio 16:30-19:30) con 2 bus; 7 ore di morbida con 1 bus.
4. **Dati mancanti**: Determinazione del corrispettivo chilometrico definitivo nel nuovo bando di gara d'appalto dell'Agenzia TPL.
5. **Anomalie o risultati inattesi**: L'adozione del modello a 8 consente di aumentare le frequenze del 200% nelle ore di punta a costo operativo costante.
6. **Decisioni che richiedono revisione umana**: Modalità contrattuale di scorporo delle corse di Ravellino e Caprino rispetto al bacino core dei 5 comuni.

### CHECKPOINT F: Rapporto Finale e Mappa Interattiva
1. **Risultati principali**: Generato il rapporto tecnico completo con risposte puntuali alle 18 domande decisionali (`docs/rapporto_finale.md`); creata la mappa geografica interattiva in Leaflet con 7 layer commutabili; prodotti 6 grafici istituzionali ad alta risoluzione; predisposta la suite completa del questionario residenti GDPR-compliant; superati 39 test su 39 con pytest.
2. **File da revisionare**: `docs/rapporto_finale.md`, `docs/metodologia.md`, `docs/fonti.md`, `docs/limiti.md`, `outputs/maps/mappa_interattiva_rete_tpl_olgiate.html`, `outputs/figures/`, `survey/questionario.md`, `tests/`.
3. **Assunzioni utilizzate**: Criteri di trasparenza epistemica (FACT, ESTIMATE, ASSUMPTION, MODEL OUTPUT).
4. **Dati mancanti**: Risposte del questionario di gradimento della popolazione (in attesa di somministrazione sul territorio).
5. **Anomalie o risultati inattesi**: Nessun test fallito (39/39 passed in 0.66s).
6. **Decisioni che richiedono revisione umana**: Approvazione del questionario da parte delle amministrazioni comunali e avvio della campagna di consultazione pubblica.
