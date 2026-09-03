# Gate E — Service math: PASS

**Verdetto:** PASS
**Data:** 2026-09-03
**Branch:** `gate-e-workstream`
**Commit computazionale validato:** `e2d096ca929c92da0d8a4abdacde827445e208bd`
**CI validato:** run `33755350763`, job `100648344246`
**Test Gate E:** 130/130 PASS

## 1. Portata del PASS

Gate E certifica che la matematica di esercizio è riproducibile, fail-closed e coerente con gli upstream formalmente validati A/B/C/D. Il PASS riguarda formule, lineage, controlli epistemici, budget bus-km, headway, flotta minima, cycle-time decomposition e vehicle-hours.

Il PASS **non seleziona una topologia né un orario futuro**. Le candidate di Gate D restano `HYPOTHESIS_NOT_RECOMMENDATION`; la composizione a figura 8, i target di headway, dwell, recovery, numero di giorni di servizio e flotta scelta restano `ASSUMPTION` quando usati in sensitivity analysis. La scelta tra tali alternative appartiene a Gate F.

## 2. Upstream consumati

- Gate A: PASS.
- Gate B: PASS, commit validato `55d726564e13acca55ce563cc911263ac513acb0`.
- Gate C: PASS, commit `dcc3e75ae3b4f4ea5170f48e85345b83620c5536`.
- Gate D: PASS, commit computazionale `7c220f7586d0f6e5cccd14a2d518be52eb1c4a55`.
- Gate D artifact: ID `9891607118`, SHA256 `6fbc06d74d5ba970bc980e4cde6234245e0753c22386f703ea313c6a4de9206a`.

Il CI di Gate E scarica l'artifact D PASS originale, ne verifica il digest, confronta byte-per-byte `structural_candidate_metrics.csv` con la snapshot versionata e rigenera deterministicamente l'evidenza minima di chiusura degli anelli dai waypoint D.

## 3. Benchmark di risorse

`data/risorse_tpl_pdb.csv` fornisce il benchmark validato:

- D184: 52.560 bus-km/anno;
- D185: 58.859 bus-km/anno;
- D184 + D185: **111.419 bus-km/anno**.

Il totale è letto dal file e verificato aritmeticamente; non è incorporato come costante nello script di produzione. Le componenti punta + morbida presentano un mismatch ricostruito di 1 km sul totale combinato, che Gate E conserva esplicitamente e non nasconde.

Il file PdB disponibile non contiene un benchmark di vehicle-hours D184+D185. Gate E pertanto non produce una falsa equivalenza in ore o costi. Le vehicle-hours del progetto sono calcolabili deterministicamente una volta definito il piano di esercizio, ma il confronto storico in ore richiede un'ulteriore fonte autorevole.

## 4. Route math da Gate D PASS

Le tre famiglie per cui Gate D fornisce esattamente una variante CW e una CCW chiusa sul medesimo hub FS sono:

| famiglia | km CW | km CCW | pure running CW | pure running CCW | stato definizione |
|---|---:|---:|---:|---:|---|
| `WEST_COMPACT_MONDONICO` | 10,253 | 9,740 | 19,653 min | 18,948 min | ASSUMPTION / hypothesis |
| `EAST_COMPACT_ARLATE` | 13,453 | 13,298 | 26,125 min | 26,007 min | ASSUMPTION / hypothesis |
| `EAST_CALCO_SUPERIORE_SENSITIVITY` | 15,799 | 15,704 | 32,028 min | 32,005 min | ASSUMPTION / sensitivity |

Le distanze sono `DERIVED` da metriche Gate D `DERIVED_OSM_STRUCTURAL`; i pure running time restano `MODEL_OUTPUT`. Le candidate unidirezionali, `SENSITIVITY` o `OUT_AND_BACK` non vengono trasformate artificialmente in un servizio bidirezionale e sono registrate come non eleggibili alla full bidirectional service math.

## 5. Ipotesi figura 8 compatta

Solo come sensitivity, Gate E compone `WEST_COMPACT_MONDONICO` + `EAST_COMPACT_ARLATE` perché entrambi gli anelli chiudono sul nodo `FS`. La composizione non è una raccomandazione e mantiene `route_definition_status=ASSUMPTION`.

Risultati deterministici della composizione:

- route-km CW: **23,706064 km**;
- route-km CCW: **23,037668 km**;
- pure running CW: **45,777279 min**;
- pure running CCW: **44,955157 min**;
- una coppia completa CW+CCW: **46,743733 bus-km**;
- pure running della coppia: **90,732436 min**.

## 6. Budget envelope senza inventare giorni di servizio

