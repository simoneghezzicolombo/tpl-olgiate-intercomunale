# Progetto Linea 8 Olgiate Molgora
## Rete TPL Circolare a Doppio Verso (Modello Merate D201/D202) Integrata con il Nodo Ferroviario S8

Benvenuto nel repository del progetto **Linea 8 Olgiate Molgora**. Questo workspace raccoglie tutti i dati quantitativi, i modelli di simulazione di esercizio, i bilanci chilometrici, l'analisi territoriale WorldPop e la dashboard interattiva per la trasformazione delle attuali linee radiali frammentate **D184** e **D185** in una **rete circolare continua a forma di "8"**, operante in **entrambi i versi di marcia (orario e antiorario)** e incernierata sulla **stazione ferroviaria di Olgiate-Calco-Brivio**.

---

## 📊 I Numeri Chiave dello Studio

1. **Popolazione del Bacino Core (5 Comuni, ISTAT 2025)**:
   - **La Valletta Brianza + Santa Maria Hoè**: $6.765 \text{ residenti}$ ($29,5\%$)
   - **Olgiate Molgora (Hub centrale)**: $6.332 \text{ residenti}$ ($27,6\%$)
   - **Calco + Brivio**: $9.817 \text{ residenti}$ ($42,8\%$)
   - **Totale Bacino Primario**: **22.914 residenti**.
2. **Crescita Ferroviaria alla Stazione di Olgiate-Calco-Brivio**:
   - Da **1.420 saliti/giorno nel 2019** a **2.400 nel 2025** (**+69,01%**, fonte SFR Regione Lombardia / Trenord linea S8).
3. **Massa Critica Chilometrica Disponibile nel Programma di Bacino (PdB)**:
   - **D184**: $52.560 \text{ bus-km/anno}$ ($15.264 \text{ punta} + 37.296 \text{ morbida}$)
   - **D185**: $58.859 \text{ bus-km/anno}$ ($19.144 \text{ punta} + 39.714 \text{ morbida}$)
   - **Totale Attuale**: **111.419 bus-km/anno**.
   - **Confronto con le Circolari di Merate (D201 + D202 = 90.372 km/anno)**: Olgiate dispone già del **+23,3% di chilometri in più** (+21.047 km/anno)!
4. **Il Paradosso dell'Orario Attuale**:
   - Nonostante 111 mila km/anno, oggi il servizio offre solo 6 coppie/giorno con buchi fino a **6 ore e 55 minuti sulla D184** e buchi di **4 ore e 35 minuti sulla D185**.
5. **Il Ciclo dell'8 e il Raddoppio dell'Offerta**:
   - Percorso Ovest (Olgiate FS – Perego – Santa Maria Hoè): **25 minuti**.
   - Percorso Est (Olgiate FS – Calco – Beverate – Brivio): **30 minuti**.
   - **8 completo**: **55 minuti** (perfettamente compatibile con il modulo orario di **60 minuti** con 5 min di margine a Olgiate FS).
   - **Da 6 a 13 coppie di corse al giorno (+117% nel core)** con un solo autobus in turno orario!
6. **L'Impostazione a Doppio Verso (Stile Circolari di Merate)**:
   - La linea è strutturata per essere percorsa in entrambi i versi (**Senso Orario CW** e **Senso Antiorario CCW**), eliminando il problema degli utenti costretti a fare l'intero anello al ritorno.
   - Nello **Scenario C Ibrido** (2 bus contemporanei nelle 6 ore di punta + 1 bus in morbida per 7 ore = 19 cicli/giorno), il fabbisogno chilometrico è di **112.261 km/anno**, ovvero **perfetta neutralità economica (+0,75%)** rispetto ai 111.419 km attuali!

---

## 📁 Struttura della Cartella

