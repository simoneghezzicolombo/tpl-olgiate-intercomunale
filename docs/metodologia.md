# Documento di Metodologia Scientifica e Trasportistica

## 1. Principi Guida: Dati Prima del Tracciato
Il progetto segue un paradigma analitico rigoroso e riproducibile: il tracciato della rete non è stato pre-disegnato su basi intuitive o confinarie, ma è il risultato della sovrapposizione tra la **distribuzione spaziale granulare della popolazione**, la **matrice origine-destinazione degli spostamenti sistematici**, l'**accessibilità pedonale corretta per la pendenza (slope-adjusted)** e l'**ottimizzazione multi-obiettivo sulla Frontiera di Pareto**.

---

## 2. Il Modello Demografico a Griglia Calibrata (~100m)

Per superare l'errore sistematico dell'attribuzione della popolazione ai soli confini comunali amministrativi, è stato implementato un modello raster ad alta risoluzione:
1. **Risoluzione di Cella**: celle quadrate di lato indicativo $100 \times 100 \text{ m}$ (passo angolare $0,0009^\circ$ di latitudine e $0,0013^\circ$ di longitudine).
2. **Microdati Demografici Ufficiali ISTAT**: estrazione dai dati **ISTAT POSAS al 1° gennaio 2025** per la provincia di Lecco.
3. **Funzione di Calibrazione Demografica**:
   $$\text{Pop}_{\text{calibrata}}(c) = \text{Pop}_{\text{raw}}(c) \times \frac{\text{Totale}_{\text{ISTAT}}(M)}{\sum_{i \in M} \text{Pop}_{\text{raw}}(i)}$$
   dove $M$ è il comune di appartenenza della cella $c$.
   Questo garantisce che la somma algebrica delle celle coincida esattamente con il totale demografico ufficiale:
   - Olgiate Molgora: 6.332 ab.
   - Calco: 5.460 ab.
   - Brivio: 4.357 ab.
   - La Valletta Brianza: 4.656 ab.
   - Santa Maria Hoè: 2.109 ab.
   - **Totale Core**: **22.914 abitanti esatti**.

---

## 3. Rete Pedonale Reale e Correzione Altimetrica (Tobler Slope-Adjustment)

La misurazione dell'attrattività pedonale di una fermata non può basarsi su buffer euclidei in linea d'aria né considerare uguali percorsi pianeggianti e salite collinari ripide (frequenti in Brianza).

### Modello di Routing Pedonale
- **Grafo Stradale e Calpestabile**: derivato dalla rete OpenStreetMap (footways, residential, paths, secondary, tertiary).
- **Detour Factor**: applicazione di un coefficiente di tortuosità reale medio di $1,25$ rispetto alla distanza euclidea.
- **Quota DEM (Digital Elevation Model)**: altimetria estratta per ciascuna cella e ciascuna fermata.
- **Funzione di Velocità Pedonale di Tobler Modificata**:
  $$v(s) = v_0 \times \exp\left(-3,5 \times |s + 0,05|\right)$$
  dove $v_0 = 80 \text{ m/min} = 4,8 \text{ km/h}$ (velocità base in piano) e $s = \frac{\Delta \text{elevazione}}{\text{distanza}}$ (pendenza).
  - Su piano ($s=0$): $v \approx 4,8 \text{ km/h}$.
  - Su salita $10\%$ ($s=+0,10$): $v \approx 3,55 \text{ km/h}$ (+35% tempo di cammino).
  - Su salite ripide $20\%$ ($s=+0,20$ come San Zeno o Calco Superiore): $v \approx 2,49 \text{ km/h}$ (tempo quasi raddoppiato).
- **Deduplicazione Spaziale**: per le soglie isocrone a 5, 8, 10 e 12 minuti, ciascuna cella abitata viene associata esclusivamente alla fermata più prossima nel tempo, evitando rigorosamente il double-counting.

---

## 4. Efficienza Marginale delle Deviazioni

Per valutare se una deviazione verso una frazione debba essere inclusa nel percorso cadenzato orario o esclusa, si applica l'indicatore di rendimento marginale:

$$\mathbf{Rendimento}_{\text{deviazione}} = \frac{\Delta \text{Nuovi Residenti serviti entro 8 min a piedi}}{\Delta \text{Minuti aggiuntivi al ciclo di marcia}}$$

### Vincolo Rigido di Ciclo
Partendo da un tempo di marcia base di **55 minuti** (26 min Ovest + 29 min Est), per mantenere un cadenzamento orario regolare con 1 o 2 autobus è obbligatorio che:
$$\text{Runtime Totale} + \text{Buffer di Recupero a Olgiate FS} = 60,0 \text{ minuti}$$
con $\text{Buffer di Recupero} \ge 5,0 \text{ minuti}$ per assorbire ritardi e garantire coincidenze certe con i treni S8.
Ne consegue che qualsiasi deviazione che aggiunga più di **3,5–4,0 minuti netti** al ciclo globale è tecnicamente insostenibile all'interno del servizio orario a frequenza fissa.

---

## 5. Selezione Multi-Obiettivo e Frontiera di Pareto

Per scongiurare l'arbitrarietà di formule a punteggio unico con pesi scelti soggettivamente, è stata costruita la **Frontiera di Pareto** analizzando il set delle soluzioni non dominate nello spazio a 5 dimensioni:
- **Massimizzazione**: Residenti serviti a 10 min, POI intercettati, Flusso pendolare OD.
- **Minimizzazione**: Chilometri di percorso, Runtime totale di ciclo.

Una variante $A$ domina $B$ se $A$ è migliore o uguale su tutti gli obiettivi e strettamente superiore su almeno uno. Le varianti non dominate costituiscono il set ottimale tra cui effettuare la scelta di piano supportata da sensitivity analysis.

---

## 6. Sincronizzazione Oraria Ferro-Gomma a Olgiate FS

Il nodo di Olgiate-Calco-Brivio FS è modellato su una finestra di interscambio ottimale compresa tra **4 e 16 minuti** rispetto ai transiti S8:
- **Treni per Milano Garibaldi**: partenze al minuto **:08** e **:38**.
- **Treni da Milano Garibaldi**: arrivi al minuto **:21** e **:51**.
- **Treni per Lecco**: partenze al minuto **:22** e **:52**.
- **Treni da Lecco**: arrivi al minuto **:07** e **:37**.

L'algoritmo calcola per ciascuno scenario:
1. Percentuale dei treni S8 serviti da coincidenza utile.
2. Percentuale delle corse bus che incontrano un treno utile entro 15 minuti.
3. Tempo medio, mediana e 90° percentile (P90) dei tempi di attesa all'interscambio.
