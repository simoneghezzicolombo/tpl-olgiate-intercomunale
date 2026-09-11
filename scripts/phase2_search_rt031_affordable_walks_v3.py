"""Real-data physical walk search and conditional walking-access comparison."""
import argparse
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
from pathlib import Path
import pandas as pd
from scripts.phase2_audit_rt031_real_pairwise_compatible_domain_v3 import (
    load_inputs,validate_via_way_evidence,sha256_file,canonical,
    build_realization_catalog,build_boundary_catalog,FrozenRT017ViaNodeAdapter,
    RT023ScopedTransitionOracle,build_pairwise_compatibility)
from scripts.phase2_screen_rt031_resource_budget_v3 import PINNED
from src.phase2_rt031_budgeted_walk_search_v3 import search_walks
from src.phase2_rt031_rt023_physical_compatible_domain_v3 import evaluate_realization_chain,LEGAL
from phase2_rt029_v4_substrate import validate_walk_matrix
from phase2_rt029_v4_metrics import evaluate_unique_stop_sets


def main(inputs,evidence,walk_file,out,max_expansions):
    tables,hashes=load_inputs(inputs);validate_via_way_evidence(evidence)
    for path,digest in PINNED.items():
        if sha256_file(Path(path))!=digest:raise ValueError('approved policy lineage changed')
    policy=json.loads(Path('config/phase2_final_policy_contract_v3.json').read_text())
    cap=Decimal(str(policy['human_policy_decisions']['annual_bus_km_cap']))
    # Broadest distance envelope in the existing frequent-service grid. These
    # service assumptions are explicit, not a selected final operating calendar.
    budget=cap*1000/(32*260)
    cat,slots=build_realization_catalog(tables['patterns'],tables['corridors'],tables['edges'])
    boundary=build_boundary_catalog(tables['patterns'],tables['occurrences'],tables['corridors'],tables['edges'])
    adapter=FrozenRT017ViaNodeAdapter(tables['edges'],tables['rules'],unresolved_external_via_way_count=2)
    scoped=RT023ScopedTransitionOracle(adapter,sorted({e for r in cat.values() for e in r['edge_ids']}),
        successor_via_way_irrelevance_certified=True,evidence_id='RT031_SUCCESSOR_VIA_WAY::'+sha256_file(evidence))
    for r in cat.values():
        if evaluate_realization_chain([r],boundary,scoped.oracle)['status']!=LEGAL:raise ValueError('atomic legality open')
    pairs=build_pairwise_compatibility(cat,boundary,scoped.oracle,history_locality_certified=True)
    edges={r['edge_id']:r for r in tables['edges']}
    weights={rid:sum((Decimal(edges[e]['length_m']) for e in r['edge_ids']),Decimal(0)) for rid,r in cat.items()}
    stop_sets={r['realization_id']:r['ordered_passenger_stop_ids'].split(';') for r in tables['patterns']}
    result=search_walks(cat,pairs,weights,stop_sets,budget_m=budget,max_expansions=max_expansions,
        history_locality_certified=True,atomic_legality_certified=True)
    if not result['candidates']:raise ValueError('no closed walk found within execution budget')
    for r in result['candidates']:
        selected=[cat[rid] for rid in r['realization_ids']]
        if evaluate_realization_chain(selected+[selected[0]],boundary,scoped.oracle)['status']!=LEGAL:
            raise AssertionError('closed witness fails independent full-history replay')
        if set(r['available_stop_ids'])!=set().union(*(set(stop_sets[rid]) for rid in r['realization_ids'])):
            raise AssertionError('availability union drift')
        r['stop_set_id']='WALK_'+hashlib.sha256(';'.join(r['available_stop_ids']).encode()).hexdigest()[:20]
        r['conditional_annual_carrier_km_h30_260days']=str(Decimal(r['minimum_found_distance_m'])*32*260/1000)
        running=sum((Decimal(edges[e]['running_minutes_model']) for rid in r['realization_ids'] for e in cat[rid]['edge_ids']),Decimal(0))
        if not running.is_finite() or running<=0:raise ValueError('invalid source running model')
        r['running_minutes_source_model']=str(running)
        r['running_time_status']='SOURCE_MODEL_NOT_OBSERVED_EXCLUDES_DWELL'
        r['fleet_lower_bound_source_model_by_recovery']={str(recovery):int(((running+recovery)/30).to_integral_value(rounding=ROUND_CEILING)) for recovery in (5,10,15)}
        r['vehicle_block_plan_certified']=False
    walk=validate_walk_matrix(pd.read_csv(walk_file))
    membership=pd.DataFrame([dict(stop_set_id=r['stop_set_id'],ordered_stop_place_ids=';'.join(r['available_stop_ids'])) for r in result['candidates']])
    access,municipality,equity=evaluate_unique_stop_sets(membership,walk)
    core=access[access['scope']=='CORE'].set_index('stop_set_id')
    eq=equity.pivot(index='stop_set_id',columns='threshold_min',values='minimum_core_municipality_share')
    summary=[]
    for r in result['candidates']:
        sid=r['stop_set_id'];row=dict(stop_set_id=sid,available_stop_count=len(r['available_stop_ids']),
            carrier_distance_m=r['minimum_found_distance_m'],
            conditional_annual_carrier_km_h30_260days=r['conditional_annual_carrier_km_h30_260days'],
            running_minutes_source_model=r['running_minutes_source_model'],
            model_fleet_lower_bound_recovery5=r['fleet_lower_bound_source_model_by_recovery']['5'],
            model_fleet_lower_bound_recovery10=r['fleet_lower_bound_source_model_by_recovery']['10'],
            model_fleet_lower_bound_recovery15=r['fleet_lower_bound_source_model_by_recovery']['15'])
        for t in (5,8,10,12):
            row[f'potential_core_share_{t}min']=float(core.loc[sid,f'share_le_{t}_min'])
            row[f'potential_worst_municipality_share_{t}min']=float(eq.loc[sid,t])
        summary.append(row)
    # Nondominance within evaluated walks only: six existing territorial axes
    # plus exact physical distance. No weighted score and no final service rank.
    def vector(r):
        return tuple(r[f'potential_{scope}_share_{t}min'] for scope in ('core','worst_municipality') for t in (5,8,10))
    def dominates(a,b):
        av,bv=vector(a),vector(b);ad,bd=Decimal(a['carrier_distance_m']),Decimal(b['carrier_distance_m'])
        return all(x>=y for x,y in zip(av,bv)) and ad<=bd and (av!=bv or ad<bd)
    frontier=[]
    for row in sorted(summary,key=lambda r:(Decimal(r['carrier_distance_m']),r['stop_set_id'])):
        if any(dominates(other,row) for other in frontier):continue
        frontier=[other for other in frontier if not dominates(row,other)]+[row]
    out.mkdir(parents=True,exist_ok=True)
    for name,frame in [('conditional_access.csv',access),('conditional_municipality_access.csv',municipality),
        ('conditional_equity.csv',equity),('physical_candidate_comparison.csv',pd.DataFrame(summary)),
        ('evaluated_set_conditional_frontier.csv',pd.DataFrame(frontier))]:frame.to_csv(out/name,index=False,lineterminator='\n')
    result.update(input_sha256=hashes,via_way_evidence_sha256=sha256_file(evidence),walk_matrix_sha256=sha256_file(walk_file),
        policy_sha256=PINNED,calendar_is_design_assumption=True,conditional_headway_min=30,
        conditional_departure_window='06:00-22:00_HALF_OPEN',conditional_annual_days=260,
        coverage_semantics='CONDITIONAL_WALKING_ACCESS_IF_AVAILABLE_STOPS_BECOME_PUBLICLY_SERVED_NOT_CERTIFIED_PASSENGER_SERVICE',
        evaluated_set_frontier_size=len(frontier),maximum_available_stop_count=max(r['available_stop_count'] for r in summary),
        final_recommendation=False)
    (out/'physical_walk_search.json').write_bytes(canonical(result))
    audit={k:v for k,v in result.items() if k!='candidates'}
    (out/'search_audit.json').write_bytes(canonical(audit));print(json.dumps(audit,sort_keys=True))
    # Full comparisons are exported; examples are descriptive extrema, not ranking.
    for field in ('available_stop_count','potential_core_share_10min','potential_worst_municipality_share_10min'):
        row=max(summary,key=lambda r:(r[field],r['stop_set_id']))
        print(json.dumps({'descriptive_extremum':field,'row':row},sort_keys=True))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--via-way-evidence',type=Path,required=True);p.add_argument('--walk-matrix',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--max-expansions',type=int,default=250000)
    a=p.parse_args();main(a.inputs,a.via_way_evidence,a.walk_matrix,a.out,a.max_expansions)
