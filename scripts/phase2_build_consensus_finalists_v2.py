#!/usr/bin/env python3
"""Build decision-rule sensitivity finalists from service-adjusted accessibility V2.

No single compromise score is privileged. The script evaluates several fully
disclosed normalized decision rules over the three territorial accessibility
utility dimensions and reports the union/intersection of exact rule winners.
S8 robustness is then reported as a separate Pareto screen inside that small
winner union. This gate still does not select PRIMARY or RUNNER-UP.
"""
from __future__ import annotations

import argparse,csv,hashlib,json,math
from collections import Counter
from pathlib import Path

from src.phase2_robustness_tournament_v2 import nondominated_indices

STATUS='PASS_CONSENSUS_FINALISTS_V2_BUILD'
CONTRACT='PHASE2_DECISION_RULE_SENSITIVITY_FINALISTS_V2'
AXES=(
 'resident_access_service_opportunity_index',
 'worst_municipality_access_service_opportunity_index',
 'territorial_worker_od_service_opportunity_upper_bound',
)
EPS=1e-12


def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def rows(path):
 with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def winners_max(rows,key):
 best=max(key(r) for r in rows);return {r['representative_service_identity_id'] for r in rows if abs(key(r)-best)<=EPS},best

def winners_min(rows,key):
 best=min(key(r) for r in rows);return {r['representative_service_identity_id'] for r in rows if abs(key(r)-best)<=EPS},best


