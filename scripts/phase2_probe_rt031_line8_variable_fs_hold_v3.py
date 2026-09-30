"""Bounded 16-full-trip timetable test with per-trip intermediate-FS holding.

The public road path and stop occurrences do not change. This is a diagnostic,
not a service selection or a claim about physical manoeuvres/boarding.
"""
import argparse
import gzip
import hashlib
import heapq
import json
import math
from collections import defaultdict

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csc_matrix

from scripts.phase2_close_rt031_line8_16_full_trips_v3 import (
    AUTH, authority, staggered_rail_inputs, source_fingerprints)
from scripts.phase2_rebuild_rt031_uniform_complete_line_v3 import BASE, ROOT, inputs
from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops
from scripts.phase2_solve_rt031_line8_flexible_peaks_v3 import interval_covers
from scripts.phase2_audit_rt031_line8_passenger_peaks_v3 import uncovered_intervals

OUTPUT = BASE / 'variable_fs_hold_16_full_trips.json.gz'
MANOEUVRES = BASE / 'stop_plan_and_additions.json.gz'


def wing_offsets(loops):
    result = {}
    for moving in (.9, 1., 1.1):
        for dwell in (0., .5, 1.):
            adjusted = adjusted_loops(loops, moving, dwell)
            result[moving, dwell] = {}
            for wing, loop in adjusted.items():
                sites = {}
                for sid in sorted({e['stop_place_id'] for e in loop['events']}):
                    events = [e for e in loop['events'] if e['stop_place_id'] == sid]
                    sites[sid] = {
                        'to_fs': max(e['offset_from_wing_origin_min'] for e in events),
                        'from_fs': 0,
                    }
                result[moving, dwell][wing] = {'road_minutes': loop['road_minutes'], 'sites': sites}
    return result


def windows(start, shoulder):
    return [(start, 600, shoulder), (600, 960, 120), (960, 1180, shoulder)]


def ordered_stop_ledger(loops, first, selected):
    second = next(k for k in loops if k != first)
    adjusted = adjusted_loops(loops, 1.1, .5)
    ledger = []
    for q in selected:
        events = [{'role': 'FULL_TRIP_START_FS', 'time_min': q['first_fs_min']}]
        for wing, start, edge_shift in ((first, q['first_fs_min'], 0),
                                        (second, q['second_fs_min'],
                                         len(loops[first]['edge_ids']))):
            for event in sorted(adjusted[wing]['events'],
                                key=lambda e: (e['path_node_index'], e['stop_place_id'])):
                events.append({'role': 'DESIGN_STOP_OCCURRENCE', 'wing': wing,
                               'site_id': event['stop_place_id'],
                               'occurrence_id': event['occurrence_id'],
                               'full_path_edge_index': edge_shift+event['path_node_index'],
                               'board_event_min': start+event['offset_from_wing_origin_min'],
                               'alight_event_min': start+event['offset_from_wing_origin_min']-.5,
                               'physical_boarding_authorised': False})
            if wing == first:
                events.append({'role': 'INTERMEDIATE_FS_STAY_ONBOARD_DESIGN',
                               'arrival_min': start+adjusted[first]['road_minutes'],
                               'departure_min': q['second_fs_min'],
                               'physical_continuity_certified': False})
        events.append({'role': 'FULL_TRIP_END_FS',
                       'arrival_min': q['second_fs_min']+adjusted[second]['road_minutes']})
        ledger.append({'first_fs_min': q['first_fs_min'], 'second_fs_min': q['second_fs_min'],
                       'events': events})
    return ledger


