"""Reconcile the twelve inherited principles with one actual comparison witness."""
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csc_matrix, hstack, vstack

from scripts.phase2_compare_rt031_line8_deep_offpeak_v3 import build_problem
from scripts.phase2_export_rt031_line8_deep_offpeak_v3 import build as build_witness, LEDGER
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import BASE, FLAGS, PHASES, verify

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=BASE/'best_practices_readiness.json'
DOC=ROOT/'docs/RT031_LINEA8_VERIFICA_BEST_PRACTICES_V3.md'
PRINCIPLES=ROOT/'docs/PHASE2_TRANSIT_BEST_PRACTICES.md'


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()


def journeys(ledger):
    grouped=defaultdict(list)
    for trip in ledger['trips']:
        events=defaultdict(list)
        for e in trip['events_nominal']:
            events[e['stop_place_id']].append(e)
        for sid,items in events.items():
            early=min(items,key=lambda e:e['departure_min'])
            late=max(items,key=lambda e:e['departure_min'])
            outward=early['departure_min']-.5-trip['departure_min']
            inward=trip['fs_return_nominal_min']-late['departure_min']
            if min(outward,inward)<-1e-6:raise ValueError('event outside trip')
            grouped[sid].append({'trip_index':trip['trip_index'],'name':early['name'],
                'pattern':trip['loop'],'from_fs_ride_min':outward,'to_fs_ride_min':inward,
                'from_fs_occurrence_id':early['occurrence_id'],'to_fs_occurrence_id':late['occurrence_id'],
                'boarding_authorised':False,'passenger_continuity_certified':False})
    return [{'site_id':sid,'name':rows[0]['name'],'journeys':rows,
             'from_fs_min_range':[min(r['from_fs_ride_min'] for r in rows),max(r['from_fs_ride_min'] for r in rows)],
             'to_fs_min_range':[min(r['to_fs_ride_min'] for r in rows),max(r['to_fs_ride_min'] for r in rows)]}
            for sid,rows in sorted(grouped.items())]


def cadence(trips):
    result=[]
    for wing in ('west','east'):
        times=sorted(t['departure_min'] for t in trips if t['loop'].startswith(wing))
        if not times:raise ValueError('missing wing')
        residues=Counter(t%30 for t in times)
        result.append({'wing':wing,'departures_min':times,'minute_of_hour_values':sorted({t%60 for t in times}),
                       'modulo_30_counts':dict(sorted(residues.items())),
                       'departures_outside_most_common_half_hour_phase':len(times)-max(residues.values()),
                       'successive_departure_gaps_min':[b-a for a,b in zip(times,times[1:])]})
    return result


def anchor_phase_conflicts(problem):
    certificates=[]
    for wing in ('west','east'):
        anchors=[a for a in problem['anchors'] if a['wing']==wing]
        for i,a in enumerate(anchors):
            ap={problem['trips'][j]['departure_min']%30 for j in a['eligible']}
            for b in anchors[i+1:]:
                bp={problem['trips'][j]['departure_min']%30 for j in b['eligible']}
                if ap.isdisjoint(bp):
                    certificates.append({'wing':wing,'first_anchor':dict(a),'second_anchor':dict(b),
                                         'first_allowed_modulo_30':sorted(ap),'second_allowed_modulo_30':sorted(bp)})
                    break
            if certificates and certificates[-1]['wing']==wing:break
    return certificates


