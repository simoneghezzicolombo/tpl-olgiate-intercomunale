# Linea 8: una proposta concreta a 16 giri da approvare come base

**Aggiornamento 1 ottobre 2026:** il successivo «ok andiamo avanti, verso la chiusura» conferma questa base di progetto, incluse transizione alle 16:20 e fasi sfalsate. Vedi la [proposta unica consolidata](RT031_LINEA8_PROPOSTA_UNICA_CONSOLIDATA_2026_10_01.md) e il nuovo contratto di conferma. La richiesta di conferma e i flag sottostanti sono conservati come stato storico precedente; non richiedono una seconda approvazione. Nessuna autorizzazione di esercizio, calendario o selezione è inferita.

## Risultato

Sul tracciato Santa Maria–Calco confermato esiste un **testimone verificato a 16 giri completi**, con **27 siti di progetto**, quattro gruppi H30 ferroviari e cap H60 nelle spalle. **112.833,793 km/anno nel confronto a 260 giorni**, cioè **+1.414,793 km / +1,27%** rispetto a 111.419. Nessun diciassettesimo giro, nessuna corsa corta, nessuna seconda linea, nessun nuovo servizio inverso.

La condizione da sottoporre al chiamante è la transizione della morbida nel modello: **10:00–16:20**, invece di 10:00–16:00. Le fasi ferroviarie H30 indicate sotto richiedono anch'esse conferma; non sono una promessa simultanea 07–09 / 17–19 in ogni frazione. La proposta non è selezionata né finanziata. Il numero 260 non è un calendario annuale adottato; km a vuoto e costo completo dell'operatore restano mancanti.

## L'orario: ogni riga è UNA corsa completa

Stesso tracciato e stessi eventi ad ogni giro: **FS → ala est → FS intermedia, permanenza a bordo progettata → ala ovest → FS finale**. Le due colonne non sono due linee o due corse indipendenti. La permanenza a bordo è un requisito di progetto, non ancora un'autorizzazione fisica dell'operatore.

| Giro | Partenza FS verso est | Ripartenza FS verso ovest |
|---:|---|---|
| 1 | 06:05 | 07:00 |
| 2 | 06:35 | 07:30 |
| 3 | 07:05 | 08:00 |
| 4 | 07:35 | 08:30 |
| 5 | 08:05 | 09:00 |
| 6 | 09:00 | 09:55 |
| 7 | 10:00 | 10:50 |
| 8 | 11:55 | 12:50 |
| 9 | 13:40 | 14:35 |
| 10 | 15:40 | 16:35 |
| 11 | 16:40 | 17:35 |
| 12 | 17:10 | 18:05 |
| 13 | 17:40 | 18:35 |
| 14 | 18:10 | 19:05 |
| 15 | 18:40 | 19:35 |
| 16 | 19:40 | 20:30 |

L'ultimo giro rientra a FS alle **21:08 circa** nell'ipotesi nominale. La prima e ultima opportunità ad una fermata dipendono dal suo evento ordinato lungo il giro: non si attribuiscono automaticamente 06:05–21:08 a tutte le fermate.

Non è un orario regolare H70. In morbida alcuni intervalli sono 115/105/120 minuti, e il rientro dalla morbida non è identico nei due punti FS. Le finestre del modello verificano l'attesa del passeggero pronto all'evento pertinente, non soltanto il gap fra partenze FS. **H60 nelle spalle è un cap di readiness**, non la dichiarazione che ogni intervallo debba essere esattamente 60 minuti. I due eventi locali di Olgiate sud e San Zeno restano distinti: il modello non usa una fermata precoce con giro lungo per simulare la garanzia dell'evento rapido verso FS.

## H30 legato a treni effettivi

Registro ferroviario ufficiale del 1 ottobre 2026, verificato su tutte le chiamate GTFS e sul quadro RFI vigente: **74 chiamate**, non un filtro S8 assunto come completo. Per questa data le chiamate risultano tutte S8.

| Flusso del gruppo H30 | Treni supportati dal testimone | Partenze bus FS assegnate |
|---|---|---|
| Est → treni per Milano, mattina | 06:56, 07:26, 07:56, 08:26, 08:56 | 06:05–08:05 ogni 30 min |
| Ovest → treni per Milano, mattina | 07:56, 08:26, 08:56, 09:26, 09:56 | 07:00–09:00 ogni 30 min |
| Da Milano → est, sera | Arrivi 16:32, 17:02, 17:32, 18:02, 18:32 | 16:40–18:40 ogni 30 min, attesa 8 min |
| Da Milano → ovest, sera | Arrivi 17:32, 18:02, 18:32, 19:02, 19:32 | 17:35–19:35 ogni 30 min, attesa 3 min |

Le finestre sono sfalsate. Anche il treno da Milano delle **16:32** ha la ripartenza ovest delle **16:35**, pur fuori dal gruppo di cinque corse serali occidentali. Non sono garantiti H30 clockwise + counterclockwise, né ogni treno di ogni direzione con attesa breve.

Tutti i treni da/per Lecco e Milano sono nel registro dei **296 flussi ala/treno/direzione di interscambio**, con attesa concreta o assenza di una corsa compatibile. Non si usa la tabella dei quattro gruppi per nascondere gli altri servizi. Il trasferimento pedonale di 3 minuti rimane un'ipotesi ereditata, da verificare fisicamente.