def main():
 p=argparse.ArgumentParser();p.add_argument('--utility',type=Path,required=True);p.add_argument('--utility-validation',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--validation',type=Path,required=True);a=p.parse_args()
 uv=json.loads(a.utility_validation.read_text())
 if uv.get('status')!='PASS_ACCESSIBILITY_UTILITY_FRONTIER_V2_BUILD' or uv.get('lineage',{}).get('output_sha256')!=sha(a.utility):raise ValueError('Accessibility utility V2 not certified')
 if any(uv.get(k) is not False for k in ('weighted_composite_score_used','primary_selected','runner_up_selected')):raise ValueError('Utility upstream violates selection boundary')
 data=rows(a.utility)
 if len(data)!=int(uv['input_decision_stratum_count']):raise ValueError('Utility input count mismatch')
 for r in data:
  for x in AXES:
   r[x]=float(r[x])
  r['stress_min_connection_match_share']=float(r['stress_min_connection_match_share'])
  r['stress_worst_route_weighted_mean_gap_min']=float(r['stress_worst_route_weighted_mean_gap_min'])

 # Territorial-only Pareto removes S8 from primary territorial utility rather than privileging rail feeding.
 tidx=set(nondominated_indices(data,maximize=AXES,minimize=()))
 territorial=[r for i,r in enumerate(data) if i in tidx]
 maxima={x:max(r[x] for r in territorial) for x in AXES}
 if any(v<=0 for v in maxima.values()):raise ValueError('Territorial utility ideal point is non-positive')
 for r in territorial:
  r['_n_resident']=r[AXES[0]]/maxima[AXES[0]]
  r['_n_worst']=r[AXES[1]]/maxima[AXES[1]]
  r['_n_od']=r[AXES[2]]/maxima[AXES[2]]
  r['_rule_maximin_total_od']=min(r['_n_resident'],r['_n_od'])
  r['_rule_maximin_balanced']=min(r['_n_resident'],r['_n_worst'],r['_n_od'])
  r['_rule_geomean_balanced']=(r['_n_resident']*r['_n_worst']*r['_n_od'])**(1/3) if r['_n_resident']*r['_n_worst']*r['_n_od']>0 else 0.0
  r['_rule_arithmetic_balanced']=(r['_n_resident']+r['_n_worst']+r['_n_od'])/3
  r['_rule_l2_ideal']=math.sqrt((1-r['_n_resident'])**2+(1-r['_n_worst'])**2+(1-r['_n_od'])**2)

 rules={}
 rules['MAXIMIN_TOTAL_ACCESS_OD'],_=winners_max(territorial,lambda r:r['_rule_maximin_total_od'])
 rules['MAXIMIN_BALANCED'],_=winners_max(territorial,lambda r:r['_rule_maximin_balanced'])
 rules['GEOMETRIC_MEAN_BALANCED'],_=winners_max(territorial,lambda r:r['_rule_geomean_balanced'])
 rules['ARITHMETIC_MEAN_BALANCED'],_=winners_max(territorial,lambda r:r['_rule_arithmetic_balanced'])
 rules['MIN_L2_DISTANCE_TO_TERRITORIAL_IDEAL'],_=winners_min(territorial,lambda r:r['_rule_l2_ideal'])
 union=set().union(*rules.values()); intersection=set.intersection(*rules.values())
 union_rows=[r for r in territorial if r['representative_service_identity_id'] in union]
 s8idx=set(nondominated_indices(union_rows,maximize=('stress_min_connection_match_share',),minimize=('stress_worst_route_weighted_mean_gap_min',)))
 s8_nondominated={union_rows[i]['representative_service_identity_id'] for i in s8idx}

 output=[]
 for r in territorial:
  service=r['representative_service_identity_id']; won=sorted(name for name,ids in rules.items() if service in ids)
  output.append({
   'representative_service_identity_id':service,'representative_plan_id':r['representative_plan_id'],
   'topology_family_aliases_json':r['topology_family_aliases_json'],'uniform_headway_min':r['uniform_headway_min'],'span_id':r['span_id'],'calendar_id':r['calendar_id'],
   **{x:f"{r[x]:.12f}" for x in AXES},
   'normalized_resident_achievement':f"{r['_n_resident']:.12f}",'normalized_worst_municipality_achievement':f"{r['_n_worst']:.12f}",'normalized_od_achievement':f"{r['_n_od']:.12f}",
   'maximin_total_access_od_score':f"{r['_rule_maximin_total_od']:.12f}",'maximin_balanced_score':f"{r['_rule_maximin_balanced']:.12f}",'geometric_mean_balanced_score':f"{r['_rule_geomean_balanced']:.12f}",'arithmetic_mean_balanced_score':f"{r['_rule_arithmetic_balanced']:.12f}",'l2_distance_to_territorial_ideal':f"{r['_rule_l2_ideal']:.12f}",
   'decision_rules_won_json':json.dumps(won,separators=(',',':')),'decision_rule_win_count':len(won),
   'decision_rule_winner_union_member':str(service in union).lower(),'decision_rule_unanimous_winner_member':str(service in intersection).lower(),
   's8_nondominated_within_rule_winner_union':str(service in s8_nondominated).lower(),
   'stress_min_connection_match_share':f"{r['stress_min_connection_match_share']:.12f}",'stress_worst_route_weighted_mean_gap_min':f"{r['stress_worst_route_weighted_mean_gap_min']:.12f}",
   'exact_annual_bus_km':r['exact_annual_bus_km'],'stress_max_fleet_recovery15':r['stress_max_fleet_recovery15'],'public_route_count':r['public_route_count'],'public_explicit_field_check_pending_count':r['public_explicit_field_check_pending_count'],
   'single_decision_rule_privileged':'false','primary_selected':'false','runner_up_selected':'false'
  })
 fields=list(output[0]);a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(sorted(output,key=lambda r:r['representative_service_identity_id']))
 fam=Counter();heads=Counter()
 for r in union_rows:
  fam['+'.join(json.loads(r['topology_family_aliases_json']))]+=1;heads[int(float(r['uniform_headway_min']))]+=1
 report={
  'status':STATUS,'contract':CONTRACT,'input_accessibility_utility_count':len(data),'territorial_utility_frontier_count':len(territorial),
  'decision_rule_count':len(rules),'decision_rule_winner_counts':{k:len(v) for k,v in rules.items()},'decision_rule_winners':{k:sorted(v) for k,v in rules.items()},
  'decision_rule_winner_union_count':len(union),'decision_rule_winner_union_ids':sorted(union),'decision_rule_unanimous_intersection_count':len(intersection),'decision_rule_unanimous_intersection_ids':sorted(intersection),
  's8_nondominated_within_winner_union_count':len(s8_nondominated),'s8_nondominated_within_winner_union_ids':sorted(s8_nondominated),
  'winner_union_family_alias_signature_counts':dict(sorted(fam.items())),'winner_union_headway_counts':dict(sorted(heads.items())),
  'normalization':'EACH_TERRITORIAL_UTILITY_AXIS_DIVIDED_BY_FEASIBLE_TERRITORIAL_FRONTIER_MAXIMUM; ZERO_REMAINS_ZERO',
  'decision_rules':{
   'MAXIMIN_TOTAL_ACCESS_OD':'MAXIMISE_MIN(NORMALIZED_RESIDENT_ACCESS,NORMALIZED_OD); WORST-MUNICIPALITY EQUITY REMAINS SAFEGUARD/DIAGNOSTIC',
   'MAXIMIN_BALANCED':'MAXIMISE_MIN(NORMALIZED_RESIDENT_ACCESS,NORMALIZED_WORST_MUNICIPALITY_ACCESS,NORMALIZED_OD)',
   'GEOMETRIC_MEAN_BALANCED':'MAXIMISE_EQUAL-EXPONENT GEOMETRIC MEAN OF THREE NORMALIZED TERRITORIAL AXES',
   'ARITHMETIC_MEAN_BALANCED':'MAXIMISE EQUAL-WEIGHT ARITHMETIC MEAN OF THREE NORMALIZED TERRITORIAL AXES',
   'MIN_L2_DISTANCE_TO_TERRITORIAL_IDEAL':'MINIMISE EUCLIDEAN DISTANCE TO (1,1,1) IN NORMALIZED TERRITORIAL UTILITY SPACE'
  },
  'single_decision_rule_privileged':False,'s8_used_inside_territorial_compromise_score':False,'weighted_composite_score_used_for_final_selection':False,'full_gjt_calculated':False,'topology_ranked':False,'service_policy_selected':False,'primary_selected':False,'runner_up_selected':False,
  'lineage':{'utility_sha256':sha(a.utility),'utility_validation_sha256':sha(a.utility_validation),'output_sha256':sha(a.output)},
  'epistemic_note':'Compromise scores are explicit decision-rule sensitivity diagnostics, not one privileged hidden score. The gate asks whether materially different neutral compromise rules converge. S8 robustness is kept separate and only Pareto-screened within the union of territorial rule winners.'
 }
 a.validation.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps(report,indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
