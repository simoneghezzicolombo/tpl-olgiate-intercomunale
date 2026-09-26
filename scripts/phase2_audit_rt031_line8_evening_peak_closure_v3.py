"""Exact ready-time intersections and a finite add-only evening-witness repair.

Two-hour windows are comparison requirements, not selected Decision Contract
inputs. Passing the optimistic event model is not boarding/operation approval.
"""
import argparse
from collections import Counter
import itertools
import json
import math
from pathlib import Path

from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import (
    BASE, EXPECTED, FLAGS, load_sources, make_trips, ordered,
)
from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops
from scripts.phase2_audit_rt031_line8_independent_wings_v3 import minimum_blocks

WINDOWS = {'AM': (360, 660), 'PM': (900, 1260)}
DIRECTIONS = ('to_fs', 'from_fs')


def merge(intervals):
    result = []
    for lo, hi in sorted(intervals):
        if hi <= lo:
            continue
        if result and lo <= result[-1][1] + 1e-9:
            result[-1][1] = max(hi, result[-1][1])
        else:
            result.append([lo, hi])
    return result


def intersect(a, b):
    return merge((max(x, u), min(y, v)) for x, y in a for u, v in b
                 if min(y, v) > max(x, u))


def ready_intervals(departures, lo, hi):
    return merge((max(lo, t - 30), min(hi, t)) for t in departures)


def opportunities(trips, loops):
    result = {}
    for trip_index, trip in enumerate(trips):
        for event in loops[trip['loop']]['events']:
            value = result.setdefault(event['stop_place_id'], {d: [] for d in DIRECTIONS})
            for direction, minute in (
                    ('from_fs', trip['departure_min']),
                    ('to_fs', trip['departure_min'] + event['offset_from_wing_origin_min'])):
                value[direction].append({'minute': minute, 'trip_index': trip_index,
                                         'pattern': trip['loop'], 'occurrence_id': event['occurrence_id']})
    return result


def common_intervals(sites, peak, directions):
    lo, hi = WINDOWS[peak]
    result = [[lo, hi]]
    for site in sites.values():
        for direction in directions:
            result = intersect(result, ready_intervals([e['minute'] for e in site[direction]], lo, hi))
    return result


def describe(intervals):
    longest = max((b - a for a, b in intervals), default=0)
    # A whole-minute witness is a convenience, not an optimisation or chosen phase.
    witness = next(([math.ceil(a - 1e-8), math.ceil(a - 1e-8) + 120]
                    for a, b in intervals if math.ceil(a - 1e-8) + 120 <= b + 1e-8), None)
    return {'common_intervals_min': [[round(a, 6), round(b, 6)] for a, b in intervals],
            'longest_common_interval_min': round(longest, 6),
            'exists_common_two_hour_window_in_model': longest >= 120 - 1e-8,
            'illustrative_whole_minute_two_hour_window': witness}


def audit(trips, raw_loops, joins):
    aggregate = {(peak, direction): [list(bounds)] for peak, bounds in WINDOWS.items()
                 for direction in (*DIRECTIONS, 'both')}
    scenarios = []
    for multiplier, dwell in itertools.product((.9, 1., 1.1), (0., .5, 1.)):
        loops = adjusted_loops(raw_loops, multiplier, dwell)
        sites = opportunities(trips, loops)
        for peak, direction in aggregate:
            common = common_intervals(sites, peak, DIRECTIONS if direction == 'both' else (direction,))
            aggregate[peak, direction] = intersect(aggregate[peak, direction], common)
        scenarios.append({'moving_multiplier': multiplier, 'dwell_min': dwell,
                          'max_optimistic_identity_gap_min': round(max(
                              max(b - a for a, b in zip(times, times[1:]))
                              for site in sites.values() for direction in DIRECTIONS
                              for times in [sorted(e['minute'] for e in site[direction])]), 6),
                          'minimum_vehicle_counts_by_recovery': [
                              {'recovery_min': recovery,
                               'minimum_vehicle_count_conditional': minimum_blocks(trips, loops, joins, recovery)['minimum_vehicle_count_conditional']}
                              for recovery in (5, 10, 15)]})
    windows = {peak: {direction: describe(aggregate[peak, direction])
                     for direction in (*DIRECTIONS, 'both')} for peak in WINDOWS}
    return {'grid_common_windows': windows, 'conditional_fleet_grid': scenarios,
            'two_hour_both_directions_in_both_peaks_model_pass': all(
                windows[peak]['both']['exists_common_two_hour_window_in_model'] for peak in WINDOWS),
            'two_hour_priority_directions_model_pass': (
                windows['AM']['to_fs']['exists_common_two_hour_window_in_model']
                and windows['PM']['from_fs']['exists_common_two_hour_window_in_model'])}


def redistribute_for_peaks(base, midpoint_times):
    """Two explicit same-inventory witnesses, not an exhaustive phase search."""
    result = [t.copy() for t in base if t['loop'] in ('west_A', 'east_B')]
    for pattern in ('west_B', 'east_A'):
        first = min(t['departure_min'] for t in base if t['loop'] == pattern)
        times = [first - 30, first, *midpoint_times, 970, 1000, 1030, 1060, 1090, 1120, 1180, 1240]
        result.extend({'loop': pattern, 'departure_min': t} for t in times)
    if Counter(t['loop'] for t in result) != Counter(t['loop'] for t in base):
        raise ValueError('redistribution changes pattern inventory')
    return ordered(result)