def clockface_probe(problem,time_limit=45,banded=False,fixed_peak_starts=None):
    # A strict, explicit diagnostic: one phase modulo 30 per wing all day.
    # It permits skipped slots (H60/H120), not arbitrary gaps or changed rail rules.
    bands=('before_10','from_10') if banded else ('all_day',)
    n=len(problem['costs']);phases=[(w,b,r) for w in ('west','east') for b in bands for r in range(0,30,5)]
    rows=[];cols=[];data=[];lo=[];hi=[]
    for i,t in enumerate(problem['trips']):
        if banded and t['departure_min']==problem['ready_span'][1]:continue
        band=('before_10' if t['departure_min']<600 else 'from_10') if banded else 'all_day'
        phase=(t['loop'].split('_')[0],band,t['departure_min']%30)
        row=len(lo);rows.extend([row,row]);cols.extend([i,n+phases.index(phase)]);data.extend([1.,-1.]);lo.append(-np.inf);hi.append(0.)
    for wing in ('west','east'):
        for band in bands:
            row=len(lo)
            for j,(w,b,_) in enumerate(phases):
                if w==wing and b==band:rows.append(row);cols.append(n+j);data.append(1.)
            lo.append(1.);hi.append(1.)
    extra=csc_matrix((data,(rows,cols)),shape=(len(lo),n+len(phases)))
    matrix=vstack([hstack([problem['matrix'],csc_matrix((problem['matrix'].shape[0],len(phases)))]),extra],format='csc')
    upper=problem['upper'].copy();upper[problem['fleet_rows']]=4
    costs=np.r_[problem['costs'],np.zeros(len(phases))]
    variable_upper=np.ones(len(costs))
    if fixed_peak_starts is not None:
        if set(fixed_peak_starts)!={'AM','PM'} or any((k,v) not in PHASES for k,v in fixed_peak_starts.items()):
            raise ValueError('fixed peak outside existing phase domain')
        for i,(label,start) in enumerate(PHASES):
            if start!=fixed_peak_starts[label]:variable_upper[len(problem['trips'])+i]=0
    answer=milp(costs,integrality=np.ones(len(costs)),bounds=Bounds(0,variable_upper),
                constraints=LinearConstraint(matrix,np.r_[problem['lower'],lo],np.r_[upper,hi]),
                options={'time_limit':time_limit,'mip_rel_gap':0})
    result={'solver_status':int(answer.status),'solver_message':str(answer.message),
            'strict_all_day_half_hour_phase_per_wing':not banded,'banded_with_final_departure_exception':banded,'policy_adopted':False,
            'scope':'Same four full paths, all 49 peak phases, same frequency windows, frozen per-site rail anchors and four nominal vehicles. Strict mode: one modulo-30 FS phase per wing all day. Banded mode: one per wing before 10:00 and one from 10:00; departure at 19:40 excepted. No other exception or adopted policy. Not all legible timetables.',
            'infeasibility_proven_in_this_domain':answer.status==2,'optimality_proven_in_this_domain':bool(answer.success),
            'witness_found':False,'time_limit_s':time_limit}
    result['fixed_peak_starts_comparison']=fixed_peak_starts
    bound=getattr(answer,'mip_dual_bound',None)
    if bound is not None and np.isfinite(bound):result['annual_service_km_lower_bound_in_domain']=float(bound)*260
    if answer.x is None:return result
    if max(abs(answer.x-np.rint(answer.x)))>1e-5:raise ValueError('fractional clockface witness')
    trips=sorted([t for i,t in enumerate(problem['trips']) if answer.x[i]>.5],key=lambda t:(t['departure_min'],t['loop']))
    peaks=[{'peak':label,'start_min':start,'end_min':start+120} for i,(label,start) in enumerate(PHASES) if answer.x[len(problem['trips'])+i]>.5]
    scenarios=verify(problem,trips,peaks,4)
    actual=cadence(trips)
    selected_phases=[{'wing':w,'band':b,'modulo_30':r} for i,(w,b,r) in enumerate(phases) if answer.x[n+i]>.5]
    for t in trips:
        if banded and t['departure_min']==problem['ready_span'][1]:continue
        band=('before_10' if t['departure_min']<600 else 'from_10') if banded else 'all_day'
        phase=next(p for p in selected_phases if p['wing']==t['loop'].split('_')[0] and p['band']==band)
        if t['departure_min']%30!=phase['modulo_30']:raise ValueError('clockface phase violated')
    result.update(witness_found=True,trips=trips,comparison_peak_windows=peaks,cadence=actual,clockface_phases=selected_phases,
                  annual_service_km=sum(problem['family']['loops'][t['loop']]['distance_m']*.26 for t in trips),
                  conditional_scenarios=scenarios)
    return result