def solve(p, loops, first, shifted, shoulder=60, time_limit=90, max_mid=None,
          full_trip_count=16, minimize_hold=False):
    """One fixed complete-path orientation; only intermediate FS hold varies."""
    second = next(k for k in loops if k != first)
    if not all(p['family']['joins'].get(k) is True for k in (first+'>'+second, second+'>'+first)):
        raise ValueError('unrepresented full-trip join')
    if shifted:
        p, substitutions = staggered_rail_inputs(p, second.split('_')[0])
    else:
        substitutions = []
    a = authority()
    if a['full_commercial_trips_per_day_adopted'] != 16:
        raise ValueError('wrong caller trip count')
    offsets = wing_offsets(loops)
    min_mid = 5 * math.ceil((offsets[1.1, 1.][first]['road_minutes']+1)/5)
    mid_offsets = list(range(min_mid, min_mid+31, 5))
    if max_mid is not None:
        mid_offsets = [m for m in mid_offsets if m <= max_mid]
    if not mid_offsets:
        raise ValueError('no stress-feasible intermediate FS hold')
    first_times = list(range(300, 1181, 5))
    second_times = list(range(300+min_mid, 1181+mid_offsets[-1], 5))
    times = {first: first_times, second: second_times}
    ix = {(first, t): i for i, t in enumerate(first_times)}
    ix.update({(second, t): len(first_times)+i for i, t in enumerate(second_times)})
    nx = len(first_times)+len(second_times)
    # The absolute second-FS departure, not a second route, is paired to its
    # own first-FS departure. Every selected pair remains one indivisible trip.
    pairs = [(t, t+m, m) for t in first_times for m in mid_offsets]
    pair_col = {(t, u): nx+i for i, (t, u, _) in enumerate(pairs)}
    assignments = []
    targets = sorted({(a0['wing'], a0['kind'], a0['rail_min']) for a0 in p['anchors']})
    for wing_prefix, kind, minute in targets:
        wing = next(w for w in (first, second) if w.startswith(wing_prefix))
        eligible = []
        for t in times[wing]:
            if kind == 'bus_to_rail':
                waits = [minute-t-g[wing]['road_minutes']-3 for g in offsets.values()]
                valid = min(waits) >= -1e-8 and max(waits) <= p['wait_ceiling']+1e-8
            else:
                valid = 3 <= t-minute <= 8
            if valid:
                eligible.append(t)
        if not eligible:
            return {'solver_status': 2, 'infeasibility_proven': True,
                    'reason': 'empty rail eligibility', 'empty_target': [wing_prefix, kind, minute]}
        assignments.append({'wing': wing, 'kind': kind, 'rail_min': minute,
                            'eligible': eligible})
    aa = [(r, t) for r, row in enumerate(assignments) for t in row['eligible']]
    aa_col = {(r, t): nx+len(pairs)+i for i, (r, t) in enumerate(aa)}
    n = nx+len(pairs)+len(aa)
    rr, cc, vv, lower, upper = [], [], [], [], []

    def row(entries, lo, hi):
        r = len(lower)
        for col, value in entries:
            rr.append(r); cc.append(col); vv.append(value)
        lower.append(lo); upper.append(hi)

    # Exactly one paired complete trip per first-FS start. A second-FS event
    # cannot be used by two full trips.
    for t in first_times:
        row([(pair_col[t, t+m], 1) for m in mid_offsets]+[(ix[first, t], -1)], 0, 0)
    by_second = defaultdict(list)
    for t, u, _ in pairs:
        by_second[u].append(pair_col[t, u])
    for u in second_times:
        row([(j, 1) for j in by_second[u]]+[(ix[second, u], -1)], 0, 0)
    row([(ix[first, t], 1) for t in first_times], full_trip_count, full_trip_count)

    start = 405 if first == 'west_B' else 410
    for scenario in offsets.values():
        for wing in (first, second):
            for site in scenario[wing]['sites'].values():
                for direction in ('to_fs', 'from_fs'):
                    events = [(ix[wing, t], t+site[direction]) for t in times[wing]]
                    for lo, hi, wait in windows(start, shoulder):
                        for cover in interval_covers(events, lo, hi, wait):
                            row([(i, 1) for i in cover], 1, np.inf)

    for r, target in enumerate(assignments):
        row([(aa_col[r, t], 1) for t in target['eligible']], 1, 1)
        for t in target['eligible']:
            row([(aa_col[r, t], 1), (ix[target['wing'], t], -1)], -np.inf, 0)
    for wing in (first, second):
        for kind in ('bus_to_rail', 'rail_to_bus'):
            core = sorted([r for r, a0 in enumerate(assignments)
                           if a0['wing'] == wing and a0['kind'] == kind],
                          key=lambda r: assignments[r]['rail_min'])[:5]
            for before, after in zip(core, core[1:]):
                entries = [(aa_col[r, t], t*(1 if r == after else -1))
                           for r in (before, after) for t in assignments[r]['eligible']]
                row(entries, 30, 30)
            for t in times[wing]:
                same = [aa_col[r, t] for r, a0 in enumerate(assignments)
                        if a0['wing'] == wing and a0['kind'] == kind and t in a0['eligible']]
                if same:
                    row([(j, 1) for j in same], -np.inf, 1)
    matrix = csc_matrix((vv, (rr, cc)), shape=(len(lower), n))
    pair_costs = [m if minimize_hold else 0 for _, _, m in pairs]
    answer = milp(np.r_[np.zeros(nx), pair_costs, np.zeros(len(aa))],
                  integrality=np.ones(n), bounds=Bounds(0, 1),
                  constraints=LinearConstraint(matrix, lower, upper),
                  options={'time_limit': time_limit, 'mip_rel_gap': 0})
    result = {'first_wing': first, 'second_wing': second, 'shifted_rail_targets': shifted,
              'target_substitutions_not_adopted': substitutions,
              'shoulder_headway_cap_min': shoulder, 'core_headway_cap_min': 120,
              'ready_start_min': start, 'candidate_mid_offsets_min': mid_offsets,
              'five_minute_grid': True, 'full_trip_count': full_trip_count,
              'intermediate_holding_minimized': minimize_hold,
              'solver_status': int(answer.status), 'solver_message': str(answer.message),
              'infeasibility_proven': answer.status == 2, 'witness_found': answer.x is not None}
    if answer.x is None:
        return result
    if max(abs(answer.x-np.rint(answer.x))) > 1e-6:
        raise ValueError('noninteger timetable witness')
    selected = [{'first_fs_min': t, 'second_fs_min': u, 'intermediate_offset_min': m}
                for i, (t, u, m) in enumerate(pairs) if answer.x[nx+i] > .5]
    selected.sort(key=lambda q: q['first_fs_min'])
    if len(selected) != full_trip_count or len({q['second_fs_min'] for q in selected}) != full_trip_count:
        raise ValueError('incomplete or overlapping full trips')
    selected_times = {first: [q['first_fs_min'] for q in selected],
                      second: sorted(q['second_fs_min'] for q in selected)}
    for scenario in offsets.values():
        for wing in (first, second):
            for site in scenario[wing]['sites'].values():
                for direction in ('to_fs', 'from_fs'):
                    values = [t+site[direction] for t in selected_times[wing]]
                    for lo, hi, wait in windows(start, shoulder):
                        if uncovered_intervals(values, lo, hi, wait):
                            raise ValueError('site ready-time witness verification failed')
    chosen = [{'wing': assignments[r]['wing'], 'kind': assignments[r]['kind'],
               'rail_min': assignments[r]['rail_min'], 'wing_fs_departure_min': t}
              for i, (r, t) in enumerate(aa) if answer.x[nx+len(pairs)+i] > .5]
    if len(chosen) != len(targets):
        raise ValueError('rail target witness verification failed')
    vehicle_cases = []
    for (moving, dwell), scenario in offsets.items():
        for recovery in (5, 10, 15):
            ongoing = []
            maximum = 0
            for q in selected:
                t = q['first_fs_min']
                while ongoing and ongoing[0] <= t+1e-8:
                    heapq.heappop(ongoing)
                heapq.heappush(ongoing, q['second_fs_min']+
                               scenario[second]['road_minutes']+recovery)
                maximum = max(maximum, len(ongoing))
            vehicle_cases.append({'moving_multiplier': moving, 'dwell_min': dwell,
                                  'terminal_recovery_min': recovery,
                                  'minimum_vehicle_count_conditional': maximum})
    nominal_first = offsets[1.1, .5][first]['road_minutes']
    nominal_second = offsets[1.1, .5][second]['road_minutes']
    result.update(full_trips=selected, rail_assignments=chosen,
                  ordered_stop_event_ledger_nominal=(
                      ordered_stop_ledger(loops, first, selected)
                      if full_trip_count == 16 else None),
                  total_intermediate_offset_min=sum(q['intermediate_offset_min'] for q in selected),
                  maximum_intermediate_fs_onboard_wait_nominal_min=max(
                      q['intermediate_offset_min']-nominal_first for q in selected),
                  nominal_full_trip_duration_range_min=[
                      min(q['intermediate_offset_min']+nominal_second for q in selected),
                      max(q['intermediate_offset_min']+nominal_second for q in selected)],
                  vehicle_cases_conditional=vehicle_cases,
                  maximum_root_gap_min=max(b['first_fs_min']-a0['first_fs_min']
                                           for a0, b in zip(selected, selected[1:])),
                  maximum_second_wing_gap_min=max(b-a0 for a0, b in zip(
                      selected_times[second], selected_times[second][1:])),
                  annual_service_km_260_day_comparison=
                      full_trip_count*sum(loop['distance_m'] for loop in loops.values())/1000*260,
                  detailed_timetable_adopted=False, operating_plan_adopted=False,
                  physical_passenger_continuity_certified=False,
                  network_selected=False, primary_selection_authorised=False,
                  runner_up_selection_authorised=False)
    return result


