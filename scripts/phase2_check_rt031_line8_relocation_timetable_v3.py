"""Rebuild H30/H60 and H30/H90 for every zero-covered-unit-loss relocation."""
import copy
import hashlib
import json

from scripts.phase2_probe_rt031_line8_stop_relocation_v3 import OUTPUT as SCREEN, RETENTION, BASE
from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import load_sources, FLAGS
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import family_inputs, prepare, solve
from scripts.phase2_compare_rt031_line8_shorter_span_v3 import SPANS

OUTPUT = BASE / 'stop_relocation_timetable.json'
PEAKS = {'AM': 410, 'PM': 995}


def sha(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def materialize(reference, retention, case):
    variant = next(v for v in retention['variants'][case['wing']] if v['variant_id'] == case['variant_id'])
    loops = copy.deepcopy(reference['loops'])
    for pattern, raw in variant['loops'].items():
        if (raw['edge_ids'][0], raw['edge_ids'][-1]) != (loops[pattern]['edge_ids'][0], loops[pattern]['edge_ids'][-1]):
            raise ValueError('FS boundary changed: cannot inherit represented joins')
        loop = copy.deepcopy(raw)
        loop['events'] = sorted(loop['events'] + case['new_site_occurrences'][pattern],
                               key=lambda e: (e['path_node_index'], e['stop_place_id']))
        loops[pattern] = loop
    for wing in ('west', 'east'):
        if {e['stop_place_id'] for e in loops[wing + '_A']['events']} != {e['stop_place_id'] for e in loops[wing + '_B']['events']}:
            raise ValueError('directional site identity sets differ')
    return {**reference, 'name': 'relocation__' + case['case_id'], 'loops': loops}


if __name__ == '__main__':
    screen = json.loads(SCREEN.read_text(encoding='utf-8'))
    retention = json.loads(RETENTION.read_text(encoding='utf-8'))
    if screen['source_sha256_normalized_retention'] != sha(RETENTION) or any(screen[k] for k in FLAGS):
        raise ValueError('source drift or selected relocation')
    reference = next(f for f in family_inputs(load_sources()) if f['name'] == 'fast_local_both_directions')
    ceiling = prepare(reference, 60, False, ready_span=(390, 1180), pm_arrivals=SPANS['last_fs_1940']['pm_arrivals'])['wait_ceiling']
    diagnostic = [c for c in screen['cases'] if c['direction_pair_m_saved'] > 1e-6 and c['no_previously_covered_units_lost']]
    result = {'contract': 'RT031_LINE8_RELOCATION_CONDITIONAL_TIMETABLE_V3',
              'status': 'ALL_ZERO_COVERED_UNIT_LOSS_SAVING_CASES_CHECKED_NOT_SELECTED',
              'source_sha256_normalized_newlines': {'screen': sha(SCREEN), 'retention': sha(RETENTION)},
              'diagnostic_case_ids': [c['case_id'] for c in diagnostic],
              'frozen_reference_am_wait_ceiling_comparison_min': ceiling,
              'cases': [], 'reference_cap_unchanged': 111419,
              'semantics': 'All distance-saving cases with no previously covered population unit lost at any 5/8/10-minute threshold; not an adopted no-loss constraint for other investigations. Two headways compared, H60 requested and H90 not adopted. Same frozen AM wait ceiling, 19:40 span, rail targets, peak phases and four nominal vehicles. Real road paths unchanged by the new stop; conditional joins inherited only after exact FS boundary-edge check. No final budget, field approval, empirical probability or total operating cost.',
              **{k: False for k in FLAGS}, 'actual_timetable_certified': False,
              'decision_budget_km': None, 'uncertainty_band_min': None, 'total_operating_km': None}
    for case in diagnostic:
        family = materialize(reference, retention, case)
        for headway in (60, 90):
            problem = prepare(family, headway, ready_span=(390, 1180),
                              pm_arrivals=SPANS['last_fs_1940']['pm_arrivals'],
                              am_wait_ceiling_comparison_min=ceiling)
            answer = solve(problem, 4, 30, fixed_peak_starts=PEAKS)
            answer['relocation_case_id'] = case['case_id']
            result['cases'].append(answer)
            OUTPUT.write_text(json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
            print(json.dumps({k: answer.get(k) for k in ('relocation_case_id', 'offpeak_wait_comparison_min', 'annual_service_km', 'solver_status', 'worst_grid_vehicle_count_conditional')}), flush=True)
    result['all_diagnostic_cases_proven_optimal'] = len(result['cases']) == 2 * len(diagnostic) and all(c['optimality_proven_in_this_domain'] for c in result['cases'])
    OUTPUT.write_text(json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
