# RT031 — Figura a otto: prova fisica e accesso, non scelta della linea

**Stato al 22 settembre 2026.** Il disegno politico dell'unica linea riconoscibile
con Olgiate FS come cerniera tra anello ovest ed est è un'ipotesi testabile, non
una rete selezionata. La [prova fisica](https://github.com/simoneghezzicolombo/tpl-olgiate-intercomunale/actions/runs/35745222839)
trova nel dominio RT023 fissato un cammino legale FS→ovest→FS→est→FS,
anche nel verso opposto, che visita fermate disponibili per Scarpone,
Rovagnate, Perego, Santa Maria, Calco, Arlate, Brivio e Beverate nell'ordine
imposto dalla corsia di prova. Sono fermate identificate, **non** una
certificazione che i centri/frazioni desiderati siano effettivamente serviti.
La prova include memoria di restrizione stradale, replay dell'intera storia
e della giunzione con il ciclo successivo.

La [tipizzazione del servizio](https://github.com/simoneghezzicolombo/tpl-olgiate-intercomunale/actions/runs/35745433362)
crea eventi ordinati per ciascun pattern, con FS sia iniziale/finale sia
intermedia, e dichiara una sola identità di linea pubblica. La continuità
del passeggero al passaggio intermedio è esplicita nel pattern; i **due versi
insieme non sono ancora certificati come un servizio unico**, perché non
esiste un orario congiunto. Non vanno contati i segmenti stradali o i mezzi
come linee distinte, né la dichiarazione di identità come orario realizzato.

## Cosa dicono davvero i numeri

L'[audit esatto di accesso pedonale](https://github.com/simoneghezzicolombo/tpl-olgiate-intercomunale/actions/runs/35745713815)
(artefatto `10701404155`, SHA-256
`a029684a5e788a0c2a23b5da389f4719ed787e5c31f6951a0f60fdd9b590a076`)
è riprodotto byte-per-byte due volte in CI e coincide con il calcolo locale.
Le percentuali sono quota di popolazione con **una fermata del pattern entro
10 minuti a piedi**, non domanda osservata, frequenza, tempo fino alla
stazione o quota di coincidenze riuscite.

| Corsia diagnostica | km/ciclo fisici | Fermate attuali esatte | Totale | Brivio | Calco | Olgiate | Santa Maria | La Valletta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Ordine richiesto, ovest→est | 22,148 | 4/11 | 61,63% | 77,91% | 62,52% | 35,01% | 91,89% | 67,84% |
| Come sopra, con Via Statale Olgiate | 22,464 | 4/11 | 63,55% | 77,91% | 62,52% | 41,96% | 91,89% | 67,84% |
| Ordine inverso, ovest→est | 22,169 | 4/11 | 62,87% | 78,24% | 62,52% | 39,27% | 91,89% | 67,84% |
| Come sopra, con Via Statale Olgiate | 22,304 | 4/11 | 64,79% | 78,24% | 62,52% | 46,22% | 91,89% | 67,84% |

La differenza tra i due versi dipende anche dall'insieme di fermate
fisicamente incontrate, non da un ipotetico vantaggio di orario. L'aggiunta
della fermata disponibile `ASF::OLGIATE_MOLGORA_VIA_STATALE` porta circa
**+6,95 punti percentuali a Olgiate** e +1,92 punti totali in ciascuno dei
due pattern, con +0,135–0,316 km/ciclo fisici. Non conserva un'altra delle
11 identità attuali D184/D185: è una diversa fermata esistente nel substrato.

Il [confronto precedente](RT031_ARLATE_ROVAGNATE_TRADEOFF_V3.md) comprende
una linea non-8 con 66,94% totale, 53,05% a Olgiate e 6/11 fermate attuali
esatte a 21,22 km/ciclo. Ciò **non elegge** quella linea, ma impedisce di
dire che la forma a otto appena cercata sia già la migliore. Viceversa
nessuno dei numeri di copertura prova che l'altra linea dia i tempi e la
riconoscibilità desiderati verso FS. I due confronti vanno tenuti insieme.

## Lacune che cambiano la proposta

- Il dominio di fermate disponibile non identifica ancora come servite
  Mondonico, Cornello, Calco Alta, Cassina, San Zeno o i luoghi urbani
  richiesti di Olgiate. `SPECIAL::CASA_DI_COMUNITA_OLGIATE` non compare in
  nessun pattern RT030: non è automaticamente una fermata TPL convenzionale.
  Un eventuale stop nuovo/sud Olgiate richiede verifica di posizione,
  pedonalità/barriere e autorizzazione, non una copertura inventata.
- Le distanze sono minimi sul grafo pairwise fissato e non includono
  dwell, recupero, tempo di fermata, corsa ferroviaria o vincoli di flotta.
  Il riferimento storico 20 cicli/giorno ×260 giorni e 111.419 km implica
  21,427 km/ciclo; **tutti e quattro i pattern lo superano**, ma quel
  riferimento non è un `decision_budget_km` approvato né una bocciatura.
- Mancano un orario cadenzato congiunto per i due versi e i tempi ordinati
  frazione→FS/FS→frazione, inclusi attesa, passaggio alla cerniera,
  coincidenza e span. Le indicazioni Google Popular Times sono proxy
  descrittivi e non domanda OD né prova che H30/H60 sia ottimo.

**Dunque:** la forma a otto è fisicamente promettente e merita una corsia
di progetto, ma questa versione sottocopre Olgiate rispetto alle alternative
e non dimostra ancora un servizio affidabile e frequente. Il prossimo
confronto deve mettere sullo stesso piano l'8 migliorato per Olgiate e le
alternative non-8, usando eventi, tempi per località, orari e accesso a
parità di fonti. Conservazione fermate resta preferenza Pareto, non filtro.

`candidate_domain_complete=false` · `decision_budget_km=null` ·
`uncertainty_band_min=null` · `network_selected=false` ·
`primary_selection_authorised=false` · `runner_up_selection_authorised=false`
