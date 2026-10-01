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


def original_target_compatibility(p, offsets, selected_times):
    compatible = []
    missing = []
    for wing_prefix, kind, minute in sorted({
            (a['wing'], a['kind'], a['rail_min']) for a in p['anchors']}):
        wing = next(w for w in selected_times if w.startswith(wing_prefix))
        eligible = []
        for t in selected_times[wing]:
            if kind == 'bus_to_rail':
                waits = [minute-t-g[wing]['road_minutes']-3
                         for g in offsets.values()]
                ok = min(waits) >= -1e-8 and max(waits) <= p['wait_ceiling']+1e-8
            else:
                ok = 3 <= t-minute <= 8
            if ok:
                eligible.append(t)
        item = {'wing': wing_prefix, 'kind': kind, 'rail_min': minute,
                'eligible_wing_fs_departures_min': eligible}
        (compatible if eligible else missing).append(item)
    reused = [(a['wing'], a['kind'], t)
              for a in compatible for t in a['eligible_wing_fs_departures_min']]
    if len(reused) != len(set(reused)):
        raise ValueError('one wing event reused for distinct original target trains')
    return {'compatible_count': len(compatible), 'compatible': compatible,
            'missing': missing}


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
          full_trip_count=16, minimize_hold=False, anchor_policy='fixed_22',
          required_train_bank_start=None, vehicle_cap=None):
    """One fixed complete-path orientation; only intermediate FS hold varies."""
    second = next(k for k in loops if k != first)
    if anchor_policy not in ('fixed_22', 'h30_unbound', 'max_supported',
                             'flexible_real_trains'):
        raise ValueError('unknown rail-anchor policy')
    if shifted and anchor_policy != 'fixed_22':
        raise ValueError('cannot shift targets when rail anchors are unbound')
    if required_train_bank_start is not None and anchor_policy != 'flexible_real_trains':
        raise ValueError('required real-train bank needs flexible real trains')
    if minimize_hold and anchor_policy in ('max_supported', 'flexible_real_trains'):
        raise ValueError('separate rail-coverage and holding objectives')
    original_p = p
    original_targets = {(a0['wing'], a0['kind'], a0['rail_min']) for a0 in p['anchors']}
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
    if anchor_policy == 'flexible_real_trains':
        morning = sorted({int(e['departure_min']) for e in p['rail']['events']
                          if e['direction'] == 'MILANO' and
                          416 <= e['departure_min'] <= 596})
        evening = sorted({int(e['arrival_min']) for e in p['rail']['events']
                          if e['direction'] == 'LECCO' and
                          962 <= e['arrival_min'] <= 1172})
        if morning != list(range(416, 597, 30)) or evening != list(range(962, 1173, 30)):
            raise ValueError('dated real-train candidate bank drift')
        targets = sorted((wing, kind, minute)
                         for wing in ('west', 'east')
                         for kind, minutes in (('bus_to_rail', morning),
                                               ('rail_to_bus', evening))
                         for minute in minutes)
    else:
        targets = (sorted({(a0['wing'], a0['kind'], a0['rail_min']) for a0 in p['anchors']})
                   if anchor_policy != 'h30_unbound' else [])
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
        if not eligible and anchor_policy == 'fixed_22':
            return {'solver_status': 2, 'infeasibility_proven': True,
                    'reason': 'empty rail eligibility', 'empty_target': [wing_prefix, kind, minute]}
        assignments.append({'wing': wing, 'kind': kind, 'rail_min': minute,
                            'eligible': eligible})
    aa = [(r, t) for r, row in enumerate(assignments) for t in row['eligible']]
    aa_col = {(r, t): nx+len(pairs)+i for i, (r, t) in enumerate(aa)}
    banks = []
    if anchor_policy in ('h30_unbound', 'max_supported'):
        for wing in (first, second):
            for peak, start_lo, start_hi in (('AM', 330, 450), ('PM', 930, 1050)):
                for start in range(start_lo, start_hi+1, 5):
                    if all(start+30*k in times[wing] for k in range(5)):
                        banks.append((wing, peak, start))
    bank_col = {bank: nx+len(pairs)+len(aa)+i for i, bank in enumerate(banks)}
    train_banks = []
    if anchor_policy == 'flexible_real_trains':
        for wing in (first, second):
            for kind in ('bus_to_rail', 'rail_to_bus'):
                group = [r for r, a0 in enumerate(assignments)
                         if a0['wing'] == wing and a0['kind'] == kind]
                group.sort(key=lambda r: assignments[r]['rail_min'])
                for start in range(len(group)-4):
                    train_banks.append((wing, kind, tuple(group[start:start+5])))
    train_bank_col = {bank: nx+len(pairs)+len(aa)+len(banks)+i
                      for i, bank in enumerate(train_banks)}
    n = nx+len(pairs)+len(aa)+len(banks)+len(train_banks)
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
    if vehicle_cap is not None:
        # For intervals sharing the same FS terminal, maximum concurrent
        # vehicle occupation occurs immediately after a first-FS departure.
        # The slowest common scenario and largest recovery dominate the other
        # 26 cases; this is conditional engineering, not fleet approval.
        stress_end_offset = offsets[1.1, 1.][second]['road_minutes']+15
        for instant in first_times:
            concurrent = [(pair_col[t, u], 1) for t, u, _ in pairs
                          if t <= instant < u+stress_end_offset-1e-8]
            row(concurrent, -np.inf, vehicle_cap)

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
        row([(aa_col[r, t], 1) for t in target['eligible']],
            1 if anchor_policy == 'fixed_22' else 0, 1)
        for t in target['eligible']:
            row([(aa_col[r, t], 1), (ix[target['wing'], t], -1)], -np.inf, 0)
    for wing in (first, second):
        for kind in ('bus_to_rail', 'rail_to_bus'):
            core = sorted([r for r, a0 in enumerate(assignments)
                           if a0['wing'] == wing and a0['kind'] == kind],
                          key=lambda r: assignments[r]['rail_min'])[:5]
            if anchor_policy == 'fixed_22':
                for before, after in zip(core, core[1:]):
                    entries = [(aa_col[r, t], t*(1 if r == after else -1))
                               for r in (before, after) for t in assignments[r]['eligible']]
                    row(entries, 30, 30)
            for t in times[wing]:
                same = [aa_col[r, t] for r, a0 in enumerate(assignments)
                        if a0['wing'] == wing and a0['kind'] == kind and t in a0['eligible']]
                if same:
                    row([(j, 1) for j in same], -np.inf, 1)
    for wing in (first, second):
        for peak in ('AM', 'PM'):
            selected_banks = [bank for bank in banks if bank[:2] == (wing, peak)]
            if selected_banks:
                row([(bank_col[bank], 1) for bank in selected_banks], 1, 1)
                for bank in selected_banks:
                    for k in range(5):
                        row([(ix[wing, bank[2]+30*k], 1),
                             (bank_col[bank], -1)], 0, np.inf)
    if anchor_policy == 'flexible_real_trains':
        for wing in (first, second):
            for kind in ('bus_to_rail', 'rail_to_bus'):
                group = [bank for bank in train_banks if bank[:2] == (wing, kind)]
                row([(train_bank_col[bank], 1) for bank in group], 1, 1)
        if required_train_bank_start is not None:
            wing_prefix, kind, minute = required_train_bank_start
            forced = [bank for bank in train_banks
                      if bank[0].startswith(wing_prefix) and bank[1] == kind
                      and assignments[bank[2][0]]['rail_min'] == minute]
            if len(forced) != 1:
                raise ValueError('requested real-train bank is not in declared window')
            row([(train_bank_col[forced[0]], 1)], 1, 1)
        for r, target in enumerate(assignments):
            choices = [bank for bank in train_banks if r in bank[2]]
            row([(aa_col[r, t], 1) for t in target['eligible']]+
                [(train_bank_col[bank], -1) for bank in choices], -np.inf, 0)
        for bank in train_banks:
            col = train_bank_col[bank]
            for r in bank[2]:
                row([(aa_col[r, t], 1) for t in assignments[r]['eligible']]+
                    [(col, -1)], 0, np.inf)
            for before, after in zip(bank[2], bank[2][1:]):
                difference = [(aa_col[r, t], t*(1 if r == after else -1))
                              for r in (before, after)
                              for t in assignments[r]['eligible']]
                row(difference+[(col, 2000)], -np.inf, 2030)
                row(difference+[(col, -2000)], -1970, np.inf)
    matrix = csc_matrix((vv, (rr, cc)), shape=(len(lower), n))
    pair_costs = [m if minimize_hold else 0 for _, _, m in pairs]
    assignment_costs = [-1 if anchor_policy == 'max_supported' else 0]*len(aa)
    answer = milp(np.r_[np.zeros(nx), pair_costs, assignment_costs,
                         np.zeros(len(banks)+len(train_banks))],
                  integrality=np.ones(n), bounds=Bounds(0, 1),
                  constraints=LinearConstraint(matrix, lower, upper),
                  options={'time_limit': time_limit, 'mip_rel_gap': 0})
    result = {'first_wing': first, 'second_wing': second, 'shifted_rail_targets': shifted,
              'target_substitutions_not_adopted': substitutions,
              'shoulder_headway_cap_min': shoulder, 'core_headway_cap_min': 120,
              'ready_start_min': start, 'candidate_mid_offsets_min': mid_offsets,
              'five_minute_grid': True, 'full_trip_count': full_trip_count,
              'anchor_policy': anchor_policy,
              'vehicle_cap_conditional_not_adopted': vehicle_cap,
              'required_train_bank_start_not_adopted': required_train_bank_start,
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
    original_compatibility = original_target_compatibility(
        original_p, offsets, selected_times)
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
    if anchor_policy == 'fixed_22' and len(chosen) != len(targets):
        raise ValueError('rail target witness verification failed')
    chosen_banks = [{'wing': wing, 'peak': peak, 'start_min': start,
                     'departures_min': [start+30*k for k in range(5)]}
                    for bank, col in bank_col.items() if answer.x[col] > .5
                    for wing, peak, start in [bank]]
    if anchor_policy != 'fixed_22' and len(chosen_banks) != 4:
        if anchor_policy != 'flexible_real_trains':
            raise ValueError('missing full H30 banks')
    chosen_train_banks = [
        {'wing': wing, 'kind': kind,
         'rail_minutes': [assignments[r]['rail_min'] for r in group],
         'bus_departures_min': [next(a['wing_fs_departure_min'] for a in chosen
                                     if a['wing'] == wing and a['kind'] == kind
                                     and a['rail_min'] == assignments[r]['rail_min'])
                                for r in group]}
        for bank, col in train_bank_col.items() if answer.x[col] > .5
        for wing, kind, group in [bank]]
    if anchor_policy == 'flexible_real_trains':
        if len(chosen_train_banks) != 4 or len(chosen) != 20:
            raise ValueError('incomplete real-train H30 banks')
        if any(any(b-a != 30 for a, b in zip(bank['bus_departures_min'],
                                              bank['bus_departures_min'][1:]))
               for bank in chosen_train_banks):
            raise ValueError('real-train H30 bank has non-H30 bus departures')
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
    original_chosen = [a for a in chosen
                       if (a['wing'].split('_')[0], a['kind'], a['rail_min'])
                       in original_targets]
    result.update(full_trips=selected, rail_assignments=chosen,
                  peak_banks_without_rail_binding=chosen_banks,
                  selected_real_train_banks_not_adopted=chosen_train_banks,
                  original_22_target_compatibility_full_timetable=
                      original_compatibility,
                  original_22_train_targets_all_bound=(len(original_chosen) == 22),
                  original_train_targets_bound_count=len(original_chosen),
                  original_train_targets_unbound=[
                      {'wing': wing, 'kind': kind, 'rail_min': minute}
                      for wing, kind, minute in sorted(original_targets)
                      if not any(a['wing'].startswith(wing) and a['kind'] == kind
                                 and a['rail_min'] == minute for a in original_chosen)],
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
        # Deliberately drop exact train bindings while retaining a two-hour
        # H30 bank on each wing/peak, then maximise the number of ORIGINAL
        # dated targets that still bind. This is a cardinality bound, not a
        # passenger-utility weight or a selected replacement train set.
        for policy in ('h30_unbound', 'max_supported'):
            case = solve(p, loops, first, False, 60, time_limit,
                         anchor_policy=policy)
            case['case_id'] = f'{first}_16_shoulder60_{policy}'
            case['rail_objective_relaxed_not_adopted'] = True
            cases.append(case)
            print(case['case_id'], case['solver_status'], case['witness_found'],
                  case.get('original_train_targets_bound_count'), flush=True)
    real_train_comparisons = [
        ('west_B', 60, 85, None, None),
        ('west_B', 70, 55, None, None),
        ('west_B', 70, 60, None, None),
        ('west_B', 70, 85, 4, None),
        ('east_A', 60, 80, None, None),
        ('east_A', 65, 55, None, None),
        ('east_A', 65, 70, None, None),
        ('east_A', 70, 50, None, None),
        ('east_A', 70, 55, 4, None),
        ('east_A', 70, 80, None, ('west', 'bus_to_rail', 416)),
    ]
    for first, shoulder, max_mid, vehicle_cap, forced_train in real_train_comparisons:
        case = solve(p, loops, first, False, shoulder, time_limit,
                     max_mid=max_mid, anchor_policy='flexible_real_trains',
                     vehicle_cap=vehicle_cap,
                     required_train_bank_start=forced_train)
        forced_label = 'west0656' if forced_train else 'free'
        case['case_id'] = (f'{first}_realtrains_16_shoulder{shoulder}_'
                           f'maxmid{max_mid}_fleet{vehicle_cap or "free"}_'
                           f'{forced_label}')
        case['candidate_orientations_selected'] = False
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
            'engineering_validation_priority_case_id':
                'west_B_realtrains_16_shoulder70_maxmid60_fleetfree_free',
            'engineering_validation_priority_not_network_selection': True,
            'scope': 'Same 27.679 km full road path and 29 design sites in each trip; 16 trips, '
                     'five-minute grid, root FS starts 05:00-19:40, per-trip intermediate '
                     'FS departure offset in seven five-minute values from stress-feasible '
                     'minimum through +30. Ready-time windows 06:45 or 06:50-19:40; '
                     'H120 10-16, tested H60/H65/H70/H90/H95/H120 shoulders. These '
                     'are ready-time opportunity waiting limits, not a cap on every '
                     'consecutive departure gap across a window boundary. In fixed_22 cases '
                     'five core target-bound trips are H30 in each wing. Rail-relaxed '
                     'diagnostics instead enforce explicit five-trip H30 banks per wing/peak '
                     'with starts 05:30-07:30 AM and 15:30-17:30 PM, then count original '
                     'dated targets without weighting or replacing them. Flexible-real-train '
                     'cases choose five consecutive actual dated trains per wing and per peak '
                     'from 06:56-09:56 Milan departures and 16:02-19:32 inbound arrivals; '
                     'their selection is diagnostic, not a demand-derived train preference. '
                     'A four-vehicle cap tests only common deterministic worst stress. '
                     '17/18-trip cases '
                     'are non-adopted comparisons. '
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
