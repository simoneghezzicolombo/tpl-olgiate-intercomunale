"""H90/H120 only in explicit midday comparison windows; rail and peaks retained."""
import copy
import json
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import (
    BASE, FLAGS, family_inputs, load_sources, prepare, solve, verify)
from scripts.phase2_compare_rt031_line8_shorter_span_v3 import SPANS
from scripts.phase2_probe_rt031_line8_stop_relocation_v3 import digest

OUTPUT = BASE/'deep_offpeak_comparison.json'
WINDOWS = {'11_15': (660, 900), '10_16': (600, 960)}


def build_problem(midday_window=None, wait=60):
    family = copy.deepcopy(family_inputs(load_sources())[1])
    family['rail_anchor_scope'] = 'each_declared_site'
    kwargs = dict(ready_span=(390,1180), pm_arrivals=SPANS['last_fs_1940']['pm_arrivals'])
    ceiling = prepare(family,60,False,**kwargs)['wait_ceiling']
    windows = None if midday_window is None else [(390,midday_window[0],60),(*midday_window,wait),(midday_window[1],1180,60)]
    return prepare(family,60,True,**kwargs,am_wait_ceiling_comparison_min=ceiling,offpeak_windows=windows)


if __name__=='__main__':
    result={'contract':'RT031_LINE8_DEEP_OFFPEAK_WINDOW_COMPARISON_V3', 'cases':[],
            'source_sha256_normalized_newlines':{k:digest(BASE/v,True) for k,v in {'wings':'independent_wings.json','counterflow':'local_counterflow.json','rail_comparison':'shorter_span_comparison.json'}.items()},
            'user_authorisation':'Railway connections remain a requirement. H90/H120 acceptable in the deepest off-peak, not a blanket replacement of H60 outside peaks. Exact windows are illustrative, not adopted.',
            'semantics':'Four unchanged full corrected wing paths, all 28 sites, same 297 per-site frozen railway targets and nine timing scenarios, four nominal vehicles, 260 assumed days, passenger-ready span 06:30-19:40. All 49 AM/PM peak phases allowed; H30 overrides the piecewise off-peak policy. Waiting is checked for passenger-ready instants, including each window boundary, not merely at departure times. No demand or Google-popularity threshold used to certify quiet hours. Not the larger partial-service search domain, a selected public timetable or current railway certification.',
            'window_selection_authorised':False,'actual_timetable_certified':False,
            'decision_budget_km':None,'uncertainty_band_min':None,'total_operating_km':None,
            **{k:False for k in FLAGS}}
    for label,window,wait in [('h60_reference',None,60)]+[(f'{name}_h{h}',w,h) for name,w in WINDOWS.items() for h in (90,120)]:
        p=build_problem(window,wait)
        answer=solve(p,4,45)
        answer.update(case_id=label,midday_window_comparison_min=window,midday_wait_comparison_min=wait,
                      per_site_rail_anchor_count=len(p['anchors']))
        result['cases'].append(answer)
        result['all_five_cases_checked']=len(result['cases'])==5
        OUTPUT.write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
        print(json.dumps({k:answer.get(k) for k in ('case_id','annual_service_km','daily_trip_count','witness_found','optimality_proven_in_this_domain')}),flush=True)
