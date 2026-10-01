"""Explicit shorter-span comparisons, preserving fast local rides and peak quality."""
import argparse
import hashlib
import json
from pathlib import Path

from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import BASE, EXPECTED, FLAGS, load_sources
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import (
    DEFAULT_PM_ARRIVALS, family_inputs, prepare, solve, verify,
)

SPANS = {
    'last_fs_1940': {'end_min': 1180, 'pm_arrivals': DEFAULT_PM_ARRIVALS[:-1]},
    'last_fs_2010': {'end_min': 1210, 'pm_arrivals': (*DEFAULT_PM_ARRIVALS[:-1], 1202)},
    'last_fs_2040_reference': {'end_min': 1240, 'pm_arrivals': DEFAULT_PM_ARRIVALS},
}


def validate_rail(sources):
    rail = sources['rail']
    if sources['rail_contract']['service_date'] != '2026-09-03' or {r['service_date'] for r in rail} != {'2026-09-03'}:
        raise ValueError('frozen rail date drift')
    arrivals = {float(r['arrival_min']) for r in rail if r['direction'] == 'LECCO'}
    if not set().union(*(set(s['pm_arrivals']) for s in SPANS.values())) <= arrivals:
        raise ValueError('declared shortened-span train arrival absent from frozen rail')
    departures = {float(r['departure_min']) for r in rail if r['direction'] == 'MILANO'}
    if not {446, 476, 506, 536, 566} <= departures:
        raise ValueError('missing retained morning target')


def annotate(case, span_id):
    spec = SPANS[span_id]
    row = dict(case)
    row.update(span_comparison_id=span_id,
               ready_span_comparison_min=[390, spec['end_min']],
               declared_pm_rail_arrival_targets_min=list(spec['pm_arrivals']),
               reference_pm_targets_not_retained_min=sorted(set(DEFAULT_PM_ARRIVALS) - set(spec['pm_arrivals'])),
               replacement_pm_targets_min=sorted(set(spec['pm_arrivals']) - set(DEFAULT_PM_ARRIVALS)),
               last_fs_departure_limit_min=spec['end_min'],
               ready_span_length_min=spec['end_min'] - 390,
               h120_boundary_relaxation_only=case['offpeak_wait_comparison_min'] == 120,
               user_approval_recorded=False,
               morning_targets_unchanged=True, geography_unchanged=True,
               peak_duration_unchanged_min=120, annual_days_unchanged=260)
    if row['witness_found']:
        row['first_actual_fs_departure_min'] = min(t['departure_min'] for t in row['trips'])
        row['last_actual_fs_departure_min'] = max(t['departure_min'] for t in row['trips'])
    return row


