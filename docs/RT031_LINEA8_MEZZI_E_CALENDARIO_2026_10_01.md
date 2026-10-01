# Linea 8 — mezzi e calendario della proposta confermata

Sono stati assegnati i 16 giri completi a mezzi di modello per tutti i 27 scenari ereditati. Il minimo condizionale è 4 nel nominale e nel caso con sosta/recupero maggiori: 25 casi richiedono 4 mezzi, due casi 3. Non sono turni autista o disponibilità reale della flotta.

| Mezzo di modello | Giri completi assegnati, nominale e stress mostrato |
|---|---|
| B1 | 1, 5, 9, 13 |
| B2 | 2, 6, 10, 14 |
| B3 | 3, 7, 11, 15 |
| B4 | 4, 8, 12, 16 |

Ogni mezzo assegnato percorre entrambe le ali dentro ogni giro; FS intermedia è una sosta dello stesso mezzo. Quattro mezzi non significa due linee. Nei due casi mostrati, alle 07:35 i giri 1, 2, 3 e 4 occupano contemporaneamente un mezzo: questo prova che tre non bastano entro le ipotesi dichiarate.

Nominale: fine ultimo giro 21:08:18. Stress con marcia ×1,1, sosta 1 minuto ed ultimo recupero 15 minuti: fine 21:15:18. Dati ingegneristici, non ritardi osservati o probabilità.

Nel JSON le ore di servizio del giro (incluse le soste FS intermedie) sono separate dalle ore di occupazione del mezzo comprensive del recupero finale. Nessuna delle due è un turno autista: deposito, posizionamento, pause e norme di lavoro non sono modellati.

## Il calendario cambia il confronto annuo

| Giorni con identico servizio | Km commerciali/anno | Differenza su 111.419 |
|---:|---:|---:|
| 256 | 111.097,888 | -0,29% |
| 257 | 111.531,864 | +0,10% |
| 260 | 112.833,793 | +1,27% |
| 303 | 131.494,766 | +18,02% |

I 260 giorni sono un confronto ipotetico. I 303 giorni sono la somma dei tipi di giornata attivi del progetto D184/D185 nel Programma di Bacino: applicarli alla nuova proposta è una sensibilità aritmetica. Nessuno dei due costituisce un calendario annuale attuale già accertato o scelto. [Prova primaria e dettaglio dei tipi di giornata](RT031_LINEA8_CALENDARIO_E_RISORSE_2026_10_01.md).

**Il +1,27% non vale senza specificare i 260 giorni.** Con 303 giorni identici il confronto sale a +18,02%. Per rimanere entro il solo riferimento commerciale 111.419 si possono conteggiare al massimo 256 giorni identici; nessuna giornata è eliminata con questo calcolo. Km a vuoto, costo completo e finanziamento restano da definire.

[Blocchi e prove di minimo nei 27 scenari, contabilità e limiti](../outputs/phase2/rt031_line8_local_shortcuts_v3/caller_confirmed_vehicle_blocks_accounting_20261001.json) · [Proposta unica](RT031_LINEA8_PROPOSTA_UNICA_CONSOLIDATA_2026_10_01.md) · [Richieste operative](RT031_LINEA8_SCHEDA_VERIFICA_OPERATORE_2026_10_01.md)

`operating_plan_adopted=false`; `network_selected=false`; PRIMARY/RUNNER-UP non autorizzati; calendario non adottato; `decision_budget_km=null`; `uncertainty_band_min=null`.