def build(time_limit=90):
    _, p, _, _, loops = inputs()
    cases = []
    for first in ('west_B', 'east_A'):
        minimum = 5 * math.ceil((wing_offsets(loops)[1.1, 1.][first]['road_minutes']+1)/5)
        comparisons = [
            (False, 60, 16, None, False),
            (False, 95, 16, None, False),
            (True, 60, 16, None, False),
            (True, 90, 16, None, False),
            (True, 95, 16, minimum+25, False),
            (True, 95, 16, None, True),
            (True, 120, 16, None, False),
            (True, 60, 17, None, False),
            (True, 60, 18, None, True),
        ]
        for shifted, shoulder, count, max_mid, minimize in comparisons:
            case = solve(p, loops, first, shifted, shoulder, time_limit,
                         max_mid=max_mid, full_trip_count=count,
                         minimize_hold=minimize)
            case['case_id'] = (f'{first}_{"shifted" if shifted else "original"}_'
                               f'{count}_shoulder{shoulder}_maxmid{max_mid or "all"}_'
                               f'{"minhold" if minimize else "feasibility"}')
            case['comparison_trip_count_not_adopted'] = count != 16
            cases.append(case)
            print(case['case_id'], case['solver_status'], case['witness_found'], flush=True)
    manoeuvres = json.loads(gzip.decompress(MANOEUVRES.read_bytes()))['manoeuvres']
    if len(manoeuvres) != 6 or any(m['bus_manoeuvre_authorised'] for m in manoeuvres):
        raise ValueError('source physical manoeuvre status drift')
    nominal = adjusted_loops(loops, 1.1, .5)
    local_fast_passages = []
    for wing, sid in [('west_B', 'RT031::P2V2S_0031_PROJECTED_ROAD_POINT'),
                      ('east_A', 'PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE')]:
        events = [e for e in nominal[wing]['events'] if e['stop_place_id'] == sid]
        if len(events) != 2:
            raise ValueError('local directional occurrence guarantee drift')
        first_event, last_event = sorted(events, key=lambda e: e['path_node_index'])
        local_fast_passages.append({
            'wing': wing, 'site_id': sid,
            'first_outbound_occurrence_id': first_event['occurrence_id'],
            'outbound_alight_from_wing_fs_nominal_min':
                first_event['offset_from_wing_origin_min']-.5,
            'last_inbound_occurrence_id': last_event['occurrence_id'],
            'inbound_board_to_next_fs_nominal_min':
                nominal[wing]['road_minutes']-last_event['offset_from_wing_origin_min'],
            'physical_stop_boarding_authorised': False,
        })
    return {'contract': 'RT031_LINE8_VARIABLE_FS_HOLD_16_FULL_TRIPS_DIAGNOSTIC_V3',
            'authority_source': str(AUTH.relative_to(ROOT)).replace('\\', '/'),
            'parent_sources': source_fingerprints(p, loops), 'cases': cases,
            'manoeuvre_source': str(MANOEUVRES.relative_to(ROOT)).replace('\\', '/'),
            'manoeuvre_source_sha256': hashlib.sha256(MANOEUVRES.read_bytes()).hexdigest(),
            'six_reverse_edge_manoeuvres_all_bus_authorisation_missing': True,
            'manoeuvre_ids_requiring_vehicle_sweep': [m['id'] for m in manoeuvres],
            'local_fast_directional_passages_nominal': local_fast_passages,
            'scope': 'Same 27.679 km full road path and 29 design sites in each trip; 16 trips, '
                     'five-minute grid, root FS starts 05:00-19:40, per-trip intermediate '
                     'FS departure offset in seven five-minute values from stress-feasible '
                     'minimum through +30. Ready-time windows 06:45 or 06:50-19:40; '
                     'H120 10-16, tested H60/H90/H95/H120 shoulders. Five core target-bound '
                     'trips H30 in each wing. 17/18-trip cases are non-adopted comparisons. '
                     'This is not a continuous-time or physical bus-operation proof.',
            'decision_budget_km': None, 'uncertainty_band_min': None,
            'annual_calendar_adopted': False,
            'rail_target_substitutions_adopted': False,
            'detailed_timetable_adopted': False,
            'physical_passenger_continuity_certified': False,
            'operating_plan_adopted': False,
            'network_selected': False, 'primary_selection_authorised': False,
            'runner_up_selection_authorised': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--time-limit', type=int, default=90)
    parser.add_argument('--output', default=OUTPUT)
    args = parser.parse_args()
    from pathlib import Path
    payload = (json.dumps(build(args.time_limit), ensure_ascii=False,
                          sort_keys=True, separators=(',', ':'))+'\n').encode('utf-8')
    Path(args.output).write_bytes(gzip.compress(payload, mtime=0))