## Le coincidenze deboli, senza dichiararle risolte

Sono compatibili con le finestre del confronto **19 dei 22 vecchi obiettivi ferroviari**, con un assegnamento a eventi distinti. I tre non compatibili sono:

- **Ovest → Milano 07:26:** nessun arrivo bus ovest compatibile; primo arrivo ovest nominale a FS circa 07:38.
- **Est → Milano 09:26:** treno raggiungibile con il bus precedente, ma **circa 40 minuti di attesa**; non rientra nel vecchio test di attesa utile. Non è una coincidenza fisicamente assente.
- **Da Milano 17:02 → ovest:** bus successivo 17:35, **33 minuti di attesa**, non i 3–8 del confronto.

Altri esempi che non appartenevano ai 22 target: arrivo da Milano **16:02**, bus est 16:40 (**38 min**), ovest 16:35 (**33 min**). Questi sono limiti della proposta, non una probabilità stimata. Nessuna inferenza di domanda OD o pesi per minimizzare una media favorevole.

L'idea precedente di anticipare tre minuti tutte le cinque partenze est serali valeva come confronto da **17 giri**. Non viene trasferita qui: con 16 giri, anticipare anche l'ultimo evento del gruppo rompe il cap H60 verso l'ultima partenza delle 19:40. Gli orari di questa scheda sono quelli effettivamente verificati, non una combinazione di miglioramenti incompatibili.

## Soste ed esercizio ancora condizionati

- Sosta intermedia a FS nominale: **9,22–14,22 minuti**, comprensiva della permanenza fra arrivo e ripartenza, non un recupero terminale applicato due volte.
- Nei nove casi di marcia/dwell ereditati: **2,22–27,36 minuti**. Una marcia più rapida può significare maggiore sosta a FS; il nominale non è il massimo garantito.
- Durata nominale completa: **88,30–93,30 minuti**, secondo la sosta intermedia.
- Fabbisogno condizionale: **3 mezzi in 2 casi, 4 in 25 dei 27 casi** con recupero. Non è disponibilità o autorizzazione di una flotta; turni, deadhead, costo, manovre e continuità devono essere confermati dall'operatore.
- Accosto Calco e altre nuove fermate, accessibilità fisica, legalità stradale a storia completa e manovre non diventano approvati tramite il solver.
- I viaggi lunghi ereditati dal percorso non sono accorciati modificando l'orario. Lo scambio Santa Maria–Calco non è un rimedio universale ai tempi di viaggio.

I 9/27 casi sono stress ingegneristici, **non prove osservate**, non una probabilità di coincidenza mancata e non una scelta di `uncertainty_band_min`.

## Audit del contratto e stato di chiusura

La scheda JSON include la mappa di readiness di ogni input: fonte certificata, semantica, autorità e limiti. Il contratto storico a 16 giri aveva 29 siti: i 27 siti attuali derivano dalle successive scelte esplicite del chiamante, non da una rinomina del vecchio artefatto. Il vecchio finalizer non viene alimentato con GJT pesato o probabilità inventati.

Nel dominio attuale (stesso ordine est→ovest, griglia dichiarata, 16 giri, quattro gruppi ferroviari, scenari ereditati), il cap H60 con morbida terminante esattamente alle 16:00 ha esito negativo sia sulla griglia 5 minuti sia nel test 1 minuto con intervalli intermedi estesi. Il test 1 minuto/intervallo massimo 55 è invece terminato senza testimone al limite di tempo: **non** viene contato come prova di impossibilità. Nessun esito costituisce impossibilità globale su ogni orario o ogni contratto.

Nella griglia 5 minuti e con intervallo intermedio massimo 55, la finestra fino alle 16:15 ha esito negativo; **16:20 ha un testimone**. È una soglia del confronto dichiarato, non un optimum temporale globale. Non vengono allentati H30, numero di giri, territorio o calendario per farlo apparire positivo.

**Decisione richiesta al chiamante:** accettare o meno questa base con la transizione fino alle 16:20, le fasi H30 sfalsate e le coincidenze deboli riportate. Non è necessario riaprire la geometria per prendere questa decisione. Se accettata, resta una base di progetto da portare alla verifica fisica/operativa, non un servizio già approvato o una promessa che soddisfi tutto al 100%.

## Artefatti

- [Proposta unica machine-readable, ledger di tutti i giri, tutti i flussi e readiness degli input](../outputs/phase2/rt031_line8_local_shortcuts_v3/current_16_trip_proposal_for_caller_review.json).
- [Testimone a 16 giri della scheda](../outputs/phase2/rt031_line8_local_shortcuts_v3/current_16_trip_timetable_step5_H60_mid55_PM8_AMinherited_flexible_real_trains_core980_eastfree.json).
- [Tracciato con Calco adottata](../outputs/phase2/rt031_line8_local_shortcuts_v3/calco_centre_adopted_design.geojson).
- [Quadro ferroviario corrente e limiti delle fonti](RT031_LINEA8_QUADRO_FERROVIARIO_2026_10_01.md).

`detailed_timetable_adopted=false`, `transition_extension_adopted=false`, `network_selected=false`, `primary_selection_authorised=false`, `runner_up_selection_authorised=false`, `decision_budget_km=null`, `uncertainty_band_min=null`.
