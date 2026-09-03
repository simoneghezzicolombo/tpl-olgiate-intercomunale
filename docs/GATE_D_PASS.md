# GATE D — Route integrity: PASS

**Data:** 2026-09-03  
**Reviewer/co-developer:** GPT  
**Branch:** `gate-d-workstream`  
**Baseline originale:** `549198743e7265b333da565ce6990f9241cfd1fd`  
**Commit computazionale validato:** `7c220f7586d0f6e5cccd14a2d518be52eb1c4a55`  
**GitHub Actions:** run `33746091690`, retry live job `100629760313`, static job `100629761488`  
**Verdetto:** **PASS**

## 1. Dipendenze upstream

- Gate A: PASS.
- Gate B: PASS, commit validato `55d726564e13acca55ce563cc911263ac513acb0`.
- Gate C: PASS, commit finale `dcc3e75ae3b4f4ea5170f48e85345b83620c5536`.
- Il GTFS bus Arriva 2025-2026 è usato in Gate D come **FACT ufficiale del periodo di riferimento per geometria e pattern strutturali**, non come rappresentazione del servizio corrente dopo il 2026-06-08. Il servizio corrente resta governato dal contratto metodologico di Gate C.

## 2. Cosa è stato invalidato

La precedente pipeline `scripts/08_candidate_routes.py` conteneva km, runtime, popolazioni, OD capture e giudizi di raccomandazione hard-coded. In particolare il vecchio valore di circa 19,8 km e le etichette “Raccomandata/PARETO-OTTIMALE” non costituiscono evidenza e restano **INVALIDATED**.

Gate D non produce una raccomandazione e non forza la vittoria della figura 8.

## 3. Rete stradale e routing verificati

La pipeline finale costruisce un grafo bus diretto da OSM reale e usa EPSG:32632 per le distanze metriche. Vengono gestiti:

- segmentazione a ogni vertice OSM;
- `oneway=yes`, `oneway=-1`, roundabout;
- precedenza di accesso modale `bus > psv > vehicle/motor_vehicle/access`;
- override `oneway:bus` / `oneway:psv`;
- restrizioni di accesso esplicite e valori non riconosciuti fail-closed;
- turn restrictions OSM via-node mediante Dijkstra stateful;
- snap dei waypoint con soglia fail-closed;
- distinzione tra `DERIVED_OSM_STRUCTURAL` per km e `MODEL_OUTPUT` per pure running time.

Acquisizione live finale OSM:

- bbox: `45.68, 9.31, 45.82, 9.56`;
- SHA256 raw OSM: `834d5caa0bfd6e9f4a1400ef5d2f5083ed0da60ba51c0331f59fcbcb5d4b097c`;
- elementi raw: 229.643;
- highway ways: 24.384;
- nodi grafo: 104.071;
- archi diretti: 199.217.

Turn restrictions:

- relazioni totali: 575;
- restrizioni via-node applicabili ai bus: 566;
- chiavi caricate: 551, di cui 535 corrispondenti a nodi del grafo;
- 8 restrizioni `via-way` non sono approssimate;
- 1 relazione non ha coordinate `via` risolvibili.

L'audit indipendente delle 8 relazioni `via-way` non approssimate non ha trovato una candidata che percorra la sequenza vietata `from → via → to`; il limite resta documentato per future topologie, ma non blocca le candidate Gate D correnti.

## 4. Risultati strutturali delle candidate

Tutti i valori seguenti sono calcolati sullo stesso grafo reale. I tempi sono **MODEL OUTPUT**, non tempi osservati.