def assessment(ledger):
    titles=re.findall(r'^### (BP-\d+) — (.+)$',PRINCIPLES.read_text(encoding='utf-8'),re.M)
    if len(titles)!=12:raise ValueError('principle inventory changed: review mapping')
    # References are scoped to actual evidence, not blanket compliance badges.
    entries=[
      ('MODEL_VERIFIED_WITH_SERVICE_TRADEOFF','deep_offpeak_comparison.json','H30 peaks and piecewise waits rechecked; H120 reduces midday opportunities.','Evaluate useful midday trips and first/last journeys per site.','DESKTOP_AND_CALLER'),
      ('PARTIAL_NO_DEMAND_WEIGHTED_UTILITY','deep_offpeak_witness.json','Actual within-trip rides available; no spatialised passenger OD or certified weighted GJT.','Publish walking/waiting/ride components separately; do not manufacture a demand-weighted ranking.','DESKTOP_AND_MISSING_DATA'),
      ('PARTIAL_CLOCKFACE_NOT_YET_PUBLIC_TIMETABLE','deep_offpeak_witness.json','Stable two-pattern geometry but irregular departure minutes; strict clockface diagnostic reported separately.','Reconcile legibility, rail phasing and endpoint coverage without calling an engineering example the public timetable.','DESKTOP'),
      ('PARTIAL_FROZEN_RAIL_ONLY','deep_offpeak_comparison.json','297 per-site checks on frozen targets, not current all-day interchange.','Obtain applicable rail events, midday target journeys and physical transfer times.','EXTERNAL_TIMETABLE_AND_FIELD'),
      ('PARTIAL_DETERMINISTIC_STRESS_ONLY','deep_offpeak_comparison.json','Nine timing cases and recovery scenarios, four nominal/up to six stress vehicles; no empirical probability.','Validate running/dwell distributions, fleet availability, driver duties and depot movements.','OPERATOR_AND_FIELD'),
      ('PARTIAL_ALL_SITE_RIDES_NOT_DIRECTNESS_CERTIFICATION','free_order_road_comparison.json','Local short rides and finite-domain shortest road orders do not prove all passenger journeys are short.','Review all-site directional rides; no arbitrary ride-time acceptance threshold is adopted.','DESKTOP_AND_CALLER'),
      ('PARTIAL_PHYSICAL_STOPS_UNAPPROVED','multistop_recovery.json','Stop retention/relocation alternatives and walking trade-offs explored; no site authorisation.','Check actual ordered boarding sides, safe stop space and six manoeuvres; audit acceleration/braking representation.','FIELD_AND_OPERATOR'),
      ('PARTIAL_TWO_PATTERNS_NOT_CONTINUITY_APPROVAL','deep_offpeak_witness.json','Two full wing patterns, no partial trips in this witness; same vehicle is not same passenger service.','Specify route identity, destination displays, FS through-service or transfer, and public timetable.','DESKTOP_AND_OPERATOR'),
      ('PARTIAL_PRIOR_EXPLORATION_NOT_COMPARABLE_FINAL_TOURNAMENT','partial_services_findings.json','Prior generated alternatives and retention trade-offs exist; current result is conditional on four paths.','Keep old evidence scoped; no universal optimality or passenger relocation count without supporting data.','DESKTOP_AND_MISSING_DATA'),
      ('PARTIAL_SPATIAL_EQUITY_NOT_RIDERSHIP','brivio_existing_sites_walk.json','Municipal walking catchments retained, not temporal utility or observed passengers.','Report weak areas and central-hour losses; no undeclared coverage floor, score or fabricated OD.','DESKTOP_AND_CALLER'),
      ('PARTIAL_FUNCTIONAL_JOURNEYS_NOT_FULLY_VALIDATED','deep_offpeak_comparison.json','Five-municipality feeder concept with rail hub, not only Olgiate.','Check external destinations and useful onward rail journeys using supported evidence.','EXTERNAL_TIMETABLE_AND_MISSING_DATA'),
      ('PARTIAL_ACCESSIBILITY_NOT_UNIVERSAL_ACCESS','deep_offpeak_witness.geojson','Potential pedestrian access and separate south/north points; proxy is not whole-neighbourhood coverage.','Verify south perimeter, step-free paths, safe crossings and station interchange.','DESKTOP_AND_FIELD')]
    result=[]
    for (pid,title),(status,source,evidence,action,owner) in zip(titles,entries):
        result.append({'id':pid,'title':title,'status':status,'evidence_source':str((BASE/source).relative_to(ROOT)).replace('\\','/'),
                       'supported_conclusion':evidence,'remaining_action':action,'resolution_scope':owner,'fully_certified':False})
    return result


