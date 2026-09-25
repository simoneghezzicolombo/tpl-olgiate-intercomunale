# Linea 8 — il tracciato da 25 km non era il minimo chilometrico

**25 settembre 2026.** Questa è una verifica del grafo RT017 fissato, non
una selezione della linea né un orario. La promessa confrontata è una corsa
utile alla fermata ogni 30 minuti per quattro ore di punta e ogni 60 minuti
nelle altre dodici ore, per 260 giorni: **20 traversate complete/giorno in
totale**, qui rappresentate come 10 per ciascun senso. Questo conto non
dimostra che i passaggi siano regolari o che i viaggi verso FS siano utili.

Il precedente algoritmo [`shortest`](../scripts/phase2_audit_rt031_south_road_probe_v3.py)
minimizzava **i minuti di marcia** su ogni tratto tra waypoint; i metri
erano soltanto lo spareggio. Non era quindi corretto chiamare il percorso
inclusivo da circa 25 km «il più corto in km».

Il nuovo [audit con entrambi gli obiettivi](../outputs/phase2/rt031_line8_local_shortcuts_v3/distance_objective_audit.json)
usa gli stessi file RT017 fissati per hash, gli stessi waypoint e le
svolte *via-node* rappresentate:

| Ordine dei waypoint | Criterio delle strade | Coppia dei sensi | Km/anno con 10 coppie/giorno | Identità di fermata incontrate in entrambi i sensi |
| --- | --- | ---: | ---: | ---: |
| Inclusivo iniziale | minuti | 52,208 km | 135.740 | 25 |
| Inclusivo iniziale | metri | 50,218 km | 130.568 | 19 |
| Riordino ovest che conservava tutte le identità | minuti | 50,919 km | 132.389 | 25 |
| Stesso riordino ovest | metri | **49,951 km** | **129.873** | **22** |

Il percorso a metri col riordino ovest perde l'incontro, in entrambi i
sensi, con `ASF::BRIVIO_BAR_CRISTALLO`,
`ASF::OLGIATE_MOLGORA_VIA_STATALE` e `FROZEN::300956`. Questo è un
compromesso geografico reale, non un risparmio «gratis»; la tabella non
quantifica ancora la perdita pedonale né certifica fermate attive.
La [mappa comparativa](../outputs/phase2/rt031_line8_local_shortcuts_v3/distance_option.png)
e il [tracciato GeoJSON](../outputs/phase2/rt031_line8_local_shortcuts_v3/distance_option.geojson)
mostrano entrambe le direzioni, le tre identità non più incontrate e i
due bisogni di nuova fermata, ancora non approvati.

Per verificare se un *ordine completamente diverso* potesse colmare il
divario, il [limite inferiore su tutti gli ordini dei waypoint fissi](../outputs/phase2/rt031_line8_local_shortcuts_v3/waypoint_lower_bound.json)
usa programmazione dinamica su tutte le permutazioni interne alle due
ali, mantenendo FS, Olgiate sud e San Zeno nei loro ruoli. Concede a
ogni coppia di waypoint la strada minima in metri **indipendentemente**
dalle altre: è quindi ottimistico e può perfino non comporre un percorso
legale o conservare le fermate incontrate.

- Limite inferiore: **48,613 km per coppia**, pari ad almeno **126.394
  km/anno** prima di deposito e sosta, se i waypoint restano esattamente
  quelli attuali nelle rispettive ali.
- Per 111.419 km/anno servirebbero al massimo **42,853 km per coppia**
  prima di qualunque extra. Mancano ancora almeno **14.975 km/anno** anche
  nel limite ottimistico: un diverso ordine o una strada alternativa
  fra questi medesimi punti non può chiudere il divario.
- Fra i 13 singoli waypoint esistenti rimovibili, solo omettere **Brivio
  centro** fa scendere il limite inferiore sotto il cap, a **111.130
  km/anno**: appena **289 km** di margine teorico, prima di deposito,
  fermate, legalità delle giunzioni e viaggi passeggeri. Non è una
  proposta: omettere il waypoint non garantisce più il servizio al centro
  di Brivio, che l'utente desidera, e questo limite può non essere
  realizzabile. Il test locale di semplice omissione del waypoint
  perdeva due identità d'inventario e 46,61 punti percentuali di accesso
  potenziale a 10 minuti nel comune di Brivio: non va confuso con
  questo nuovo limite ottimistico su tutti gli ordini.

**Conclusione operativa:** il dominio «stessi punti precisi, due ali,
stessa promessa di frequenza e 111.419 km» è insufficiente anche con
strade e ordini ottimizzati. Il confronto successivo deve spostare o
sostituire *punti rappresentativi* e verificare la perdita di accesso
pedonale 5/8/10 minuti e i viaggi reali verso FS; oppure dichiarare i
chilometri aggiuntivi necessari. La conservazione delle fermate resta
una preferenza da misurare, non un vincolo inventato. Nessuna PRIMARY o
RUNNER-UP è autorizzata.
