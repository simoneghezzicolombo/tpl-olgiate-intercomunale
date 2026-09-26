"""Reallocate midday trips to evening, explicitly relaxing off-peak headways.

No road search, demand model, approved timetable or policy selection. Frozen
road/event witnesses are reused verbatim; only their dispatch inventory changes.
"""
import argparse
from collections import Counter
import csv
import hashlib
import itertools
import json
from pathlib import Path

from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops
from scripts.phase2_audit_rt031_line8_independent_wings_v3 import minimum_blocks

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'outputs/phase2/rt031_line8_local_shortcuts_v3'
EXPECTED = {
    'wings': '72060ac2d37a0f32b2efe059c88e785557a617d5132a1b35a2c52d42a2e955de',
    'timetable': 'e999fbd5976935d40eee1dcdc6335e9c34e377d6ca5fc5653bdb4132ab545e68',
    'counterflow': '17186e1e666c99c2830303048e4a242f523267ac4942c16c572085de780a734f',
    'rail': '00b9994c1331ab5caa09a6092815bc5554f07baddbde8a651857a470d0fdb71b',
    'rail_contract': '4b2c3f2a9d05fb1fc42b3b1c1a8d9fbc153c36267721b332dbb2a643df613d72',
}
FLAGS = ('network_selected', 'primary_selection_authorised', 'runner_up_selection_authorised')
PM = [1000, 1030, 1060, 1090, 1120]
# Midday times after the unchanged first REST trip; evening times after PM.
CASES = {
    'baseline': (list(range(580, 941, 60)), []),
    'move_one_smooth_1940': ([580, 640, 730, 820, 880, 940], [1180]),
    'move_two_smooth_2040': ([580, 670, 760, 850, 940], [1180, 1240]),
    'move_two_holes_2040': ([580, 640, 760, 880, 940], [1180, 1240]),
    'one_moved_one_added_2040': ([580, 640, 730, 820, 880, 940], [1180, 1240]),
    'add_two_h60_2040': (list(range(580, 941, 60)), [1180, 1240]),
}


def source_paths():
    return dict(wings=BASE / 'independent_wings.json',
                timetable=BASE / 'peak_direction_retimed.json',
                counterflow=BASE / 'local_counterflow.json',
                rail=ROOT / 'outputs/phase2/s8_events.csv',
                rail_contract=ROOT / 'outputs/phase2/s8_interchange_contract.json')


