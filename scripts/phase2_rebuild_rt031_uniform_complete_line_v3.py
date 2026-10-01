"""Every public trip operates the SAME complete eight; never two wing-only lines.

First bounded rebuild keeps inherited station-access ready windows and rail
targets. A timed intermediate FS call separates passenger dwell from holding;
terminal recovery is charged once per complete commercial trip, not per wing.
All timing/boarding/road approvals remain conditional.
"""
import gzip
import hashlib
import json
import math

import numpy as np
from scipy.optimize import Bounds,LinearConstraint,milp
from scipy.sparse import csc_matrix

from scripts.phase2_audit_rt031_line8_through_service_v3 import (
    inputs,ROOT,BASE,clock,AUTH as STOP_AUTH,EXAMPLES,TIMETABLE)
from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops
from scripts.phase2_audit_rt031_line8_independent_wings_v3 import minimum_blocks
from scripts.phase2_solve_rt031_line8_flexible_peaks_v3 import interval_covers
from scripts.phase2_audit_rt031_line8_passenger_peaks_v3 import uncovered_intervals
from scripts.phase2_close_rt031_line8_31_trips_v3 import digest,PEAKS

AUTH=ROOT/'config/rt031_uniform_complete_line_authority_v3.json'
OUTPUT=BASE/'uniform_complete_line_rebuild.json.gz'
DOC=ROOT/'docs/RT031_LINEA8_PERCORSO_UNICO_COMPLETO_V3.md'


def read_result():
    return json.loads(gzip.decompress(OUTPUT.read_bytes()))


def source_fingerprints(p,loops):
    payload={'loops':loops,'rail':p['rail'],'rail_anchors':p['anchors'],
             'am_wait_ceiling_min':p['wait_ceiling'],'inherited_peak_windows':PEAKS}
    return {
        'source_sha256_normalized_newlines':{
            'authority':digest(AUTH),'stop_choices':digest(STOP_AUTH),
            'historical_wing_timetable':digest(TIMETABLE),'stop_addition_events':digest(EXAMPLES),
            'geometry_confirmation':digest(ROOT/p['authority']['geometry_confirmation_source'])},
        'consumed_model_inputs_sha256':hashlib.sha256(json.dumps(payload,sort_keys=True,
            ensure_ascii=False,separators=(',',':')).encode('utf-8')).hexdigest()}


def timing_offsets(loops,first,midpoint):
    second=next(k for k in loops if k!=first)
    grid={}
    for moving in (.9,1.,1.1):
        for dwell in (0.,.5,1.):
            adjusted=adjusted_loops(loops,moving,dwell)
            if adjusted[first]['road_minutes']+dwell>midpoint+1e-8:
                raise ValueError('intermediate FS departure precedes arrival plus public dwell')
            sites={}
            for pattern,start in ((first,0),(second,midpoint)):
                for sid in sorted({e['stop_place_id'] for e in adjusted[pattern]['events']}):
                    own=[e for e in adjusted[pattern]['events'] if e['stop_place_id']==sid]
                    latest=max(own,key=lambda e:e['path_node_index']);earliest=min(own,key=lambda e:e['path_node_index'])
                    sites[sid]={'wing':pattern,'from_fs':start,
                        'to_fs':start+latest['offset_from_wing_origin_min'],
                        'alight_from_fs':start+earliest['offset_from_wing_origin_min']-dwell,
                        'fs_arrival':start+adjusted[pattern]['road_minutes'],
                        'board_occurrence_id':latest['occurrence_id'],'alight_occurrence_id':earliest['occurrence_id']}
            grid[moving,dwell]={'sites':sites,'midpoint_arrival':adjusted[first]['road_minutes'],
                'midpoint_departure':midpoint,'public_fs_dwell_assumption_min':dwell,
                'intermediate_fs_holding_excluding_dwell_min':midpoint-adjusted[first]['road_minutes']-dwell,
                'full_trip_arrival':midpoint+adjusted[second]['road_minutes']}
    return grid


