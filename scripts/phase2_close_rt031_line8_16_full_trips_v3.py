"""16 identical full circuits: audit timing assumptions without dropping targets.

H30 event banks are explicitly NOT the former all-site common-clock promise.
All rail targets remain; wider wait bounds are comparisons, not user choices.
"""
import argparse
import copy
import gzip
import json
import math

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csc_matrix

from scripts.phase2_rebuild_rt031_uniform_complete_line_v3 import (
    ROOT, BASE, inputs, timing_offsets, source_fingerprints, digest, clock)
from scripts.phase2_solve_rt031_line8_flexible_peaks_v3 import interval_covers
from scripts.phase2_audit_rt031_line8_passenger_peaks_v3 import uncovered_intervals
from scripts.phase2_audit_rt031_line8_independent_wings_v3 import minimum_blocks
from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops

AUTH = ROOT / 'config/rt031_16_full_trips_authority_v3.json'
OUTPUT = BASE / 'uniform_16_full_trips.json.gz'
DOC = ROOT / 'docs/RT031_LINEA8_16_GIRI_COMPLETI_V3.md'
FREE_ORDER = BASE / 'free_order_road_comparison.json'


def domain_inputs(p, loops, first, midpoint, offpeak='inherited'):
    grid = timing_offsets(loops, first, midpoint)
    departures = list(range(300, 1181, 5))
    covers = set()
    for g in grid.values():
        for row in g['sites'].values():
            for direction in ('to_fs', 'from_fs'):
                events = [(i, t + row[direction]) for i, t in enumerate(departures)]
                windows = ready_windows(row, offpeak)
                for start, end, wait in windows:
                    covers.update(interval_covers(events, start, end, wait))
    banks = [(kind, start) for kind, lo, hi in [('AM', 300, 450), ('PM', 900, 1035)]
             for start in range(lo, hi + 1, 5)]
    return grid, departures, covers, banks


def ready_windows(row, offpeak):
    if offpeak in ('start_0645_h60_shoulders_h120_core', 'start_0650_h60_shoulders_h120_core'):
        start = 405 if '0645' in offpeak else 410
        return [(start, 600, 60), (600, 960, 120), (960, 1180, 60)]
    if offpeak in ('start_0645_cap115_diagnostic', 'start_0650_cap115_diagnostic',
                   'start_0645_cap110_diagnostic', 'start_0650_cap110_diagnostic'):
        start = 405 if '0645' in offpeak else 410
        cap = 110 if 'cap110' in offpeak else 115
        return [(start, 1180, cap), (start, 420, 60), (1135, 1180, 60)]
    if offpeak == 'start_07_staggered_diagnostic':
        return [(420, 1180, 155 if row['wing'] == 'west_B' else 120),
                (420, 450, 60), (1135, 1180, 60)]
    if isinstance(offpeak, (int, float)):
        return [(390, 1180, offpeak), (390, 420, 60), (1135, 1180, 60)]
    if offpeak == 'inherited':
        return [(390, 1180, 155 if row['wing'] == 'west_B' else 120),
                (390, 420, 60), (1135, 1180, 60)]
    if offpeak == 'central_10_16':
        return [(390, 600, 60), (600, 960, 120), (960, 1180, 60)]
    raise ValueError('unknown offpeak comparison')


def rail_eligible(p, grid, departures, am_ceiling, pm_ceiling):
    requirements = []
    for wing, kind, minute in sorted({(a['wing'], a['kind'], a['rail_min']) for a in p['anchors']}):
        sid = next(s for s, r in grid[1.1, .5]['sites'].items() if r['wing'].startswith(wing))
        eligible = []
        for i, t in enumerate(departures):
            if kind == 'bus_to_rail':
                ok = all(-1e-8 <= minute-t-g['sites'][sid]['fs_arrival']-3 <= am_ceiling+1e-8
                         for g in grid.values())
            else:
                ok = 3 <= t+grid[1.1, .5]['sites'][sid]['from_fs']-minute <= pm_ceiling
            if ok:
                eligible.append(i)
        requirements.append({'wing': wing, 'kind': kind, 'rail_min': minute, 'eligible': eligible})
    return requirements


