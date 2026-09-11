"""Provenance-only historical stop-place binding; never directional boarding binding."""
from collections import defaultdict


def bind_historical_stops(stops, inventory, crosswalk):
    identities = [r['stop_place_id'] for r in inventory]
    if len(identities) != len(set(identities)):
        raise ValueError('duplicate frozen stop-place identity')
    native = defaultdict(set)
    for row in inventory:
        if row['service_class'] != 'CONVENTIONAL_TPL':
            continue
        # Provider namespaces are essential: native ID equality alone is insufficient.
        families = row['source_families'].split('|')
        prefixes = []
        if 'FROZEN_GTFS_REFERENCE' in families: prefixes.append('FROZEN_GTFS::')
        if 'ASF_OPERATOR_OTP' in families or 'ASF_C146_OBSERVED' in families: prefixes.append('ASF_OTP::')
        for prefix in prefixes:
            for sid in row['source_native_ids'].split('|'):
                if sid: native[prefix+sid].add(row['stop_place_id'])
    evidence = defaultdict(list)
    for row in crosswalk:
        sources = set(filter(None,row['target_source_records'].split('|')))
        targets = sorted(set().union(*(native[s] for s in sources))) if sources else []
        for sid in sources:
            if sid.startswith('FROZEN_GTFS::'):
                evidence[sid].append(dict(crosswalk_id=row['crosswalk_id'],
                    stop_place_decision=row['stop_place_decision'],
                    boarding_point_decision=row['boarding_point_decision'],
                    candidate_stop_place_ids=targets))
    results = {}
    for source in stops:
        sid = source['stop_id']
        if sid in results: raise ValueError('duplicate historical stop identity')
        key = 'FROZEN_GTFS::'+sid
        direct = native[key]
        support = set(direct)
        proposals = set(direct)
        rows = sorted(evidence[key],key=lambda r:r['crosswalk_id'])
        for row in rows:
            if row['stop_place_decision'] == 'SAME_STOP_PLACE_CONFIRMED':
                support.update(row['candidate_stop_place_ids'])
            proposals.update(row['candidate_stop_place_ids'])
        if len(proposals)>1:
            status,target = 'AMBIGUOUS_STOP_PLACE',None
        elif len(support)==1:
            target=next(iter(support))
            status='EXACT_FROZEN_SOURCE_PROVENANCE' if target in direct else 'CONFIRMED_CROSSWALK_STOP_PLACE'
        else:
            status,target = ('UNCONFIRMED_STOP_PLACE_CANDIDATE' if proposals else 'NO_FROZEN_BINDING_EVIDENCE'),None
        results[sid]=dict(historical_stop_id=sid,status=status,frozen_stop_place_id=target,
            candidate_stop_place_ids=sorted(proposals),direct_frozen_source_targets=sorted(direct),
            crosswalk_evidence=rows,directional_boarding_point_id=None,
            rt017_attachment_id=None,source_coordinates_modified=False,
            current_service_inferred=False)
    return results
