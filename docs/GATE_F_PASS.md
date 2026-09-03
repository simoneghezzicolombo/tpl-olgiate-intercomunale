# Gate F — Recommendation / Pareto: PASS

**Verdetto:** PASS
**Data:** 2026-09-03
**Branch:** `gate-f-workstream`
**Implementazione validata:** `66628937d9786d737cd0edcfa5450f8ff2c3e582`
**CI validata:** run `33756779905`, job `100653029473`
**Test Gate F:** 84/84 PASS
**Recommendation status:** `NO_DEFINITIVE_RECOMMENDATION_SUPPORTED_BY_CURRENT_EVIDENCE`

## 1. Significato del PASS

Gate F ha completato il proprio compito decisionale senza imporre a priori la figura 8 e senza trasformare ipotesi di progetto in risultati fattuali.

Il risultato finale non è la selezione di una topologia. Il risultato è che, con gli artefatti A-E formalmente validati, **non esistono almeno due alternative future pairable e sufficientemente definite senza ipotesi di progetto da cui derivare un Pareto definitivo sulle sei metriche di Gate F**.

Di conseguenza una raccomandazione unica oggi richiederebbe di scegliere internamente almeno fermate future, headway, calendario, dwell/recovery, nozione di flotta e fase di interscambio S8. Queste scelte non sono risultati upstream e non vengono inventate da Gate F.

Un PASS senza vincitore è quindi intenzionale: il gate ha verificato che la decisione non è identificabile dai dati correnti e ha impedito una falsa precisione.

## 2. Upstream verificati

La CI Gate F costruisce un bundle hashato e verifica direttamente gli evidence file negli oggetti Git dei workstream A-E.

- Gate A: PASS.
- Gate B: PASS, motore spaziale validato al commit `55d726564e13acca55ce563cc911263ac513acb0`.
- Gate C: PASS, branch validata `dcc3e75ae3b4f4ea5170f48e85345b83620c5536`.
- Gate D: PASS, commit computazionale `7c220f7586d0f6e5cccd14a2d518be52eb1c4a55`.
- Gate E: PASS, commit computazionale `e2d096ca929c92da0d8a4abdacde827445e208bd`, stato di chiusura `236fc479421e5da42f1028be5ff466233f8f15b0`.

Il closure runner ha confermato `A=B=C=D=E=PASS` da evidence verificata, non da flag digitati manualmente.

## 3. Inventario completo, senza cherry-picking

Gate F importa automaticamente tutti gli scenari esposti dal Gate E PASS. Non esiste un flag `preferred` o `recommended` e `FIG8_COMPACT` non riceve trattamento speciale.

### Alternative pairable con service math Gate E

| scenario | paired cycle km CW+CCW | pure running min CW+CCW | max coppie annue nel budget | bus-km al limite | margine budget |
|---|---:|---:|---:|---:|---:|
| `WEST_COMPACT_MONDONICO` | 19,992512 | 38,600714 | 5.573 | 111.418,270 | +0,730 km |
| `EAST_COMPACT_ARLATE` | 26,751220 | 52,131722 | 4.165 | 111.418,833 | +0,167 km |
| `EAST_CALCO_SUPERIORE_SENSITIVITY` | 31,503071 | 64,033797 | 3.536 | 111.394,859 | +24,141 km |
| `FIG8_COMPACT` | 46,743733 | 90,732436 | 2.383 | 111.390,315 | +28,685 km |

Il benchmark comune è D184+D185 = **111.419 bus-km/anno**. Le quantità sopra sono budget envelope deterministici di Gate E, non un calendario di servizio.

Tutte e quattro le righe mantengono `route_definition_status=ASSUMPTION`. Gate E stesso le definisce hypothesis/sensitivity, non recommendation.

### Candidate non pairable

L'inventario conserva inoltre tutte le cinque candidate che Gate E non può trasformare in full bidirectional service math:

- `EAST_CAPRINO_CELANA_EXTENSION`;
- `WEST_D184_CORRIDOR_OUT_AND_BACK`;
- `EAST_D185_CORRIDOR_OUT_AND_BACK`;
- `WEST_RAVELLINO_EXTENSION`;
- `WEST_SAN_ZENO_SENSITIVITY`.

Sono registrate come `UNPAIRED_NOT_ELIGIBLE_FOR_FULL_BIDIRECTIONAL_SERVICE_MATH`, non eliminate silenziosamente.

Totale inventario verificato in CI: **9 alternative**, di cui **4 pairable** e **5 unpaired**.

## 4. Perché non viene pubblicata una falsa frontiera Pareto definitiva

Il contratto Gate F v2 prevede sei obiettivi comparabili:

1. copertura di popolazione, max;
2. headway combinato rate-equivalent, min;
3. bus-km annui, min;
4. minimo di veicoli scheduled in servizio, min;
5. connessioni S8 utili, max;
6. territori serviti, max.