def solve_case(p, loops, first, midpoint, am_ceiling, pm_ceiling, offpeak='inherited', exact_count=None):
    second = next(k for k in loops if k != first)
    if not all(p['family']['joins'].get(k) is True for k in (first+'>'+second, second+'>'+first)):
        raise ValueError('unrepresented complete-route join')
    grid, departures, covers, banks = domain_inputs(p, loops, first, midpoint, offpeak)
    rail = rail_eligible(p, grid, departures, am_ceiling, pm_ceiling)
    # Explicit per-target matching prevents one bus arrival being advertised
    # as distinct H30 connections to two consecutive target trains.
    assignments = [(r, i) for r, row in enumerate(rail) for i in row['eligible']]
    n = len(departures); nb = len(banks); nv = n + nb + len(assignments)
    rr = []; cc = []; vv = []; lower = []; upper = []

    def constraint(values, lo, hi):
        rid = len(lower)
        for col, value in values:
            rr.append(rid); cc.append(col); vv.append(value)
        lower.append(lo); upper.append(hi)

    for cover in sorted(covers):
        constraint([(i, 1) for i in cover], 1, np.inf)
    index = {t: i for i, t in enumerate(departures)}
    for b, (kind, start) in enumerate(banks):
        for t in range(start, start+121, 30):
            constraint([(index[t], 1), (n+b, -1)], 0, np.inf)
    for kind in ('AM', 'PM'):
        constraint([(n+b, 1) for b, (k, _) in enumerate(banks) if k == kind], 1, 1)
    for r in range(len(rail)):
        constraint([(n+nb+a, 1) for a, (r0, _) in enumerate(assignments) if r0 == r], 1, 1)
    # Protect H30 on the actual five core train connections on EACH wing,
    # not just an arbitrary early/late regular bank elsewhere in the day.
    for wing in ('west', 'east'):
        for kind in ('bus_to_rail', 'rail_to_bus'):
            core = sorted([r for r, row in enumerate(rail) if row['wing'] == wing and row['kind'] == kind],
                          key=lambda r: rail[r]['rail_min'])[:5]
            for previous, following in zip(core, core[1:]):
                values = [(n+nb+a, departures[i]*(1 if r == following else -1))
                          for a, (r, i) in enumerate(assignments) if r in (previous, following)]
                constraint(values, 30, 30)
    for a, (_, i) in enumerate(assignments):
        constraint([(n+nb+a, 1), (i, -1)], -np.inf, 0)
    for wing in ('west', 'east'):
        for kind in ('bus_to_rail', 'rail_to_bus'):
            for i in range(n):
                group = [(n+nb+a, 1) for a, (r, ii) in enumerate(assignments)
                         if ii == i and rail[r]['wing'] == wing and rail[r]['kind'] == kind]
                if group:
                    constraint(group, -np.inf, 1)
    if exact_count is not None:
        constraint([(i, 1) for i in range(n)], exact_count, exact_count)
    matrix = csc_matrix((vv, (rr, cc)), shape=(len(lower), nv))
    answer = milp(np.r_[np.ones(n), np.zeros(nv-n)], integrality=np.ones(nv),
                  bounds=Bounds(0, 1), constraints=LinearConstraint(matrix, lower, upper),
                  options={'time_limit': 20, 'mip_rel_gap': 0})
    result = {'first_wing': first, 'second_wing': next(k for k in loops if k != first),
              'midpoint_departure_offset_min': midpoint, 'am_residual_wait_ceiling_min': am_ceiling,
              'pm_train_to_bus_ceiling_min': pm_ceiling, 'offpeak_comparison': offpeak,
              'exact_count_tested': exact_count, 'solver_status': int(answer.status),
              'minimum_proven': answer.status == 0 and exact_count is None,
              'infeasibility_proven': answer.status == 2, 'witness_found': answer.x is not None}
    if answer.x is None:
        if answer.status not in (1, 2):
            raise ValueError('16-trip comparison solver failure')
        return result
    if max(abs(answer.x-np.rint(answer.x))) > 1e-6:
        raise ValueError('fractional service witness')
    selected = [t for t, x in zip(departures, answer.x[:n]) if x > .5]
    chosen_banks = [{'peak': kind, 'root_start_min': start, 'departures_min': list(range(start, start+121, 30))}
                    for b, (kind, start) in enumerate(banks) if answer.x[n+b] > .5]
    chosen_rail = [{**{k: v for k, v in rail[r].items() if k != 'eligible'},
                    'full_trip_departure_min': departures[i]}
                   for a, (r, i) in enumerate(assignments) if answer.x[n+nb+a] > .5]
    result.update(full_trip_count=len(selected), full_trip_departures_min=selected,
                  peak_banks=chosen_banks, rail_assignments=chosen_rail,
                  annual_service_km=len(selected)*sum(l['distance_m'] for l in loops.values())/1000*260)
    if exact_count == 16:
        result['full_trip_stop_event_ledger_nominal'] = full_trip_stop_ledger(loops, first, midpoint, selected)
    result['verification'] = verify(p, loops, result)
    return result


def full_trip_stop_ledger(loops, first, midpoint, departures):
    """Ordered design events, not a claim of kerbside permission or observed time."""
    second = next(k for k in loops if k != first)
    nominal = adjusted_loops(loops, 1.1, .5)
    rows = []
    for t in departures:
        events = [{'role': 'FULL_TRIP_START_AT_FS', 'time_min': t,
                   'boarding_authorised': False, 'physical_platform_side': None}]
        for wing, shift, edge_prefix in ((first, 0, 0),
                                         (second, midpoint, len(loops[first]['edge_ids']))):
            for e in sorted(nominal[wing]['events'],
                            key=lambda x: (x['path_node_index'], x['stop_place_id'])):
                events.append({'role': 'DESIGN_STOP_OCCURRENCE', 'wing': wing,
                               'site_id': e['stop_place_id'], 'occurrence_id': e['occurrence_id'],
                               'full_path_edge_index': edge_prefix+e['path_node_index'],
                               'alight_event_min': t+shift+e['offset_from_wing_origin_min']-.5,
                               'board_event_min': t+shift+e['offset_from_wing_origin_min'],
                               'boarding_authorised': False, 'physical_platform_side': None})
            if wing == first:
                events.append({'role': 'INTERMEDIATE_FS_PUBLIC_STOP_STAY_ONBOARD_DESIGN',
                               'arrival_min': t+nominal[first]['road_minutes'],
                               'departure_min': t+midpoint, 'physical_continuity_certified': False})
        events.append({'role': 'FULL_TRIP_END_AT_FS',
                       'arrival_min': t+midpoint+nominal[second]['road_minutes'],
                       'cross_trip_passenger_continuation_certified': False})
        rows.append({'full_trip_departure_min': t, 'uniform_full_pattern_id': first+'>'+second,
                     'events': events, 'observed_timetable': False})
    return rows