| Candidata | km | pure running min |
| --- | ---: | ---: |
| WEST_COMPACT_MONDONICO_CW | 10,253 | 19,65 |
| WEST_COMPACT_MONDONICO_CCW | 9,740 | 18,95 |
| EAST_COMPACT_ARLATE_CW | 13,453 | 26,12 |
| EAST_COMPACT_ARLATE_CCW | 13,298 | 26,01 |
| WEST_RAVELLINO_EXTENSION | 19,052 | 37,40 |
| EAST_CAPRINO_CELANA_EXTENSION | 25,719 | 47,76 |
| WEST_SAN_ZENO_SENSITIVITY | 11,244 | 23,08 |
| EAST_CALCO_SUPERIORE_SENSITIVITY_CW | 15,799 | 32,03 |
| EAST_CALCO_SUPERIORE_SENSITIVITY_CCW | 15,704 | 32,01 |

La combinazione compatta dei due anelli produce una lunghezza media complessiva di **23,372 km** e un pure running time modello medio di **45,37 min**. La differenza direzionale è 0,513 km sull'anello ovest e 0,155 km sull'est.

Le righe `WEST_D184_CORRIDOR_OUT_AND_BACK` e `EAST_D185_CORRIDOR_OUT_AND_BACK` sono **sensitività non-loop costruite come shortest path fra un insieme sparso di anchor GTFS**, non ricostruzioni esatte dei corridoi D184/D185 esistenti. Il vero confronto con il servizio esistente è la calibrazione completa dei pattern ufficiali descritta sotto.

## 5. Calibrazione D184/D185

Sono stati selezionati automaticamente i pattern ufficiali dominanti per direzione, senza hardcodare Ravellino, Caprino o Celana come capolinea. I punti fermata sono vincolati alla shape GTFS ufficiale prima dello snap al grafo stradale.

Sono stati routati 4 pattern reali:

- D184 dir. 0: 22 min GTFS, 10,791 km shape, 10,582 km road route;
- D184 dir. 1: 22 min GTFS, 10,626 km shape, 10,500 km road route;
- D185 dir. 0: 25 min GTFS, 11,151 km shape, 11,477 km road route;
- D185 dir. 1: 25 min GTFS, 11,195 km shape, 10,951 km road route.

Diagnostica complessiva:

- copertura minima road-route entro 35 m dalla shape GTFS: **86,21%**;
- mediana `scheduled/model`: **1,1409**;
- errore assoluto mediano schedule meno model: **2,92 min**;
- nessun fattore di calibrazione viene applicato alle candidate.

La mancata applicazione è intenzionale: l'orario terminale-terminal contiene fermate, dwell e traffico, mentre il valore candidato è pure running time. La calibrazione è quindi diagnostica e non un moltiplicatore trasferibile.

È inoltre conservata la discrepanza interna del GTFS vicino alla stazione: alcune shape risultano coerenti con il punto ferroviario mentre lo stop `300407` è circa 486-528 m discosto. La pipeline non nasconde questo problema e vincola la ricostruzione spaziale alla shape ufficiale.

## 6. DSM e pendenze

Il primo audit slope usava erroneamente il DEM clippato ai 5 comuni anche sulle estensioni esterne, generando falsi spike di centinaia di punti percentuali. Il difetto è stato corretto prima del PASS.

La CI finale scarica su clone pulito il **Copernicus GLO-30 N45/E009 completo** dall'URL ufficiale del manifest e ne verifica lo SHA256 `fb357e36d4f0ebea0c96cec7793c686506bb6aaeb34b92d464b46f05889f824d` prima dell'uso.

Il profilo finale usa filtro median 3x3, interpolazione bilineare e campionamento ogni 60 m. Copertura DEM: **100% per tutte le candidate**. Le pendenze restano `ESTIMATE_FROM_COPERNICUS_DSM` e non sono trasformate in una soglia automatica di fattibilità.

Valori indicativi:

- compact Mondonico: p95 8,21-8,40%, max 11,06-12,59%;
- compact Arlate: p95 7,87-8,56%, max 22,45-22,92%;
- Ravellino: p95 13,03%, max 23,83%;
- Caprino/Celana: p95 11,13%, max 22,84%;
- Calco Superiore: p95 11,28-11,35%, max circa 22,92%.

