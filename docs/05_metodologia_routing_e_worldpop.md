# 05. Metodologia: Routing Reale e Accessibilità WorldPop

## 1. Superare l'Illusione dei Confini Comunali

I dati demografici ISTAT attribuiscono ai 5 comuni del bacino **22.914 residenti**. Tuttavia, nella pianificazione trasportistica moderna, i residenti censiti a livello comunale rappresentano solo un'indicazione potenziale:
- Una frazione isolata a 2 km dalla fermata più vicina non è servita dal trasporto pubblico.
- Un cittadino che deve camminare 25 minuti lungo una strada provinciale senza marciapiede utilizzerà sistematicamente l'automobile.

Il vero valore di un sistema TPL non si misura sulla popolazione teorica dei comuni attraversati, ma sulla **popolazione effettivamente raggiungibile a piedi (pedonale a 5 e 10 minuti)** dalle fermate del servizio.

---

## 2. La Metodologia Ereditata dal Progetto S8

L'analisi dell'accessibilità applicata alla Linea 8 adotta la metodologia scientifica testata ed elaborata nel progetto S8 Milano-Lecco (cfr. `data/README_methodology.txt`):

### Componenti del Modello Spaziale
1. **Griglia Raster WorldPop (~100 metri)**:
   - Dati raster di popolazione ad alta risoluzione spaziale (`ita_ppp_2020_UNadj.tif`), con valori espressi in residenti per cella di circa $100 \times 100 \text{ m}$.
   - Consente di mappare la reale concentrazione urbana, distinguendo i nuclei compatti (es. centri storici di Olgiate, Perego, Brivio) dall'edificato sparso rurale.
2. **Grafo Stradale e Pedonale da OpenStreetMap (OSM)**:
   - Estrazione della rete viaria e dei percorsi calpestabili (footway, path, pedestrian, residential, tertiary, secondary).
   - Velocità pedonale media calibrata a **4,8 km/h** su strade pianeggianti, **3,0 km/h** su rampe e gradini, con penalità per pendenze collinari accentuate (es. San Zeno, Calco Superiore, Mondonico).
3. **Calcolo delle Isocrone Pedonali Reali**:
   - Misurazione dei tempi di cammino effettivi da ciascuna cella abitata alla fermata più vicina.
   - Soglie standard di attrattività pedonale:
     - **5 minuti** ($\sim 400 \text{ metri}$): accessibilità ottimale (utenza captive e spontanea).
     - **10 minuti** ($\sim 800 \text{ metri}$): raggio massimo standard per il TPL di superficie.
     - **15 minuti** ($\sim 1.200 \text{ metri}$): soglia limite (attrattività ridotta del 70%).

---

## 3. Il Confronto con i Dati di Stazione di Olgiate FS

Dall'estrazione dei dati di bacino del progetto S8 (`data/population_by_station_meratese_only.csv`), l'accessibilità pedonale diretta alla sola **Stazione FS di Olgiate-Calco-Brivio** risulta:
- **Entro 5 minuti a piedi**: **785 residenti** (30 celle)
- **Entro 10 minuti a piedi**: **2.478 residenti** (141 celle)
- **Entro 15 minuti a piedi**: **4.579 residenti** (323 celle)

Questo dimostra perché il solo treno non basta: **ben 18.335 dei 22.914 residenti (l'80% della popolazione del bacino!) vivono a più di 15 minuti a piedi dalla stazione**.

### L'effetto moltiplicatore della Linea 8
Distribuendo circa 18-20 fermate lungo i due anelli dell'8:
- Ovest: 9 fermate (FS, Olgiate Centro/Municipio, Scarpone, Rovagnate Centro, Perego Centro, Santa Maria Hoè Centro, Monticello, Mondonico, San Zeno Basso).
- Est: 10 fermate (FS, Calco Nazionale, Calco Chiesa, Beverate Scuole, Beverate Centro, Brivio Castello, Brivio Porto Adda, Arlate San Colombano, Calco Basso, FS).

La popolazione compresa entro **5-10 minuti a piedi** da una fermata del sistema sale da **4.579** a oltre **17.500 residenti** (oltre il 76% dell'intero bacino a 5 comuni).
Questo trasforma la ferrovia da servizio di prossimità per poche centinaia di metri a dorsale di mobilità dell'intero distretto.