def covers_and_rails(p,loops,first,midpoint,departures):
    grid=timing_offsets(loops,first,midpoint);covers=set()
    # Scope retained for comparison; no relabelled 31-trip count or wing dispatch.
    for case in grid.values():
        for sid,offset in case['sites'].items():
            wait=155 if offset['wing']=='west_B' else 120
            for direction in ('to_fs','from_fs'):
                ev=[(i,t+offset[direction]) for i,t in enumerate(departures)]
                for start,end,limit in ((390,1180,wait),(390,420,60),(1135,1180,60),
                                        *((x['start_min'],x['end_min'],30) for x in PEAKS)):
                    covers.update(interval_covers(ev,start,end,limit))
    targets=sorted({(a['wing'],a['kind'],a['rail_min']) for a in p['anchors']})
    rail=[]
    for wing,kind,minute in targets:
        pattern=next(k for k in loops if k.startswith(wing))
        sid=next(sid for sid,row in grid[1.1,.5]['sites'].items() if row['wing']==pattern)
        eligible=[]
        for i,t in enumerate(departures):
            if kind=='bus_to_rail':
                ok=all(-1e-8<=minute-t-case['sites'][sid]['fs_arrival']-3<=p['wait_ceiling']+1e-8 for case in grid.values())
            else:ok=3<=t+grid[1.1,.5]['sites'][sid]['from_fs']-minute<=8
            if ok:eligible.append(i)
        covers.add(tuple(eligible))
        rail.append({'wing':pattern,'kind':kind,'rail_min':minute,'eligible_candidate_indices':eligible})
    return grid,covers,rail


def verify(grid,departures,p,loops):
    for case in grid.values():
        for row in case['sites'].values():
            for direction in ('to_fs','from_fs'):
                values=[t+row[direction] for t in departures]
                for start,end,limit in ((390,1180,155 if row['wing']=='west_B' else 120),
                    (390,420,60),(1135,1180,60),*((x['start_min'],x['end_min'],30) for x in PEAKS)):
                    if uncovered_intervals(values,start,end,limit):raise ValueError('uniform site-ready service gap')
    bindings=[]
    for wing,kind,minute in sorted({(a['wing'],a['kind'],a['rail_min']) for a in p['anchors']}):
        pattern=next(k for k in loops if k.startswith(wing))
        for sid,row in grid[1.1,.5]['sites'].items():
            if row['wing']!=pattern:continue
            eligible=[t for t in departures if (
                all(-1e-8<=minute-t-case['sites'][sid]['fs_arrival']-3<=p['wait_ceiling']+1e-8 for case in grid.values())
                if kind=='bus_to_rail' else 3<=t+row['from_fs']-minute<=8)]
            if not eligible:raise ValueError('uniform rail target failure')
            direction='MILANO' if kind=='bus_to_rail' else 'LECCO'
            field='departure_min' if kind=='bus_to_rail' else 'arrival_min'
            trains=[e for e in p['rail']['events'] if e['direction']==direction and e[field]==minute]
            if len(trains)!=1:raise ValueError('absent or ambiguous dated rail event')
            bindings.append({'site_id':sid,'kind':kind,'rail_min':minute,'rail_trip_id':trains[0]['trip_id'],
                'eligible_full_trip_departures_min':eligible})
    scenarios=[]
    for (moving,dwell),case in grid.items():
        for recovery in (5,10,15):
            blocks=minimum_blocks([{'loop':'FULL_EIGHT','departure_min':t} for t in departures],
                {'FULL_EIGHT':{'road_minutes':case['full_trip_arrival']}},{'FULL_EIGHT>FULL_EIGHT':True},recovery)
            scenarios.append({'moving_multiplier':moving,'public_stop_dwell_min':dwell,
                'terminal_recovery_once_per_full_trip_min':recovery,
                'midpoint_holding_excludes_terminal_recovery':True,**blocks})
    return bindings,scenarios