def verify(p, loops, result):
    departures = result['full_trip_departures_min']
    if departures != sorted(set(departures)) or any(t not in range(300, 1181, 5) for t in departures):
        raise ValueError('duplicate, unordered or out-of-domain full departure')
    if result['full_trip_count'] != len(departures):
        raise ValueError('reported full-trip count drift')
    if 'full_trip_stop_event_ledger_nominal' in result:
        if result['full_trip_stop_event_ledger_nominal'] != full_trip_stop_ledger(
                loops, result['first_wing'], result['midpoint_departure_offset_min'], departures):
            raise ValueError('ordered complete-route stop-event ledger drift')
    if result['exact_count_tested'] is not None and len(departures) != result['exact_count_tested']:
        raise ValueError('wrong full-trip count')
    grid = timing_offsets(loops, result['first_wing'], result['midpoint_departure_offset_min'])
    for g in grid.values():
        for row in g['sites'].values():
            for direction in ('to_fs', 'from_fs'):
                values = [t+row[direction] for t in departures]
                for start, end, wait in ready_windows(row, result['offpeak_comparison']):
                    if uncovered_intervals(values, start, end, wait):
                        raise ValueError('offpeak ready-time gap')
    if {b['peak'] for b in result['peak_banks']} != {'AM', 'PM'}:
        raise ValueError('missing peak')
    for bank in result['peak_banks']:
        if bank['departures_min'] != list(range(bank['root_start_min'], bank['root_start_min']+121, 30)):
            raise ValueError('not a true H30 bank')
        if not set(bank['departures_min']).issubset(departures):
            raise ValueError('absent H30 full trip')
    targets = {(a['wing'], a['kind'], a['rail_min']) for a in p['anchors']}
    if (len(result['rail_assignments']) != len(targets)
            or {(a['wing'], a['kind'], a['rail_min']) for a in result['rail_assignments']} != targets):
        raise ValueError('rail target dropped')
    reused = set(); rail_checks = []; all_waits = []
    for wing in ('west', 'east'):
        for kind in ('bus_to_rail', 'rail_to_bus'):
            core = sorted([a for a in result['rail_assignments'] if a['wing'] == wing and a['kind'] == kind],
                          key=lambda a: a['rail_min'])[:5]
            if len(core) != 5 or any(b['full_trip_departure_min']-a['full_trip_departure_min'] != 30
                                     for a, b in zip(core, core[1:])):
                raise ValueError('actual core rail trips are not H30')
    for a in result['rail_assignments']:
        t = a['full_trip_departure_min']; key = (a['wing'], a['kind'], t)
        if key in reused or t not in departures:
            raise ValueError('rail target reuses same wing event or absent full trip')
        reused.add(key)
        field = 'departure_min' if a['kind'] == 'bus_to_rail' else 'arrival_min'
        direction = 'MILANO' if a['kind'] == 'bus_to_rail' else 'LECCO'
        trains = [e for e in p['rail']['events'] if e['direction'] == direction and e[field] == a['rail_min']]
        if len(trains) != 1:
            raise ValueError('rail event absent or ambiguous')
        for sid, row in grid[1.1, .5]['sites'].items():
            if not row['wing'].startswith(a['wing']):
                continue
            if a['kind'] == 'bus_to_rail':
                waits = [a['rail_min']-t-g['sites'][sid]['fs_arrival']-3 for g in grid.values()]
                if min(waits) < -1e-8 or max(waits) > result['am_residual_wait_ceiling_min']+1e-8:
                    raise ValueError('AM connection outside declared comparison')
                nominal = a['rail_min']-t-row['fs_arrival']
                all_waits.append(nominal)
            else:
                waits = [t+row['from_fs']-a['rail_min']]
                nominal = waits[0]
                if not 3 <= nominal <= result['pm_train_to_bus_ceiling_min']:
                    raise ValueError('PM connection outside declared comparison')
            rail_checks.append({'site_id': sid, **a, 'rail_trip_id': trains[0]['trip_id'],
                                'nominal_total_connection_min': nominal,
                                'scenario_min_checked_min': min(waits), 'scenario_max_checked_min': max(waits)})
    scenarios = []
    for (moving, dwell), g in grid.items():
        for recovery in (5, 10, 15):
            blocks = minimum_blocks([{'loop': 'FULL_EIGHT', 'departure_min': t} for t in departures],
                                    {'FULL_EIGHT': {'road_minutes': g['full_trip_arrival']}},
                                    {'FULL_EIGHT>FULL_EIGHT': True}, recovery)
            scenarios.append({'moving_multiplier': moving, 'dwell_min': dwell,
                              'terminal_recovery_min': recovery, **blocks})
    nominal = grid[1.1, .5]
    peak_events = [{'site_id': sid, 'wing': row['wing'], 'direction': direction, 'peak': b['peak'],
                    'first_opportunity_min': b['root_start_min']+row[direction],
                    'last_opportunity_min': b['root_start_min']+120+row[direction],
                    'occurrence_id': row['board_occurrence_id'] if direction == 'to_fs' else 'FS departure',
                    'headway_min': 30}
                   for sid, row in nominal['sites'].items() for direction in ('to_fs', 'from_fs')
                   for b in result['peak_banks']]
    gaps = [b-a for a, b in zip(departures, departures[1:])]
    maximal_banks = []
    run = [departures[0]]
    for t in departures[1:]:
        if t-run[-1] == 30:
            run.append(t)
        else:
            if len(run) >= 5:
                maximal_banks.append(run)
            run = [t]
    if len(run) >= 5:
        maximal_banks.append(run)
    return {'rail_bindings': rail_checks, 'peak_site_events_nominal': peak_events,
            'all_9_same_scenario_h30_event_banks_pass': True,
            'actual_five_core_train_bound_trips_h30_each_wing_am_and_pm': True,
            'all_27_resource_cases': scenarios,
            'maximal_regular_h30_root_departure_sequences': maximal_banks,
            'maximum_consecutive_opportunity_gap_min': max(gaps),
            'root_departure_gaps_min': gaps,
            'same_gap_sequence_at_each_fixed_occurrence_in_each_common_scenario': True,
            'max_nominal_am_station_time_including_transfer_min': max(all_waits),
            'nominal_intermediate_fs_wait_min': nominal['midpoint_departure']-nominal['midpoint_arrival'],
            'first_full_departure_min': min(departures), 'last_full_departure_min': max(departures),
            'last_full_arrival_nominal_min': max(departures)+nominal['full_trip_arrival'],
            'all_site_common_clock_legacy_peak_windows_certified': False,
            'independent_trip_delays_certified': False, 'operating_authorised': False}


def read_result():
    return json.loads(gzip.decompress(OUTPUT.read_bytes()))