def build():
    ledger,shape=build_witness()
    if json.loads(json.dumps(ledger))!=json.loads(LEDGER.read_text(encoding='utf-8')):raise ValueError('witness source drift')
    problem=build_problem((600,960),120)
    probe=clockface_probe(problem)
    banded=clockface_probe(problem,banded=True)
    same_peaks=clockface_probe(problem,banded=True,fixed_peak_starts={p['peak']:p['start_min'] for p in ledger['comparison_peak_windows']})
    refs=[PRINCIPLES,ROOT/'docs/RT031_PRIOR_WORK_EVIDENCE_MAP.md',ROOT/'config/rt031_requirements_audit_v3.json',LEDGER]
    rows=assessment(ledger)
    refs.extend(ROOT/r['evidence_source'] for r in rows)
    return {'contract':'RT031_LINE8_TWELVE_BEST_PRACTICES_READINESS_V3','status':'NOT_READY_FOR_FINAL_OPERATING_PROPOSAL',
            'scope':'Current 10-16/H120 witness, inherited BP-01..12 and prior-work map; not an exhaustive audit of every historical conversation or branch. No ranking or new normative thresholds.',
            'source_sha256_normalized_newlines':{p.relative_to(ROOT).as_posix():digest(p) for p in sorted(set(refs))},
            'principles':rows,'nominal_site_rides':journeys(ledger),'cadence':cadence(ledger['trips']),
            'strict_clockface_comparison':probe,'banded_clockface_comparison':banded,
            'banded_same_peak_windows_comparison':same_peaks,
            'strict_phase_conflict_certificates':anchor_phase_conflicts(problem),'annual_service_km':ledger['annual_service_km'],
            'site_count_including_fs':ledger['site_count_including_fs'],
            'ride_semantics':'Nominal x1.1 moving, 0.5 dwell. Earliest within-trip alighting from FS and latest boarding to FS are separate ordered events. Optimistic conditional boarding; exclude walk, wait, rail and inter-trip transfers. No observed demand, universal directness test or implicit acceptable maximum.',
            'demand_weighted_gjt_improvement_min':None,'missed_connection_probability':None,
            'actual_timetable_certified':False,'decision_budget_km':None,'uncertainty_band_min':None,
            'approved_uplift_percent':None,'total_operating_km':None,**{k:False for k in FLAGS}}