def solve_case(p,loops,first,midpoint):
    grid=timing_offsets(loops,first,midpoint)
    max_offset=max(row[direction] for case in grid.values() for row in case['sites'].values() for direction in ('to_fs','from_fs'))
    earliest=5*math.floor((390-max_offset)/5)
    domain=list(range(earliest,1181,5))
    grid,covers,rail=covers_and_rails(p,loops,first,midpoint,domain)
    result={'first_wing':first,'second_wing':next(k for k in loops if k!=first),
        'intermediate_fs_departure_offset_min':midpoint,'root_departure_domain_min':[earliest,1180],
        'public_route_id':'LINEA_8_UNIFORM_COMPLETE_DESIGN','every_trip_operates_both_wings':True,
        'short_turns_present':False,'operating_plan_adopted':False}
    if () in covers:
        return {**result,'infeasible_in_declared_domain':True,'proof':'empty_required_ready_or_rail_cover','witness_found':False}
    rows=[];cols=[]
    for r,cover in enumerate(sorted(covers)):
        for i in cover:rows.append(r);cols.append(i)
    matrix=csc_matrix((np.ones(len(rows)),(rows,cols)),shape=(len(covers),len(domain)))
    answer=milp(np.ones(len(domain)),integrality=np.ones(len(domain)),bounds=Bounds(0,1),
        constraints=LinearConstraint(matrix,np.ones(len(covers)),np.full(len(covers),np.inf)),
        options={'time_limit':30,'mip_rel_gap':0})
    result.update(solver_status=int(answer.status),infeasible_in_declared_domain=answer.status==2,
        witness_found=answer.x is not None,minimum_full_trip_count_proven=answer.status==0)
    if answer.x is None:
        if answer.status not in (1,2):raise ValueError('uniform dispatch solver failed')
        return result
    if max(abs(answer.x-np.rint(answer.x)))>1e-6:raise ValueError('fractional full-trip witness')
    selected=[t for t,x in zip(domain,answer.x) if x>.5]
    bindings,scenarios=verify(grid,selected,p,loops)
    km=sum(l['distance_m'] for l in loops.values())/1000
    nom=next(s for s in scenarios if (s['moving_multiplier'],s['public_stop_dwell_min'],s['terminal_recovery_once_per_full_trip_min'])==(1.1,.5,10))
    result.update(full_trip_departures_min=selected,full_trip_count=len(selected),
        annual_service_km=len(selected)*km*260,rail_target_bindings=bindings,
        nominal_full_trip_duration_min=grid[1.1,.5]['full_trip_arrival'],
        nominal_intermediate_fs_onboard_wait_min=midpoint-grid[1.1,.5]['midpoint_arrival'],
        nominal_vehicle_count=nom['minimum_vehicle_count_conditional'],
        maximum_grid_vehicle_count=max(s['minimum_vehicle_count_conditional'] for s in scenarios),
        conditional_scenarios=scenarios,
        full_trip_ledger=[{'departure_min':t,'public_route_id':result['public_route_id'],
            'full_pattern_id':first+'>'+result['second_wing'],'intermediate_fs_arrival_nominal_min':t+grid[1.1,.5]['midpoint_arrival'],
            'intermediate_fs_departure_min':t+midpoint,'final_fs_arrival_nominal_min':t+grid[1.1,.5]['full_trip_arrival'],
            'passengers_may_remain_onboard_in_design':True,'operating_authorised':False} for t in selected])
    return result


