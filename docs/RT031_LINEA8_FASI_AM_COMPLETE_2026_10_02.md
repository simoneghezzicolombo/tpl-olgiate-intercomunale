# Linea 8 — confronto AM completo, senza cambiare la proposta

**Corretto il 7 ottobre dopo il riscontro del committente sul sottopasso.** Chiusa la verifica interna dei tre casi già esposti: fase confermata, prime cinque partenze est +1 o +2 minuti. Stessa geometria, 27 siti, 28 eventi non-FS, 16 giri, H30 e calendario feriale 2027. Ovest e tutte le partenze successive restano invariati; nessuna variante viene adottata.

Per ogni caso sono ricostruiti e verificati nove registri ordinati di tutte le corse, 27 blocchi mezzi e tutti i 296 flussi ferroviari in ciascuna delle due diagnostiche. Non sono 27 prove empiriche e non danno una probabilità.

## Quanto tempo deve realmente bastare

La prima coppia è arrivo da Milano 06:02 e partenza verso Milano 06:56; le quattro successive sono ogni 30 minuti. Il tempo est peggiore del modello è 47,7766 minuti. I budget sono **totali**, non tempi di solo cammino: ingresso include discesa, percorso effettivo, salita e ritardo/riserva treno; uscita include percorso alla porta, salita/chiusura porte e ritardo/riserva bus aggiuntivo rispetto al tempo est già stressato. Nessuna riserva è stata scelta.

| Prima partenza est | Budget totale treno→bus | Budget totale bus→treno dopo giro stressato | Km feriali 2027 | Massimo mezzi di modello |
|---|---:|---:|---:|---:|
| 06:05 (base) | 3 min | 3.223 min | 110229.936 | 4 |
| 06:06 (non adottata) | 4 min | 2.223 min | 110229.936 | 4 |
| 06:07 (non adottata) | 5 min | 1.223 min | 110229.936 | 4 |

L’ipotesi +1 ha partenze 06:06, 06:36, 07:06, 07:36, 08:06; +2: 06:07, 06:37, 07:07, 07:37, 08:07. Entrambe rispettano i cap direzionali di attesa e superano i controlli di corsa completa del modello ereditato. “Superano i controlli” non significa che le coincidenze reali siano garantite.

Il +1 riduce di 5 minuti/giorno la sosta intermedia complessiva, il +2 di 10; rispettivamente −21,167 e −42,333 ore di servizio nominale sui 254 giorni. Non si percorrono meno metri e non sono risparmi economici o turni autista certificati.

## Due diagnostiche, due esiti: non scegliere quella più favorevole

Con **3 minuti uguali per ogni trasferimento**, +1 e +2 fanno perdere il rispetto di tutti i nove scenari alla stessa corsa verso ciascuno dei cinque treni AM Milano. Non si occulta questo esito.

Con il **sottopasso corretto**, +1 e +2 non introducono perdite rispetto alle coincidenze bus→treno già rispettate in tutti i nove casi di quella diagnostica. Ma la base ora offre già il bus a **3 minuti dai cinque arrivi AM** nel proxy, non 33/58. Le due ipotesi portano quell’attesa a 4/5 minuti e riducono il residuo verso il treno di 1/2 minuti, pur accorciando la sosta intermedia. Tutte le righe Milano/Lecco sono conservate. Questo è un confronto fra effetti distinti, non una graduatoria pesata. Il proxy corretto omette ancora scale, porte e ritardi.

**Conclusione:** viene ritirata la motivazione del +1 come rimedio al vecchio giro esterno. Si mantiene la fase confermata: non occorre un’altra scelta del committente per correggere quell’errore. Le ipotesi +1/+2 restano confronti non adottati, non vincitori. Nella base le spese totali devono stare entro 3 minuti in ingresso e 3 minuti 13,4 secondi in uscita dopo il giro est stressato. I due trasferimenti effettivi e l’eventuale riserva restano da verificare, senza imporre una priorità normativa.

## Dove finisce la chiusura interna

Percorso e orario confermati rimangono la proposta di base. Non servono altre varianti per chiudere questo confronto locale: serve una prova del giro est in punta e dei trasferimenti effettivi, con piattaforme reali e percorso accessibile; poi si confrontano i totali con questi budget, senza trasformare dati assenti in zero. Treni 2027, accosti/sagoma, continuità passeggeri, turni/deposito e costo completo restano nella [distinta operativa](RT031_LINEA8_CHIUSURA_VERIFICHE_2026_10_02.md). Nessuna misurazione o risposta dell’operatore è simulata.

[Confronto macchina completo e tutte le righe](../outputs/phase2/rt031_line8_local_shortcuts_v3/directional_AM_phase_complete_comparisons_20261002.json) · [Accessi e fonti distinti](RT031_LINEA8_ACCESSI_BINARI_2026_10_02.md)

`physical_operation_ready=false`; `rail_2027_certified=false`; `timetable_change_adopted=false`; `primary_selection_authorised=false`; `runner_up_selection_authorised=false`; `decision_budget_km=null`; `uncertainty_band_min=null`.
