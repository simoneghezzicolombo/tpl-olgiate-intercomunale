# Linea 8 — chiusura del confronto d'orario sulla geometria a ordine conservato

Il confronto da **116.411,944 km/anno**, 28 siti inclusa FS, sola Hoè esclusa e ordine di servizio conservato è stato riprodotto in CI. Non è una rete selezionata né una variante fisicamente autorizzata. La [mappa e le perdite territoriali](RT031_LINEA8_COMPROMESSO_HOE_V3.md) rimangono quelle dichiarate; questa verifica non modifica la geometria.

## Esito dei controlli mirati

| Confronto non adottato | Esito nel dominio dichiarato |
|---|---|
| 16 giri, H60 nelle spalle, prima ovest oppure prima est, offset intermedio massimo 55 o 85 minuti | Infeasibilità dimostrata nei quattro casi |
| 16 giri, H65, prima ovest oppure prima est, offset massimo 55 minuti | Infeasibilità dimostrata nei due casi |
| 16 giri, H70, prima ovest, massimo quattro mezzi nel comune stress peggiore, offset massimo 55 oppure 85 minuti | Infeasibilità dimostrata nei due casi |
| 16 giri, H70, gruppo est di rientro iniziato con il treno delle 16:02, entrambe le orientazioni, offset massimo 55 minuti | Infeasibilità dimostrata nei due casi |
| 16 giri, H70, gruppo est di rientro iniziato con il treno delle 16:32, entrambe le orientazioni, offset massimo 55 minuti | Infeasibilità dimostrata nei due casi |
| 17 giri, H60, prima ovest, offset massimo 55 minuti | Infeasibilità dimostrata |
| 18 giri, H60, prima ovest, offset massimo 55 minuti | Testimone trovato; **130.963,437 km/anno**, circa **+17,54%** rispetto a 111.419 |

Il caso da 18 giri è solo un confronto: **non sostituisce i 16 giri approvati**, non risolve il budget e non è adottato. Il caso da 16 giri H70 rimane il testimone fattibile da 116.412 km; non viene chiamato H60. H120 resta nella morbida 10–16.

Le prove negative valgono soltanto per questa geometria, gli eventi di servizio conservati, i 9 scenari di marcia/dwell, le finestre readiness del contratto, la griglia partenze di cinque minuti e i gruppi di cinque treni consecutivi congelati. Non provano impossibilità per ogni geometria o un orario continuo. H60/H65/H70 sono limiti di attesa della prossima opportunità utile nelle finestre definite, non una promessa di intervallo uniforme a ogni confine di fascia. Status del solver 2 significa infeasibilità dimostrata; timeout senza testimone non significherebbe impossibilità.

## Quali vecchi obiettivi ferroviari mancano davvero

Il testimone a 16 giri lega 20 abbinamenti ai nuovi gruppi H30, di cui 17 appartenenti ai vecchi 22 obiettivi. **18 dei vecchi 22 sono comunque compatibili** con l'orario completo: compatibilità fisica modellata e assegnazione scelta non sono la stessa cosa. I quattro obiettivi incompatibili sono:

| Ala | Esigenza precedente | Treno congelato |
|---|---|---|
| Est | Bus → treno verso Milano | 07:26 |
| Ovest | Bus → treno verso Milano | 09:26 |
| Est | Treno da Milano → bus | 16:32 |
| Est | Treno da Milano → bus | 17:02 |

Queste sono lacune di servizio da discutere, **non probabilità empiriche di perdere il treno**. Dire solo “H30 in punta” le nasconderebbe. Il gruppo est serale del testimone parte dagli arrivi ferroviari 17:32–19:32, quello ovest dagli arrivi 16:32–18:32. Gli orari appartengono al dataset archiviato: non sono una verifica del servizio ferroviario oggi.

## Il punto decisionale, senza altri giri a vuoto

La variante da 16 giri non soddisfa ancora tutte le preferenze: richiede di accettare esplicitamente **Hoè esclusa, +4,48%, H70 nelle spalle e i quattro obiettivi sopra non coperti**. Nessuno di questi compromessi viene approvato dal semplice “andiamo avanti”. La flotta nominale è quattro mezzi; uno scenario deterministico ne richiede cinque. Non c'è un tetto di flotta approvato. Idoneità autobus, manovra a FS, restrizioni dipendenti dalla storia completa, accosti e attraversamenti rimangono da verificare con Agenzia/operatore e sopralluogo.

Se tali compromessi non sono accettabili, il risultato di questa verifica è un **no-go per questa specifica proposta**, non una richiesta automatica di più km o un taglio nascosto della frequenza. La scelta fra alternative richiede una preferenza normativa esplicita; non viene introdotto un punteggio ponderato.

`network_selected=false`, `primary_selection_authorised=false`, `runner_up_selection_authorised=false`, `decision_budget_km=null`, `uncertainty_band_min=null`.

[Risultati machine-readable dei 14 confronti e testimone di riferimento](../outputs/phase2/rt031_line8_local_shortcuts_v3/hoe_fixed_order_timetable_closure.json.gz).