def build():
    authority=json.loads(AUTH.read_text(encoding='utf-8'))
    if (not authority['all_commercial_trips_same_complete_path']
            or not authority['both_wings_required_in_every_commercial_trip']
            or not authority['fs_is_intermediate_passenger_stop_not_forced_transfer']
            or authority['short_turn_public_trips_allowed']
            or authority['mixing_wing_only_public_services_allowed']):
        raise ValueError('uniform route authority drift')
    _,p,_,_,loops=inputs();length=sum(l['distance_m'] for l in loops.values())/1000
    cases=[];patterns={}
    for first in ('west_B','east_A'):
        second=next(k for k in loops if k!=first)
        if not all(p['family']['joins'].get(k) is True for k in (first+'>'+second,second+'>'+first)):
            raise ValueError('complete cycle lacks represented boundary compatibility')
        # Each alternative has ONE complete public path for all its trips. The
        # two possible FS cycle roots are compared separately, never mixed.
        patterns[first+'>'+second]={'edge_ids':loops[first]['edge_ids']+loops[second]['edge_ids'],
            'first_wing':first,'second_wing':second,'intermediate_fs_path_index':len(loops[first]['edge_ids']),
            'full_distance_km':length,'represented_midpoint_join':p['family']['joins'][first+'>'+second],
            'represented_terminal_join':p['family']['joins'][second+'>'+first],
            'full_history_legality_certified':False}
        minimum=5*math.ceil((adjusted_loops(loops,1.1,1.)[first]['road_minutes']+1)/5)
        for midpoint in range(minimum,minimum+31,5):
            case=solve_case(p,loops,first,midpoint);cases.append(case)
            print(first,midpoint,{k:case[k] for k in ('witness_found','full_trip_count','annual_service_km','nominal_vehicle_count') if k in case},flush=True)
    feasible=[c for c in cases if c['witness_found']]
    return {'contract':'RT031_UNIFORM_COMPLETE_PUBLIC_ROUTE_REBUILD_V3','authority_sha256':digest(AUTH),
        **source_fingerprints(p,loops),
        'source_geometry_confirmation':p['authority']['geometry_confirmation_source'],
        'full_route_patterns':patterns,'full_circuit_distance_km':length,
        'current_design_site_count_including_fs':29,'accepted_addition_ids':['N1212'],'rejected_addition_ids':['N0655'],
        'production_comparisons':[{'full_trips_per_day':n,'annual_service_km':n*length*260,
            'delta_vs_111419_km':n*length*260-111419} for n in (15,16,31)],
        'assumed_service_days':260,'annual_calendar_adopted':False,
        'cases':cases,'minimum_full_trip_count_in_examined_domain':min(c['full_trip_count'] for c in feasible) if feasible else None,
        'minimum_service_km_in_examined_domain':min(c['annual_service_km'] for c in feasible) if feasible else None,
        'all_examined_case_minima_proven':all(c.get('minimum_full_trip_count_proven') or c['infeasible_in_declared_domain'] for c in cases),
        'terminal_location_used_for_comparison':'FS cycle root, not an adopted physical terminal',
        'cross_terminal_passenger_continuation_certified':False,
        'domain':'Two alternative cyclic roots of the same directed eight, compared separately, never mixed in one timetable. For each, fixed intermediate FS departure offsets on five-minute grid from first feasible stress offset through +30 min (one H30 period); no global optimality claim beyond those offsets. Full public trips only. Inherited all-site ready H30 windows, 155/120 offpeak bounds, H60 edges and dated rail targets retained as explicit comparison constraints. Intermediate FS is a timed public call, not forced alighting or a second commercial trip. Terminal recovery 5/10/15 charged once per full trip; FS public dwell 0/0.5/1 uses existing deterministic sensitivity assumptions. Earlier origins needed to serve the second wing are disclosed, not adopted.',
        'current_final_proposal_status':'UNIFORM_INTENT_CORRECTED_NO_NEW_TIMETABLE_OR_BUDGET_ADOPTED',
        'earlier_31_wing_trip_plan_is_final_proposal':False,
        'physical_passenger_continuity_certified':False,'operating_plan_adopted':False,
        'decision_budget_km':None,'uncertainty_band_min':None,'network_selected':False,
        'primary_selection_authorised':False,'runner_up_selection_authorised':False}


