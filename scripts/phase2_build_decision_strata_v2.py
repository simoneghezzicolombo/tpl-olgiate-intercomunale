#!/usr/bin/env python3
"""Build passenger-equivalent decision strata for the Phase 2 robust frontier.

Only operational service identities with exactly the same values on every
robust passenger-dominance axis are treated as indistinguishable. Within such an
exact-equivalence stratum, the practical tie-break from the original Phase 2
specification is applied without sacrificing a measured passenger outcome:
reliability, simplicity, lower annual bus-km, fewer field-check elements and
continuity. This gate does not compare or select between non-equivalent strata.
"""
from __future__ import annotations

import argparse,csv,hashlib,json
from collections import Counter,defaultdict
from pathlib import Path

STATUS='PASS_DECISION_STRATA_V2_BUILD'
CONTRACT='PHASE2_ROBUST_PASSENGER_EQUIVALENCE_STRATA_V2'


def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()


def rows(path:Path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def sid(payload)->str:
    text=json.dumps(payload,sort_keys=True,separators=(',',':'))
    return 'P2STRATUM_'+hashlib.sha256(text.encode()).hexdigest()[:16]


def num(text):
    return float(text)


def practical_key(row):
    # Original practical tie-break, using only available audited proxies.
    # 1 reliability: incomplete routes under stress, then max fleet under recovery15
    # 2 simplicity: public route-pattern count
    # 3 lower annual bus-km
    # 4 fewer field-check / proposed-stop elements
    # 5 continuity: more existing stop anchors
    return (
        int(float(row['stress_max_incomplete_route_count'])),
        int(float(row['stress_max_fleet_recovery15'])),
        int(float(row['public_route_count'])),
        num(row['exact_annual_bus_km']),
        int(float(row['public_explicit_field_check_pending_count'])),
        int(float(row['public_explicit_proposed_stop_count'])),
        -int(float(row['public_explicit_existing_stop_count'])),
        row['service_identity_id'],
    )


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument('--identities',type=Path,required=True)
    p.add_argument('--identity-validation',type=Path,required=True)
    p.add_argument('--robust-validation',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--validation',type=Path,required=True)
    a=p.parse_args()
    iv=json.loads(a.identity_validation.read_text())
    rv=json.loads(a.robust_validation.read_text())
    if iv.get('status')!='PASS_ROBUST_SERVICE_IDENTITY_AUDIT_V2' or iv.get('lineage',{}).get('output_sha256')!=sha(a.identities):
        raise ValueError('Robust service identity audit is not certified')
    if rv.get('status')!='PASS_ROBUSTNESS_TOURNAMENT_V2_BUILD':raise ValueError('Robustness tournament is not certified')
    if any(rv.get(k) is not False for k in ('weighted_composite_score_used','primary_selected','runner_up_selected')):
        raise ValueError('Robustness upstream violates decision boundary')

    data=rows(a.identities)
    if len(data)!=int(iv['unique_operational_service_identity_count']):raise ValueError('Identity count mismatch')
    axes=list(rv['dominance_axes']['maximize'])+list(rv['dominance_axes']['minimize'])
    missing=[x for x in axes if x not in data[0]]
    if missing:raise ValueError(f'Identity output missing robust passenger axes: {missing}')

    groups=defaultdict(list)
    signatures={}
    for row in data:
        payload={field:row[field] for field in axes}
        stratum=sid(payload)
        signatures[stratum]=payload
        groups[stratum].append(row)

    out=[]; tie_groups=0; removed=0
    for stratum,members in sorted(groups.items()):
        ordered=sorted(members,key=practical_key)
        winner=ordered[0]
        invoked=len(members)>1
        if invoked:
            tie_groups+=1; removed+=len(members)-1
        out.append({
            'decision_stratum_id':stratum,
            'passenger_equivalent_service_count':len(members),
            'representative_service_identity_id':winner['service_identity_id'],
            'representative_plan_id':winner['representative_plan_id'],
            'all_service_identity_ids_json':json.dumps(sorted(r['service_identity_id'] for r in members),separators=(',',':')),
            'all_representative_plan_ids_json':json.dumps(sorted(r['representative_plan_id'] for r in members),separators=(',',':')),
            'topology_family_aliases_json':json.dumps(sorted({f for r in members for f in json.loads(r['topology_families_json'])}),separators=(',',':')),
            'practical_tiebreak_invoked':str(invoked).lower(),
            'practical_tiebreak_rule':'RELIABILITY_INCOMPLETE_ROUTES_THEN_FLEET__SIMPLICITY_ROUTE_COUNT__BUS_KM__FIELD_CHECKS_PROPOSED_STOPS__EXISTING_STOP_CONTINUITY',
            **{field:winner[field] for field in axes},
            'stress_max_incomplete_route_count':winner['stress_max_incomplete_route_count'],
            'stress_max_fleet_recovery15':winner['stress_max_fleet_recovery15'],
            'public_route_count':winner['public_route_count'],
            'exact_annual_bus_km':winner['exact_annual_bus_km'],
            'public_explicit_field_check_pending_count':winner['public_explicit_field_check_pending_count'],
            'public_explicit_proposed_stop_count':winner['public_explicit_proposed_stop_count'],
            'public_explicit_existing_stop_count':winner['public_explicit_existing_stop_count'],
            'robust_frontier_classes':winner['robust_frontier_classes'],
            'primary_selected':'false','runner_up_selected':'false'
        })
    fields=list(out[0])
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(out)
    hcounts=Counter(int(float(r['uniform_headway_min'])) for r in out)
    aliases=Counter()
    for r in out:
        aliases['+'.join(json.loads(r['topology_family_aliases_json']))]+=1
    report={
        'status':STATUS,'contract':CONTRACT,
        'input_operational_service_identity_count':len(data),
        'unique_robust_passenger_metric_stratum_count':len(out),
        'passenger_equivalent_multi_service_stratum_count':tie_groups,
        'service_identities_removed_by_exact_passenger_equivalence_tiebreak':removed,
        'decision_stratum_headway_counts':dict(sorted(hcounts.items())),
        'decision_stratum_family_alias_signature_counts':dict(sorted(aliases.items())),
        'passenger_signature_fields':axes,
        'practical_tiebreak_applied_only_with_exact_passenger_signature_equivalence':True,
        'weighted_composite_score_used':False,'non_equivalent_strata_ranked':False,
        'topology_ranked':False,'service_policy_selected':False,'primary_selected':False,'runner_up_selected':False,
        'lineage':{
            'identities_sha256':sha(a.identities),'identity_validation_sha256':sha(a.identity_validation),
            'robust_validation_sha256':sha(a.robust_validation),'output_sha256':sha(a.output)
        },
        'epistemic_note':'The practical tie-break is invoked only inside exact robust-passenger metric equivalence classes. Different passenger signatures remain unresolved trade-offs and are not ranked here.'
    }
    a.validation.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2,sort_keys=True))
    return 0

if __name__=='__main__':raise SystemExit(main())
