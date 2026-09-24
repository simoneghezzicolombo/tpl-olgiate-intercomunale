# Linea 8 — audit di scorciatoie locali, non scelta della rete

**24 settembre 2026.** Si parte dalla geometria inclusiva 11/11, non
dall'anello corto di Olgiate. Le [24 modifiche singole sul grafo
fissato](../outputs/phase2/rt031_line8_local_shortcuts_v3/audit.json)
consistono nel togliere **un** waypoint esistente oppure scambiare
**due waypoint esistenti adiacenti**. Olgiate sud, San Zeno e FS restano
nei rispettivi ruoli; non sono stati cercati tutti i possibili ordini,
percorsi stradali o siti di fermata. Le distanze sono di cammini
modellati, non di un itinerario TPL autorizzato.

La variante inclusiva di riferimento misura **52,208 km per una coppia
dei due versi** (26,455 + 25,753). Tutte le 24 modifiche sono
percorribili sul grafo e non mostrano violazioni delle svolte *via-node*
rappresentate. Tredici riducono i km; **nessuna delle tredici conserva
tutte le 25 identità di fermata d'inventario incontrate nei due versi**.
Questo non equivale a perdere la stessa quota di residenti: la
[matrice pedonale ricalcolata](../outputs/phase2/rt031_line8_local_shortcuts_v3/walk.json)
misura l'effetto potenziale a 5/8/10 minuti, supponendo che ogni
fermata incontrata e i due nuovi punti ipotetici diventino eventi di
salita utili.

| Modifica singola | Risparmio km per coppia | Fermate incontrate perse | Effetto locale a 10 min |
| --- | ---: | --- | --- |
| Saltare Brivio centro | 5,098 | 2, fra cui Brivio centro | Brivio **−46,61 pp** |
| Saltare Hoè | 2,928 | Hoè | Santa Maria Hoè **−2,32 pp**; a 5 min −8,67 pp |
| Saltare Arlate | 2,433 | Arlate | Calco **−12,08 pp** |
| Invertire Rovagnate/Perego | **1,562** | Via Como a Santa Maria Hoè | **0,00 pp** a 10 min in tutti e cinque i comuni; a 5 min Santa Maria Hoè −2,84 pp, La Valletta −0,21 pp |
| Saltare Calco Via Nazionale | 0,108 | Via Nazionale | Calco **−5,40 pp** |

L'inversione Rovagnate/Perego è il **primo approfondimento sensato**,
non una selezione: mantiene i waypoint di tutte le località richieste,
inclusi sud e San Zeno, e continua a incontrare tutte le 11 identità
attuali del confronto. Perde però la fermata d'inventario di Via Como
nel passaggio in entrambi i versi. Il 10-minuti pedonale potenziale resta
invariato in ogni comune; l'8-minuti pure, ma il 5-minuti peggiora come
indicato. Il tempo stradale modellato dal waypoint alla successiva FS,
esclusi sosta, recupero e attesa, cambia di **non più di circa 1,1 min**
per i waypoint comuni; questo non prova viaggi passeggeri equivalenti.
La [mappa a due scale](../outputs/phase2/rt031_line8_local_shortcuts_v3/west_swap_preview.png)
e il [GeoJSON dei due versi](../outputs/phase2/rt031_line8_local_shortcuts_v3/west_swap.geojson)
rendono controllabile lo spostamento di strada.

Il risparmio è reale *nel modello*: circa **3,0%** della coppia,
equivalente a **3.250 km/anno** se si effettuano otto coppie al giorno
per 260 giorni. Anche così, dieci coppie giornaliere per 260 giorni
richiederebbero circa **131.678 km/anno** prima degli extra, oltre il
cap di 111.419. È dunque un miglioramento da validare, **non la
soluzione al divario di frequenza/span**.

Prima di proporla ad Agenzia e operatore occorre verificare sul campo
la strada divergente, idoneità e manovre del bus, posizione/verso della
fermata Via Como e delle altre fermate, restrizioni dipendenti dalla
storia del percorso, tempi con sosta e traffico, viaggi reali verso/da
FS e orario/mezzi. Il grafo RT017 non certifica l'ottimo globale né
tutte le restrizioni *via-way*. Nessuna PRIMARY o RUNNER-UP è autorizzata.
