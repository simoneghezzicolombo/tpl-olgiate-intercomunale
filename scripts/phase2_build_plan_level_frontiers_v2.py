#!/usr/bin/env python3
"""Build exact non-dominated plan-level frontiers from the certified shortlist.

Base-public plans and positive scheduled-extension plans are kept epistemically
separate. Base frontiers use realised public structural metrics. Extension
frontiers use the certified all-extension-anchors structural upper bound and are
therefore candidate-preservation devices, not realised accessibility claims.

No scalar score, topology rank, S8 phase, exact timetable, PRIMARY or RUNNER-UP
is produced.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

STATUS = "PASS_PLAN_LEVEL_FRONTIERS_V2_BUILD"
CONTRACT = "PHASE2_PLAN_LEVEL_FRONTIERS_V2"


def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def b(text: str) -> bool:
    if text == 'true': return True
    if text == 'false': return False
    raise ValueError(f'Invalid boolean {text!r}')


def signature(row: dict[str,str], *, extension_upper_bound: bool) -> tuple[float,...]:
    pfx='public_plus_extensions' if extension_upper_bound else 'public'
    # First six axes are maximised, last three minimised.
    return (
        float(row[f'{pfx}_population_coverage_share_10min']),
        float(row[f'{pfx}_worst_municipality_coverage_share_10min']),
        float(row[f'{pfx}_structurally_addressable_worker_od_mass_upper_bound']),
        float(row['s8_public_complete_match_route_share']),
        float(row['span_minutes']),
        float(row['annual_service_days']),
        float(row['uniform_headway_min']),
        float(row['annual_bus_km']),
        float(row['fleet_lower_bound_recovery15']),
    )


def dominates(a: tuple[float,...], c: tuple[float,...]) -> bool:
    weak = all(a[i] >= c[i] for i in range(6)) and all(a[i] <= c[i] for i in range(6,9))
    return weak and a != c


def frontier_signatures(rows: list[dict[str,str]], *, extension_upper_bound: bool) -> set[tuple[float,...]]:
    unique=list({signature(row, extension_upper_bound=extension_upper_bound) for row in rows})
    # Cheap pre-order: strong high-access/low-headway points are tested early.
    unique.sort(key=lambda x:(-x[0],-x[1],-x[2],-x[3],x[6],x[7],x[8],-x[4],-x[5]))
    keep=set()
    for i, point in enumerate(unique):
        if not any(j != i and dominates(other, point) for j, other in enumerate(unique)):
            keep.add(point)
    return keep


def load_rows(path: Path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader=csv.DictReader(f)
        required={
            'plan_id','scenario_id','topology_family','extension_share','uniform_headway_min','span_minutes',
            'annual_service_days','annual_bus_km','fleet_lower_bound_recovery15',
            'public_population_coverage_share_10min','public_worst_municipality_coverage_share_10min',
            'public_structurally_addressable_worker_od_mass_upper_bound',
            'public_plus_extensions_population_coverage_share_10min',
            'public_plus_extensions_worst_municipality_coverage_share_10min',
            'public_plus_extensions_structurally_addressable_worker_od_mass_upper_bound',
            's8_public_complete_match_route_share','reference_budget_robust_all_recoveries','structural_shortlist',
            'extension_access_realised','weighted_composite_score_used','worker_reference_assigned_to_routes',
            's8_phase_selected','exact_timetable_constructed','topology_ranked','service_policy_selected','primary_selected','runner_up_selected',
        }
        if not required <= set(reader.fieldnames or []):
            raise ValueError(f'Shortlist schema missing {sorted(required-set(reader.fieldnames or []))}')
        rows=[]; ids=set()
        for row in reader:
            if row['plan_id'] in ids: raise ValueError(f"Duplicate plan {row['plan_id']}")
            ids.add(row['plan_id'])
            if row['reference_budget_robust_all_recoveries']!='true' or row['structural_shortlist']!='true':
                raise ValueError('Input contains non-shortlisted/non-robust plan')
            for field in ('extension_access_realised','weighted_composite_score_used','worker_reference_assigned_to_routes','s8_phase_selected','exact_timetable_constructed','topology_ranked','service_policy_selected','primary_selected','runner_up_selected'):
                if b(row[field]): raise ValueError(f'Forbidden upstream flag {field}=true')
            rows.append(row)
    return rows, reader.fieldnames or []


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument('--shortlist',type=Path,required=True)
    p.add_argument('--shortlist-validation',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--validation',type=Path,required=True)
    args=p.parse_args()

    upstream=json.loads(args.shortlist_validation.read_text(encoding='utf-8'))
    if upstream.get('status')!='PASS_REFERENCE_SERVICE_PLAN_SHORTLIST_V2_BUILD' or upstream.get('lineage',{}).get('output_sha256')!=sha(args.shortlist):
        raise ValueError('Reference service-plan shortlist V2 is not certified')
    rows, source_fields=load_rows(args.shortlist)
    if len(rows)!=int(upstream['shortlist_scenario_plan_count']):
        raise ValueError('Shortlist row count mismatch')

    base=[r for r in rows if abs(float(r['extension_share'])) <= 1e-12]
    extensions=[r for r in rows if float(r['extension_share']) > 1e-12]
    if any(r['topology_family']!='scheduled_extensions' for r in extensions):
        raise ValueError('Positive extension share outside scheduled_extensions family')
    base_frequent=[r for r in base if int(r['uniform_headway_min']) <= 30]
    ext_frequent=[r for r in extensions if int(r['uniform_headway_min']) <= 30]

    classes={
        'BASE_UNRESTRICTED':(base,False),
        'BASE_FREQUENT_30':(base_frequent,False),
        'EXTENSION_UPPER_BOUND_UNRESTRICTED':(extensions,True),
        'EXTENSION_UPPER_BOUND_FREQUENT_30':(ext_frequent,True),
    }
    memberships: dict[str,set[str]]=defaultdict(set)
    class_counts={}; class_unique_signatures={}
    for name,(subset,use_ext) in classes.items():
        fs=frontier_signatures(subset, extension_upper_bound=use_ext) if subset else set()
        class_unique_signatures[name]=len(fs)
        count=0
        for row in subset:
            if signature(row,extension_upper_bound=use_ext) in fs:
                memberships[row['plan_id']].add(name); count+=1
        class_counts[name]=count

    output_rows=[r for r in rows if r['plan_id'] in memberships]
    fields=list(source_fields)+['plan_level_frontier_classes','base_access_realised','extension_upper_bound_only','plan_level_ranked','exact_timetable_required_next']
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n')
        writer.writeheader()
        for row in sorted(output_rows,key=lambda r:r['plan_id']):
            names=memberships[row['plan_id']]
            writer.writerow({
                **row,
                'plan_level_frontier_classes':';'.join(sorted(names)),
                'base_access_realised':'true' if any(n.startswith('BASE_') for n in names) else 'false',
                'extension_upper_bound_only':'true' if names and all(n.startswith('EXTENSION_') for n in names) else 'false',
                'plan_level_ranked':'false',
                'exact_timetable_required_next':'true',
            })

    family_counts=Counter(r['topology_family'] for r in output_rows)
    headway_counts=Counter(int(r['uniform_headway_min']) for r in output_rows)
    validation={
        'status':STATUS,'contract':CONTRACT,
        'shortlist_input_count':len(rows),'base_plan_input_count':len(base),'positive_extension_plan_input_count':len(extensions),
        'frontier_union_plan_count':len(output_rows),'frontier_union_unique_scenario_count':len({r['scenario_id'] for r in output_rows}),
        'frontier_class_plan_counts':class_counts,'frontier_class_unique_metric_signature_counts':class_unique_signatures,
        'frontier_union_family_counts':dict(sorted(family_counts.items())),'frontier_union_headway_counts':dict(sorted(headway_counts.items())),
        'base_frontier_semantics':'REALISED_BASE_PUBLIC_STRUCTURAL_ACCESS_PLUS_ROUTE_UNWEIGHTED_S8_ENVELOPE_AND_JOINT_SERVICE_POLICY_RESOURCES',
        'extension_frontier_semantics':'ALL_EXTENSION_ANCHORS_STRUCTURAL_UPPER_BOUND_ONLY; NOT_REALISED_ACCESS; PRESERVED_FOR_EXACT_TIMETABLE_TEST',
        'dominance_axes':{
            'maximize':['resident_10min_access','worst_municipality_10min_access','territorial_work_od_addressability_upper_bound','s8_public_complete_match_route_share','span_minutes','annual_service_days'],
            'minimize':['uniform_headway_min','annual_bus_km','fleet_lower_bound_recovery15'],
        },
        'weighted_composite_score_used':False,'worker_reference_assigned_to_routes':False,'s8_phase_selected':False,
        'exact_timetable_constructed':False,'topology_ranked':False,'service_policy_selected':False,'primary_selected':False,'runner_up_selected':False,
        'lineage':{'shortlist_sha256':sha(args.shortlist),'shortlist_validation_sha256':sha(args.shortlist_validation),'output_sha256':sha(args.output)},
    }
    args.validation.write_text(json.dumps(validation,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(validation,indent=2,sort_keys=True))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
