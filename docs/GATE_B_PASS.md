# Gate B — Real spatial integrity: PASS

**Verdetto:** PASS  
**Data:** 2026-09-03  
**Branch:** `antigravity-real-data`  
**Validated computational commit:** `55d726564e13acca55ce563cc911263ac513acb0`  
**GitHub Actions run:** `33700372497`  
**Job:** `100478156571`  
**Audit artifact:** `9873385893` (`gate-b-spatial-audit-55d726564e13acca55ce563cc911263ac513acb0`)  
**Artifact SHA256:** `aca8889c8f1a4148c252c3530a56e8c68fa3f33c8e6ddf81a9ed743c51c1cfd1`

## Evidenza di validazione

Gate B è stato validato su runner Ubuntu pulito partendo da una ricostruzione completa degli input di Gate A. Il workflow non utilizza gli output sintetici legacy.

Il run `33700372497` ha completato con successo:

- rebuild completo degli input Gate A da clean checkout: PASS;
- pipeline spaziale reale Gate B: PASS;
- suite `tests/test_gate_b_spatial.py`: **10/10 PASS**;
- red-team persistente `scripts/audit_02_redteam.py`: PASS;
- generazione e upload dell'artifact di audit: PASS.

## Popolazione e calibrazione

Il precedente doppio conteggio POSAS è stato identificato durante il red-team e corretto. La riga `Età=999` è il totale ufficiale comunale e non viene più sommata alle righe di dettaglio 0–100. La pipeline verifica inoltre che il dettaglio per età riconcili con il totale aggregato.

Totale core POSAS 2025: **22.914 abitanti**.

| Comune | POSAS 2025 | WorldPop 2020 raw | Fattore calibrazione |
|---|---:|---:|---:|
| Brivio | 4.357 | 5.126,07 | 0,8500 |
| Calco | 5.460 | 6.172,18 | 0,8846 |
| Olgiate Molgora | 6.332 | 6.414,41 | 0,9872 |
| Santa Maria Hoè | 2.109 | 2.354,13 | 0,8959 |
| La Valletta Brianza | 4.656 | 5.060,97 | 0,9200 |

`worldpop_2020_raw` resta `FACT`; `pop_calibrated_2025` è distinto e classificato `ESTIMATE`.

## Grafo pedonale e DSM

Il grafo deriva da OSM reale e contiene circa 28.758 nodi. La giant component comprende il **94,04%** dei nodi.

Il primo campionamento DSM nearest-pixel produceva falsi gradini altimetrici su segmenti OSM corti ed è stato invalidato. Il metodo approvato utilizza:

1. Copernicus GLO-30 trattato esplicitamente come DSM, non DTM;
2. filtro mediano locale 3×3;
3. interpolazione bilineare continua;
4. tempi direzionali con funzione di Tobler.

Diagnostica finale su 27.742 archi della giant component:

- mediana |slope|: **5,01%**;
- p90: **19,37%**;
- p95: **25,32%**;
- p99: **38,46%**;
- archi |slope| >30%: **801, pari al 2,89%**;
- archi |slope| >50%: **68, pari allo 0,25%**.

La coda ripida è concentrata soprattutto su categorie OSM coerenti con forti pendenze: tra gli archi >30%, 435 sono `path`, 102 `track` e 35 `steps`. I test includono guardrail per impedire il ritorno dell'artefatto raster: p95 <30%, p99 <50% e quota di archi >30% <5%.

## Fermate GTFS

La fonte istituzionale primaria resta `stops.txt` del GTFS ufficiale Agenzia TPL Como-Lecco-Varese. OSM non definisce il set delle fermate.

- fermate selezionate nel contesto core: 66;
- fermate agganciate al grafo entro 250 m: 62;
- spot-check indipendenti: **5/5 PASS**;
- errori di coordinate sui cinque spot-check: 0 m rispetto ai valori GTFS attesi.

Le quattro fermate non agganciate sono punti di bordo/esterni associati al contesto Brivio (`Monte Marenzo` / `Calolziocorte`) e vengono escluse dal routing perché superano esplicitamente la soglia di snap. Non vengono forzate sul grafo.

## Accessibilità spaziale

La popolazione calibrata collegabile al grafo entro il connettore massimo di 300 m è **100%**. Le distanze cella→grafo hanno mediana 32,1 m, p95 124,5 m, p99 178,4 m e massimo 272,8 m.

Copertura verso una localizzazione di fermata GTFS ufficiale:

| Soglia pedonale | Copertura core |
|---|---:|
| ≤ 5 min | **48,69%** |
| ≤ 8 min | **72,12%** |
| ≤ 10 min | **80,00%** |
| ≤ 12 min | **85,90%** |

La sensitivity analysis mostra che il connettore massimo di 300 m non gonfia materialmente i risultati. Con un cap molto più restrittivo di 100 m, la copertura a 10 minuti è 79,57% contro 80,00% nel modello approvato.

Il controfattuale senza pendenza produce coperture 49,04%, 72,98%, 81,82% e 87,16%. L'effetto della pendenza rispetto al flat è quindi rispettivamente −0,35, −0,86, −1,82 e −1,26 punti percentuali: la correzione altimetrica è rilevante ma non domina il modello.

## Limiti espliciti

Il PASS di Gate B certifica l'integrità della modellazione **spaziale**. Non certifica che ogni fermata sia servita in ogni fascia oraria, né frequenze, calendari, coincidenze ferroviarie o configurazioni temporanee di linea. Questi elementi appartengono a Gate C.

La popolazione è rappresentata dal centro delle celle WorldPop e la calibrazione comunale 2025 mantiene la distribuzione intracomunale del raster 2020. Il Copernicus GLO-30 resta un DSM e non viene presentato come verità bare-earth.

## Conseguenza

**Gate B è PASS. Gate C — transit integrity è sbloccato.**

I risultati di Gate B possono essere usati come base spaziale downstream, mantenendo i rispettivi status epistemici. Nessuna configurazione di rete, frequenza o raccomandazione finale è ancora approvata.