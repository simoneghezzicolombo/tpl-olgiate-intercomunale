#!/usr/bin/env python3
"""Audit duplicate operational identities on the robust Phase 2 frontier V2.

A topology-family label is not a distinct service if the public route sequences,
route-specific clock phases, headway, span and calendar are identical. This
builder groups such plans without preferring any family. It fails closed if two
members of one operational identity disagree on passenger, robustness or
resource metrics that should be invariant to a mere label alias.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

STATUS = "PASS_ROBUST_SERVICE_IDENTITY_AUDIT_V2"
CONTRACT = "PHASE2_ROBUST_SERVICE_IDENTITY_V2"


def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def stable_id(payload) -> str:
    text=json.dumps(payload,sort_keys=True,separators=(',',':'))
    return 'P2SERVICE_'+hashlib.sha256(text.encode()).hexdigest()[:16]


def load_rows(path: Path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument('--frontier',type=Path,required=True)
    p.add_argument('--robust-validation',type=Path,required=True)
    p.add_argument('--exact-plans',type=Path,required=True)
    p.add_argument('--exact-validation',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--validation',type=Path,required=True)
    args=p.parse_args()

    rv=json.loads(args.robust_validation.read_text())
    ev=json.loads(args.exact_validation.read_text())
    if rv.get('status')!='PASS_ROBUSTNESS_TOURNAMENT_V2_BUILD' or rv.get('lineage',{}).get('frontier_output_sha256')!=sha(args.frontier):
        raise ValueError('Robustness frontier is not certified')
    if ev.get('status')!='PASS_BASE_EXACT_TIMETABLES_V2_BUILD' or ev.get('lineage',{}).get('plan_output_sha256')!=sha(args.exact_plans):
        raise ValueError('Exact plans are not certified')
    if rv.get('primary_selected') is not False or rv.get('runner_up_selected') is not False:
        raise ValueError('Robust frontier already contains final selection')

    frontier=load_rows(args.frontier)
    exact={row['plan_id']:row for row in load_rows(args.exact_plans)}
    if len(frontier)!=int(rv['robust_frontier_union_count']):
        raise ValueError('Robust frontier count mismatch')
    if any(row['plan_id'] not in exact for row in frontier):
        raise ValueError('Robust frontier plan missing from exact-plan catalog')

    invariant_fields=[
        'uniform_headway_min','span_id','span_minutes','calendar_id','annual_service_days','exact_annual_bus_km','public_route_count',
        'public_population_coverage_share_5min','public_population_coverage_share_8min','public_population_coverage_share_10min',
        'public_worst_municipality_coverage_share_5min','public_worst_municipality_coverage_share_8min','public_worst_municipality_coverage_share_10min',
        'public_structurally_addressable_worker_od_mass_upper_bound','stress_min_connection_match_share','stress_median_connection_match_share',
        'stress_max_unmatched_connection_event_count','stress_max_incomplete_route_count','stress_worst_route_weighted_mean_gap_min',
        'stress_max_fleet_recovery15','public_explicit_existing_stop_count','public_explicit_proposed_stop_count','public_explicit_field_check_pending_count'
    ]
    groups=defaultdict(list)
    identities={}
    for row in frontier:
        ex=exact[row['plan_id']]
        phases=json.loads(ex['candidate_route_phases_json'])
        route_phase=sorted((str(route_id),int(phase)) for route_id,phase in phases.items())
        payload={
            'route_phase':route_phase,
            'uniform_headway_min':int(row['uniform_headway_min']),
            'span_id':row['span_id'],
            'calendar_id':row['calendar_id'],
        }
        sid=stable_id(payload)
        identities[sid]=payload
        groups[sid].append(row)

    output_rows=[]
    alias_group_count=0
    cross_family_alias_group_count=0
    for sid,members in sorted(groups.items()):
        base=members[0]
        mismatches=[]
        for other in members[1:]:
            for field in invariant_fields:
                if base[field]!=other[field]:
                    mismatches.append((other['plan_id'],field,base[field],other[field]))
        if mismatches:
            raise ValueError(f'Operational identity {sid} has invariant metric mismatch: {mismatches[:5]}')
        families=sorted({row['topology_family'] for row in members})
        if len(members)>1:
            alias_group_count+=1
        if len(families)>1:
            cross_family_alias_group_count+=1
        output_rows.append({
            'service_identity_id':sid,
            'representative_plan_id':min(row['plan_id'] for row in members),
            'plan_alias_count':len(members),
            'scenario_alias_count':len({row['scenario_id'] for row in members}),
            'topology_family_alias_count':len(families),
            'topology_families_json':json.dumps(families,separators=(',',':')),
            'plan_ids_json':json.dumps(sorted(row['plan_id'] for row in members),separators=(',',':')),
            'scenario_ids_json':json.dumps(sorted({row['scenario_id'] for row in members}),separators=(',',':')),
            'route_phases_json':json.dumps(identities[sid]['route_phase'],separators=(',',':')),
            'uniform_headway_min':base['uniform_headway_min'],
            'span_id':base['span_id'],
            'calendar_id':base['calendar_id'],
            'robust_frontier_classes':base['robust_frontier_classes'],
            **{field:base[field] for field in invariant_fields if field not in {'uniform_headway_min','span_id','calendar_id'}},
            'operational_identity_metrics_invariant':'true',
            'family_label_used_to_select_representative':'false',
            'primary_selected':'false',
            'runner_up_selected':'false',
        })

    fields=list(output_rows[0])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n')
        w.writeheader(); w.writerows(output_rows)

    family_signature_counts=Counter()
    for row in output_rows:
        families=tuple(json.loads(row['topology_families_json']))
        family_signature_counts['+'.join(families)]+=1
    report={
        'status':STATUS,
        'contract':CONTRACT,
        'robust_frontier_plan_count':len(frontier),
        'unique_operational_service_identity_count':len(output_rows),
        'duplicate_plan_alias_count':len(frontier)-len(output_rows),
        'multi_plan_alias_group_count':alias_group_count,
        'cross_family_alias_group_count':cross_family_alias_group_count,
        'family_alias_signature_counts':dict(sorted(family_signature_counts.items())),
        'operational_identity_key':'SORTED_ROUTE_ID_PLUS_SELECTED_CLOCK_PHASE__HEADWAY__SPAN__CALENDAR',
        'metric_invariance_checked':True,
        'family_label_used_to_select_representative':False,
        'weighted_composite_score_used':False,
        'topology_ranked':False,
        'service_policy_selected':False,
        'primary_selected':False,
        'runner_up_selected':False,
        'lineage':{
            'robust_frontier_sha256':sha(args.frontier),
            'robust_validation_sha256':sha(args.robust_validation),
            'exact_plans_sha256':sha(args.exact_plans),
            'exact_validation_sha256':sha(args.exact_validation),
            'output_sha256':sha(args.output),
        },
        'epistemic_note':'This audit removes label aliases only. Two plans are one operational identity only when their exact public route IDs, selected route phases, headway, span and calendar match and all declared invariant metrics are identical. No topology family is preferred.'
    }
    args.validation.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2,sort_keys=True))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