def build(sources):
    wings, timetable, counterflow = (sources[k] for k in ('wings', 'timetable', 'counterflow'))
    if any(any(item[k] is not False for k in FLAGS) for item in (wings, timetable, counterflow)):
        raise ValueError('decisional evidence')
    families = []
    for name, loops, original, joins in (
            ('original_priority_direction', wings['loops'], timetable['trips'], wings['represented_via_node_joins']),
            ('fast_local_both_directions', counterflow['candidate_loops'],
             counterflow['full_correction_one_minute_retiming']['trips'],
             next(c for c in counterflow['cases'] if c['case_id'] == 'both')['represented_via_node_joins'])):
        base = make_trips(original, 'move_two_smooth_2040')
        candidates = [{'loop': p, 'departure_min': max(t['departure_min'] for t in original if t['loop'] == p) + 30}
                      for p in ('west_A', 'east_B')]
        candidates += [{'loop': p, 'departure_min': 1150} for p in ('west_B', 'east_A')]
        cases = []
        for bits in itertools.product((0, 1), repeat=4):
            added = [t for bit, t in zip(bits, candidates) if bit]
            trips = ordered(base + added)
            annual = sum(loops[t['loop']]['distance_m'] for t in trips) * .26
            cases.append({'case_id': ''.join(map(str, bits)), 'added_trips': added, 'trips': trips,
                          'annual_service_km': round(annual, 6), 'daily_trip_count': len(trips),
                          'removed_trips': [], 'changed_paths': [], 'policy_adopted': False,
                          **audit(trips, loops, joins)})
        passing = [c for c in cases if c['two_hour_both_directions_in_both_peaks_model_pass']]
        least = min((c['annual_service_km'] for c in passing), default=None)
        least_ids = [c['case_id'] for c in passing if c['annual_service_km'] == least]
        retimings = []
        for label, midpoints in (('same_km_clockface_midday_h120', [610, 730, 850]),
                                ('same_km_irregular_midday_max111', [639, 749, 860])):
            trips = redistribute_for_peaks(base, midpoints)
            retimings.append({'case_id': label, 'trips': trips, 'daily_trip_count': len(trips),
                              'annual_service_km': round(sum(loops[t['loop']]['distance_m'] for t in trips) * .26, 6),
                              'pattern_counts_unchanged': True, 'am_five_trip_bank_unchanged': True,
                              'pm_five_trip_bank_unchanged': True, 'evening_1940_and_2040_unchanged': True,
                              'changed_paths': [], 'policy_adopted': False, **audit(trips, loops, joins)})
        families.append({'family_id': name, 'candidate_additions': candidates,
                         'cases': cases, 'passing_case_count': len(passing),
                         'minimum_service_km_in_this_add_only_domain': least,
                         'least_km_case_ids_in_this_add_only_domain': least_ids,
                         'same_km_redistribution_witnesses': retimings,
                         'nominal_baseline_event_opportunities': opportunities(base, adjusted_loops(loops, 1.1, .5))})
    return {'contract': 'RT031_LINE8_EVENING_COMMON_PEAK_CLOSURE_V3',
            'status': 'FINITE_ADD_ONLY_AND_SAME_KM_RETIMING_COMPARISON_NOT_ADOPTED',
            'source_sha256_normalized_newlines': EXPECTED.copy(),
            'families': families, 'annual_service_days_assumption': 260,
            'reference_cap_unchanged': 111419,
            'semantics': {
                'source': 'The move_two_smooth_2040 dispatch case, regenerated from frozen sources; 28 sites, H90 midday, last FS departure 20:40.',
                'domain': 'All 16 subsets of four explicit added wing trips per family. Existing dispatches cannot move or disappear. Finite conditional minimum ONLY, not a global timetable/network optimum.',
                'separate_retiming_domain': 'Two additional constructive witnesses per family redistribute REST trips while retaining every AM trip and original PM five-trip bank, plus 19:40/20:40. Same pattern counts/km, but midday gaps 111/120 minutes and larger conditional fleet. NOT adopted off-peak policy or proof of a global lower bound.',
                'windows': 'Find the full continuous ready-time intersection over 27 nonhub identities, both directions and nine deterministic moving/dwell cases, within AM 06-11 and PM 15-21. Test existence of a 120-minute interval; illustrative phases are NOT adopted peak windows.',
                'metric': 'Ready time until a hypothetical boardable departure, not ride duration or station-arrival time. Optimistic union of occurrences; individual event identities remain in source and nominal evidence. Success does NOT certify authorised boarding or passenger continuity.',
                'grid': 'Same multiplier and dwell for every trip in a scenario. The intersection yields a single window across all cases, not a different window per case. Not stochastic reliability or missed-connection probability.',
                'fleet': 'Represented via-node successor joins with 5/10/15 minute recovery; no full-history, depot or driver-duty certification.',
                'preserved': 'No geographic changes. Original five AM trips and the 19:40/20:40 dispatches remain, preserving their previously tested morning targets and two evening rail opportunities. Other rail opportunities may change under redistribution. No assertion of current railway validity, unchanged operating costs or selected policy.'},
            **{k: False for k in FLAGS}, 'actual_timetable_certified': False,
            'boarding_authorised': False, 'decision_budget_km': None, 'uncertainty_band_min': None,
            'approved_uplift_percent': None, 'total_operating_km': None}


def reproduce():
    return build(load_sources())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=str(BASE / 'evening_peak_closure.json'))
    args = parser.parse_args()
    result = reproduce()
    Path(args.output).write_text(json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    for family in result['families']:
        print(family['family_id'], family['passing_case_count'], family['minimum_service_km_in_this_add_only_domain'], family['least_km_case_ids_in_this_add_only_domain'])
