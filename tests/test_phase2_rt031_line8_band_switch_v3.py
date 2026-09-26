import json
from pathlib import Path
import unittest
from scripts.phase2_audit_rt031_line8_band_switch_v3 import dispatches, largest_gap, fleet_lower_bound


class BandSwitchTests(unittest.TestCase):
    def test_dispatch_counts_and_peak_boundary(self):
        self.assertEqual(len(dispatches(420,1200)),17)
        self.assertEqual(len(dispatches(360,1200)),18)
        self.assertEqual(len(dispatches(360,1320)),20)
        self.assertIn(510,dispatches(420,1200))
        self.assertNotIn(570,dispatches(420,1200))

    def test_offsets_can_create_gap_despite_hourly_dispatch(self):
        gap = largest_gap([{'minute':60,'event_id':'a'},{'minute':140,'event_id':'b'}])
        self.assertEqual(gap['minutes'],80)
        self.assertEqual(gap['before']['event_id'],'a')

    def test_vehicle_release_before_simultaneous_departure(self):
        self.assertEqual(fleet_lower_bound([(0,'a'),(60,'a')], {'a':{'running_minutes_excluding_dwell':55}},5),1)
        self.assertEqual(fleet_lower_bound([(0,'a'),(60,'a')], {'a':{'running_minutes_excluding_dwell':55}},10),2)

    def test_committed_domain_and_conditional_case(self):
        path = Path(__file__).resolve().parents[1]/'outputs/phase2/rt031_line8_local_shortcuts_v3/band_switch.json'
        a = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(len(a['scenarios']),384)
        self.assertFalse(a['actual_timetable_certified'])
        self.assertFalse(a['network_selected'])
        self.assertFalse(a['primary_selection_authorised'])
        self.assertFalse(a['runner_up_selection_authorised'])
        self.assertIsNone(a['decision_budget_km'])
        self.assertIsNone(a['uncertainty_band_min'])
        assignment = {'am':'west_forward_east_reverse','off':'west_reverse_east_forward','pm':'west_reverse_east_forward'}
        r = next(s for s in a['scenarios'] if s['start_min']==420 and s['end_min']==1200 and s['assignment']==assignment)
        self.assertEqual(r['annual_km_before_extras'],109285.99)
        self.assertAlmostEqual(r['maximum_optimistic_identity_gap_min'],60,places=5)
        early = next(s for s in a['scenarios'] if s['start_min']==360 and s['end_min']==1140 and s['assignment']==assignment)
        self.assertGreater(early['maximum_optimistic_identity_gap_min'],81)


if __name__ == '__main__':
    unittest.main()
