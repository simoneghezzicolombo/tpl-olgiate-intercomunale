"""Separate timetable robustness assumptions from geography and annual accounting.

Diagnostic subsets are NOT permission to reduce service reliability. Full-grid
rechecks explicitly expose violations; none is an empirical miss probability.
"""
import hashlib
import json
import math
from collections import Counter

from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import BASE, EXPECTED, FLAGS, load_sources
from scripts.phase2_compare_rt031_line8_shorter_span_v3 import SPANS, validate_rail
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import (
    GRID, family_inputs, prepare, solve, verify, events_by_site,
)
from scripts.phase2_audit_rt031_line8_passenger_peaks_v3 import uncovered_intervals

PROFILES = {
    'nominal_only': ((1.1, .5),),
    'moving_range_fixed_dwell': ((.9, .5), (1., .5), (1.1, .5)),
    'full_grid': GRID,
}
SPAN_IDS = ('last_fs_1940', 'last_fs_2040_reference')


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def accounting(daily_km, reference=111419):
    if not math.isfinite(daily_km) or daily_km <= 0:
        raise ValueError('positive finite daily service km required')
    maximum_days = math.floor(reference / daily_km)
    return {'daily_service_km': daily_km, 'annual_service_days_assumption': 260,
            'annual_service_km': daily_km * 260,
            'maximum_whole_identical_service_days_within_reference': maximum_days,
            'days_removed_from_260_to_fit_reference': max(0, 260 - maximum_days),
            'calendar_adopted': False, 'depot_and_repositioning_included': False,
            'actual_weekend_days_in_calendar': None}


def stress_audit(problem, case):
    """Check every declared site/direction continuously in each frozen scenario."""
    rows = []
    trips = case['trips']
    selected = {(t['loop'], t['departure_min']) for t in trips}
    for (moving, dwell), loops in problem['adjusted'].items():
        opportunities = events_by_site(trips, loops)
        expected_sites = {e['stop_place_id'] for loop in loops.values() for e in loop['events']}
        if {sid for sid, direction in opportunities} != expected_sites:
            raise ValueError('missing site in diagnostic witness')
        failures = []
        for (sid, direction), events in sorted(opportunities.items()):
            for label, start, end, headway in [
                ('offpeak_envelope', *problem['ready_span'], 60),
                *((p['peak'], p['start_min'], p['end_min'], 30) for p in case['comparison_peak_windows'])
            ]:
                gaps = uncovered_intervals([t for _, t in events], start, end, headway)
                if gaps:
                    failures.append({'site_id': sid, 'direction': direction, 'window': label,
                                     'uncovered_ready_intervals_min': gaps})
        # Unlike the joint eligibility list, this checks an individual scenario.
        anchors_failed = []
        for anchor in problem['anchors']:
            eligible = []
            for pattern, departure in selected:
                if not pattern.startswith(anchor['wing']):
                    continue
                if anchor['kind'] == 'bus_to_rail':
                    residual = anchor['rail_min'] - departure - loops[pattern]['road_minutes'] - 3
                    ok = -1e-8 <= residual <= problem['wait_ceiling'] + 1e-8
                else:
                    ok = 3 <= departure - anchor['rail_min'] <= 8
                if ok:
                    eligible.append((pattern, departure))
            if not eligible:
                anchors_failed.append({k: anchor[k] for k in ('wing', 'kind', 'rail_min')})
        rows.append({'moving_multiplier': moving, 'dwell_min': dwell,
                     'frequency_failures': failures, 'rail_anchor_failures': anchors_failed,
                     'frequency_and_rail_pass': not failures and not anchors_failed})
    return rows