I motori per calcolarli sono predisposti e testati, ma gli upstream non definiscono un unico stop set futuro né un unico service plan futuro per ciascuna topologia. Il Gate D artifact contiene waypoint di routing e anchor di progetto, non una decisione sulle fermate effettivamente servite. Gate E certifica la service math, ma dichiara headway target, dwell, recovery, calendario e scelta di flotta come input decisionali quando usati nelle sensitivity. Gate C fornisce i 74 eventi S8 reali del 2026-09-03, ma una percentuale di coincidenze futura richiede gli eventi bus al nodo e una policy di interscambio dichiarata.

Inserire questi elementi a mano per produrre sei numeri completi violerebbe il principio zero-hardcoding del progetto e potrebbe cambiare artificialmente la frontiera.

Pertanto la frontiera Pareto definitiva è **non eleggibile**, non vuota e non fallita. Il closure audit conta **0 alternative pairable assumption-free** e blocca qualsiasi `recommended_scenario_id`.

## 5. Cosa possiamo già concludere numericamente

Le metriche Gate E mostrano un trade-off reale e non controverso sulle risorse: le alternative più estese richiedono più km per coppia e più pure running time, quindi consentono meno coppie complete entro lo stesso envelope di 111.419 bus-km/anno.

`FIG8_COMPACT`, per esempio, combina WEST compact + EAST compact e richiede 46,743733 km per una coppia CW+CCW, contro 19,992512 km per WEST e 26,751220 km per EAST. Al limite del budget consente 2.383 coppie complete annue, contro 5.573 WEST e 4.165 EAST.

Questo non dimostra che la figura 8 sia peggiore: il suo potenziale beneficio è proprio integrare più territorio in un unico disegno. Ma quel beneficio deve essere misurato con stop set e service policy coerenti prima di poterlo bilanciare contro il costo operativo. Dichiararla già vincente, o già perdente, sarebbe metodologicamente scorretto.

## 6. Verifiche Gate F

La CI finale `33756779905` ha superato:

- `git diff --check` dall'originaria baseline Gate F;
- **84/84 test** unitari e di integrazione;
- compile di tutto lo stack Gate F v1 + v2 + closure;
- verifica hashata dei PASS A-E nei rispettivi Git object;
- replay del vero artifact Gate B PASS;
- copertura Gate B a 10 minuti: target `80.003271618260`, replay `80.003271618260`, errore assoluto **0**;
- import automatico del completo inventario Gate E, 4 pairable + 5 unpaired;
- verifica di **0** alternative pairable definitive senza assumption;
- presenza della figura 8 nell'inventario senza flag di preferenza;
- rifiuto esplicito dei legacy hardcoded `outputs/route_variants.csv` e relativi percorsi invalidati.

## 7. Problemi corretti durante Gate F

Gate F ha neutralizzato i principali rischi del vecchio progetto:

- raccomandazione hardcoded della doppia circolare prima dell'analisi;
- valori scenario hardcoded in `scripts/10_service_simulation.py`;
- arrivi/partenze bus manuali e rail score arbitrario in `scripts/11_train_coordination.py`;
- scenario comparison hardcoded in `scripts/12_scenario_comparison.py`;
- ranking con pesi arbitrari in `src/multi_criteria.py`;
- conversione errata di stringhe CSV `false` in booleano vero;
- confusione tra flotta scheduled minima e flotta reale di procurement;
- confusione tra path instradabile Gate D e idoneità fisica autobus dimostrata;
- rischio di riutilizzare la copertura Gate B baseline come copertura della figura 8 senza ricalcolo.

## 8. Decisione finale

**GATE F — PASS.**

**Recommendation status:** `NO_DEFINITIVE_RECOMMENDATION_SUPPORTED_BY_CURRENT_EVIDENCE`.

Non viene selezionata `FIG8_COMPACT`, né un'altra topologia, perché i dati validati non identificano un vincitore senza introdurre ulteriori decisioni di progetto.

La figura 8 resta una **ipotesi progettuale seria da portare alla fase di specificazione**, non la conclusione dello studio.

## 9. Cosa servirebbe per una successiva selezione progettuale

Una futura decisione topologica, distinta dalla chiusura di questo gate, richiederebbe di congelare in modo esplicito e comune tra alternative:

1. stop set effettivo per ciascuna topologia;
2. calendario e fascia di servizio;
3. headway per direzione;
4. dwell e recovery;
5. regola di flotta, direction-locked o interlining;
6. eventi bus al nodo e policy di interscambio S8;
7. eventuali field check per le incertezze stradali D ancora `QUANTIFIED` o `UNKNOWN`.

A quel punto i bridge B/C/D/E già sviluppati da Gate F possono generare automaticamente le sei metriche e il Pareto definitivo senza cambiare metodologia.