Per non imporre 303, 365 o un altro numero di giorni, Gate E calcola il massimo numero intero annuale di cicli completi con uguale numero CW e CCW direttamente dal budget di 111.419 bus-km.

| ipotesi | max coppie CW+CCW/anno | bus-km al massimo | margine residuo | prima coppia successiva |
|---|---:|---:|---:|---:|
| WEST compact | 5.573 | 111.418,270 | +0,730 km | sfora di 19,263 km |
| EAST compact | 4.165 | 111.418,833 | +0,167 km | sfora di 26,584 km |
| Calco Superiore sensitivity | 3.536 | 111.394,859 | +24,141 km | sfora di 7,362 km |
| FIG8 compact | **2.383** | **111.390,315** | **+28,685 km** | **2.384 coppie = +18,058 km oltre budget** |

Questi valori sono budget envelopes, non un calendario. Non è quindi consentito descrivere 2.383 coppie/anno come una frequenza giornaliera senza una successiva ipotesi esplicita sul calendario di servizio.

Per la figura 8, al limite di 2.383 coppie, le sole pure-running vehicle-hours sono circa **3.603,590 ore/anno**. Scheduled vehicle-hours maggiori richiedono dwell e recovery scelti esplicitamente.

## 7. Headway e flotta: sensitivity verificata

Il cycle time è sempre:

`cycle = pure_running + dwell + recovery`

Per la figura 8 compatta, i test verificano tra gli altri i seguenti confini:

- **60 min per direzione, 1 bus CW + 1 bus CCW:** compatibile solo se dwell+recovery non superano 14,223 min CW e 15,045 min CCW. Il rate-equivalent combinato è 30 min dove il pattern di fermate condivise lo renda applicabile. Non equivale al massimo gap passeggeri senza un timetable fasato.
- **45 min per direzione, 1 bus CW:** impossibile anche con dwell=recovery=0, perché il pure running CW è 45,777 min. In CCW resterebbero solo 0,045 min per dwell+recovery.
- **30 min per direzione:** almeno 2 mezzi CW e 2 CCW sono necessari già dal solo pure running, quindi almeno 4 mezzi in servizio prima di deadhead, relief, spares o altre esigenze di esercizio. Il rate-equivalent combinato simmetrico è 15 min, non un max-gap dimostrato.

Gate E distingue sempre `headway_CW`, `headway_CCW` e combined rate-equivalent e non usa la frequenza combinata come sinonimo della frequenza per direzione.

## 8. Red-team e fail-closed

Il run validato ha superato:

- `git diff --check`;
- compile dell'intero stack Gate E;
- **130/130 test**;
- verifica SHA256 delle snapshot D versionate;
- integrazione pinning Gate C PASS;
- benchmark runtime GTFS D184/D185: 42 trip completi in 18 gruppi, classificati `DERIVED` e non osservati nel traffico;
- download dell'artifact D PASS originale da GitHub Actions e verifica SHA256;
- confronto byte-per-byte delle metriche D;
- rigenerazione e confronto dell'evidenza waypoint ridotta;
- calcolo della composizione figura 8 come `ASSUMPTION`;
- test del confine 2.383/2.384 coppie rispetto al budget;
- test del confine flotta/headway a 45 e 60 minuti;
- esclusione automatica delle candidate non bidirezionali;
- benchmark PdB;
- fail-closed quando manca un piano di servizio integrato.

Un precedente run rosso era dovuto esclusivamente a CRLF/LF nella snapshot CSV derivata. Il problema è stato corretto canonizzando `lineterminator='\n'`; il run di PASS verifica ora sia il digest canonico sia la rigenerazione dal waypoint artifact originale.

## 9. Limiti che restano veri dopo il PASS

- `uncertain_road_km` di Gate D resta un'incertezza fisica da non reinterpretare come idoneità autobus dimostrata.
- I pure running time sono `MODEL_OUTPUT`, non tempi osservati nel traffico.
- Dwell, recovery, headway target, calendario, spare ratio, deadhead e relief non sono fatti osservati del futuro servizio.
- La figura 8 non è stata scelta da Gate E.
- Nessuna equivalenza economica può essere dedotta soltanto dal quasi-esaurimento dei bus-km.
- Nessun confronto storico in vehicle-hours viene inventato in assenza del relativo dato PdB.

Questi punti non sono failure della matematica di Gate E. Sono input decisionali e limiti epistemici che Gate F deve conservare.

## 10. Verdetto

**GATE E — PASS.**

La service math è sufficientemente verificata per sbloccare **GATE F — recommendation**, con l'obbligo di mantenere separate le metriche `DERIVED`/`MODEL_OUTPUT` dalle scelte `ASSUMPTION` e di non promuovere la figura 8 o una frequenza specifica a raccomandazione prima dell'analisi comparativa finale.
