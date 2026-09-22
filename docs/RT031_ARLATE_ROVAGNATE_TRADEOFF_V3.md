# RT031 — Arlate e Rovagnate: il trade-off osservato

Questo è un confronto **non decisionale** tra linee pubbliche singole. L'[audit
macchina](../outputs/phase2/rt031_arlate_rovagnate_convergence_v3/convergence_audit_v3.json)
fissa fonti, run, digest e limiti semantici. Le percentuali qui sotto sono
**copertura pedonale potenziale della popolazione a 10 minuti**, non domanda
osservata né tempi di viaggio generalizzati pesati per OD.

| Linea strutturale | km/ciclo | Fermate attuali esatte | Totale | Brivio | Olgiate | Santa Maria | La Valletta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Arlate Cantina + Rovagnate `PATH_271779790861d8f4cb39` | 21,22 | 6/11 | 66,94% | 83,00% | 53,05% | 91,89% | 64,69% |
| Arlate Cantina + Rovagnate `PATH_b503ca14c59884289fa4` | 21,17 | 6/11 | 65,66% | 87,29% | 45,45% | 91,89% | 64,69% |
| Arlate Cantina + Rovagnate `PATH_5d1fe65e1849feb21601` | 21,23 | 6/11 | 62,58% | 80,11% | 45,16% | 91,89% | 50,32% |
| Arlate Cantina + Rovagnate + Santa Maria centro `PATH_f01db28ef0cefbc5e0b4` | 21,39 | 7/11 | 65,80% | 87,29% | 45,45% | 93,43% | 64,70% |
| Arlate Cantina + Rovagnate + Santa Maria centro `PATH_2a3831867599e05d3fa1` | 21,42 | 7/11 | 62,72% | 80,11% | 45,16% | 93,43% | 50,32% |
| Brivio + Santa Maria `WALK_8586d7e865308d0510c6` | 21,39 | 7/11 | 65,89% | 87,80% | 55,92% | 91,89% | 52,48% |
| Brivio + Santa Maria `WALK_e5d89184ad2835c735e1` | 21,41 | 7/11 | 66,06% | 88,70% | 55,92% | 91,89% | 52,48% |

I valori sono arrotondati: l'[artefatto di confronto esatto](https://github.com/simoneghezzicolombo/tpl-olgiate-intercomunale/actions/runs/35714978357)
usa frazioni razionali sui cinque comuni e sulle soglie 5/8/10 minuti, più
conservazione delle fermate come preferenza e distanza come costo. **Tutte e
sette** le linee restano Pareto-non-dominate in questo insieme di prova. Non
c'è un punteggio composito né una preferenza normativa per sceglierne una.

## Cosa è cambiato rispetto al percorso minimo via Arlate

La ricerca generica con priorità Arlate, limitata a un milione di espansioni,
non aveva trovato una linea Brivio + Santa Maria + Arlate: 190 stati erano
ancora in coda. Questo non è un risultato di impossibilità. Il calcolo mirato
di distanza aveva già certificato percorsi fisici con tutte e tre le località.

Le varianti via Arlate che conservavano 7–8 fermate attuali eliminavano però
il ramo Rovagnate: La Valletta scendeva all'1,09% a 10 minuti. Richiedendo
invece la fermata attuale `FROZEN::300879` (*Rovagnate — Vinicola Ghezzi*)
come priorità **di una corsia diagnostica**, non come filtro del dominio
complessivo, sono emersi tre percorsi via `Arlate — Cantina Pirovano` sotto
il riferimento di 21,427 km/ciclo. Mantengono 6/11 identità attuali e
recuperano La Valletta fino al 64,69%. Il percorso più favorevole al totale
porta 66,94% contro 66,06% della migliore variante precedente, ma Brivio
scende da 88,70% a 83,00% e si conserva una fermata attuale in meno.

Con `Arlate — Bivio per il Paese` e Rovagnate, nessuna delle dieci combinazioni
mirate di altre due fermate attuali rientra nello stesso riferimento; il
minimo è 22,325 km/ciclo. È una conclusione **solo per quelle combinazioni e
quel riferimento**, non l'esclusione di qualunque linea via quel punto.

Un'ulteriore prova mirata ha richiesto anche due identità di Santa Maria:
`300805` (*Tremonte/Via Trento*) e `300782` (*S. Maria Hoè*). Due dei nove
percorsi minimi così cercati restano sotto il riferimento, a **21,391** e
**21,420 km/ciclo**, con **7/11** fermate attuali conservate. Il secondo ha
solo circa **6,6 metri per ciclo** di margine nel contesto 20×260. La prima
linea aggiunge centro di Santa Maria e mantiene La Valletta al 64,70%, ma
Olgiate scende al 45,45% contro il 55,92% delle due varianti precedenti.
Questi due [witness tipizzati](https://github.com/simoneghezzicolombo/tpl-olgiate-intercomunale/actions/runs/35714609548)
sono anch'essi una sola linea con eventi ordinati, non un orario adottato.

Ogni nuova variante sotto il riferimento è stata ricostruita come **una sola
linea pubblica riconoscibile con eventi di fermata ordinati**; gli artefatti
tipizzati sono riprodotti byte-per-byte. L'[audit mezzi](https://github.com/simoneghezzicolombo/tpl-olgiate-intercomunale/actions/runs/35714850830)
mostra per le cinque linee un tempo di corsa da modello di circa 44–46 minuti,
**senza dwell osservato**. Nella griglia deterministica a 18 ore, con 2 ore
H30 in punta e 16 ore H60, occorrono 2–3 mezzi a seconda del caso
ingegneristico; le griglie 12/14/16 ore arrivano a 4. Queste frequenze e
questi span sono esempi di confronto, non l'orario scelto.

Restano fuori da questa corsia le fermate proposte di Pianezzo (verifica sul
campo pendente) e gli stop storici di Sartirana fuori dal dominio fisico
pinned RT022. Non sono dichiarati impossibili. Non sono stati fissati
`decision_budget_km`, `uncertainty_band_min`, limite mezzi o preferenze pesate;
OD municipale non è attribuito a passeggeri/percorsi e nessuna frequenza della
griglia è una probabilità empirica di coincidenza persa.

```text
candidate_domain_complete=false
network_selected=false
primary_selection_authorised=false
runner_up_selection_authorised=false
```