def authority():
    a = json.loads(AUTH.read_text(encoding='utf-8'))
    if (a['full_commercial_trips_per_day_adopted'] != 16
            or a['short_turn_public_trips_allowed'] or not a['both_wings_in_every_trip']
            or a['exact_peak_phases_or_connection_wait_changes_adopted']):
        raise ValueError('caller scope drift; do not silently change service promises')
    return a


def staggered_rail_inputs(p, delayed_wing):
    """Compare, never adopt: move two target trains on one wing, not sites."""
    if delayed_wing not in ('west', 'east'):
        raise ValueError('unknown delayed wing')
    comparison = copy.deepcopy(p)
    substitutions = [
        {'wing': delayed_wing, 'kind': 'bus_to_rail', 'from_rail_min': 446, 'to_rail_min': 596},
        {'wing': delayed_wing, 'kind': 'rail_to_bus', 'from_rail_min': 992, 'to_rail_min': 1142},
    ]
    for replacement in substitutions:
        matching = [a for a in comparison['anchors'] if
                    (a['wing'], a['kind'], a['rail_min']) ==
                    (replacement['wing'], replacement['kind'], replacement['from_rail_min'])]
        if not matching:
            raise ValueError('shifted rail source missing')
        for a in matching:
            a['rail_min'] = replacement['to_rail_min']
            a.pop('eligible', None)  # Inherited old-time candidate indices are invalid here.
        direction = 'MILANO' if replacement['kind'] == 'bus_to_rail' else 'LECCO'
        field = 'departure_min' if replacement['kind'] == 'bus_to_rail' else 'arrival_min'
        if len([e for e in p['rail']['events'] if
                e['direction'] == direction and e[field] == replacement['to_rail_min']]) != 1:
            raise ValueError('replacement rail event not uniquely present in frozen service date')
    originals = {(a['wing'], a['kind'], a['rail_min']) for a in p['anchors']}
    shifted = {(a['wing'], a['kind'], a['rail_min']) for a in comparison['anchors']}
    if len(originals) != 22 or len(shifted) != 22 or len(originals-shifted) != 2 or len(shifted-originals) != 2:
        raise ValueError('target substitution has unexpected scope')
    return comparison, substitutions


