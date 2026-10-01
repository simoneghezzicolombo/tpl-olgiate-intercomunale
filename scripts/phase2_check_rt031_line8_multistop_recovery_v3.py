"""Rebuild timetable after adding stops; never reuse pre-addition annual km."""
import json
from scripts.phase2_probe_rt031_line8_multistop_recovery_v3 import OUTPUT as SOURCE
from scripts.phase2_probe_rt031_line8_stop_relocation_v3 import digest
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import BASE, FLAGS, family_inputs, load_sources, prepare, solve
from scripts.phase2_compare_rt031_line8_shorter_span_v3 import SPANS
from scripts.phase2_check_rt031_line8_relocation_timetable_v3 import PEAKS

OUTPUT = BASE / 'multistop_recovery_timetable.json'


def build_problem(source):
    if source['contract'] != 'RT031_LINE8_MULTISTOP_RECOVERY_V3' or any(source[k] for k in FLAGS):
        raise ValueError('unsupported or decisional spatial input')
    reference = family_inputs(load_sources())[1]
    loops = source['loops']
    for p, l in loops.items():
        original = reference['loops'][p]
        if (l['edge_ids'][0], l['edge_ids'][-1]) != (original['edge_ids'][0], original['edge_ids'][-1]):
            raise ValueError('FS joins cannot be inherited')
    for wing in ('west', 'east'):
        if {e['stop_place_id'] for e in loops[wing+'_A']['events']} != {e['stop_place_id'] for e in loops[wing+'_B']['events']}:
            raise ValueError('directional site domains differ')
    family = {**reference, 'name': 'multiple_stops_on_shortest_previous_geometry', 'loops': loops,
              'rail_anchor_scope': 'each_declared_site',
              'comparison_nonhub_site_ids': sorted({e['stop_place_id'] for l in loops.values() for e in l['events']})}
    kwargs = dict(ready_span=(390,1180), pm_arrivals=SPANS['last_fs_1940']['pm_arrivals'])
    ceiling = prepare(reference,60,False,**kwargs)['wait_ceiling']
    return prepare(family,60,True,**kwargs,am_wait_ceiling_comparison_min=ceiling)


if __name__ == '__main__':
    source = json.loads(SOURCE.read_text(encoding='utf-8'))
    problem = build_problem(source)
    answer = solve(problem,4,60,fixed_peak_starts=PEAKS)
    result = {'contract':'RT031_LINE8_MULTISTOP_RECOVERY_TIMETABLE_V3', 'case':answer,
              'source_sha256_normalized_newlines':digest(SOURCE,True),
              'per_site_rail_anchor_count':len(problem['anchors']),
              'site_count_including_fs':len(problem['family']['comparison_nonhub_site_ids'])+1,
              'semantics':'Spatial cardinality witness only; not every equivalent stop placement. Every added node visit receives dwell before nine-case H30/H60, per-site frozen rail and fleet checks. Same fixed comparison peaks, 06:30-19:40 ready span, 260 days and four nominal vehicles as the previous short-geometry comparison. Current trains, authorised boarding, bus manoeuvres, full-history legality and actual demand remain uncertified. Coverage losses remain explicit in the source; no adoption or budget uplift.',
              'actual_timetable_certified':False, 'decision_budget_km':None, 'uncertainty_band_min':None,
              'total_operating_km':None, **{k:False for k in FLAGS}}
    OUTPUT.write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print(json.dumps({k:answer.get(k) for k in ('annual_service_km','witness_found','optimality_proven_in_this_domain','worst_grid_vehicle_count_conditional')}),flush=True)
