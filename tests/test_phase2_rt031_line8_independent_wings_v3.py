import json
from pathlib import Path
import unittest
from scripts.phase2_audit_rt031_line8_independent_wings_v3 import minimum_blocks


class IndependentWingsTest(unittest.TestCase):
    def test_matching_respects_turn_and_time(self):
        trips=[{'departure_min':0,'loop':'a'},{'departure_min':30,'loop':'a'}]
        loops={'a':{'road_minutes':26}}
        self.assertEqual(minimum_blocks(trips,loops,{'a>a':True},0)['minimum_vehicle_count_conditional'],1)
        self.assertEqual(minimum_blocks(trips,loops,{'a>a':True},5)['minimum_vehicle_count_conditional'],2)
        self.assertEqual(minimum_blocks(trips,loops,{'a>a':False},0)['minimum_vehicle_count_conditional'],2)

    def test_committed_blocks_are_complete_and_replayable(self):
        a=json.loads((Path(__file__).resolve().parents[1]/'outputs/phase2/rt031_line8_local_shortcuts_v3/independent_wings.json').read_text(encoding='utf-8'))
        self.assertEqual(len(a['cases']),9)
        self.assertFalse(a['network_selected'])
        self.assertFalse(a['primary_selection_authorised'])
        self.assertFalse(a['runner_up_selection_authorised'])
        self.assertIsNone(a['decision_budget_km'])
        self.assertIsNone(a['uncertainty_band_min'])
        for c in a['cases']:
            for b in c['blocks']:
                flat=[i for block in b['trip_index_blocks'] for i in block]
                self.assertEqual(sorted(flat),list(range(len(c['trips']))))
                for block in b['trip_index_blocks']:
                    for i,j in zip(block,block[1:]):
                        x,y=c['trips'][i],c['trips'][j]
                        self.assertTrue(a['represented_via_node_joins'][x['loop']+'>'+y['loop']])
                        self.assertLessEqual(x['departure_min']+a['loops'][x['loop']]['road_minutes']+b['allowance_per_wing_trip_min'],y['departure_min']+1e-9)
        base=next(c for c in a['cases'] if c['calendar_case']=='synchronised_07' and c['east_shift_min']==0)
        self.assertEqual(base['annual_km_before_extras'],109285.99)


if __name__=='__main__':
    unittest.main()