def build():
    a = authority()
    _, p, _, _, loops = inputs()
    km = 16*sum(l['distance_m'] for l in loops.values())/1000*260
    if abs(km-a['specific_annual_service_km_comparison_accepted']) > 1e-6:
        raise ValueError('geometry or specific 16-trip production drift')
    cases = []
    for first in ('west_B', 'east_A'):
        minimum = 5*math.ceil((adjusted_loops(loops, 1.1, 1)[first]['road_minutes']+1)/5)
        for midpoint in range(minimum, minimum+31, 5):
            # Offpeak and common-clock peak promises are not silently adopted
            # together with the caller's choice of the daily full-trip count.
            for cap, count in [('inherited', None), (210, 16), (215, 16)]:
                c = solve_case(p, loops, first, midpoint, p['wait_ceiling'], 8, cap, count)
                c['case_id'] = f'{first}_M{midpoint}_{cap}'
                cases.append(c)
                print(c['case_id'], c['solver_status'], c.get('full_trip_count'), flush=True)
    same_bounds = [c for c in cases if c['offpeak_comparison'] == 'inherited']
    lower = [c for c in cases if c['offpeak_comparison'] == 210]
    witnesses = [c for c in cases if c['offpeak_comparison'] == 215 and c['witness_found']]
    staggered = []
    for first, midpoint, delayed in [('west_B', 60, 'east'), ('east_A', 55, 'west')]:
        q, replacements = staggered_rail_inputs(p, delayed)
        c = solve_case(q, loops, first, midpoint, p['wait_ceiling'], 8,
                       'start_07_staggered_diagnostic', 16)
        if not c['witness_found']:
            raise ValueError('declared staggered comparison lacks 16-trip witness')
        c['case_id'] = f'{first}_M{midpoint}_staggered_{delayed}'
        c['rail_target_substitutions_not_adopted'] = replacements
        c['original_22_train_targets_all_retained'] = False
        c['new_22_train_target_bindings_verified'] = True
        c['ready_service_start_min_not_adopted'] = 420
        staggered.append(c)
    refined = []
    early_start_failures = []
    tighter_gap_failures = []
    h60_shoulder_minima = []
    for first, midpoint, delayed, start in [('west_B', 60, 'east', 405),
                                             ('east_A', 55, 'west', 410)]:
        q, replacements = staggered_rail_inputs(p, delayed)
        minimum = 5*math.ceil((adjusted_loops(loops, 1.1, 1)[first]['road_minutes']+1)/5)
        for offset in range(minimum, minimum+31, 5):
            c = solve_case(q, loops, first, offset, p['wait_ceiling'], 8, 120, 16)
            c['case_id'] = f'{first}_M{offset}_shifted_0630_cap120'
            early_start_failures.append(c)
            c = solve_case(q, loops, first, offset, p['wait_ceiling'], 8,
                           f"start_{'0645' if start == 405 else '0650'}_cap110_diagnostic", 16)
            c['case_id'] = f'{first}_M{offset}_shifted_cap110'
            tighter_gap_failures.append(c)
            c = solve_case(q, loops, first, offset, p['wait_ceiling'], 8,
                           f"start_{'0645' if start == 405 else '0650'}_h60_shoulders_h120_core")
            c['case_id'] = f'{first}_M{offset}_shifted_h60_shoulders_h120_core'
            h60_shoulder_minima.append(c)
        c = solve_case(q, loops, first, midpoint, p['wait_ceiling'], 8,
                       f"start_{'0645' if start == 405 else '0650'}_cap115_diagnostic", 16)
        if not c['witness_found'] or c['verification']['maximum_consecutive_opportunity_gap_min'] != 115:
            raise ValueError('declared 115-minute staggered comparison lacks a witness')
        c['case_id'] = f'{first}_M{midpoint}_shifted_start{start}_cap115'
        c['rail_target_substitutions_not_adopted'] = replacements
        c['original_22_train_targets_all_retained'] = False
        c['new_22_train_target_bindings_verified'] = True
        c['ready_service_start_min_not_adopted'] = start
        refined.append(c)
    if not all(c['infeasibility_proven'] for c in early_start_failures+tighter_gap_failures):
        raise ValueError('claimed finite-domain infeasibility did not reproduce')
    if (not all(c['minimum_proven'] for c in h60_shoulder_minima)
            or min(c['full_trip_count'] for c in h60_shoulder_minima) != 18):
        raise ValueError('H60 shoulder trip-count lower bound did not reproduce')
    free_order = json.loads(FREE_ORDER.read_text(encoding='utf-8'))
    certified = {row['reference_pattern']: row for row in free_order['audits']
                 if row['reference_pattern'] in loops and
                 row['minimum_distance_proven_in_represented_fixed_boundary_domain']}
    if set(certified) != set(loops) or len(free_order['reference_site_ids']) != 28:
        raise ValueError('retained-site free-order proof missing or scope changed')
    for pattern, loop in loops.items():
        if abs(certified[pattern]['distance_m']-loop['distance_m']) > 1e-6:
            raise ValueError('fixed-site road minimum no longer matches 29-site design path')
    current_full_km = sum(l['distance_m'] for l in loops.values())/1000
    max_full_km_at_18_same_production = km/(18*260)
    road_length_audit = {
        'source': str(FREE_ORDER.relative_to(ROOT)).replace('\\', '/'),
        'source_sha256_normalized_newlines': digest(FREE_ORDER),
        'reference_site_count_before_on_path_N1212_addition': len(free_order['reference_site_ids']),
        'current_design_site_count_including_fs': 29,
        'same_road_path_with_N1212_on_path': True,
        'fixed_boundary_all_retained_site_free_order_minima_km':
            {k: certified[k]['distance_m']/1000 for k in sorted(certified)},
        'current_complete_route_km': current_full_km,
        'maximum_complete_route_km_for_18_trips_at_current_16_trip_annual_production':
            max_full_km_at_18_same_production,
        'required_saving_km_per_complete_route': current_full_km-max_full_km_at_18_same_production,
        'required_saving_fraction_of_current_route':
            (current_full_km-max_full_km_at_18_same_production)/current_full_km,
        'free_interior_stop_reordering_saving_km_in_fixed_boundary_domain': 0.0,
        'can_reach_18_trips_at_current_production_by_interior_reordering_only': False,
        'domain': 'Frozen graph, represented via-node restrictions, fixed FS-to-first and last-to-FS '
                  'boundary paths, all 28 prior site identities retained. N1212 is an added '
                  'on-path event with no route-distance change. Does not certify full-history '
                  'restrictions, bus manoeuvres, alternate boundary legs or another street graph.',
        'route_shortening_adopted': False,
    }
    return {'contract': 'RT031_16_COMPLETE_TRIPS_TIMING_AUDIT_V3',
            'authority_source': str(AUTH.relative_to(ROOT)).replace('\\', '/'),
            'authority_sha256': digest(AUTH), 'parent_sources': source_fingerprints(p, loops),
            'full_trips_adopted_per_day': 16, 'annual_service_km': km,
            'assumed_service_days': 260, 'annual_calendar_adopted': False,
            'current_design_site_count': 29, 'geometry_changed': False,
            'accepted_addition_ids': ['N1212'], 'rejected_addition_ids': ['N0655'],
            'full_route_source': 'uniform_complete_line_rebuild.json.gz',
            'all_trips_same_complete_path_within_each_comparison': True,
            'comparisons_mix_different_roots_in_one_timetable': False,
            'cases': cases,
            'staggered_120_minute_diagnostics': staggered,
            'refined_115_minute_diagnostics': refined,
            'shifted_start_0630_cap120_all_14_offsets_infeasible': early_start_failures,
            'shifted_cap110_all_14_offsets_infeasible': tighter_gap_failures,
            'shifted_h60_shoulders_h120_core_all_14_minima': h60_shoulder_minima,
            'minimum_full_trips_with_shifted_rail_h60_shoulders_h120_core': 18,
            'minimum_annual_service_km_at_260_assumed_days_h60_shoulders_h120_core':
                18*sum(l['distance_m'] for l in loops.values())/1000*260,
            'eighteen_full_trips_adopted': False,
            'road_length_budget_audit': road_length_audit,
            'refined_diagnostics_adopted': False,
            'staggered_comparisons_adopted': False,
            'staggered_ready_start_07_accepted': False,
            'original_rail_targets_and_wait_bounds_retained_in_42_base_cases': True,
            'unique_train_wing_targets': len({(x['wing'], x['kind'], x['rail_min']) for x in p['anchors']}),
            'minimum_full_count_with_h30_banks_and_inherited_offpeak': min(
                c['full_trip_count'] for c in same_bounds if c['witness_found']),
            'all_inherited_offpeak_minima_proven': all(c['minimum_proven'] or c['infeasibility_proven'] for c in same_bounds),
            'all_examined_16_trip_210_minute_cases_infeasible': all(c['infeasibility_proven'] for c in lower),
            'witness_16_trip_215_minute_case_ids': [c['case_id'] for c in witnesses],
            'scope': 'Two cyclic roots separately, seven fixed intermediate-FS offsets per root, five-minute full departures 05:00-19:40. H30 enforced on all five AM target-bound trips and first five PM target-bound trips for EACH wing, plus explicit full-departure banks; site-specific clock windows, not former identical all-site common-clock guarantee. Nine common engineering timing scenarios, not independent per-trip delays. Ready-time base 06:30-19:40 with inherited 60-minute edges. Limits 210 and 215 minutes are explicitly non-adopted offpeak diagnostics. All dated train targets and original connection wait ceilings preserved with distinct bus events per target on each wing. No global continuous-time, variable-offset or terminal-location optimum.',
            'reference_am_ceiling_min': p['wait_ceiling'], 'reference_pm_train_to_bus_ceiling_min': 8,
            'detailed_timetable_adopted': False, 'h30_phase_changes_adopted': False,
            'offpeak_215_minutes_adopted': False, 'new_fleet_increase_accepted': False,
            'physical_passenger_continuity_certified': False, 'operating_plan_adopted': False,
            'decision_budget_km': None, 'uncertainty_band_min': None,
            'network_selected': False, 'primary_selection_authorised': False,
            'runner_up_selection_authorised': False}


