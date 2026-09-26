# Linea 8 — spostare corse dalla parte centrale alla sera

## Risultato concreto, non ancora adottato

Si può portare l'ultima partenza **da FS dalle 18:40 alle 20:40**, senza cambiare percorsi, siti serviti o chilometri annui: si spostano alla sera due corse per ala e si ridistribuiscono le corse intermedie. **Il prezzo è H90 nella parte centrale della giornata, anziché H60.** Non è una soluzione che rispetta contemporaneamente tutte le richieste precedenti.

Le cinque corse mattutine e le cinque corse pomeridiane ogni trenta minuti restano identiche, così come le prime partenze e i treni mattutini di riferimento. Questo mantiene le banche di corse H30 esistenti: **non certifica una finestra comune di due ore H30 a tutte le fermate**, né risolve i limiti operativi già registrati.

Conserviamo separatamente i due percorsi già studiati. Non usiamo il testimone economico che perdeva molta copertura a Brivio e Calco.

## Confronto riproducibile

Chilometri di servizio annui, **260 giorni**, senza deposito/riposizionamenti. Riferimento invariato: 111.419 km; nessun nuovo tetto approvato.

| Calendario | Corse al giorno, due ali | Ultima partenza FS | Intervallo massimo intermedio | Percorso con controflusso lento | Percorso con collegamenti locali brevi nei due versi |
|---|---:|---:|---:|---:|---:|
| Riferimento precedente | 36 | 18:40 | 60 min | 115.800 km | 130.567 km |
| Una corsa per ala spostata, redistribuzione | 36 | 19:40 | 90 min | 115.800 km | 130.567 km |
| **Due corse per ala spostate, redistribuzione** | **36** | **20:40** | **90 min** | **115.800 km** | **130.567 km** |
| Due corse per ala tolte senza redistribuire | 36 | 20:40 | 120 min | 115.800 km | 130.567 km |
| Una spostata e una aggiunta per ala | 38 | 20:40 | 90 min, meno intervalli lunghi | 122.203 km | 137.764 km |
| Due aggiunte per ala, nessuna riduzione intermedia | 40 | 20:40 | 60 min | 128.605 km | 144.960 km |

La redistribuzione a 90 minuti riduce il massimo buco rispetto alla semplice cancellazione, ma non è dichiarata migliore per ogni passeggero: cambiano gli orari puntuali. Nessun punteggio pesato, selezione automatica o affermazione che a mezzogiorno non ci sia domanda. I dati Google non autorizzano tale conclusione.

**Il percorso da 115.800 km conserva viaggi di circa 31–32 minuti nel controflusso locale.** Quello da 130.567 km li riduce nei due versi per Olgiate sud e San Zeno, con gli altri compromessi già documentati. Spostare corse non accorcia quei viaggi. Il primo resta +3,93% e il secondo +17,19% rispetto al riferimento, prima degli extra.

## Orario esplicito: due corse per ala spostate, senza km aggiuntivi

Partenze FS, non tempi di passaggio in ogni località:

| Blocco | Ala ovest | Ala est |
|---|---|---|
| Mattino, percorso precedente | 06:34, 07:04, 07:34, 08:04, 08:34 | 06:27, 06:57, 07:27, 07:57, 08:27 |
| Mattino, percorso locale corretto nei due versi | 06:33, 07:03, 07:33, 08:03, 08:33 | Come sopra |
| Prima corsa con orientamento del resto del giorno, entrambi i percorsi | 08:55 | 08:48 |
| Parte centrale, entrambi | 09:40, **11:10, 12:40, 14:10**, 15:40 | Uguale |
| Banca pomeridiana invariata, entrambi | 16:40, 17:10, 17:40, 18:10, 18:40 | Uguale |
| Prolungamento serale, entrambi | **19:40, 20:40** | Uguale |

Fra 09:40 e 15:40 gli intervalli sono tutti di 90 minuti; dopo 18:40 sono di 60. Sono 18 corse per ala: 5 mattutine più 13 nell'altro orientamento, esattamente come prima. Ridistribuire implica anche spostare alcune partenze residue, non solo cancellare due orari.

L'ultimo ritorno a FS del caso nominale (+10% marcia, 30 secondi per evento di fermata) è circa **21:16** sul percorso precedente e **21:21** su quello corretto. Nei casi più lenti della griglia arriva circa alle 21:24 / 21:30 (arrotondamento per eccesso al minuto). Non sono orari di rientro in deposito. Le 20:40 sono l'ultima partenza, non la fine di ogni corsa.

## Cosa resta invariato e cosa non possiamo promettere

- **28 identità di sito incluso FS**, tutti i tracciati e tutte le occorrenze ordinate invariati dentro ciascuna famiglia. Nessun taglio di frazione. È una conservazione geografica, non della copertura temporale né della domanda servita; le fermate ipotetiche non diventano autorizzate.
- Tutte le 27 combinazioni marcia/sosta/recupero mantengono i nuovi treni mattutini 07:26–09:26. Il vecchio primo treno 06:56 non è ripristinato.
- Nel solo giorno ferroviario congelato **3 settembre 2026**, gli arrivi da Milano 19:32 e 20:32 precedono i bus 19:40 e 20:40: otto minuti, di cui tre assunti per il trasferimento, cinque residui. **Non è una verifica dell'orario ferroviario vigente o una probabilità di coincidenza.**
- Mezzi condizionali: percorso precedente quattro nel nominale e fino a cinque nello stress; percorso corretto quattro/cinque nel nominale secondo il recupero e fino a sei nello stress. Gli spostamenti non riducono questi massimi. Restano da verificare legalità stradale completa, fermate, mezzi, turni e deposito.
- Stessi km non significa stessi costi: allungare la giornata può modificare turni e ore pagate. Nessuna garanzia finanziaria dedotta dai km.

## Tracciati invariati, evidenze e riproduzione

![Contesto del percorso precedente](../outputs/phase2/rt031_line8_local_shortcuts_v3/full_retention_context.png)

![Correzione dei viaggi locali nei due versi](../outputs/phase2/rt031_line8_local_shortcuts_v3/local_counterflow.png)

- [Confronto macchina, 12 casi e 324 scenari condizionali](../outputs/phase2/rt031_line8_local_shortcuts_v3/evening_reallocation.json): inventario prima/dopo, gap, eventi distinti, blocchi e hash delle fonti.
- [Generatore](../scripts/phase2_compare_rt031_line8_evening_reallocation_v3.py), [test](../tests/test_phase2_rt031_line8_evening_reallocation_v3.py).
- Fonti congelate: `independent_wings.json`, `peak_direction_retimed.json`, `local_counterflow.json`, `s8_events.csv` e `s8_interchange_contract.json`. Hash normalizzati per newline fissati nel generatore: una variazione blocca il confronto.

```powershell
$env:PYTHONPATH='.;src'
python -m scripts.phase2_compare_rt031_line8_evening_reallocation_v3
python -m unittest discover -s tests -p test_phase2_rt031_line8_evening_reallocation_v3.py
```

La scelta ora è esplicita: accettare H90 intermedio per estendere la sera a parità di km, oppure conservare H60 aggiungendo corse. La richiesta dell'utente autorizza questo confronto, **non è registrata come adozione di H90**. Nessuna famiglia viene selezionata; `network_selected`, `primary_selection_authorised`, `runner_up_selection_authorised` restano `false`; budget decisionale e banda di incertezza restano `null`.