```text
d:\linea_8_olgiate\
├── README.md                                 # Questo indice generale
├── index.html                                # Dashboard interattiva web con mappa SVG animata e simulatore
├── styles.css                                # Design system moderno (dark/light, glassmorphism, responsive)
├── app.js                                    # Logica interattiva, calcolo semaforo e generazione orari
│
├── data/                                     # Dati quantitativi e matrici strutturate
│   ├── demografia_core_istat_2025.csv        # Popolazione 5 comuni ISTAT 2025 e quote di bacino
│   ├── risorse_tpl_pdb.csv                   # Budget km PdB D184, D185 e confronto Merate D201, D202
│   ├── orario_attuale_estivo_2026.csv        # Corse attuali e quantificazione buchi di servizio
│   ├── scenario0_tempi_percorsi.csv          # Tempi, tratte e chilometraggi di Scenario 0
│   ├── semaforo_economico_parametri.json     # Parametri soglie km (Verde 19.6 km, Giallo 28.3 km)
│   ├── frazioni_matrice_valutazione.csv      # Ranking deviazioni con formula Rendimento = Pop / Tempo
│   ├── simulazione_scenari.json              # Risultati esportati dei 4 scenari di esercizio
│   ├── flussi_stazioni_meratese_2015_2025.csv# Serie storica passeggeri saliti 2015-2025
│   ├── population_by_station_meratese_only.csv# Benchmark isocrone pedonali WorldPop stazioni S8
│   ├── station_coordinates_and_graph_snap.csv# Coordinate stazioni e nodi grafo OSM
│   └── README_methodology.txt                # Metodologia originale isocrone WorldPop e OSM
│
├── docs/                                     # Relazioni tecniche e documentazione metodologica
│   ├── 01_diagnosi_e_quadro_strategico.md    # Il paradosso dei 111k km dispersi vs i buchi di 7 ore
│   ├── 02_concetto_linea_8_e_nodo_olgiate.md # La geometria dell'8, cerniera Olgiate FS nodo .30/.00
│   ├── 03_modello_circolare_doppio_verso_merate.md # Il modello Merate: orario/antiorario, 1 vs 2 bus
│   ├── 04_bilancio_chilometrico_e_semaforo_economico.md # Dimostrazione matematica semaforo Verde/Giallo/Rosso
│   ├── 05_metodologia_routing_e_worldpop.md  # Superamento confini comunali con raster 100m e OSM
│   ├── 06_valutazione_frazioni_e_deviazioni.md# Formula rendimento, frazioni ammesse e bocciate
│   └── 07_scenario0_benchmark.md             # Specifiche complete dello Scenario 0 di controllo
│
└── scripts/                                  # Strumenti di calcolo e simulazione
    ├── simula_linea_8.py                     # Simulatore di esercizio, cicli, orario e bilancio km
    └── valuta_deviazioni.py                  # Calcolo rendimento frazioni e verifica vincolo 60'
```

---

## 🚀 Come Utilizzare gli Strumenti

### 1. Dashboard Web Interattiva
Basta aprire [index.html](file:///d:/linea_8_olgiate/index.html) in un qualsiasi browser moderno per accedere alla suite completa:
- **Mappa schematica SVG animata**: visualizza i due anelli, le fermate e gli autobus in movimento in Senso Orario (CW) e Antiorario (CCW).
- **Simulatore in tempo reale**: muovi gli slider di km per ciclo e cicli giornalieri per vedere accendersi il semaforo (Verde, Giallo, Rosso) con il calcolo istantaneo dei km annui.
- **Valutatore Frazioni**: clicca sui pulsanti di Mondonico, Perego, Arlate, Calco Superiore, San Zeno, Ravellino per visualizzare l'impatto sul tempo di ciclo e la raccomandazione trasportistica.
- **Quadro Orario & S8 Sync**: tabella partenze con le coincidenze per i treni S8 verso Milano e Lecco.

### 2. Esecuzione degli Script Python
Puoi eseguire in qualsiasi momento i simulatori da terminale:
```bash
# Esegue la simulazione dei 4 scenari di esercizio e aggiorna i JSON
python scripts/simula_linea_8.py

# Esegue il ranking socio-economico delle frazioni
python scripts/valuta_deviazioni.py
```

---

## 🏆 Sintesi delle Scelte Progettuali

1. **Perego e Beverate**: incluse d'ufficio a costo zero (già sugli assi centrali SP342 dir e SP72).
2. **Mondonico e Arlate**: non deviazioni a fondo cieco, ma rami di ritorno che chiudono i due anelli garantendo un rendimento elevatissimo (>300 residenti/minuto) e rispettando il ciclo orario.
3. **San Zeno, Ravellino e Caprino**: bocciate dall'orario orario fisso del core (farebbero sforare il ciclo a 65-75 minuti). Vanno gestite come prolungamenti scolastici/biorari dedicati o servizi a chiamata.
4. **Modello Merate a Doppio Verso**: implementato in modo sostenibile attraverso lo **Scenario C** (2 autobus in punta nei due versi opposti + 1 autobus in morbida), garantendo frequenza elevata e interscambio sistematico a Olgiate FS con i treni S8 a **saldo zero** rispetto alle risorse storiche del Piano di Bacino.
