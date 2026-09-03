# Gate C audit findings

**Workstream:** `gate-c-workstream`
**Original baseline:** `549198743e7265b333da565ce6990f9241cfd1fd`
**Verdict corrente:** `PASS`
**Chiusura autorevole:** `docs/GATE_C_PASS.md`

## Stato upstream

- Gate A: `PASS`.
- Gate B: `PASS`; computational commit validato `55d726564e13acca55ce563cc911263ac513acb0`.
- La dipendenza spaziale di Gate C non è più bloccante.
- `AGENT_PROTOCOL.md` non era presente nella baseline originaria; il protocollo operativo presente era `COLLABORATION_PROTOCOL.md`.

## Finding C-01 — pseudo-GTFS ricostruito usato come sorgente

**Severità:** critica
**Stato:** `CORRECTED / INVALIDATED / QUARANTINED`

La pipeline legacy `scripts/02_parse_gtfs.py` costruiva D184/D185, fermate, orari e una variante emergenziale manualmente. I test legacy potevano quindi risultare verdi contro un dataset internamente coerente ma non istituzionale.

`network_structural` e `network_2026_emergency` sono `RECONSTRUCTED` + `INVALIDATED_AS_EVIDENCE`. `scripts/02_parse_gtfs.py` è ora fail-closed.

## Finding C-02 — calendario bus effettivo in calendar_dates

**Severità:** alta
**Stato:** `CORRECTED`

Nel GTFS Arriva ufficiale `calendar.txt` è header-only. Le attivazioni reali sono in `calendar_dates.txt`. Il parser Gate C applica entrambe le tabelle secondo GTFS e non interpreta il testo del `service_id`.

Su 2026-05-06 risultano:

- D184: 15 trip attivi, 8 pattern;
- D185: 19 trip attivi, 9 pattern;
- D150: 33 trip attivi, 28 pattern;
- D170: 96 trip attivi, 49 pattern.

## Finding C-03 — GTFS bus conservato scaduto a settembre 2026

**Severità:** alta
**Stato:** `RESOLVED_WITH_PRIMARY_CURRENT_TIMETABLES`

Il feed Arriva conservato termina l'8 giugno 2026 e non viene estrapolato. Per il 3 settembre 2026 Gate C usa invece i timetable ufficiali Lecco Trasporti / Arriva validi dal 9 giugno al 13 settembre 2026.

Il parser live usa coordinate PDF per associare day-code e note alle singole colonne. I risultati sono classificati `RECONSTRUCTED_FROM_OFFICIAL_PRIMARY_TIMETABLE`, non GTFS.

Dopo l'applicazione delle note A/B/D/V al 3 settembre 2026:

- D184: 12 colonne attive;
- D185: 13 colonne attive;
- D150: 30 colonne attive;
- D170: 49 colonne attive.

## Finding C-04 — deviazione D185 reale diversa dalla ricostruzione legacy

**Severità:** critica
**Stato:** `RESOLVED / PRIMARY-SOURCE FACT`

Le fonti ufficiali attestano la deviazione D185 dovuta ai lavori al ponte di Brivio. Il timetable corrente indica transito via Ponte Cantù e sospensione di `CISANO Sosta`.

La precedente ricostruzione con aumento manuale `+25 min` resta invalidata. La deviazione temporanea non viene trasformata in servizio ordinario.

Fonti primarie registrate:

- `https://tplcomoleccovarese.it/atpcolc/po/mostra_news.php?area=H&id=1137`
- `https://www.provincia.lecco.it/2026/04/23/chiusura-ponte-di-brivio-le-modifiche-alle-linee-bus/`
- `https://www.leccotrasporti.it/avvisi/linea-d185-chiusura-ponte-di-brivio/`
- `https://www.leccotrasporti.it/percorsi/estivo/linea-d185.pdf`

## Finding C-05 — denominazione ufficiale della stazione S8

**Severità:** media
**Stato:** `CORRECTED / REGRESSION-TESTED`

La stazione GTFS è `S01514`, `Olgiate-Calco-Brivio`. Una prima implementazione cercava anche il token `Molgora`, producendo zero match. Il resolver e il test sono stati corretti.

## Finding C-06 — snapshot Trenord senza calendario standard

**Severità:** alta
**Stato:** `RESOLVED_WITH_CURRENT_OFFICIAL_GTFS`

Lo snapshot ferroviario storico nel repository manca di `calendar.txt` e `calendar_dates.txt`, quindi non viene usato per attestare il servizio corrente.

Gate C scarica ora il GTFS ufficiale Regione Lombardia / Trenord. Il feed auditato copre 2026-07-26 → 2026-12-12. Il 3 settembre 2026 risultano 74 trip S8 attivi e 74 eventi S8 a `S01514`.

## Finding C-07 — S8 e current-service hard-coded

**Severità:** alta
**Stato:** `QUARANTINED`

`src/timetable_engine.py::TRENI_S8_VIGENTI` resta `INVALIDATED_AS_EVIDENCE`. I precedenti script che lo consumavano o incorporavano metriche transit manuali non possono più produrre output:

- `scripts/02_parse_gtfs.py` — fail-closed;
- `scripts/05_current_service.py` — fail-closed;
- `scripts/11_train_coordination.py` — fail-closed.

`tests/test_gate_c_quarantine.py` verifica questo comportamento.

## Finding C-08 — parser PDF, falsi positivi e coordinate

**Severità:** media
**Stato:** `CORRECTED / TESTED`

Durante il Gate C sono stati scoperti e corretti tre failure reali prima del PASS:

1. ricerca troppo generica della parola `SOLO`, che poteva confondere la nota B con il testo del contact center;
2. uso di `visitor_text` in modalità layout `pypdf`, che non restituiva le coordinate necessarie;
3. dipendenza dal glifo grafico `D185`, non sempre esposto come testo dal PDF.

La versione finale usa `pdfplumber.extract_words()` per le coordinate, verifica la fonte tramite URL ufficiale route-specific, verifica contenuto/direzioni e periodo di validità separatamente e applica le note per posizione orizzontale.

## Chiusura

Tutti i blocker precedenti sono risolti:

- Gate B è PASS;
- D150/D170 correnti sono verificati;
- il calendario S8 corrente è risolto da GTFS ufficiale;
- il gap temporale del GTFS bus è coperto da timetable primari, senza creare GTFS sintetico;
- i consumer legacy hard-coded sono quarantinati;
- CI source-grounded, test avversariali, anti-synthetic guardrails e `git diff --check` sono verdi.

**VERDICT: PASS.**