def run(time_limit=60):
    sources = load_sources()
    validate_rail(sources)
    family = next(f for f in family_inputs(sources) if f['name'] == 'fast_local_both_directions')
    reference_path = BASE / 'shorter_span_comparison.json'
    reference = json.loads(reference_path.read_text(encoding='utf-8'))
    if any(reference[k] for k in FLAGS) or any(reference['source_sha256_normalized_newlines'][k] != v for k, v in EXPECTED.items()):
        raise ValueError('reference flags or source drift')
    cases = []
    for span_id in SPAN_IDS:
        spec = SPANS[span_id]
        full = prepare(family, 60, False, ready_span=(390, spec['end_min']), pm_arrivals=spec['pm_arrivals'])
        for profile_id, grid in PROFILES.items():
            if profile_id == 'full_grid':
                case = dict(next(c for c in reference['cases'] if c['span_comparison_id'] == span_id
                                 and c['offpeak_wait_comparison_min'] == 60))
                verify(full, case['trips'], case['comparison_peak_windows'], 4)
                case['reused_verified_full_grid_reference'] = True
            else:
                problem = prepare(family, 60, ready_span=(390, spec['end_min']),
                                  pm_arrivals=spec['pm_arrivals'], timing_grid=grid,
                                  am_wait_ceiling_comparison_min=full['wait_ceiling'])
                case = solve(problem, 4, time_limit)
            case.update(profile_id=profile_id, span_comparison_id=span_id,
                        timing_grid_comparison=[list(pair) for pair in grid])
            if case['witness_found']:
                daily = sum(family['loops'][t['loop']]['distance_m'] / 1000 for t in case['trips'])
                case['service_day_accounting'] = accounting(daily)
                case['patterns_used'] = dict(Counter(t['loop'] for t in case['trips']))
                case['full_grid_frequency_and_rail_audit'] = stress_audit(full, case)
                try:
                    verify(full, case['trips'], case['comparison_peak_windows'], 4)
                    case['passes_full_reference_contract'] = True
                except ValueError as exc:
                    case['passes_full_reference_contract'] = False
                    case['full_reference_rejection'] = str(exc)
            cases.append(case)
            print(json.dumps({k: case.get(k) for k in ('profile_id', 'span_comparison_id', 'solver_status',
                             'annual_service_km', 'annual_service_km_lower_bound_in_domain',
                             'passes_full_reference_contract', 'patterns_used')}), flush=True)
    return {'contract': 'RT031_LINE8_ROBUSTNESS_COST_DIAGNOSTIC_V3', 'cases': cases,
            'source_sha256_normalized_newlines': {**EXPECTED, 'shorter_span': digest(reference_path)},
            'all_comparisons_completed': len(cases) == len(PROFILES) * len(SPAN_IDS),
            'semantics': {
                'fixed': 'All 28 sites and four corrected full wing paths retained; H30 two common 120-minute peaks, H60 otherwise, 260 assumed days, four nominal vehicles, identical rail targets within each span and full-grid inherited AM wait ceiling.',
                'changed': 'Only timing scenarios required in optimisation. Nominal means moving x1.1 and 0.5 minute dwell, not observed mean. Phases and departures jointly optimised on the existing five-minute domain.',
                'stress': 'Reduced grids are diagnostic assumptions, NOT certified evidence or policy adoption. All resulting witnesses audited against original nine cases. Failures are deterministic counterexamples, not missed-connection probabilities.',
                'calendar': '260 is an assumed number of identical service days, not an actual dated calendar. No additional weekend reduction can be claimed from that number. Break-even days are arithmetic only; no days removed or calendar selected.',
                'limits': 'Service km only, not total operating cost; current rail schedule, field running times, platforms, vehicle suitability and full-history restrictions unverified. No guarantee of short rides at all other sites. No route or normative preferences selected.'},
            **{k: False for k in FLAGS}, 'actual_timetable_certified': False,
            'decision_budget_km': None, 'uncertainty_band_min': None,
            'approved_uplift_percent': None, 'total_operating_km': None}


def render_diagnostic(graph_dir):
    from scripts.phase2_render_rt031_line8_counterflow_v3 import render
    result = json.loads((BASE / 'robustness_cost_diagnostic.json').read_text(encoding='utf-8'))
    if any(result[k] for k in FLAGS) or any(
            set(c['patterns_used']) != {'west_B', 'east_A'} for c in result['cases'] if c['witness_found']):
        raise ValueError('map domain drift')
    render(graph_dir, BASE / 'robustness_cost_diagnostic.png', patterns=('west_B', 'east_A'),
           show_baseline=False,
           title='Stesso tracciato, tutti i 28 siti: H30 in punta / H60 nel resto\n'
                 'Confronto ipotesi di tempo e fascia serale — nessuna proposta selezionata')


if __name__ == '__main__':
    result = run()
    (BASE / 'robustness_cost_diagnostic.json').write_text(
        json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
