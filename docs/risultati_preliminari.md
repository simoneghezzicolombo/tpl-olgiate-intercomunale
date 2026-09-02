# Risultati Preliminari e Sintesi dei Checkpoint (A - E)

## Checkpoint A: La Baseline dell'Offerta Esistente
L'estrazione dell'orario reale e dei dati di Piano ha confermato una severa disfunzionalità nell'allocazione delle risorse attuali:
- **Produzione assegnata dal Programma di Bacino**: $111.419 \text{ bus-km/anno}$ ($52.560 \text{ km}$ D184 + $58.859 \text{ km}$ D185).
- **Confronto con Merate**: D184+D185 dispongono del **+23,3% di km in più** rispetto all'intera rete delle Circolari Meratesi (D201+D202 = $90.372 \text{ km/anno}$).
- **Buchi orari inaccettabili**:
  - D184: buco di **6 ore e 55 minuti** tra le 06:42 e le 13:37 da Olgiate verso Monte; buco di **7 ore e 4 minuti** in direzione opposta (07:20 → 14:24).
  - D185: buchi di **4 ore e 30 minuti** tra le 09:05 e le 13:35.
- Solo 6 coppie di corse al giorno per linea, con un cadenzamento formale di 120 minuti che nei fatti esclude i cittadini dall'uso spontaneo del TPL.

---

## Checkpoint B: Popolazione, Copertura Reale e Domanda Pendolare
- **Popolazione Core calibrata a 100m**: **22.914 residenti ISTAT 2025**.
- **Copertura pedonale attuale della stazione Olgiate FS**: solo **4.579 residenti** vivono entro 15 minuti a piedi dal treno. Ben l'**80% del bacino** (18.335 persone) non può raggiungere a piedi la ferrovia.
- **Rete a fermate diffuse**: portando le fermate lungo i due anelli dell'8, la popolazione entro **10 minuti di cammino reale (slope-adjusted con pendenza)** sale a **17.045 residenti (74,4% del bacino)**.
- **Matrice OD del Pendolarismo**: oltre **4.470 spostamenti quotidiani sistematici** convergono sull'asse della stazione FS di Olgiate e sui treni S8 verso Milano e Lecco.

---

## Checkpoint C: Alternative di Tracciato ed Efficienza delle Frazioni
Il calcolo della metrica marginale $\text{Rendimento} = \frac{\Delta \text{Residenti Serviti}}{\Delta \text{Minuti Ciclo}}$ ha permesso di ordinare con rigore le deviazioni:
1. **Arlate / San Colombano**: rendimento **1.150 residenti/minuto**. Essendo posizionato sul ramo naturale di discesa da Brivio verso Calco Sud e FS, evita di percorrere due volte la SP72 a vuoto.
2. **Mondonico / Monticello**: rendimento **613 residenti/minuto**. Non è un vicolo cieco se percorso come ritorno ad anello da Santa Maria Hoè verso Olgiate FS (+1,5 min per 920 abitanti).
3. **Calco Superiore**: rendimento **128,9 residenti/minuto** (+4,5 min per 580 abitanti). Rischio critico di portare il ciclo a 59,5 minuti con buffer quasi nullo (30 secondi).
4. **San Zeno**: rendimento **94,7 residenti/minuto** (+7,5 min per 710 abitanti). **Sfora il vincolo di ciclo** portando la marcia a 62,5 min. Da escludere dall'orario fisso.
5. **Code Ravellino e Caprino**: rendimento bassissimo sul tempo di ciclo (27 ab/min Ravellino, 70 ab/min Caprino). Dilatano il ciclo a 74-75 minuti, rendendo impossibile il cadenzamento a 60 min. Vanno scorporate dal servizio base orario.

---

## Checkpoint D & E: Pareto Frontier e Soluzione Vincente
Dall'analisi delle 8 varianti candidate:
- **Soluzione Pareto-Ottimale**: **VAR_04 (Doppio Anello Simmetrico Integrato Mondonico + Arlate)**.
  - Lunghezza: **19,8 km** (inferiore persino alla baseline a spola di 22,4 km!).
  - Runtime di marcia: **55,0 minuti** (26 min Ovest + 29 min Est).
  - Buffer tecnico a Olgiate FS: **5,0 minuti netti** per ogni ora.
  - Popolazione servita a 10 min: **17.350 residenti (+2.150 nuovi residenti rispetto all'attuale)**.
  - Score bilanciato più alto: **0,829**.
- **Scenario Operativo Vincente**: **SCENARIO 4 (Ibrido di Punta a Saldo Zero)**.
  - 2 autobus contemporanei in senso Orario (CW) e Antiorario (CCW) nelle 6 ore di punta feriali (06:30–09:30 e 16:30–19:30), garantendo partenze ogni 15-30 minuti a Olgiate FS e adduzione immediata a tutti i treni S8.
  - 1 autobus continuo nelle 7 ore di morbida diurna.
  - Produzione annuale: **112.261 km/anno**, con uno scostamento di appena **+842 km/anno (+0,75%)** rispetto ai 111.419 km di budget PdB: **perfetta neutralità economica a saldo zero**.