I picchi DSM possono ancora risentire della natura surface-model e della risoluzione 30 m e richiedono verifica stradale/field check prima di inferenze vehicle-specific.

## 7. Ponte di Brivio

La chiusura temporanea 2026 e la deviazione D185 non entrano nel confronto **strutturale**: `temporary_brivio_closure_used = False`.

La geometria ordinaria del ponte è ricostruita da OSM e shape ufficiale D185, con copertura GTFS del ponte al 100%. OSM fotografa ancora lo stato lavori e `maxweight=7.5`, quindi quel tag temporaneo non viene usato come vincolo strutturale ordinario.

La fonte Prefettura di Lecco/ANAS registrata in `data/gate_d_structural_road_constraints.csv` fornisce **44 t come vincolo strutturale post-lavori**. Questo risolve il dato di progetto strutturale, ma l'idoneità operativa della specifica classe di autobus dovrà essere ricontrollata al completamento dei lavori e prima dell'esercizio.

## 8. Incertezze residue non bloccanti per Gate D

Restano da verificare sul campo o in progettazione vehicle-specific:

- Mondonico: larghezza, swept path e possibilità di incrocio per la classe di autobus scelta;
- San Zeno: turning e gestione delle strade a senso unico, se la sensitivity verrà mantenuta;
- Calco Superiore: swept path e meeting clearance; la navetta storica prova accesso motorizzato, non l'idoneità di ogni autobus da 12 m;
- ponte di Brivio: conferma operativa finale post-lavori per il veicolo scelto;
- eventuali future topologie che attraversino restrizioni OSM `via-way` richiedono un router che le implementi pienamente.

Queste incertezze sono esplicitamente separate dalle metriche e non vengono trasformate in dichiarazioni definitive di “fattibile/non fattibile”.

## 9. Test e riproducibilità

CI finale sul commit computazionale validato:

- `gate-d-unit-and-static`: **SUCCESS**;
- 54/54 test Gate D: **PASS**;
- `git diff --check 5491987..HEAD`: **PASS**;
- guard contro la rigenerazione dei vecchi output hard-coded: **PASS**;
- acquisizione GTFS/checksum: **PASS**;
- acquisizione e checksum Copernicus GLO-30 completo: **PASS**;
- acquisizione OSM estesa: **PASS** al retry;
- structural routing: **PASS**;
- calibrazione D184/D185: **PASS**;
- slope audit: **PASS**;
- artifact finale: `gate-d-structural-evidence`, ID `9891607118`, ZIP SHA256 `6fbc06d74d5ba970bc980e4cde6234245e0753c22386f703ea313c6a4de9206a`.

Il precedente attempt fallito era dovuto esclusivamente a timeout/504 simultanei degli endpoint Overpass; il retry sul medesimo commit e con i medesimi input ha completato l'intera pipeline.

## 10. Criteri di chiusura

1. Gate B PASS: **soddisfatto**.
2. Gate C e ruolo epistemico GTFS risolti: **soddisfatto**.
3. Baseline D184/D185 e candidate serie routate su grafo reale: **soddisfatto**.
4. Estensione OSM sufficiente a tutte le candidate: **soddisfatto**.
5. km/geometrie riproducibili con CRS, direzione, access e disconnessioni testati fail-closed: **soddisfatto**.
6. Incertezze fisiche quantificate e tenute fuori da conclusioni definitive: **soddisfatto**.
7. Runtime confrontato con orari reali e mantenuto `MODEL_OUTPUT`: **soddisfatto**.
8. Nessuna raccomandazione, optimalità o fattibilità derivata da costanti manuali: **soddisfatto**.

## VERDICT

**PASS**

Gate D certifica l'integrità di geometrie, distanze e runtime modello delle alternative testate. Non certifica una soluzione finale e non seleziona la figura 8. **Gate E — service math è sbloccato**.