# Linea 8: confronto degli orientamenti per fascia

## Risultato, senza selezione

Sono stati calcolati tutti i 64 abbinamenti fra quattro pattern stradali e tre fasce (punta mattutina, morbida, punta serale), per sei finestre: 06–19 e 07–20; 05–19, 06–20 e 07–21; riferimento 06–22. Totale **384 scenari**, non un dominio completo di ogni orario possibile. Le punte di partenza sono 07–09 e 17–19, come nel capitolato precedente. Nessuna fascia è adottata.

128 scenari (quelli sulle due finestre da 13 ore) stanno nel tetto **prima degli extra**. Otto scenari con cambio di orientamento non mostrano intervalli oltre 60 minuti nel modello ottimistico da/per FS; tutti iniziano alle 07. Sono risultati diagnostici, non otto servizi certificati: l'unione delle occorrenze presume accessibilità e possibilità di salita su tutti i lati, senza tempo di attraversamento.

## Un confronto concreto richiesto dal problema, non un vincitore

Il profilo che favorisce entrambe le nuove esigenze verso FS al mattino e da FS nel pomeriggio è:

| Partenze dall'origine del giro a FS | Orientamento delle ali |
|---|---|
| 07:00, 07:30, 08:00, 08:30 | Ovest A + est B |
| 09:00–16:00, ogni ora | Ovest B + est A |
| 17:00, 17:30, 18:00, 18:30 | Ovest B + est A |
| 19:00 | Ovest B + est A |

17 giri completi/giorno su 260 giorni ipotetici: **109.285,990 km/anno**, residuo **2.133,010 km**, cioè **8,204 km/giorno** per deposito e altri extra. Sono 4 giri da 25,05556 km circa e 13 da 24,62373 km circa. Stesso insieme delle 26 identità incontrate e delle due esigenze nuove; nessuna fermata fisica viene autorizzata.

Nel modello stradale senza soste: Olgiate sud → FS 3,76 minuti e San Zeno → FS 2,38 nelle corse della punta mattutina; FS → Olgiate sud 3,92 e FS → San Zeno 2,31 nelle corse della punta serale. Nei viaggi opposti permane il giro lungo. Non si dichiara superiorità territoriale sulla base dei soli due punti: i risultati di tutte le 27 identità non-FS sono nel JSON.

La massima distanza temporale fra opportunità ipotetiche da/per FS è 60 minuti. **Non prova H30 a tutte le fermate durante l'intera punta**, né frequenze direzionali su piattaforme certificate: i confini delle fasce locali sono sfalsati rispetto alle partenze da FS. Il medesimo abbinamento su 06–19 produce un intervallo massimo di 81,11 minuti. Il confronto dimostra l'importanza delle transizioni, non l'impossibilità di correggerle con altri orari.

## Limiti che incidono sulla proposta

- Le ore indicate sono una finestra delle partenze dal capolinea, non 13 ore di servizio uniforme in ogni fermata. Nel profilo mostrato, la prima opportunità ipotetica da Olgiate sud verso FS è circa **07:22**, da San Zeno circa **07:49**, con arrivi rispettivamente circa 07:25 e 07:52. Non soddisfa automaticamente chi deve prendere treni precedenti. La partenza differenziata delle ali e le corse iniziali/finali non sono state esplorate in questo dominio.
- Assumendo recuperi di 5/10/15 minuti già presenti nel repository, il limite inferiore di flotta nel giorno è rispettivamente **2/3/3 veicoli**, ancora con soste zero. Non è una pianificazione dei turni e non prova affidabilità con due mezzi.
- 8,204 km/giorno residui possono non bastare per deposito e riposizionamenti. Il deposito non è noto in questo audit: zero extra non è assunto come dato operativo.
- Il cambio di senso alle 09 impone chiarezza informativa, fermate sicure su entrambi i lati e verifica degli eventi passeggeri. Le giunzioni passano le restrizioni via-node rappresentate, non un'autorizzazione di esercizio o la verifica completa delle restrizioni storiche.

Il risultato utile è un profilo concreto da confrontare con partenze anticipate/sfalsate delle ali e dati di sosta/deposito. **Non è ancora la proposta finale** e non autorizza una riduzione tacita del servizio mattutino o di un senso. Nessun peso, punteggio o vincitore viene introdotto.

## Riproducibilità

Script: `scripts/phase2_audit_rt031_line8_band_switch_v3.py`.
Risultati: `outputs/phase2/rt031_line8_local_shortcuts_v3/band_switch.json`, con hash delle fonti, partenze di ogni scenario, prima/ultima opportunità per luogo, tempi stradali, intervalli e testimone ordinato dell'intervallo peggiore. Geometria: i quattro pattern sono ricomposizioni delle ali già esportate; nessuna nuova strada viene inventata.

`actual_timetable_certified=false`; `network_selected=false`; `primary_selection_authorised=false`; `runner_up_selection_authorised=false`; `decision_budget_km=null`; `uncertainty_band_min=null`.
