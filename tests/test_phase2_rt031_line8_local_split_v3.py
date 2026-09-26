import json
from pathlib import Path
import unittest

from scripts.phase2_probe_rt031_line8_local_split_v3 import single_trip_pairs, evaluate

BASE=Path(__file__).resolve().parents[1]/'outputs/phase2/rt031_line8_local_shortcuts_v3'


class LocalSplitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((BASE/'local_split.json').read_text(encoding='utf-8'))
        cls.wings=json.loads((BASE/'independent_wings.json').read_text(encoding='utf-8'))
        cls.source=json.loads((BASE/'peak_direction_retimed.json').read_text(encoding='utf-8'))

    def test_extra_local_services_not_free(self):
        a=self.data
        self.assertEqual(len(a['cases']),9)
        for c in a['cases']:
            self.assertEqual(c['trip_count'],72 if c['case_id']=='separate_local_services' else 54)
            expected=sum(a['loops'][t['loop']]['distance_m'] for t in c['trips'])/1000*260
            self.assertEqual(c['annual_service_km'],expected)
            self.assertGreater(expected,130000)
            self.assertEqual(c['lost_original_site_ids'],[])
            self.assertEqual(len(c['scenarios']),27)
            for phase,patterns in c['patterns_by_phase'].items():
                for p in patterns:
                    times=sorted(t['departure_min'] for t in c['trips'] if t['loop']==p and t['service_bank']==phase)
                    bank=times if phase=='AM' else times[-5:]
                    self.assertEqual(len(bank),5)
                    self.assertTrue(all(y-x==30 for x,y in zip(bank,bank[1:])))

    def test_transfers_not_erased_by_shared_vehicle_or_route_name(self):
        loops={'outer':{'events':[{'stop_place_id':'a','path_node_index':1}]},
               'local':{'events':[{'stop_place_id':'b','path_node_index':1}]}}
        self.assertNotIn(('a','b'),single_trip_pairs(loops,['outer','local']))
        self.assertNotIn(('b','a'),single_trip_pairs(loops,['outer','local']))
        for c in self.data['cases']:
            self.assertTrue(any(r['lost_hypothetical_single_trip_pairs'] for r in c['lost_direct_pair_diagnostics']))

    def test_replay_and_conditional_authority(self):
        a=self.data
        for c in a['cases']:
            replay=evaluate(a['loops'],c['trips'],a['represented_via_node_joins'],self.wings['loops'],
                            self.source,c['patterns_by_phase'],a['reference_cap_unchanged'])
            for k,v in replay.items():
                self.assertEqual(c[k],v)
            for row in c['scenarios']:
                indices=[i for block in row['trip_index_blocks'] for i in block]
                self.assertEqual(sorted(indices),list(range(c['trip_count'])))
                for block in row['trip_index_blocks']:
                    for i,j in zip(block,block[1:]):
                        self.assertTrue(a['represented_via_node_joins'][c['trips'][i]['loop']+'>'+c['trips'][j]['loop']])
        for k in ('network_selected','primary_selection_authorised','runner_up_selection_authorised','full_history_legality_certified'):
            self.assertFalse(a[k])
        for k in ('decision_budget_km','uncertainty_band_min','total_operating_km','approved_uplift_percent'):
            self.assertIsNone(a[k])


if __name__=='__main__':
    unittest.main()