def report(r):
    lines=['# Linea 8 — ripartenza corretta: ogni corsa percorre tutto l’otto','',
        '**Aggiornamento successivo:** il committente ha scelto 16 giri completi al giorno. '
        'Questo documento resta il confronto che precede la scelta; '
        '[audit dei 16 giri e dei buchi d’orario](RT031_LINEA8_16_GIRI_COMPLETI_V3.md).', '',
        '**Il chiarimento del committente sostituisce l’impostazione a corse d’ala indipendenti.** '
        'Una sola linea, **stesso percorso completo per ogni corsa commerciale**, entrambe le ali, '
        'nessuna variante pubblica limitata a FS. La stazione è anche fermata intermedia con permanenza '
        'a bordo prevista, non un cambio obbligatorio per passare nell’altra ala.',
        '',
        'La precedente proposta da **31 giri d’ala** non viene più presentata come soluzione finale. '
        'Non viene nemmeno trasformata in 31 giri completi: sarebbero circa 223.090 km/anno. '
        'I test precedenti restano prove del loro dominio, non prove che fosse soddisfatta questa richiesta.',
        '',
        '## Cosa rimane confermato','',
        '- Geometria stradale di base, Olgiate sud e San Zeno/Via Cantù inclusi.',
        '- Nuova fermata di progetto **Arlate/Via Nuova Provinciale**; esclusa N0655 in Via Indipendenza '
        'per la segnalazione del cavalcavia, senza spostamento automatico nelle immediate vicinanze.',
        '- **29 siti di progetto**, non paline fisiche autorizzate.',
        '- H30 nelle punte, utilità ferroviaria e intercomunale, attenzione al riferimento di 111.419 km. '
        'Il precedente assenso a +41,883 km per uno scenario diverso non è un nuovo budget generale.',
        '- Manovre e fermate fisiche si verificano successivamente; i relativi limiti non sono rimossi.','',
        '## Conti ora espressi in corse complete','',
        f"Un giro di entrambe le ali misura **{r['full_circuit_distance_km']:.6f} km**, senza nuove deviazioni. "
        'Il calendario da 260 giorni resta un’ipotesi comparativa, non il calendario approvato.',
        '',
        '| Giri completi al giorno | Km di servizio/anno | Scostamento da 111.419 |','|---|---:|---:|']
    for c in r['production_comparisons']:
        lines.append(f"| {c['full_trips_per_day']} | {c['annual_service_km']:.3f} | {c['delta_vs_111419_km']:+.3f} |")
    lines+=['',
        '**Questa tabella è aritmetica, non dimostra che 15 o 16 corse soddisfino frequenze e treni.** '
        'Nessuno di questi numeri è adottato come nuovo orario.',
        '',
        '## Primo orario ricostruito nel contratto corretto','',
        'Esaminate separatamente le due possibili partenze da FS sullo stesso otto diretto '
        '(prima ovest oppure prima est). **Ogni orario usa una sola sequenza, uguale per tutte le corse:** '
        'le due alternative non vengono mescolate. I percorsi completi, archi ordinati e passaggio '
        'intermedio a FS sono conservati nel file macchina.',
        '',
        'FS intermedia ha un orario di passaggio/partenza fissato. Il bus può arrivare prima e attendere '
        'con il passeggero a bordo: questo tempo è dichiarato, non eliminato dal viaggio. '
        'Il recupero di 5/10/15 minuti è ora confrontato **una volta per giro completo**, '
        'non automaticamente ad ogni ala. La sosta pubblica intermedia è distinta dal recupero. '
        'Sono assunzioni ingegneristiche da validare, non nuovi dati osservati.',
        '',
        'Nel confronto sono mantenuti, senza considerarli tutti preferenze esplicitamente scelte dall’utente:',
        '',
        '- H30 per sito verso/dalla stazione nelle finestre comuni 07–09 e 16:55–18:55;',
        '- attese massime ereditate 155/120 minuti, H60 alle estremità e servizio di riferimento 06:30–19:40;',
        '- tutti i precedenti treni-obiettivo, per tutti i siti: cambio ipotizzato di 3 minuti '
        'e attesa treno→bus di 3–8 minuti;',
        '- griglia corsa/sosta ereditata, senza trasformarla in probabilità empirica.','',
        '| Prima ala | Minuti da partenza iniziale a ripartenza intermedia FS | Minimo giri completi | Km/anno |',
        '|---|---:|---:|---:|']
    for c in r['cases']:
        if c.get('witness_found'):
            lines.append(f"| {'Ovest' if c['first_wing']=='west_B' else 'Est'} | {c['intermediate_fs_departure_offset_min']} | {c['full_trip_count']} | {c['annual_service_km']:.3f} |")
    lines+=['',
        f"**Minimo nel dominio esaminato: {r['minimum_full_trip_count_in_examined_domain']} giri completi, "
        f"{r['minimum_service_km_in_examined_domain']:.3f} km/anno.** Non è una proposta di aumento del budget. "
        'È la dimostrazione che non basta rietichettare il vecchio orario mantenendone tutte le condizioni.',
        '',
        'Il confronto usa partenze ogni cinque minuti e, per il passaggio intermedio, sette offset '
        'per ciascun ordine, dalla prima partenza compatibile con lo stress fino a +30 minuti. '
        'Non è un minimo globale su ogni possibile offset, capolinea o regola d’orario. '
        'I testimoni con meno corse possono iniziare il primo giro verso le 05:30 e terminare '
        'molto dopo l’ultima partenza: anche questo è esplicitato nel registro, **non approvato**. '
        'I mezzi calcolati sono quelli dei testimoni prodotti; non è stato ottimizzato separatamente il numero di mezzi fra tutti gli orari con lo stesso numero di corse.',
        '',
        'La radice a FS è usata per questo confronto, non decide già il capolinea fisico. '
        'Attraversare FS **all’interno** della corsa completa è diverso da restare a bordo '
        'fra due corse complete successive: quest’ultima continuità va esplicitata nei blocchi mezzo, '
        'non dedotta dal nome della linea. Non si promettono tutti i viaggi intercomunali senza cambio '
        'sulla sola base dell’identità del percorso.',
        '',
        '## Passo successivo circoscritto','',
        '**Riesaminare le condizioni temporali ereditate, non tornare a due servizi o introdurre corse corte.** '
        'In particolare distinguere l’obiettivo H30 in punta dalla scelta tecnica di finestre identiche '
        'al minuto per ogni sito, e l’integrazione ferroviaria dall’obbligo di servire tutti gli stessi '
        'treni da entrambe le ali con una finestra di soli 3–8 minuti. '
        'Queste scelte vanno confrontate con i tempi intercomunali, mantenendo visibile cosa si guadagna e cosa si perde. '
        'Nessuna riduzione di H30, rinuncia ai treni, modifica della geometria o maggiorazione di budget è adottata qui.',
        '',
        '[Contratto corretto del committente](../config/rt031_uniform_complete_line_authority_v3.json) · '
        '[Percorsi completi, orari e prove (JSON gzip)](../outputs/phase2/rt031_line8_local_shortcuts_v3/uniform_complete_line_rebuild.json.gz)',
        '',
        'Rigenerazione: `python -m scripts.phase2_rebuild_rt031_uniform_complete_line_v3` con `PYTHONPATH` '
        'su radice e `src`. Le prove usano il grafo e i tempi già fissati nelle fonti precedenti; '
        'nessuna autorizzazione stradale, di palina o di esercizio viene dedotta dal risolutore.']
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    r=build()
    OUTPUT.write_bytes(gzip.compress((json.dumps(r,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8'),mtime=0))
    DOC.write_text(report(r),encoding='utf-8')
