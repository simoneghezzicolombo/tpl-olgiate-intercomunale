from fractions import Fraction
import json
from pathlib import Path
import unittest

from scripts.phase2_probe_rt031_line8_retention_tradeoffs_v3 import removal_domain, VIRTUAL, NORTH, FS

BASE=Path(__file__).resolve().parents[1]/'outputs/phase2/rt031_line8_local_shortcuts_v3'


class RetentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a=json.loads((BASE/'retention_tradeoffs.json').read_text(encoding='utf-8'))

    def test_domain_does_not_treat_local_anchors_as_expendable(self):
        loop={'events':[{'stop_place_id':s,'path_node_index':i} for i,s in enumerate((VIRTUAL,'a','b','a',NORTH,'c'))]}
        self.assertEqual(removal_domain(loop),[(),('a',),('b',),('c',),('a','b'),('b','c')])
        self.assertEqual(len(self.a['variants']['west']),28)
        self.assertEqual(len(self.a['variants']['east']),22)
        self.assertEqual(len(self.a['cases']),616)
        for values in self.a['variants'].values():
            for v in values:
                self.assertLessEqual(len(v['omitted_required_ids']),2)
                self.assertFalse(set(v['omitted_required_ids']) & {FS,VIRTUAL,NORTH})

    def test_exact_coverage_baseline_and_deltas(self):
        a=self.a
        baseline=a['baseline_potential_access_fraction']
        for c in a['cases']:
            for municipality in baseline:
                for threshold in ('5','8','10'):
                    fraction=Fraction(c['potential_access_fraction'][municipality][threshold])
                    self.assertGreaterEqual(fraction,0); self.assertLessEqual(fraction,1)
                    expected=100*float(fraction-Fraction(baseline[municipality][threshold]))
                    self.assertEqual(expected,c['potential_access_change_pp'][municipality][threshold])
            self.assertEqual(c['retained_site_count'],28-len(c['lost_original_site_ids']))
            self.assertEqual(c['served_site_count'],c['retained_site_count']+len(c['gained_inventory_site_ids']))

    def test_budget_accounting_uses_all_36_trips(self):
        a=self.a
        lookup={v['variant_id']:v for values in a['variants'].values() for v in values}
        self.assertEqual(len(a['trips']),36)
        for c in a['cases']:
            w,e=c['case_id'].split('+'); loops={**lookup[w]['loops'],**lookup[e]['loops']}
            expected=sum(loops[t['loop']]['distance_m'] for t in a['trips'])/1000*260
            self.assertAlmostEqual(expected,c['annual_service_km'],places=7)
        minimum=min(a['cases'],key=lambda c:(c['annual_service_km'],c['case_id']))
        self.assertEqual(a['minimum_distance_case_id'],minimum['case_id'])
        self.assertAlmostEqual(minimum['annual_service_km'],111905.8472366,places=5)
        self.assertEqual(a['reference_cap_case_count'],0)
        # A four-site cut is not automatically a small territorial loss.
        self.assertGreater(-minimum['potential_access_change_pp']['97010']['10'],10)

    def test_operational_checks_and_authority_are_separate(self):
        a=self.a
        checked={c['case_id'] for c in a['conditional_operating_checks']}
        self.assertTrue({c['case_id'] for c in a['cases'] if c['annual_service_km']<=a['reference_cap_unchanged']}<=checked)
        self.assertIn(a['minimum_distance_case_id'],checked)
        for c in a['conditional_operating_checks']:
            self.assertEqual(len(c['scenarios']),27)
            for s in c['scenarios']:
                self.assertEqual(sorted(i for b in s['trip_index_blocks'] for i in b),list(range(36)))
        for flag in ('network_selected','primary_selection_authorised','runner_up_selection_authorised','full_history_legality_certified'):
            self.assertFalse(a[flag])
        for key in ('decision_budget_km','uncertainty_band_min','approved_uplift_percent','total_operating_km'):
            self.assertIsNone(a[key])


if __name__=='__main__':
    unittest.main()
