#!/usr/bin/env python3
"""Build a conservative service-adjusted accessibility utility frontier V2.

For each robust passenger decision stratum, exact clockface phases determine the
minimum departures/day offered by any public route pattern. Walking access is
summarised as the trapezoidal area under the certified 5/8/10-minute coverage
curve. Multiplying that dimensionless access AUC by minimum annual route
opportunities yields a transparent service-adjusted accessibility index.

The same transformation is applied to the worst-municipality access curve and
to the structural worker-OD mass upper bound. These are accessibility/service
opportunity indices, not passenger trips, modal shares or full GJT.
"""
from __future__ import annotations

import argparse,csv,hashlib,json,math
from collections import Counter
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from src.phase2_exact_timetable_v2 import clockface_departures
from src.phase2_robustness_tournament_v2 import nondominated_indices

STATUS='PASS_ACCESSIBILITY_UTILITY_FRONTIER_V2_BUILD'
CONTRACT='PHASE2_SERVICE_ADJUSTED_ACCESSIBILITY_UTILITY_V2'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def rows(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def auc_5_10(v5,v8,v10):
    # Trapezoidal mean coverage over the actual threshold intervals 5→8 (3 min)
    # and 8→10 (2 min), normalized by the five-minute domain width.
    return (((v5+v8)/2.0)*3.0+((v8+v10)/2.0)*2.0)/5.0


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--strata',type=Path,required=True)
    p.add_argument('--strata-validation',type=Path,required=True)
    p.add_argument('--exact-plans',type=Path,required=True)
    p.add_argument('--exact-validation',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--frontier-output',type=Path,required=True)
    p.add_argument('--validation',type=Path,required=True)
    a=p.parse_args()
    sv=json.loads(a.strata_validation.read_text()); ev=json.loads(a.exact_validation.read_text())
    if sv.get('status')!='PASS_DECISION_STRATA_V2_BUILD' or sv.get('lineage',{}).get('output_sha256')!=sha(a.strata):raise ValueError('Decision strata not certified')
    if ev.get('status')!='PASS_BASE_EXACT_TIMETABLES_V2_BUILD' or ev.get('lineage',{}).get('plan_output_sha256')!=sha(a.exact_plans):raise ValueError('Exact plans not certified')
    if sv.get('non_equivalent_strata_ranked') is not False:raise ValueError('Upstream improperly ranked non-equivalent strata')
    data=rows(a.strata); exact={r['plan_id']:r for r in rows(a.exact_plans)}
    if len(data)!=int(sv['unique_robust_passenger_metric_stratum_count']):raise ValueError('Strata count mismatch')
    out=[]
    for row in data:
        plan=exact[row['representative_plan_id']]
        phases=json.loads(plan['candidate_route_phases_json'])
        if not phases:raise ValueError('Exact phase vector empty')
        departure_counts=[]
        for phase in phases.values():
            departure_counts.append(len(clockface_departures(
                phase_min=int(phase),headway_min=int(row['uniform_headway_min']),
                span_start_min=int(plan['span_start_min']),span_end_min=int(plan['span_end_min'])
            )))
        min_departures_day=min(departure_counts)
        annual_min=min_departures_day*int(row['annual_service_days'])
        access_auc=auc_5_10(float(row['public_population_coverage_share_5min']),float(row['public_population_coverage_share_8min']),float(row['public_population_coverage_share_10min']))
        worst_auc=auc_5_10(float(row['public_worst_municipality_coverage_share_5min']),float(row['public_worst_municipality_coverage_share_8min']),float(row['public_worst_municipality_coverage_share_10min']))
        od=float(row['public_structurally_addressable_worker_od_mass_upper_bound'])
        out.append({
            **row,
            'minimum_public_pattern_departures_per_service_day':min_departures_day,
            'minimum_public_pattern_departures_per_year':annual_min,
            'population_access_auc_5_10':access_auc,
            'worst_municipality_access_auc_5_10':worst_auc,
            'resident_access_service_opportunity_index':access_auc*annual_min,
            'worst_municipality_access_service_opportunity_index':worst_auc*annual_min,
            'territorial_worker_od_service_opportunity_upper_bound':od*annual_min,
            'accessibility_utility_is_passenger_trip_count':'false',
            'accessibility_utility_is_modal_share':'false',
            'weighted_composite_score_used':'false',
            'primary_selected':'false','runner_up_selected':'false'
        })
    maximize=(
        'resident_access_service_opportunity_index',
        'worst_municipality_access_service_opportunity_index',
        'territorial_worker_od_service_opportunity_upper_bound',
        'stress_min_connection_match_share',
    )
    minimize=('stress_worst_route_weighted_mean_gap_min',)
    idx=set(nondominated_indices(out,maximize=maximize,minimize=minimize))
    frontier=[]
    for i,row in enumerate(out):
        row['accessibility_utility_frontier_member']=str(i in idx).lower()
        if i in idx:frontier.append(row)
    fields=list(out[0])
    a.output.parent.mkdir(parents=True,exist_ok=True)
    for path,data_rows in ((a.output,out),(a.frontier_output,frontier)):
        with path.open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(data_rows)
    h=Counter(int(float(r['uniform_headway_min'])) for r in frontier)
    fam=Counter('+'.join(json.loads(r['topology_family_aliases_json'])) for r in frontier)
    report={
        'status':STATUS,'contract':CONTRACT,
        'input_decision_stratum_count':len(out),'frontier_count':len(frontier),
        'frontier_headway_counts':dict(sorted(h.items())),
        'frontier_family_alias_signature_counts':dict(sorted(fam.items())),
        'walking_access_summary':'TRAPEZOIDAL_MEAN_COVERAGE_SHARE_OVER_5_TO_10_MINUTES_USING_CERTIFIED_5_8_10_THRESHOLDS',
        'service_availability_summary':'MINIMUM_EXACT_CLOCKFACE_DEPARTURES_OF_ANY_PUBLIC_PATTERN_PER_YEAR',
        'dominance_axes':{'maximize':list(maximize),'minimize':list(minimize)},
        'accessibility_utility_is_passenger_trip_count':False,'accessibility_utility_is_modal_share':False,
        'worker_od_service_opportunity_is_upper_bound':True,'full_gjt_calculated':False,
        'weighted_composite_score_used':False,'topology_ranked':False,'service_policy_selected':False,'primary_selected':False,'runner_up_selected':False,
        'lineage':{
            'strata_sha256':sha(a.strata),'strata_validation_sha256':sha(a.strata_validation),
            'exact_plans_sha256':sha(a.exact_plans),'exact_validation_sha256':sha(a.exact_validation),
            'output_sha256':sha(a.output),'frontier_output_sha256':sha(a.frontier_output)
        },
        'epistemic_note':'Service-adjusted accessibility indices multiply certified spatial accessibility or structural OD mass by the minimum exact annual route-pattern opportunities. They are deterministic accessibility indices, not passenger counts. S8 robust match/gap remains a separate frontier dimension rather than a weight inside the access index.'
    }
    a.validation.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2,sort_keys=True));return 0

if __name__=='__main__':raise SystemExit(main())
