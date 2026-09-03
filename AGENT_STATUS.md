# AGENT_STATUS

Snapshot strutturata corrente del coordinamento. La cronologia completa resta nella Git history e nella GitHub Issue #1 `Agent Coordination Bus`.

## Stato corrente

**Data:** 2026-09-03
**Fase:** Phase 2 — service-design optimisation
**Branch di integrazione:** `phase2-optimizer-core`

### Gate A–F

A, B, C, D, E e F: **PASS**. Gate F finale: `e84c409ffdbcd0313c93d248496862b5c5356663`.

### Phase 2 — evidenze validate

- **ISTAT 2021 work OD / demand profile:** PASS, SHA `1b9b3d359be48bf58e592e0698702f58e7559e19`; 8.754 resident workers. Work OD resta una sola componente della domanda.
- **Frozen Gate D graph:** PASS, branch `phase2-graph-freeze`, final HEAD `892c6906168fd658a4733a5b31a7fa3e7ed49207`, CI `33770304214`; 104.071 nodi, 199.217 archi diretti, epoca OSM congelata e routing restriction-aware.
- **Candidate-stop universe:** PASS, branch `phase2-stop-universe`, final HEAD `07091300259491c2c9915b41c819af336f89d34a`, CI `33771932566`; 43 cluster fisici esistenti, 180 candidate proposed stops, tutte `PROPOSED_STOP/FIELD_CHECK_PENDING`.
- **S8 interchange:** PASS, branch `phase2-s8-interchange`, final HEAD `88ea13a79bc3a731433dbeeee4985ea11d977580`, CI `33767531076`; 74 eventi S8 reali il 2026-09-03, scoring continuo e topology-neutral.
- **ISTAT 2011 trend audit:** `VALIDATED_WITH_SERIES_BREAK`, branch `phase2-od-2011-audit`, HEAD `329e3b15a3c31c8edc2252babf3e5bb1f6248b8c`; utile come contesto storico, non come serie perfettamente omogenea e non come blocker.
- **Optimizer core:** multi-family topology search, explicit service-policy search, service production, passenger GJT, equity/non-regression, S8 bridge, robust candidate tournament e budget frontier. Nessun `np.random`, nessun legacy hardcoded candidate/current-service output.

### Vincoli metodologici invariati

- zero dati sintetici o inventati;
- niente live Overpass nel normale optimisation loop;
- proposed stops non sono fermate fisicamente certificate finché manca il field check;
- `S8_DIRECT` non è modal share;
- popolazione, OD lavoro, accessibilità, S8, opportunità locali e produzione di servizio restano layer distinti;
- nessun weighted composite score nascosto;
- una candidata finale è `scenario_id + plan_id`, quindi topologia e piano di servizio competono con identità distinta.

## Prossimo checkpoint

**Reduced stop/path matrix → primo catalogo strutturale reale → service-policy search → passenger-utility evaluation → robustness tournament → budget frontier → primary recommendation + runner-up.**

Il budget di riferimento resta quello validato Gate E, 111.419 bus-km/anno; gli envelope inferiori e superiori sono sensitivity di progetto, non un default implicito per la decisione finale.