def document(cases, reference_hash):
    keys = {(c['span_comparison_id'], c['offpeak_wait_comparison_min']) for c in cases}
    expected = {(name, h) for name in SPANS for h in (60, 90, 120)}
    return {'contract': 'RT031_LINE8_SHORTER_SPAN_JOINT_COMPARISON_V3',
            'status': 'EXPLICIT_SPAN_AND_RAIL_TRADEOFFS_NOT_ADOPTED',
            'all_comparisons_completed': len(cases) == len(expected) and keys == expected,
            'cases': cases, 'source_sha256_normalized_newlines': {**EXPECTED, 'joint_reference': reference_hash},
            'reference_cap_unchanged': 111419, 'annual_service_days_assumption': 260,
            'semantics': {
                'scope': 'Fast-local corrected road family only: all 28 site identities retained, last local to-FS occurrence enforced, first local from-FS alighting. Same original five AM train targets and two common 120-minute peak windows across nine timing scenarios. Four nominal vehicles as comparison; worst grid fleet separately reported.',
                'span': 'Ready-time start stays 06:30. End comparisons 19:40 / 20:10 / 20:40 are 13h10 / 13h40 / 14h10, not necessarily each site first-to-last boarding span. First actual dispatch and last return are different quantities. No morning target removed silently.',
                'rail': '19:40 loses reference 20:32 train arrival. 20:10 replaces it with the frozen 20:02 arrival. Other six PM targets and five AM targets retained. All dates frozen 2026-09-03, not current railway approval; 3-8 minute rail-to-bus window unchanged.',
                'objective': 'Joint finite five-minute-grid search, minimum service km conditional on each span and H60/H90/H120 comparison; no weighted winner. A shortened span does not automatically save a trip. Solver timeout is not infeasibility. Any fixed peak alignment is labelled; equality to a previously proven unrestricted-phase lower bound certifies that it retains that broader-domain optimum.',
                'h120_boundary': 'H120 added solely as an explicit off-peak boundary relaxation, not adopted, not equivalent to H60/H90, and not asserted to be acceptable or low-demand. Peak duration/quality, geography and the declared rail anchors remain unchanged within each span.',
                'policy': 'Comparison authorised by earlier user request for 13-14 hour alternatives, not adoption of a shorter span or H90. 111419 reference, decision budget, uncertainty band and calendar unchanged.',
                'cost': 'Service km for 260 assumed days only, excluding depot/repositioning, drivers and reserve fleet. No assertion of real operating cost or empirical reliability.'},
            **{key: False for key in FLAGS}, 'actual_timetable_certified': False,
            'decision_budget_km': None, 'uncertainty_band_min': None,
            'approved_uplift_percent': None, 'total_operating_km': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--time_limit', type=float, default=45)
    parser.add_argument('--output', type=Path, default=BASE / 'shorter_span_comparison.json')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--align_h120_1940', action='store_true')
    args = parser.parse_args()
    sources = load_sources()
    validate_rail(sources)
    reference_path = BASE / 'joint_evening_timetable.json'
    reference_hash = hashlib.sha256(reference_path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    reference = json.loads(reference_path.read_text(encoding='utf-8'))
    if reference['source_sha256_normalized_newlines'] != EXPECTED or any(reference[k] for k in FLAGS):
        raise ValueError('reference source drift or selection')
    family = next(f for f in family_inputs(sources) if f['name'] == 'fast_local_both_directions')
    cases = []
    unrestricted_h120_bound = None
    if args.resume:
        previous = json.loads(args.output.read_text(encoding='utf-8'))
        if previous['source_sha256_normalized_newlines'] != {**EXPECTED, 'joint_reference': reference_hash}:
            raise ValueError('resume evidence drift')
        for case in previous['cases']:
            if args.align_h120_1940 and (case['span_comparison_id'], case['offpeak_wait_comparison_min']) == ('last_fs_1940', 120):
                unrestricted_h120_bound = case.get('unrestricted_phase_lower_bound_km', case.get('annual_service_km_lower_bound_in_domain'))
                continue
            spec = SPANS[case['span_comparison_id']]
            problem = prepare(family, case['offpeak_wait_comparison_min'], False,
                              ready_span=(390, spec['end_min']), pm_arrivals=spec['pm_arrivals'])
            if case['witness_found']:
                verify(problem, case['trips'], case['comparison_peak_windows'], 4)
            cases.append(annotate(case, case['span_comparison_id']))
    for headway in (90, 60):
        if any(c['span_comparison_id'] == 'last_fs_2040_reference' and c['offpeak_wait_comparison_min'] == headway for c in cases):
            continue
        case = next(c for c in reference['cases'] if c['family_id'] == family['name']
                    and c['offpeak_wait_comparison_min'] == headway and c['nominal_fleet_bound_comparison'] == 4)
        verify(prepare(family, headway, False), case['trips'], case['comparison_peak_windows'], 4)
        cases.append(annotate(case, 'last_fs_2040_reference'))
    for span_id in SPANS:
        spec = SPANS[span_id]
        for headway in (90, 60, 120):
            if any(c['span_comparison_id'] == span_id and c['offpeak_wait_comparison_min'] == headway for c in cases):
                continue
            problem = prepare(family, headway, ready_span=(390, spec['end_min']), pm_arrivals=spec['pm_arrivals'])
            fixed_peaks = None
            if args.align_h120_1940 and (span_id, headway) == ('last_fs_1940', 120):
                h90 = next(c for c in cases if c['span_comparison_id'] == span_id and c['offpeak_wait_comparison_min'] == 90)
                fixed_peaks = {p['peak']: p['start_min'] for p in h90['comparison_peak_windows']}
            case = annotate(solve(problem, 4, args.time_limit, fixed_peak_starts=fixed_peaks), span_id)
            if fixed_peaks is not None:
                case['unrestricted_phase_lower_bound_km'] = unrestricted_h120_bound
                case['also_optimal_in_unrestricted_phase_domain'] = bool(case['witness_found'] and unrestricted_h120_bound is not None
                    and abs(case['annual_service_km'] - unrestricted_h120_bound) < 1e-4)
            if case['witness_found']:
                nominal = problem['adjusted'][1.1, .5]
                case['last_fs_return_nominal_min'] = max(t['departure_min'] + nominal[t['loop']]['road_minutes'] for t in case['trips'])
            cases.append(case)
            args.output.write_text(json.dumps(document(cases, reference_hash), sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
            print(json.dumps({k: case.get(k) for k in ('span_comparison_id', 'offpeak_wait_comparison_min', 'solver_status', 'witness_found', 'daily_trip_count', 'annual_service_km', 'annual_service_km_lower_bound_in_domain', 'worst_grid_vehicle_count_conditional')}), flush=True)