def report(r):
    def number(value):return f'{value:,.3f}'.replace(',','_').replace('.',',').replace('_','.')
    def wing_name(value):return 'ovest' if value=='west' else 'est'
    lines=['# Linea 8 — verifica delle dodici best practice sulla proposta attuale','',
           '**Aggiornamento 1 ottobre 2026:** la verifica dei dodici principi sulla base ora confermata è nella [proposta unica consolidata](RT031_LINEA8_PROPOSTA_UNICA_CONSOLIDATA_2026_10_01.md). I numeri e gli orari di questo documento sono storici, non trapiantabili nella nuova proposta a 16 giri.','',
           '## Conclusione','',
           'Il confronto da **122.340 km/anno** non è ancora la proposta finale: mantiene i siti e i controlli del modello, '
           'ma non certifica tutte le qualità del servizio. Il richiamo alle best practice diventa qui una verifica tracciabile, '
           'non un punteggio o una dichiarazione generica di conformità. Nessuna soglia, preferenza o autorizzazione nuova.','',
           '## Tutti i principi pregressi','',
           '| Principio | Stato e prova disponibile | Cosa manca / chi può chiuderlo |','|---|---|---|']
    italian=[
        ('Frequenza e durata','H30 e attese per fascia verificati nel modello; H120 riduce le opportunità centrali.','Verificare viaggi centrali utili e primi/ultimi collegamenti per sito.'),
        ('Viaggio completo','Tempi a bordo disponibili, ma non domanda passeggeri spazializzata o GJT pesata certificata.','Separare cammino, attesa, viaggio e cambio; non inventare una graduatoria pesata.'),
        ('Orario memorabile','Minuti irregolari nel testimone iniziale; due confronti per fasce ora verificati sotto.','Scegliere il compromesso tra regolarità, fasce H30 e km senza spostamenti impliciti.'),
        ('Interscambio S8','297 controlli per sito su treni congelati; non copertura ferroviaria attuale dell’intera giornata.','Orari applicabili, viaggi centrali da proteggere e tempi fisici di interscambio.'),
        ('Affidabilità','Soste e recuperi presenti; quattro mezzi nominali, fino a sei negli stress.','Tempi osservati, flotta disponibile, turni e deposito: dati dell’operatore, non probabilità inventate.'),
        ('Direttezza','Tempi rapidi dei due quartieri non equivalgono a viaggi rapidi ovunque.','Valutare tutti i tempi nei due sensi, riportati sotto; soglia di accettabilità non scelta automaticamente.'),
        ('Fermate e velocità','Esaminati spostamenti, esclusioni e bacini pedonali; siti non autorizzati.','Sopralluogo su paline, lati di salita, attraversamenti e sei manovre; verifica accelerazione/frenata nel modello.'),
        ('Semplicità della rete','Due percorsi completi, senza corse parziali nel riferimento.','Definire identità pubblica, destinazioni esposte, permanenza a bordo o cambio a FS.'),
        ('Continuità senza ereditare tutto','Esistono alternative generate e confronti di conservazione; il minimo corrente riguarda quattro percorsi.','Non promuovere prove storiche a ottimo globale o a conteggio di passeggeri che cambiano fermata.'),
        ('Equità e domanda','Percentuali pedonali dei comuni conservate, non domanda o utilità temporale invariata.','Esplicitare zone deboli e perdite orarie; nessun minimo territoriale o peso arbitrario.'),
        ('Area funzionale','Servizio dei cinque comuni centrato sulla ferrovia, non una linea del solo comune di Olgiate.','Verificare destinazioni esterne e prosecuzioni ferroviarie realmente utili.'),
        ('Accessibilità inclusiva','Bacini pedonali potenziali; sud e nord distinti, ma due punti non certificano quartieri interi.','Perimetro sud, percorsi senza barriere, sicurezza pedonale e interscambio: verifiche dedicate e sul campo.')]
    for row,(title,evidence,action) in zip(r['principles'],italian):
        lines.append(f"| {row['id']} — {title} | {evidence} | {action} |")
    lines+=['','## Tempi effettivamente modellati per tutti i siti','',
            'Minuti sul bus nominali, esclusi cammino, attesa e treno. Le occorrenze iniziale/finale sono distinte: '
            'un breve viaggio nei due sensi può richiedere punti di salita diversi. Non sono paline autorizzate. '
            'FS è il ventottesimo sito. Questi valori descrivono il servizio 10–16/H120 corrente, non un vecchio testimone.','',
            '| Sito | Da FS, min | Verso FS, min |','|---|---:|---:|']
    for site in r['nominal_site_rides']:
        def fmt(k):
            a,b=site[k];return f'{a:.1f}' if abs(a-b)<.01 else f'{a:.1f}–{b:.1f}'
        lines.append(f"| {site['name']} | {fmt('from_fs_min_range')} | {fmt('to_fs_min_range')} |")
    lines+=['','## Regolarità: misura, non promessa','']
    for c in r['cadence']:
        lines.append(f"- Ala {wing_name(c['wing'])}: minuti nell'ora {c['minute_of_hour_values']}; {c['departures_outside_most_common_half_hour_phase']} partenze fuori dalla fase modulo 30 più frequente. È una descrizione, non una penalità normativa.")
    p=r['strict_clockface_comparison']
    lines+=['','Prova aggiuntiva: una sola coppia di minuti a distanza di 30 per ciascuna ala, per tutta la giornata; '
            f"slot saltati ammessi per H60/H120. Stessi percorsi, punte, ferrovia e quattro mezzi nominali. Esito solver: {p['solver_status']}."]
    if p['witness_found']:
        lines.append(f"Testimone verificato: **{p['annual_service_km']:.3f} km/anno**, minimo provato nel solo dominio dichiarato: {p['optimality_proven_in_this_domain']}. Non adottato.")
    elif p['infeasibility_proven_in_this_domain']:
        lines.append('**Il cadenzamento rigido per tutta la giornata è incompatibile con questo insieme di vincoli.** Non dimostra che ogni orario leggibile sia impossibile: regolarità per fascia e poche eccezioni esplicite sono concetti diversi. Nessun requisito ferroviario è stato rimosso per farlo passare.')
    else:lines.append('Ricerca non conclusiva: nessun testimone trovato entro il limite; nessuna impossibilità dichiarata.')
    for certificate in r['strict_phase_conflict_certificates']:
        lines.append(f"Conflitto riproducibile {certificate['wing']}: un controllo mattutino ammette solo fasi modulo 30 {certificate['first_allowed_modulo_30']}, un altro controllo ammette {certificate['second_allowed_modulo_30']}. Gli insiemi sono disgiunti: non è un fallimento numerico o una conclusione su tutte le politiche di coincidenza.")
    b=r['banded_clockface_comparison']
    lines+=['','### Confronto con due fasce di regolarità','',
            'Una coppia di minuti prima delle 10 e una dalle 10 per ciascuna ala; ultima partenza 19:40 dichiarata come eccezione. '
            'È una prova tecnica, non una nuova preferenza imposta. Frequenze, siti, obiettivi ferroviari e quattro mezzi nominali invariati.']
    if b['witness_found']:
        lines.append(f"Esiste un testimone verificato da **{number(b['annual_service_km'])} km/anno**; minimo nel dominio ristretto provato: {'sì' if b['optimality_proven_in_this_domain'] else 'no'}. Non adottato.")
        lines.append('')
        for phase in b['clockface_phases']:
            m=phase['modulo_30'];band='prima delle 10' if phase['band']=='before_10' else 'dalle 10'
            lines.append(f"- Ala {wing_name(phase['wing'])}, {band}: minuti :{m:02d}/:{m+30:02d}; non tutti gli slot sono serviti.")
        for row in b['cadence']:
            times=', '.join(f'{int(t)//60:02d}:{int(t)%60:02d}' for t in row['departures_min'])
            lines.append(f"- Partenze ala {wing_name(row['wing'])}: {times}.")
        for phase in b['comparison_peak_windows']:
            start,end=phase['start_min'],phase['end_min']
            lines.append(f"- Finestra H30 {phase['peak']}: {start//60:02d}:{start%60:02d}–{end//60:02d}:{end%60:02d}. La posizione della punta può differire dal testimone iniziale: non è una traslazione adottata.")
    elif b['infeasibility_proven_in_this_domain']:lines.append('Anche questa precisa regola è incompatibile nel dominio; non tutte le regolarità per fascia sono escluse.')
    else:lines.append('Prova per fasce non conclusiva entro il tempo assegnato; nessuna impossibilità dimostrata.')
    same=r['banded_same_peak_windows_comparison']
    lines+=['','### Controllo a identiche finestre di punta','',
            'Per non nascondere uno spostamento del servizio, seconda prova bandata con le stesse finestre del testimone iniziale: 07–09 e 16:55–18:55.']
    if same['witness_found']:
        lines.append(f"Risultato verificato: **{number(same['annual_service_km'])} km/anno**; minimo nel dominio provato: {'sì' if same['optimality_proven_in_this_domain'] else 'no'}. Nessuna modifica adottata.")
        lines.append(f"Differenza dal testimone iniziale: **+{number(same['annual_service_km']-r['annual_service_km'])} km/anno**. Eccedenza su 111.419: **+{100*(same['annual_service_km']/111419-1):.2f}%**. Non è un nuovo budget approvato.")
        lines.append('')
        for row in same['cadence']:
            times=', '.join(f'{int(t)//60:02d}:{int(t)%60:02d}' for t in row['departures_min'])
            lines.append(f"- Partenze ala {wing_name(row['wing'])}: {times}.")
    elif same['infeasibility_proven_in_this_domain']:lines.append('Nessuna soluzione con questa regola di regolarità e quelle esatte punte nel dominio dichiarato.')
    else:lines.append('Ricerca a punte identiche non conclusiva; nessuna impossibilità dichiarata.')
    lines+=['','## Riconciliazione delle istruzioni storiche','',
            '- Le richieste legacy di GJT pesata, probabilità di coincidenza o selezione finale non autorizzano a inventare dati mancanti: restano null/non selezionato.',
            '- La preferenza successiva per una linea a otto è un indirizzo del committente, non la prova che sia globalmente ottima.',
            '- H90/H120 è ora ammesso come confronto nelle sole ore centrali; non si applica automaticamente all’intera morbida.',
            '- Preservare tutti i siti è il controllo di questo confronto, non una trasformazione della preferenza di conservazione in un vincolo eterno.',
            '- Il riferimento 111.419 resta distinto dal tetto decisionale non dichiarato; +9,8% non è un incremento approvato.','',
            '## Chiusura del lavoro','',
            'Prima di presentare un orario finale: rendere leggibili le partenze per fascia e i tempi nei due sensi; aggiornare gli eventi ferroviari '
            'e i viaggi centrali da proteggere; validare paline, sei manovre, flotta, calendario e costi completi. '
            'Le verifiche su strada e dell’operatore non possono essere sostituite da altri test del software. '
            'Non si riapre per questo una ricerca indiscriminata né si elimina automaticamente un territorio.','',
            '[Audit macchina](../outputs/phase2/rt031_line8_local_shortcuts_v3/best_practices_readiness.json) · '
            '[Tracciato corrente](../outputs/phase2/rt031_line8_local_shortcuts_v3/deep_offpeak_witness.png) · '
            '[Best practice originali](PHASE2_TRANSIT_BEST_PRACTICES.md)']
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    result=build()
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    DOC.write_text(report(result),encoding='utf-8')
    print(json.dumps({'principles':len(result['principles']),'nonhub_sites':len(result['nominal_site_rides']),
                      'clockface':{k:v for k,v in result['strict_clockface_comparison'].items() if k not in ('trips','conditional_scenarios')}}))
