# Linea 8 - calendario e risorse, 1 ottobre 2026

**Aggiornamento del 2 ottobre:** questa nota conserva la prova primaria PdB e i confronti 260/303. La successiva [base feriale dichiarata per il 2027](RT031_LINEA8_CALENDARIO_FERIALE_2027_V3.md) comprende 254 giornate dopo i festivi nazionali e 110.229,936 km commerciali; sabato ed eccezioni locali restano da chiudere. I confronti seguenti non sono il nuovo calendario.

**Il riferimento di 111.419 km è ricostruibile dalla fonte primaria. Il calendario effettivo annuo resta da dichiarare.** Nel Programma di Bacino D184 e D185 hanno 303 giorni con sei coppie/giorno di progetto nelle categorie feriali e sabato. Applicare il giorno di progetto confermato della Linea 8 a quel numero di giorni comporterebbe **131.494,766 km commerciali/anno, +18,02%** sul riferimento. Il confronto a 260 giorni rimane **112.833,793 km, +1,27%**: il numero di giorni cambia materialmente il risultato.

Fonte: Programma di Bacino rev. 7.2, **Scheda ambito: Meratese**, fogli D184 e D185, posizioni PDF **7 e 8** (indici da zero **6 e 7**), verificati anche visivamente. :codex-file-citation{path="D:/tpl-olgiate-intercomunale/data/raw/pdb/PdB_Allegato3.4_Meratese.pdf" purpose="source"} Il [registro dell'evidenza](../config/rt031_pdb_calendar_reference_evidence_20261001_v3.json) riporta l'URL ufficiale, le celle trascritte, SHA256 `e0657cb4e8a078ddf99f28e1ebbde4a67ee36bb9b7a92fcd488e2539a948079a` e le formule.

## Che cosa rappresentano i 111.419 km

| Scheda PdB | Produzione di punta, bus km/anno | Produzione di morbida, bus km/anno | Produzione totale pubblicata, bus km/anno |
|---|---:|---:|---:|
| D184, Olgiate Molgora - Ravellino | 15.264 | 37.296 | 52.560 |
| D185, Olgiate Molgora - Caprino B. | 19.144 | 39.714 | 58.859 |
| Somma | 34.408 | 77.010 | **111.419** |

Si tratta della somma delle produzioni totali pubblicate delle due linee, con punte e morbida e con i rispettivi ambiti di percorso. Il documento di pianificazione non dimostra da solo i km oggi contrattualizzati o realmente effettuati, la loro disponibilità per la Linea 8 o il costo completo dell'operatore.

La fonte presenta due scarti di 1 km tra valori esposti: D185 punta + morbida dà 58.858, mentre il totale pubblicato è 58.859; le celle per tipo di giorno della D184 sommano a 37.297, mentre la morbida pubblicata è 37.296. Conserviamo il riferimento **52.560 + 58.859 = 111.419**, registrando gli scarti senza ricostruire valori non arrotondati assenti.

## Giorni riportati nelle due schede PdB

| Etichetta esatta della fonte | Giorni | Coppie/giorno di progetto, D184 e D185 |
|---|---:|---:|
| Feriale invernale | 187 | 6 |
| Sabato invernale | 39 | 6 |
| Festivo invernale | 46 | 0 |
| Feriale estivo no agosto | 45 | 6 |
| Sabato estivo no agosto | 9 | 6 |
| Feriale agosto | 19 | 6 |
| Sabato agosto | 4 | 6 |
| Festivo estivo | 14 | 0 |

I giorni con coppie di progetto sono **187 + 39 + 45 + 9 + 19 + 4 = 303**: 251 nelle categorie feriali e 52 nelle categorie sabato. Le due categorie festive comprendono 60 giorni a zero coppie di progetto. Tutte le celle dei giorni sommano a 363; la tabella non fornisce le date mancanti per costruire un calendario civile completo.

**303 è un conteggio dei tipi di giorno della pianificazione PdB.** Non certifica il calendario datato del servizio corrente, i giorni realmente eserciti nel 2026 o un calendario adottato per la Linea 8. Le sei coppie dei fogli storici non diventano automaticamente sedici giri della proposta.

Il GTFS Arriva ufficiale congelato nel progetto dichiara validità **1 gennaio-8 giugno 2026**. `calendar.txt` contiene solo l'intestazione; `calendar_dates.txt` contiene le attivazioni datate. Per gli undici identificativi di servizio associati a D184/D185 le date vanno dal 2 gennaio all'8 giugno. È una fonte utile per il periodo pubblicato, priva della copertura degli altri mesi necessaria a certificare un anno intero. Anche la [ricostruzione degli orari correnti](PHASE2_CURRENT_SERVICE_STOP_TIMETABLE.md) limita esplicitamente l'attivazione alla data di riferimento e non deduce giorni annui.

## Produzione della precisa proposta confermata

Il [dossier attuale](../outputs/phase2/rt031_line8_local_shortcuts_v3/caller_confirmed_design_handoff_20261001.json) registra 27,123507880067442 km per giro e 16 giri completi: **433,9761260810791 km commerciali per giorno identico**.

| Scenario aritmetico, senza adottare il calendario | Giorni identici | Km commerciali/anno | Scarto su 111.419 km |
|---|---:|---:|---:|
| Confronto ereditato del progetto | 260 | 112.833,793 | +1.414,793 / +1,27% |
| Sensibilità con il conteggio ordinario di progetto PdB | 303 | 131.494,766 | +20.075,766 / +18,02% |

Formula: **433,9761260810791 × giorni effettivamente adottati**. Le 43 giornate di differenza valgono 18.660,973 km commerciali se ciascuna ha gli stessi sedici giri. Con giornate diverse occorre sommare separatamente `numero giorni × giri del giorno × km/giro` per ogni tipo di servizio. Deposito, riposizionamenti e altri km non commerciali vanno aggiunti a parte.

La [conferma progettuale](../config/rt031_design_timetable_confirmation_20261001_v3.json) mantiene `annual_calendar_adopted=false`. I 260 giorni derivano dal confronto idealizzato cinque giorni per 52 settimane: **non identificano quali date, sabati, domeniche o festività siano serviti**. Finché le date non vengono dichiarate, non si può quantificare una perdita di servizio nel weekend o nei festivi né sottrarre ulteriori weekend dal confronto.

## Dati necessari per chiudere il piano annuo

1. Anno di esercizio e calendario datato: periodi scolastici/non scolastici, sabati, domeniche, festività ed eccezioni, con giri e percorsi per ciascun tipo di giorno.
2. Conferma di Agenzia e operatore dei km commerciali D184/D185 contrattualizzati ed effettuati e della quota effettivamente riorganizzabile, specificando punte scolastiche e code esterne al bacino della proposta.
3. Deposito, km a vuoto, piano dei mezzi e del personale, costo completo e copertura finanziaria.

Questa nota completa l'evidenza di pianificazione e rende calcolabili i confronti. La scelta del calendario e la conferma delle risorse richiedono i dati sopra; restano invariati gli atti di conferma della proposta.
