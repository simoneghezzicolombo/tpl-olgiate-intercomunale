# 06. Valutazione Frazioni: La Formula del Rendimento

## 1. La Formula del Rendimento Trasportistico

Per superare il dibattito campanilistico ("perché non passate anche dalla mia frazione?"), la pianificazione della Linea 8 applica un indicatore oggettivo di efficienza socio-economica:

$$\mathbf{Rendimento_{deviazione}} = \frac{\Delta \text{Nuovi Residenti serviti a piedi (5–10 min)}}{\Delta \text{Minuti aggiuntivi al tempo di ciclo}}$$

### I Due Vincoli Invalicabili
1. **Vincolo di Ciclo Orario ($\le 60 \text{ minuti}$)**:
   - Partendo da una baseline di **55 minuti** (25 min Ovest + 30 min Est), il margine totale disponibile per l'intero 8 è di appena **5 minuti** (necessari come buffer alla stazione di Olgiate FS).
   - Qualsiasi deviazione a spola (andata e ritorno sulla stessa strada) che aggiunga più di **3-4 minuti** complessivi fa collassare il cadenzamento a un solo mezzo.
2. **Geometria ad Anello vs Deviazione a Spola**:
   - Una deviazione che costringe il bus a entrare in una frazione e poi tornare indietro sullo stesso asse perde minuti preziosi due volte.
   - Una modifica di tracciato che **chiude l'anello percorrendo una strada diversa al ritorno** non "costa" minuti a vuoto, ma sostituisce chilometri percorsi due volte con nuovi chilometri utili a rete.

---

## 2. Matrice di Valutazione delle Frazioni

| Frazione / Località | Ramo | Comune | Popolazione Servita (WorldPop) | $\Delta$ Tempo Ciclo | Rendimento (Residenti / minuto) | Sostenibilità Ciclo 60' | Esito e Raccomandazione |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| **Perego** | Ovest | La Valletta Brianza | 1.850 | **0 min** | $\infty$ | **SI** | **CONFERMATO D'UFFICIO** (Asse centrale della SP342 dir). |
| **Beverate** | Est | Brivio | 1.600 | **0 min** | $\infty$ | **SI** | **CONFERMATO D'UFFICIO** (Asse centrale della SP72). |
| **Mondonico / Monticello** | Ovest | Olgiate Molgora | 920 | **+2,5 min** (in anello) | **368 ab./min** | **SI** | **VARIANTE RACCOMANDATA OVEST**: Chiusura dell'anello ovest via Mondonico invece di tornare dalla SP342 dir. |
| **Arlate** | Est | Calco | 1.150 | **+3,5 min** (in anello) | **328 ab./min** | **SI** | **VARIANTE RACCOMANDATA EST**: Chiusura dell'anello est via Arlate/Calendone verso Olgiate FS. |
| **Calco Superiore** | Est | Calco | 580 | **+4,5 min** | **129 ab./min** | **AL LIMITE** | **SUBORDINATA**: Rischia di portare il ramo Est a 33 min. Valutare in fase di micro-routing. |
| **San Zeno** | Ovest | Olgiate Molgora | 710 | **+7,5 min** (spola) | **95 ab./min** | **NO** | **BOCCIATA DALL'ORARIO FISSO**: Fa sforare il ciclo a 63-65 min. Da servire con TPL a chiamata / navetta. |
| **Ravellino** | Ovest (Coda) | Colle Brianza | 520 | **+19,0 min** | **27 ab./min** | **NO** | **SCORPORATA DAL CORE**: Ciclo salirebbe a 74 min. Mantenere solo come prolungamento scolastico/biorario. |
| **Caprino / Celana** | Est (Coda) | Caprino Bergamasco | 1.400 | **+20,0 min** | **70 ab./min** | **NO** | **SCORPORATA DAL CORE**: Ciclo salirebbe a 75 min. Servire con prolungamenti specifici o navetta d'Adda. |

---

## 3. Perché Mondonico e Arlate "Vincono" Diventando Rami di Chiusura

L'intuizione fondamentale emersa dalla simulazione è che **Mondonico e Arlate non devono essere trattate come deviazioni a fondo cieco**, ma come rami naturali di ritorno per trasformare le due spole in veri anelli circolari:

### L'Anello Ovest con Chiusura Mondonico
- Invece del vecchio percorso: `Olgiate FS -> Rovagnate -> Perego -> Santa Maria -> e indietro uguale` (10,4 km, 25 min)
- Il nuovo anello diventa: `Olgiate FS -> Rovagnate -> Perego -> Santa Maria Hoè -> Monticello -> Mondonico -> Olgiate FS` (9,5 km, 26-27 min).
- Non si torna indietro sui propri passi: chi sale a Santa Maria per andare a Olgiate scende rapido passando per Mondonico; chi abita a Mondonico ha il bus direttamente sotto casa verso la stazione.

### L'Anello Est con Chiusura Arlate
- Invece del vecchio percorso: `Olgiate FS -> Calco -> Beverate -> Brivio -> e indietro uguale` (12,0 km, 30 min)
- Il nuovo anello diventa: `Olgiate FS -> Calco Centro -> Beverate -> Brivio Castello/Porto -> Arlate (San Colombano) -> Olgiate FS` (10,5 km, 29-30 min).
- Si realizza una perfetta maglia circolare che costeggia l'Adda e risale dalla dorsale collinare di Arlate, collegando le scuole e gli insediamenti residenziali finora totalmente tagliati fuori dal TPL.
