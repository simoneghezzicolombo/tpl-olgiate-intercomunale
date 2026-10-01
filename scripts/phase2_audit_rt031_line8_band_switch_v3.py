"""Enumerate fixed-band orientation assignments; optimistic events, not a timetable."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path


def band(minute):
    return 'am' if 420 <= minute < 540 else 'pm' if 1020 <= minute < 1140 else 'off'


def dispatches(start, end):
    result = []
    minute = start
    while minute < end:
        result.append(minute)
        minute += 30 if band(minute) != 'off' else 60
    return result


def largest_gap(events):
    ordered = sorted(events, key=lambda e: (e['minute'], e['event_id']))
    if len(ordered) < 2:
        return None
    a, b = max(zip(ordered, ordered[1:]), key=lambda pair: pair[1]['minute']-pair[0]['minute'])
    return {'minutes': round(b['minute']-a['minute'], 6), 'before': a, 'after': b}


def fleet_lower_bound(trips, patterns, recovery):
    events = [(t, 1) for t,p in trips] + [(t+patterns[p]['running_minutes_excluding_dwell']+recovery, -1) for t,p in trips]
    active = maximum = 0
    for _, delta in sorted(events):
        active += delta
        maximum = max(maximum, active)
    return maximum


def build(source, cap):
    if source['contract'] != 'RT031_LINE8_OCCURRENCE_SERVICE_DIAGNOSTIC_V3' or source['network_selected']:
        raise ValueError('unsupported or decisional source')
    patterns = source['road_patterns']
    if any(source['represented_via_node_cycle_joins_allowed'].get(a+'_then_'+b) is not True
           for a in patterns for b in patterns):
        raise ValueError('unverified represented join between patterns')
    sites = sorted({e['stop_place_id'] for e in source['events']} - {'FROZEN::L00407'})
    # All integer-hour 13/14-hour windows containing both full declared peak bands;
    # 16-hour reference is the previously compared 06-22 window.
    windows = [(start, start+span*60) for span in (13,14) for start in range(300,421,60)
               if start+span*60 >= 1140] + [(360,1320)]
    recoveries = sorted({r['recovery_min_assumption'] for r in source['runtime_sensitivities']})
    results = []
    for start,end in windows:
        for choices in itertools.product(sorted(patterns), repeat=3):
            assignment = dict(zip(('am','off','pm'), choices))
            trips = [(t,assignment[band(t)]) for t in dispatches(start,end)]
            location_events = {s: {'to_fs': [], 'from_fs': []} for s in sites}
            for trip_index,(departure,pattern) in enumerate(trips):
                for e in source['events']:
                    sid = e['stop_place_id']
                    if sid not in location_events or e['direction'] != pattern:
                        continue
                    for direction in ('to_fs','from_fs'):
                        runtime = e['road_minutes_to_next_fs' if direction == 'to_fs' else 'road_minutes_from_previous_fs']
                        if runtime is None:
                            continue
                        minute = departure + e['offset_road_minutes'] - (runtime if direction == 'from_fs' else 0)
                        location_events[sid][direction].append({'minute': round(minute,6),
                            'event_id': f'{trip_index}:{e["occurrence_id"]}:{direction}',
                            'road_ride_min': runtime, 'dispatch_band': band(departure), 'pattern': pattern})
            by_site = {}
            for sid, directions in location_events.items():
                by_site[sid] = {key: {'optimistic_identity_gap': largest_gap(ev),
                    'first_boarding_minute': min(e['minute'] for e in ev),
                    'last_boarding_minute': max(e['minute'] for e in ev),
                    'am_dispatch_max_road_ride_min': max(e['road_ride_min'] for e in ev if e['dispatch_band']=='am'),
                    'pm_dispatch_max_road_ride_min': max(e['road_ride_min'] for e in ev if e['dispatch_band']=='pm')}
                    for key, ev in directions.items()}
            annual = sum(patterns[p]['distance_m'] for _,p in trips)/1000*260
            worst_sid, worst_direction, worst_gap = max(
                ((s,d,v[d]['optimistic_identity_gap']) for s,v in by_site.items() for d in ('to_fs','from_fs')),
                key=lambda row: row[2]['minutes'])
            for v in by_site.values():
                for d in ('to_fs','from_fs'):
                    v[d]['optimistic_identity_gap'] = v[d]['optimistic_identity_gap']['minutes']
            results.append({'scenario_id': f'{start}-{end}:'+','.join(choices),
                'start_min':start,'end_min':end,'assignment':assignment,
                'departures': [{'minute':t,'pattern':p} for t,p in trips],
                'annual_km_before_extras': round(annual,3), 'remaining_km_before_extras': round(cap-annual,3),
                'by_site': by_site,
                'maximum_optimistic_identity_gap_min': worst_gap['minutes'],
                'worst_gap_witness': {'stop_place_id':worst_sid,'journey_direction':worst_direction,**worst_gap},
                'fleet_lower_bound_zero_dwell_by_recovery': {str(r):fleet_lower_bound(trips,patterns,r) for r in recoveries}})
    return {'contract':'RT031_LINE8_BAND_SWITCH_DIAGNOSTIC_V3', 'scenarios':results,
        'domain': 'All 4^3 AM/offpeak/PM assignments of four source-backed road witnesses; 6 declared comparison windows. No additional trips or clock phases searched.',
        'peak_dispatch_bands_min': [[420,540],[1020,1140]],
        'annual_days_assumption':260, 'approved_cap_km_not_decision_budget':cap,
        'semantics': 'Zero dwell/traffic/recovery at passenger events. Each event retains trip and road-occurrence identity. Identity gap is optimistic: assumes every encounter is boardable and direction changes need no access time. It is NOT an occurrence-level service guarantee. First/last timestamps are boarding times, not service-span certification. Peak labels refer to origin dispatch, not local stop clock time.',
        'fleet_semantics':'Overlap lower bound with source-declared recovery and zero dwell; no vehicle assignment, depot or passenger-continuity certification.',
        'actual_timetable_certified':False, 'network_selected':False,
        'primary_selection_authorised':False,'runner_up_selection_authorised':False,
        'decision_budget_km':None,'uncertainty_band_min':None}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for k in ('source','policy','output'):
        p.add_argument('--'+k, required=True, type=Path)
    a = p.parse_args()
    source = json.loads(a.source.read_text(encoding='utf-8'))
    policy = json.loads(a.policy.read_text(encoding='utf-8'))
    if policy['contract'] != 'PHASE2_HUMAN_APPROVED_FINAL_POLICY_V3':
        raise ValueError('wrong policy')
    result = build(source, policy['human_policy_decisions']['annual_bus_km_cap'])
    result['source_sha256'] = {k:hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for k,path in (('source',a.source),('policy',a.policy))}
    a.output.write_text(json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(',',':'))+'\n', encoding='utf-8')