def report(r):
    lines = ['# Linea 8 — 16 giri completi: scelta registrata, orario ancora da accettare', '',
        '**Scelta del committente: 16 corse complete al giorno, tutte sullo stesso otto.** '
        'Con geometria invariata sono **115.143,267 km di servizio/anno** su 260 giorni ipotizzati: '
        '**+3.724,267 km (+3,34%)** sul riferimento di 111.419. Non è approvazione del calendario, '
        'di un budget complessivo, di più mezzi o dell’esercizio.', '',
        'Restano 29 siti di progetto: Arlate/Via Nuova Provinciale inclusa, aggiunta N0655 sul cavalcavia '
        'esclusa; Olgiate sud e San Zeno/Via Cantù mantenuti. Nessuna corsa limitata a un’ala.', '',
        '![Tracciato unico confermato della Linea 8: entrambe le ali sono percorse in ognuno dei 16 giri; '
        '29 siti di progetto](../outputs/phase2/rt031_line8_local_shortcuts_v3/linea8_16_giri_tracciato.png)', '',
        'La mappa unisce la geometria stradale già confermata alla nuova fermata di progetto N1212 ad Arlate. '
        'I punti non certificano posizione o autorizzazione fisica delle paline. I colori distinguono le ali '
        'del medesimo giro, **non due linee**; la precedenza di percorrenza resta da scegliere. '
        'Rigenerazione della mappa interattiva: '
        '`python scripts/phase2_render_rt031_16_route_inline_v3.py --output <percorso-html>`.', '',
        '## Risultato concreto e limite da non nascondere', '',
        '**Esistono esempi a 16 giri che conservano tutti i treni-obiettivo e vere sequenze H30, '
        'ma nel confronto lasciano due intervalli di 215 minuti (3 ore e 35): '
        '08:30–12:05 e 12:05–15:40 alla partenza del giro nell’esempio prima ovest. '
        'Questo peggioramento non è stato accettato e non è la proposta finale.**', '',
        f"Con i precedenti limiti centrali di 155 minuti ovest / 120 est, il minimo resta "
        f"**{r['minimum_full_count_with_h30_banks_and_inherited_offpeak']} giri** nel nuovo dominio. "
        'Non si passa automaticamente a quel numero: la scelta corrente resta 16.', '',
        'Sono stati confrontati separatamente due ordini del medesimo otto, con sette offset '
        'di ripartenza intermedia da FS ciascuno, partenze ogni cinque minuti. '
        'I 14 test a 16 giri e limite di 210 minuti sono infeasibili; alcuni test a 215 passano. '
        'Il limite riguarda questo dominio, non ogni possibile orario, capolinea o regolazione.', '',
        '## Miglioramento del confronto a 16 giri: 115 minuti', '',
        '**Due orari diagnostici mantengono i 16 giri completi, le 29 fermate di progetto e le '
        'sequenze H30 sui cinque treni centrali di punta per ciascuna ala; il massimo intervallo '
        'tra partenze scende a 115 minuti.** La copertura garantita comincia alle **06:45** '
        'se parte prima l’ala ovest, alle **06:50** se parte prima l’est: non alle 07:00 del '
        'precedente confronto. La prima corsa da FS parte prima, perché deve attraversare '
        'entrambe le ali. Restano le due sostituzioni di treni-obiettivo nella seconda ala; '
        'non sono né cancellazioni di treni reali né scelte già accettate.', '',
        '| Prima ala del giro unico | Copertura garantita da | Prima/ultima partenza FS | '
        'Prosecuzione intermedia FS | Massimo intervallo | Sosta intermedia nominale | '
        'Mezzi nominali / massimo nei 27 scenari |',
        '|---|---|---|---:|---:|---:|---:|']
    for c in r['refined_115_minute_diagnostics']:
        v = c['verification']
        nominal = next(x for x in v['all_27_resource_cases'] if
                       (x['moving_multiplier'], x['dwell_min'], x['terminal_recovery_min']) == (1.1, .5, 10))
        worst = max(x['minimum_vehicle_count_conditional'] for x in v['all_27_resource_cases'])
        lines.append(f"| {'Ovest' if c['first_wing'] == 'west_B' else 'Est'} | "
                     f"{clock(c['ready_service_start_min_not_adopted'])} | "
                     f"{clock(v['first_full_departure_min'])} / {clock(v['last_full_departure_min'])} | "
                     f"+{c['midpoint_departure_offset_min']} min | "
                     f"{v['maximum_consecutive_opportunity_gap_min']} min | "
                     f"{v['nominal_intermediate_fs_wait_min']:.2f} min | "
                     f"{nominal['minimum_vehicle_count_conditional']} / {worst} |")
    west, east = r['refined_115_minute_diagnostics']
    lines += ['', 'Partenze dei **16 giri completi da Olgiate FS**, non orario adottato. '
              'Ogni giro torna a FS a metà e prosegue nell’altra ala, con la sosta intermedia '
              'contata nel viaggio:', '',
              '| Giro | Prima ovest, FS | Prima est, FS |', '|---:|---|---|']
    for i, (w, e) in enumerate(zip(west['full_trip_departures_min'], east['full_trip_departures_min']), 1):
        lines.append(f'| {i} | {clock(w)} | {clock(e)} |')
    lines += ['',
        'I 22 obiettivi ala/treno restano 22, ma due cambiano rispetto ai precedenti: nella seconda '
        'ala 07:26 → 09:56 verso Milano e 16:32 → 19:02 da Milano. Restano 308 controlli '
        'sito/treno per ciascun esempio; non viene inferita domanda passeggeri. '
        'Nel dominio di sette offset intermedi per ciascuna delle due precedenze e partenze '
        'ogni cinque minuti, **nessun test con copertura dalle 06:30 e limite 120 minuti riesce**; '
        'con le coperture 06:45/06:50 **nessun test con limite 110 minuti riesce**. '
        'Queste sono prove finite nel dominio dichiarato, non impossibilità universali.', '',
        '**Resta una rinuncia reale:** H115 appare già dopo la punta mattutina e quindi non '
        'rispetta H60 fuori dalla sola morbida pesante 10–16. Né il primo ramo né le due '
        'sostituzioni ferroviarie né questi intervalli sono autorizzati. La continuità di '
        'veicolo e passeggeri, le paline e il fabbisogno di flotta restano condizionali.', '',
        '**Quanto costa conservare H60 fuori 10–16?** Anche usando i due obiettivi ferroviari '
        'sostituiti nella seconda ala, e consentendo H120 fra le 10 e le 16, il minimo esatto '
        'nei 14 offset del dominio è **18 giri completi**. A 260 giorni ipotizzati sono '
        '**129.536,175 km/anno**, circa **+16,26%** rispetto a 111.419: un confronto, non '
        'una proposta di aumento. Perciò i 16 giri scelti e la combinazione H60 nelle spalle '
        '+ H120 solo nella morbida pesante non coesistono in questo dominio. Il risultato non '
        'dimostra impossibilità su ogni possibile regolazione stradale o orario continuo.', '',
        'Per far rientrare **18 giri** negli stessi 115.143,267 km/anno ipotizzati per 16, '
        'il giro dovrebbe scendere da **27,679 a 24,603 km**: **3,075 km in meno '
        '(11,11%)** a ogni giro. L’audit stradale preesistente con tutti i siti mantenuti '
        'e ordine interno libero trova invece esattamente gli stessi 27,679 km come minimo '
        'nelle due ali, a estremi fissati; la nuova fermata N1212 è già sul percorso e non '
        'cambia i km. Quindi una semplice permutazione delle fermate interne **non finanzia** '
        'il passaggio a 18 giri in quel dominio. Non è un minimo globale di un altro grafo, '
        'di nuovi capolinea o di fermate spostate; nessuna geometria viene riaperta o adottata. '
        '[Prova stradale precedente](RT031_LINEA8_ORDINE_LIBERO_FERMATE_V3.md).', '',
        '## Confronto precedente a 120 minuti, conservato per tracciabilità', '',
        '**Due ulteriori orari diagnostici mantengono 16 giri e riducono il massimo intervallo '
        'fra partenze a 120 minuti, senza togliere siti di progetto o cambiare percorso.** '
        'Non sono automaticamente accettati: iniziano la finestra di servizio garantita alle '
        '**07:00 anziché 06:30**, portano l’H90/H120 già dalle **08:30–08:35** in alcune ore, '
        'e sostituiscono **due precisi treni-obiettivo dell’ala che parte seconda**. '
        'Non sono soppressioni dei treni reali: la connessione diretta e breve a quei due treni '
        'non è più garantita nel confronto. Tutti i nuovi treni-obiettivo esistono nel GTFS datato.', '',
        '| Ala percorsa per prima | Due obiettivi modificati solo nella seconda ala | '
        'Primo/ultimo giro da FS | Max intervallo tra partenze |',
        '|---|---|---|---:|']
    for c in r['staggered_120_minute_diagnostics']:
        shifted = c['rail_target_substitutions_not_adopted']
        v = c['verification']
        lines.append(f"| {'Ovest' if c['first_wing'] == 'west_B' else 'Est'} | "
                     f"{'Est' if shifted[0]['wing'] == 'east' else 'Ovest'}: "
                     f"{clock(shifted[0]['from_rail_min'])} → {clock(shifted[0]['to_rail_min'])} per Milano; "
                     f"{clock(shifted[1]['from_rail_min'])} → {clock(shifted[1]['to_rail_min'])} da Milano | "
                     f"{clock(v['first_full_departure_min'])} / {clock(v['last_full_departure_min'])} | "
                     f"{v['maximum_consecutive_opportunity_gap_min']} min |")
    lines += ['',
        'Entrambe le alternative conservano cinque **corse complete H30 abbinate ai treni di punta** '
        'in ciascuna ala, 29 siti di progetto, gli stessi 16 giri e 115.143,267 km/anno ipotizzati. '
        'Hanno 22 obiettivi ala/treno e 308 verifiche ciascuna, ma **non gli stessi 22 del precedente confronto**: '
        'due cambiano. L’ala servita più presto non viene scelta dai dati sull’utenza, che mancano. '
        'La stessa impronta geografica non implica uguale accessibilità nelle diverse ore. '
        'I 120 minuti sono un limite per tutte le ore diurne del confronto: **non soddisfano H60 '
        'fuori dalla sola morbida pesante 10–16**. Non viene selezionata una delle due.', '',
        'Una partenza FS rappresenta l’inizio del giro completo, non tutte le partenze dalle 29 fermate. '
        'Il JSON registra anche **ogni passaggio nominale ordinato alle fermate in ciascuno dei 16 giri** '
        'e la sosta intermedia. Le verifiche sono '
        'ingegneristiche condizionali, non orari approvati o domanda passeggeri osservata.', '',
        '## Confronto che conserva tutti i precedenti treni', '']
    lines += [
        '### Cosa significa H30 in questo confronto', '',
        'Ogni punta contiene almeno cinque corse **complete** consecutive a 30 minuti. '
        'Sono H30 le corse effettivamente abbinate ai cinque treni mattutini e ai primi cinque '
        'arrivi serali di ciascuna ala, non soltanto una sequenza regolare altrove nella giornata. '
        'La sequenza si ritrova a ogni occorrenza di fermata, con l’orario traslato del tempo di viaggio. '
        'Sono mantenuti entrambi gli obiettivi ferroviari di ciascuna ala, non due servizi separati. '
        'Non si dichiara però la stessa finestra 07–09 / 16:55–18:55 simultanea per tutti i siti. '
        'Le finestre per sito sono esportate; la loro utilità e accettazione rimangono aperte. '
        'Gli scenari comuni non sono una probabilità di affidabilità o un test di ritardi indipendenti.', '',
        'Tutti i 22 abbinamenti ala/treno precedenti sono conservati: cinque treni mattutini verso Milano '
        '07:26–09:26, sei arrivi serali 16:32, 17:02, 17:32, 18:02, 18:32, 19:32 per ciascuna ala. '
        'Sono 308 verifiche per sito sui dati ferroviari già fissati al 28 settembre–2 ottobre 2026. '
        'Cambio minimo ipotizzato di tre minuti e limiti d’attesa precedenti invariati. '
        'Una stessa corsa d’ala non viene ricontata come due distinte coincidenze consecutive.', '',
        '### Esempi completi, non orari selezionati', '',
        'Le due tabelle sono alternative diagnostiche, **non due linee né due tipi di corsa nello stesso orario**. '
        'La partenza finale dal capolinea non è l’ultimo passaggio: il giro continua per entrambe le ali.']
    for first, midpoint in [('west_B', 60), ('east_A', 55)]:
        c = next(c for c in r['cases'] if c['first_wing'] == first and c['midpoint_departure_offset_min'] == midpoint
                 and c['offpeak_comparison'] == 215)
        v = c['verification']
        nominal = next(x for x in v['all_27_resource_cases'] if
                       (x['moving_multiplier'], x['dwell_min'], x['terminal_recovery_min']) == (1.1, .5, 10))
        worst = max(x['minimum_vehicle_count_conditional'] for x in v['all_27_resource_cases'])
        duration = v['last_full_arrival_nominal_min']-c['full_trip_departures_min'][-1]
        lines += ['', f"### Esempio: prima {'ovest' if first == 'west_B' else 'est'}", '',
                  f"Sosta nominale a FS intermedia **{v['nominal_intermediate_fs_wait_min']:.2f} minuti**, "
                  f"contata nel viaggio intercomunale. Mezzi condizionali: **{nominal['minimum_vehicle_count_conditional']} "
                  f"nominali / {worst}** nel peggiore caso della griglia; non disponibilità certificata.", '',
                  '| Giro completo | Partenza FS verso prima ala | Prosecuzione FS verso seconda ala | Fine giro nominale |',
                  '|---:|---|---|---|']
        for i, t in enumerate(c['full_trip_departures_min'], 1):
            lines.append(f'| {i} | {clock(t)} | {clock(t+midpoint)} | {clock(t+duration)} |')
        lines += ['', 'Sequenze H30 massimali alla partenza del giro: '+', '.join(
            f"{clock(bank[0])}–{clock(bank[-1])}" for bank in v['maximal_regular_h30_root_departure_sequences'])+'.']
    lines += ['', '## Cosa è chiuso e cosa no', '',
        '- **Chiusi come scelte di progetto:** 16 giri completi, stesso percorso, geometria e scelte fermate. '
        'I 18 giri del confronto H60/H120 non sono adottati.',
        '- **Non chiusi:** un orario utile che rispetti insieme le esigenze; né i 215 minuti con tutti i vecchi treni '
        'né le alternative migliorate a 115 minuti con copertura 06:45/06:50 e due obiettivi ferroviari cambiati '
        'sono autorizzati.',
        '- Il confronto esplicita la scelta ancora necessaria: quali primi treni/prime ore garantire in ciascuna '
        'ala e quale intervallo è tollerabile già dopo la punta mattutina. Se non è accettabile nessuna delle '
        'due alternative migliorate a 115 minuti, il conteggio di 16 giri non ha ancora un orario conclusivo '
        'nel dominio esaminato. '
        'Non si eliminano di nascosto treni, H30, territori o chilometri.',
        '- Restano aperti manovre, paline, tempi osservati, blocchi completi, continuità fra giri successivi, '
        'calendario e costi extra-servizio. Nessuna approvazione operativa o PRIMARY/RUNNER-UP.', '',
        '[Scelta dei 16 giri](../config/rt031_16_full_trips_authority_v3.json) · '
        '[Confronti e verifiche riproducibili (JSON gzip)](../outputs/phase2/rt031_line8_local_shortcuts_v3/uniform_16_full_trips.json.gz)', '',
        'Rigenerazione: `python -m scripts.phase2_close_rt031_line8_16_full_trips_v3` con `PYTHONPATH=.;src` su Windows.']
    return '\n'.join(lines)+'\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', action='store_true')
    args = parser.parse_args()
    _, p, _, _, loops = inputs()
    if args.probe:
        for first, midpoint in [('west_B', 55), ('west_B', 60), ('east_A', 50), ('east_A', 55), ('east_A', 60)]:
            for am, pm in [(p['wait_ceiling'], 8), (35, 8), (40, 8), (45, 8), (45, 18), (45, 28)]:
                c = solve_case(p, loops, first, midpoint, am, pm)
                print(json.dumps({k:v for k,v in c.items() if k not in ('verification','rail_assignments')}, separators=(',',':')), flush=True)
    else:
        r = build()
        OUTPUT.write_bytes(gzip.compress((json.dumps(r, sort_keys=True, ensure_ascii=False, separators=(',', ':'))+'\n').encode('utf-8'), mtime=0))
        DOC.write_text(report(r), encoding='utf-8')
