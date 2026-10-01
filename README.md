# Progetto Linea 8 Olgiate Molgora
## Proposta intercomunale a percorso unico integrata con il nodo ferroviario

> **Base progettuale corrente (2026-10-01): [proposta unica Linea 8 consolidata](docs/RT031_LINEA8_PROPOSTA_UNICA_CONSOLIDATA_2026_10_01.md).**
> Una sola linea, **16 giri completi**, stesso otto est→FS→ovest ogni corsa:
> **27,124 km/giro, 27 siti di progetto inclusa FS, 4 nuovi punti proposti**.
> Orario di progetto confermato con punte H30 sfalsate e transizione della morbida
> fino alle 16:20; ultima partenza FS 19:40, rientro nominale circa 21:08.
> **112.833,793 km commerciali nel confronto a 260 giorni: +1,27% su 111.419**.
> Non sono un calendario, una flotta, paline, finanziamenti o esercizio approvati.
> Il doppio verso H30 resta rinviato. Tutti i flussi ferroviari e i limiti sono esposti.
> [Autorità della conferma](config/rt031_design_timetable_confirmation_20261001_v3.json) ·
> [Dossier macchina, registro siti/eventi e readiness](outputs/phase2/rt031_line8_local_shortcuts_v3/caller_confirmed_design_handoff_20261001.json) ·
> [Tracciato attuale](outputs/phase2/rt031_line8_local_shortcuts_v3/calco_centre_adopted_design.geojson).
> Restano tre verifiche esterne: percorso/accosti, tempi/continuità/turni, calendario/costo completo.
> [Scheda operativa e correzione delle sei vecchie manovre](docs/RT031_LINEA8_SCHEDA_VERIFICA_OPERATORE_2026_10_01.md).
> `network_selected=false`; PRIMARY e RUNNER-UP non autorizzati;
> `decision_budget_km=null`, `uncertainty_band_min=null`.

### Cronologia precedente — non usare questi numeri come stato corrente

> **Scelta storica (2026-09-27): [Linea 8, 16 giri completi al giorno](docs/RT031_LINEA8_16_GIRI_COMPLETI_V3.md).**
> Il committente ha scelto **16 corse complete**, **115.143,267 km di servizio/anno**
> su 260 giorni ipotizzati: **+3.724,267 km (+3,34%)**. Non è ancora un orario approvato.
> Il primo audit costruisce esempi a 16 giri, tutti i treni-obiettivo e H30 sulle corse
> ferroviarie di punta, ma nell'esempio prima ovest lascia **08:30–12:05 e 12:05–15:40**
> senza partenze del giro: **215 minuti, non accettati**.
> Il confronto migliorato a **16 giri** porta l'intervallo massimo a **115 minuti**,
> mantenendo H30 sulle corse abbinate ai treni centrali di punta: garanzia dalle **06:45**
> se parte prima l'ovest o dalle **06:50** se parte prima l'est. Richiede però H115 anche
> dopo la punta mattutina e la sostituzione di **due coincidenze-obiettivo** dell'ala
> percorsa seconda. Nel dominio verificato, 06:30/H120 e 06:45–06:50/H110 falliscono.
> Entrambe le precedenze est/ovest sono esaminate, **nessuna approvata**.
> Con i vecchi limiti centrali e tutti i vecchi treni servono almeno 18 giri nel dominio;
> anche con i due treni-obiettivo sostituiti, H60 fuori 10–16 e H120 dentro 10–16
> richiedono almeno **18 giri completi** nei 14 casi esaminati, pari a circa
> **129.536 km/anno** sui 260 giorni ipotizzati. Il confronto **non autorizza**
> ad aumentare il conteggio scelto. [Scelta registrata](config/rt031_16_full_trips_authority_v3.json).
> Per 18 giri agli stessi 115.143 km/anno del confronto a 16 occorrerebbe
> accorciare ogni giro di **3,075 km (11,11%)**. La [prova di ordine libero](docs/RT031_LINEA8_ORDINE_LIBERO_FERMATE_V3.md)
> certifica invece zero risparmio nel dominio con tutti i siti mantenuti ed estremi
> fissati: permutare le fermate interne non basta. Non esclude altri grafi o estremi.
>
> **Contratto del percorso: [stesso otto completo per ogni corsa](docs/RT031_LINEA8_PERCORSO_UNICO_COMPLETO_V3.md).**
> Una sola linea: ogni corsa commerciale percorre entrambe le ali; FS è anche fermata
> intermedia, senza cambio obbligatorio. Nessuna corsa pubblica limitata alla singola ala.
> La precedente proposta da **31 corse d'ala è superata come soluzione finale**;
> non diventa automaticamente una proposta da 31 giri completi.
> Geometria confermata e **29 siti di progetto**: aggiunta Arlate/Via Nuova Provinciale
> accolta, N0655 sul cavalcavia di Via Indipendenza esclusa senza spostamenti automatici.
> Olgiate sud e San Zeno restano inclusi. Non sono paline autorizzate.
> Il giro completo è 27,679 km. Il precedente confronto che conserva tutte le
> condizioni temporali ereditate richiede almeno 20 giri (143.929 km) nel dominio esaminato:
> è diagnostica storica, non un minimo globale né un aumento adottato. Si riesaminano quelle condizioni,
> senza rinunciare automaticamente a H30 in punta, ferrovia o utilità intercomunale.
> Calendario, costi complessivi, flotta, manovre e fermate restano da validare.
> [Contratto corretto](config/rt031_uniform_complete_line_authority_v3.json) ·
> [Stato completo e confronti storici](docs/RT031_LINEA8_SCHEDA_CONCLUSIVA_DI_AVANZAMENTO_V3.md) ·
> [Piano fermate storico e sei manovre da verificare](docs/RT031_LINEA8_PIANO_FERMATE_E_MANOVRE_V3.md).
>
> **Evidenze storiche.** La figura 8 a doppio verso era il concetto originario;
> il servizio passeggeri nei due sensi non implica due percorsi opposti a ogni ora. Le stime
> iniziali di 55 minuti/ciclo, 5 minuti di margine, 112.261 km/anno e
> coincidenze «perfette» riportate sotto sono **ipotesi storiche**, non
> prestazioni certificate della proposta attuale. Per i criteri di progetto
> usare [Transit best practices](docs/PHASE2_TRANSIT_BEST_PRACTICES.md);
> per il limite delle conclusioni iniziali vedere [Gate F](docs/GATE_F_PASS.md);
> per il precedente confronto territoriale vedere il [rapporto Arlate–Rovagnate](docs/RT031_ARLATE_ROVAGNATE_TRADEOFF_V3.md).
> Una [mappa dell'esperienza pregressa](docs/RT031_PRIOR_WORK_EVIDENCE_MAP.md)
> collega questi filoni e indica quali risultati sono tuttora riutilizzabili.

Benvenuto nel repository del progetto **Linea 8 Olgiate Molgora**. Questo workspace raccoglie dati quantitativi, modelli di simulazione di esercizio, bilanci chilometrici, analisi territoriale WorldPop e dashboard. Il concept originario prevedeva la trasformazione delle linee **D184** e **D185** in una rete circolare a forma di **otto a doppio verso**, centrata sulla **stazione ferroviaria di Olgiate-Calco-Brivio**. Per lo stato corrente fa fede la proposta consolidata del 1 ottobre sopra: geometria e orario sono confermati come base di progetto, non come esercizio autorizzato; i numeri storici sotto non sono prestazioni certificate.

---

## 📊 Numeri del concept originario (non una raccomandazione certificata)

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
