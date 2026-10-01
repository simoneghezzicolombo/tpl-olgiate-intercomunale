# Linea 8: compromesso Santa Maria–Calco e strade corrette

## Scelte ricevute dal chiamante

Il 1 ottobre 2026 l'utente ha accettato i metri aggiuntivi per evitare Via Mirasole e Via Cartiglio/Tessitura, mantenendo Piazza San Zenone. Ha autorizzato lo scambio Santa Maria–Calco come sviluppo della proposta. Il servizio H30 nei due sensi resta da ricordare, ma la relativa azione è esplicitamente rinviata. Non cambiano numero di corse, calendario o budget dichiarato.

## Compromesso territoriale calcolato

Si conserva **S. Maria Hoè** (`FROZEN::300782`) e si omette **Via Como/Alpino** (`ASF::SANTA_MARIA_HOE_VIA_COMO`) per aggiungere una sola fermata a Calco. L'area supportata dal confronto è **Via Italia–Via San Rocco**. Non sono dieci nuove fermate: sono dieci posizioni alternative per UNA fermata, la cui palina, lato, sicurezza e accessibilità devono essere verificati.

Sono stati valutati tutti i **93 vertici del grafo stradale** lungo Via Roma, Via San Rocco, Via Italia e Via San Vigilio, effettivamente attraversati dal percorso est, entro il confine comunale ufficiale di Calco e non già rappresentati da un evento servito. È un dominio esplicito di progetto, non un optimum su ogni possibile nuova fermata. Dieci punti non sono dominati sulle quindici dimensioni comunali di copertura pedonale 5/8/10 minuti; nessun peso o soglia di perdita accettabile è stato introdotto. Il punto esatto non è selezionato.

La copertura dell'attuale esempio da 27 siti è stata riprodotta esattamente prima dello scambio. Poi è stata ricalcolata congiuntamente l'omissione e ciascuna aggiunta, registrando anche le perdite lorde di popolazione precedentemente coperta.

| Comune | Effetto a 5 minuti | Effetto a 8 minuti | Effetto a 10 minuti |
|---|---:|---:|---:|
| Calco | +11,17–14,15 punti | +14,11–15,59 punti | +8,92–12,44 punti |
| Santa Maria Hoè | −2,84 punti | 0 | 0 |
| La Valletta Brianza | −0,21 punti | 0 | 0 |

I valori di Calco sono intervalli tra le dieci alternative: non una singola fermata che ottiene simultaneamente tutti i massimi. Per Brivio e Olgiate si consultino tutte le metriche nel registro; nessuna equivalenza territoriale è dedotta dalla parità del numero di fermate. La copertura a 5 minuti di Calco passa da **26,95% a 38,12–41,10%**. Sono coperture potenziali delle unità di popolazione sul substrato pedonale congelato, non domanda OD, passeggeri o accessibilità fisica certificata.

## Distanze e stato dell'orario

- Percorso originario dell'esempio: circa **27,223 km**.
- Bypass Mirasole + Cartiglio/Tessitura, mantenendo la piazza: **27,597 km**, +374,206 m.
- Dopo l'omissione Alpino: **27,124 km**, circa 99,093 m meno dell'originario.
- Ogni posizione Calco è già sul percorso: aggiungerla non introduce distanza di marcia. Introduce invece un evento di fermata e la sua ipotesi di dwell, da contabilizzare nel nuovo orario.

L'orario a 17 giri precedente NON viene trasferito automaticamente. Nessuna nuova produzione annua o fattibilità di 16/17 giri viene dichiarata qui. Le limitazioni stradali e le occorrenze esplicite sono quelle del modello diretto congelato; non sono un'approvazione dell'operatore, né legalità a storia completa. Altre strade problematiche possono ancora richiedere sopralluogo.

Con una sola aggiunta si torna a **27 siti di progetto inclusa FS**; non è il numero di paline autorizzate. Il percorso prima della scelta contiene 26 siti ed è accompagnato dalle alternative della nuova fermata. Gli eventi dei punti mantenuti sono aggiornati al percorso ricostruito nel GeoJSON.

## Passo ferroviario successivo

Il chiamante richiede **tutti i treni che fermano a Olgiate**, non soltanto il sottoinsieme S8 congelato del 3 settembre 2026. L'audit dovrà enumerare servizio, data di validità, arrivo, partenza, direzione/destinazione e provenienza; verificare bus→treno e treno→bus per entrambe le ali. Nessun treno semplicemente transitante senza fermata viene venduto come coincidenza.

Il precedente registro di 74 eventi S8, 148 righe ala/treno, non certifica questa completezza né l'orario odierno. Non vengono scelte automaticamente le priorità ferroviarie o un nuovo limite di attesa. L'incertezza della posizione Calco deve rimanere esplicita nelle realizzazioni degli eventi; la continuità del veicolo non basta a garantire quella passeggeri.

## Artefatti riproducibili

- [Confronto con tutte le 93 posizioni, perdite lorde e frontiera](../outputs/phase2/rt031_line8_local_shortcuts_v3/santa_calco_exchange.json).
- [Tracciato corretto e posizioni sulla mappa](../outputs/phase2/rt031_line8_local_shortcuts_v3/santa_calco_exchange.geojson).
- [Requisiti aggiornati del chiamante](../config/rt031_caller_street_and_rail_revision_v3.json).

`new_calco_site_selected=false`, `network_selected=false`, `primary_selection_authorised=false`, `runner_up_selection_authorised=false`, `decision_budget_km=null`, `uncertainty_band_min=null`.