def load_sources(paths=None):
    paths = source_paths() if paths is None else paths
    for key, expected in EXPECTED.items():
        actual = hashlib.sha256(paths[key].read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        if actual != expected:
            raise ValueError('frozen evidence drift: ' + key)
    result = {key: json.loads(path.read_text(encoding='utf-8'))
              for key, path in paths.items() if key != 'rail'}
    with paths['rail'].open(encoding='utf-8', newline='') as stream:
        result['rail'] = list(csv.DictReader(stream))
    return result


def ordered(trips):
    return sorted(trips, key=lambda t: (t['departure_min'], t['loop']))


def inventory(trips):
    return Counter((t['loop'], t['departure_min']) for t in trips)


def gaps(minutes):
    values = sorted(set(minutes))
    return [{'before_min': round(a, 6), 'after_min': round(b, 6),
             'gap_min': round(b - a, 6)} for a, b in zip(values, values[1:])]


def make_trips(source, case_id):
    midday, evening = CASES[case_id]
    result = []
    for wing, am, rest in (('west', 'west_A', 'west_B'), ('east', 'east_B', 'east_A')):
        own = ordered([t for t in source if t['loop'].startswith(wing)])
        if (len(own) != 18 or [t['loop'] for t in own] != [am] * 5 + [rest] * 13
                or [t['departure_min'] for t in own[-5:]] != PM
                or [t['departure_min'] for t in own[6:13]] != list(range(580, 941, 60))
                or any(b['departure_min'] - a['departure_min'] != 30
                       for a, b in zip(own[:4], own[1:5]))):
            raise ValueError('source trip inventory / peak bank drift')
        result.extend({'loop': t['loop'], 'departure_min': t['departure_min']} for t in own[:6])
        result.extend({'loop': rest, 'departure_min': minute} for minute in midday + PM + evening)
    return ordered(result)


def event_diagnostics(trips, loops):
    """Keep ordered occurrences; identity union is separately labelled optimistic."""
    streams, by_site = [], {}
    for pattern, loop in sorted(loops.items()):
        times = [t['departure_min'] for t in trips if t['loop'] == pattern]
        for event in loop['events']:
            boarding = [t + event['offset_from_wing_origin_min'] for t in times]
            sid = event['stop_place_id']
            value = by_site.setdefault(sid, {'to_fs': [], 'from_fs': []})
            value['to_fs'].extend(boarding)
            value['from_fs'].extend(times)
            streams.append({'pattern': pattern, 'occurrence_id': event['occurrence_id'],
                            'path_node_index': event['path_node_index'], 'stop_place_id': sid,
                            'departures_at_occurrence_min': [round(t, 6) for t in boarding],
                            'within_pattern_gap_max_min': max((g['gap_min'] for g in gaps(boarding)), default=0),
                            'boarding_authorised': False, 'passenger_continuity_certified': False})
    identity = [{'stop_place_id': sid, 'direction': direction,
                 'max_gap_min': max(g['gap_min'] for g in gaps(times))}
                for sid, directions in sorted(by_site.items()) for direction, times in sorted(directions.items())]
    return streams, identity


def evaluate(loops, joins, source, case_id, targets):
    trips = make_trips(source, case_id)
    annual = sum(loops[t['loop']]['distance_m'] for t in trips) * 260 / 1000
    original = sum(loops[t['loop']]['distance_m'] for t in source) * 260 / 1000
    before, after = inventory(source), inventory(trips)
    rows = []
    for multiplier, dwell in itertools.product((.9, 1., 1.1), (0., .5, 1.)):
        adjusted = adjusted_loops(loops, multiplier, dwell)
        _, identity = event_diagnostics(trips, adjusted)
        residuals = []
        for pattern in ('west_A', 'east_B'):
            am = [t for t in trips if t['loop'] == pattern]
            residuals.extend(target - t['departure_min'] - adjusted[pattern]['road_minutes'] - 3
                             for t, target in zip(am, targets))
        for recovery in (5, 10, 15):
            rows.append({'moving_multiplier': multiplier, 'dwell_min': dwell,
                         'recovery_per_wing_trip_min': recovery,
                         'max_optimistic_identity_gap_min': max(r['max_gap_min'] for r in identity),
                         'minimum_morning_target_residual_after_3_min_walk': round(min(residuals), 6),
                         'last_fs_return_min': round(max(t['departure_min'] + adjusted[t['loop']]['road_minutes'] for t in trips), 6),
                         **minimum_blocks(trips, adjusted, joins, recovery)})
    nominal = adjusted_loops(loops, 1.1, .5)
    streams, identity = event_diagnostics(trips, nominal)
    by_wing = {}
    for wing in ('west', 'east'):
        times = [t['departure_min'] for t in trips if t['loop'].startswith(wing)]
        original_times = [t['departure_min'] for t in ordered(source) if t['loop'].startswith(wing)]
        by_wing[wing] = {'departures_min': times, 'gaps': gaps(times),
                         'am_bank_unchanged': times[:5] == original_times[:5],
                         'pm_bank_unchanged': [t for t in times if 1000 <= t <= 1120] == PM}
    def delta_rows(counter):
        return [{'loop': pattern, 'departure_min': minute, 'count': n}
                for (pattern, minute), n in sorted(counter.items())]
    return {'case_id': case_id, 'trips': trips, 'daily_trip_count': len(trips),
            'removed_dispatch_events': delta_rows(before - after),
            'added_dispatch_events': delta_rows(after - before),
            'pattern_counts': dict(sorted(Counter(t['loop'] for t in trips).items())),
            'annual_service_km': round(annual, 6), 'annual_service_km_delta': round(annual - original, 6),
            'excess_km_vs_111419_reference': round(annual - 111419, 6),
            'first_fs_departure_min': min(t['departure_min'] for t in trips),
            'last_fs_departure_min': max(t['departure_min'] for t in trips),
            'by_wing': by_wing, 'conditional_scenarios': rows,
            'nominal_occurrence_streams': streams, 'nominal_optimistic_identity_gaps': identity,
            'last_nonhub_event_departure_min_nominal': max(max(s['departures_at_occurrence_min']) for s in streams),
            'all_scenarios_optimistic_h60': all(r['max_optimistic_identity_gap_min'] <= 60.000001 for r in rows),
            'all_scenarios_morning_targets_retained': all(r['minimum_morning_target_residual_after_3_min_walk'] >= 0 for r in rows),
            'common_clock_two_hour_h30_certified': False,
            'geographic_sites_and_ordered_road_patterns_unchanged': True,
            'changed_road_paths': [], 'policy_adopted': False}


def build(wings, timetable, counterflow, rail, rail_contract):
    for item, contract in ((wings, 'RT031_LINE8_INDEPENDENT_WINGS_DIAGNOSTIC_V3'),
                           (timetable, 'RT031_LINE8_SAME_KM_CONDITIONAL_RETIMING_V3'),
                           (counterflow, 'RT031_LINE8_LOCAL_COUNTERFLOW_ROAD_COMPARISON_V3')):
        if item['contract'] != contract or any(item[k] is not False for k in FLAGS):
            raise ValueError('unsupported or decisional evidence')
    if any(item['annual_service_days_assumption'] != 260 or item['reference_cap_unchanged'] != 111419
           for item in (timetable, counterflow)):
        raise ValueError('calendar or reference drift')
    if (rail_contract['service_date'] != '2026-09-03' or rail_contract['station']['stop_id'] != 'S01514'
            or {r['service_date'] for r in rail} != {'2026-09-03'} or len(rail) != rail_contract['active_s8_events']):
        raise ValueError('rail evidence drift')
    targets = timetable['new_morning_train_targets_min']
    if targets != [446, 476, 506, 536, 566] or not set(targets) <= {float(r['departure_min']) for r in rail if r['direction'] == 'MILANO'}:
        raise ValueError('morning targets drift')
    corrected = counterflow['full_correction_one_minute_retiming']
    both = next(c for c in counterflow['cases'] if c['case_id'] == 'both')
    families = []
    for name, loops, trips, joins, km in (
            ('original_priority_direction', wings['loops'], timetable['trips'], wings['represented_via_node_joins'], timetable['annual_service_km']),
            ('fast_local_both_directions', counterflow['candidate_loops'], corrected['trips'], both['represented_via_node_joins'], corrected['annual_service_km'])):
        original_sites = {e['stop_place_id'] for loop in wings['loops'].values() for e in loop['events']}
        sites = {e['stop_place_id'] for loop in loops.values() for e in loop['events']}
        if sites != original_sites or len(sites) != 27:
            raise ValueError('site identity drift')
        cases = [evaluate(loops, joins, trips, case_id, targets) for case_id in CASES]
        if abs(cases[0]['annual_service_km'] - km) > .00001 or inventory(cases[0]['trips']) != inventory(trips):
            raise ValueError('baseline reproduction failure')
        families.append({'family_id': name, 'site_count_including_fs': len(sites) + 1,
                         'nonhub_site_ids': sorted(sites),
                         'local_counterflow_short_rides': name == 'fast_local_both_directions',
                         'cases': cases})
    evening = []
    for bus in (1180, 1240):
        eligible = [r for r in rail if r['direction'] == 'LECCO' and float(r['arrival_min']) + 3 <= bus]
        train = max(eligible, key=lambda r: float(r['arrival_min']))
        evening.append({'bus_departure_min': bus, 'train_trip_id': train['trip_id'],
                        'train_arrival_min': float(train['arrival_min']),
                        'residual_after_three_min_walk': bus - float(train['arrival_min']) - 3})
    return {'contract': 'RT031_LINE8_EVENING_REALLOCATION_COMPARISON_V3',
            'status': 'BOUNDED_COMPARISON_NOT_ADOPTED', 'families': families,
            'annual_service_days_assumption': 260, 'reference_cap_unchanged': 111419,
            'morning_train_targets_min': targets, 'frozen_rail_service_date': '2026-09-03',
            'evening_rail_comparisons': evening,
            'semantics': {
                'frequency': 'Original five-trip AM and PM H30 banks unchanged. Same-km evening extension explicitly trades H60 midday for gaps of 90 or 120 minutes. No common-clock two-hour H30 certification.',
                'coverage': 'Same 28 site identities including FS and same ordered road/event witnesses within each family. Spatial footprint unchanged, NOT unchanged temporal accessibility or ridership.',
                'events': 'Nominal streams preserve each pattern and occurrence separately. Identity-union gaps are optimistic, not authorised boarding or passenger-service continuity guarantees.',
                'fleet': 'Minimum path cover on represented via-node joins and uniform deterministic running/dwell/recovery cases. Not full-history legality, vehicle/driver duties, depot feasibility or empirical reliability.',
                'rail': 'Frozen 2026-09-03 evidence, NOT the current timetable. Three-minute transfer walk assumed, no empirical missed-connection probability.',
                'cost': 'Same pattern multiplicities imply same service km, NOT same operating cost. Longer duty span, depot and positioning are unpriced.',
                'choice': 'Six constructed dispatch comparisons per frozen road family. No optimisation or weighted winner. H90/H120 not adopted; no assertion midday demand is low.'},
            'actual_timetable_certified': False, **{key: False for key in FLAGS},
            'decision_budget_km': None, 'uncertainty_band_min': None,
            'approved_uplift_percent': None, 'total_operating_km': None,
            'depot_and_positioning_km': None}


def reproduce(paths=None):
    result = build(**load_sources(paths))
    result['source_sha256_normalized_newlines'] = EXPECTED.copy()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=BASE / 'evening_reallocation.json')
    args = parser.parse_args()
    result = reproduce()
    args.output.write_text(json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    for family in result['families']:
        print(family['family_id'])
        for case in family['cases']:
            print(case['case_id'], case['daily_trip_count'], case['annual_service_km'],
                  case['last_fs_departure_min'], case['all_scenarios_optimistic_h60'],
                  case['all_scenarios_morning_targets_retained'])
