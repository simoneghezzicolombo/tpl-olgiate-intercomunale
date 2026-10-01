# Linea 8 — accesso dai quattro punti OSM di località

Audit del 2 ottobre 2026 sulla proposta confermata del 1° ottobre: 27 siti e 16 giri completi.

I quattro nomi hanno un punto OSM verificabile. Il calcolo riguarda quel punto; non delimita la frazione e non dimostra che tutti i suoi abitanti siano serviti. Le fermate e i percorsi pedonali restano da verificare fisicamente.

| Punto OSM | Sito di progetto con minor cammino dal punto | A piedi punto→sito | A piedi sito→punto | Bus sito→FS | Bus FS→sito |
| --- | --- | ---: | ---: | ---: | ---: |
| Mondonico | S. Maria Hoè - S.P. 58 ang. Via Cenisio (west_B) | 11.27 | 11.27 | 13.56 | 24.24 |
| Monticello | Olgiate Molgora - Via Della Salute (west_B) | 7.20 | 7.20 | 10.96 | 26.84 |
| Calco Superiore | Calco Centro – Municipio (east_A) | 11.42 | 11.42 | 9.71 | 30.56 |
| Crescenzaga | Rovagnate - Statale / Via Lombardia (west_B) | 13.71 | 13.71 | 24.82 | 12.98 |

Minuti modellati. La scelta del sito minimizza soltanto il cammino verso una fermata diversa da FS. Un sito più vicino può offrire un viaggio in bus più lungo; questo abbinamento non è una scelta della migliore combinazione oraria.

Il JSON conserva tutti i 108 abbinamenti punto–sito, i cammini distinti nei due versi, i connettori, le occorrenze del bus e le finestre nominali. I tempi a bordo sono quelli dell’orario di progetto con soste nominali. Sommare cammino e bus non aggiunge l’attesa: manca una domanda con ora di partenza/arrivo per confrontare i viaggi programmati. Nessuna domanda passeggeri è dedotta dagli OD comunali.

Il grafo è lo snapshot RT028 del 6 settembre 2026, con snap a nodi entro 90 m e controllo delle barriere, velocità assunta 80 m/min e direzioni pedonali preservate. Le coordinate dei punti sono confrontate con gli ID OSM grezzi; quelle dei siti sono confrontate con il registro confermato. Le distanze del precedente inventario verso la rete esistente non sono riutilizzate.

Restano da risolvere Cornello (coordinata di fermata), Cassina (identità richiesta), l’oratorio di Olgiate (sede esatta), il legame con una fermata ordinaria della Casa di Comunità e il perimetro georeferenziato del quartiere meridionale. Il punto Via Cantù a nord resta distinto dall’area Canova–San Zeno a sud.

Fonti e checksum normalizzati per i file testuali sono registrati nel [JSON dell’audit](../outputs/phase2/rt031_line8_local_shortcuts_v3/caller_confirmed_locality_point_access_20261001.json). Script: `scripts/phase2_audit_rt031_confirmed_locality_points_v3.py`. Per riprodurre: `python -m scripts.phase2_audit_rt031_confirmed_locality_points_v3 --pedestrian-osm <rt028_osm_pedestrian_snapshot_v3.osm>` con `PYTHONPATH=.;src`.
