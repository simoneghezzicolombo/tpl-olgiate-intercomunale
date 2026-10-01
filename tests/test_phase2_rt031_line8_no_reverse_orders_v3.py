import gzip
import json
import unittest
from fractions import Fraction
from pathlib import Path

from scripts.phase2_probe_rt031_line8_no_reverse_all_orders_v3 import OUTPUT, NoReverseAdapter
from tests.test_phase2_rt031_line8_manoeuvre_cycles_v3 import Allowed, edge


class NoReverseOrderTests(unittest.TestCase):
    def test_terminal_seam_cannot_hide_reverse(self):
        adapter = NoReverseAdapter({'in':edge('a','b'),'out':edge('b','a')},Allowed())
        self.assertFalse(adapter.decision(('in',),'out')['allowed'])

    def test_distance_result_is_not_a_global_selection(self):
        result=json.loads(gzip.decompress(OUTPUT.read_bytes()))
        self.assertAlmostEqual(result['annual_service_km_16_trips_260_days'],121798.83256283011,places=5)
        self.assertFalse(result['candidate_domain_complete'])
        self.assertFalse(result['network_selected'])
        for row in result['local_fast_passages_nominal'].values():
            self.assertEqual(row['served_occurrence_count'],2)
            self.assertLess(row['inbound_min_nominal'],5)
        shortest=min(result['single_inventory_omission_comparisons_not_adopted'],key=lambda c:c['distance_m'])
        self.assertEqual(shortest['omitted_stop_identity'],'FROZEN::300873')
        self.assertAlmostEqual(shortest['annual_service_km_16_trips_260_days'],115130.63730799226,places=5)
        t=shortest['timetable_comparison_not_adopted']
        self.assertTrue(t['witness_found'])
        self.assertEqual(len(t['full_trips']),16)
        self.assertEqual(len(t['rail_assignments']),20)
        self.assertLess(t['maximum_intermediate_fs_onboard_wait_nominal_min'],17)
        self.assertFalse(shortest['stop_omission_adopted'])
        self.assertFalse(shortest['retained_journey_times_preserved'])
        self.assertGreater(max(v['to_fs_min'] for v in
            shortest['access_delta_min_vs_fixed_order_reference'].values()),19)
        fixed=result['hoe_omission_fixed_event_order_comparison_not_adopted']
        self.assertTrue(fixed['retained_journey_times_preserved'])
        self.assertAlmostEqual(fixed['annual_service_km_16_trips_260_days'],116411.94368431234,places=5)
        self.assertTrue(fixed['timetable_comparison_not_adopted']['witness_found'])
        self.assertEqual(len(fixed['timetable_comparison_not_adopted']['full_trips']),16)
        protected={'PROXY::RT031_ADDITIONAL::n:534398.29:5063851.64',
                   'PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE','RT031::P2V2S_0031_PROJECTED_ROAD_POINT'}
        self.assertTrue(all(c['omitted_stop_identity'] not in protected
                            for c in result['single_inventory_omission_comparisons_not_adopted']))

    def test_municipal_loss_is_not_hidden_in_total(self):
        path=OUTPUT.parent/'no_reverse_omission_walking.json'
        result=json.loads(path.read_text(encoding='utf-8'))
        c=next(c for c in result['cases'] if c['omitted_stop_identity']=='FROZEN::300873')
        self.assertEqual(len(result['municipality_names']),5)
        self.assertGreater(c['potential_walking_access_loss_percentage_points']['97074']['5'],8)
        self.assertLess(c['potential_walking_access_loss_percentage_points']['TOTAL']['5'],1)
        for code in result['municipality_names']:
            for limit in ('5','8','10'):
                a=Fraction(c['potential_walking_access_fraction'][code][limit])
                b=Fraction(result['all_29_comparison_sites_access_fraction'][code][limit])
                self.assertLessEqual(a,b)
                if code!='97074':
                    self.assertEqual(a,b)
        self.assertFalse(result['network_selected'])
        self.assertFalse(result['physical_walking_accessibility_certified'])
        fixed=result['hoe_fixed_event_order_comparison_not_adopted']
        self.assertEqual(fixed['potential_walking_access_fraction'],c['potential_walking_access_fraction'])
        self.assertTrue(fixed['retained_nominal_fs_journey_times_preserved'])


if __name__=='__main__':
    unittest.main()
