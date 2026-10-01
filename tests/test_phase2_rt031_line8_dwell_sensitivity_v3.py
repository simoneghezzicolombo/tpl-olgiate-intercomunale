import json
from pathlib import Path
import unittest
from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops


class DwellSensitivityTests(unittest.TestCase):
    def test_colocated_labels_do_not_double_dwell(self):
        loops={'a':{'road_minutes':10,'events':[{'path_node_index':2,'offset_from_wing_origin_min':3},
            {'path_node_index':2,'offset_from_wing_origin_min':3},{'path_node_index':4,'offset_from_wing_origin_min':7}]}}
        result=adjusted_loops(loops,1.1,.5)['a']
        self.assertAlmostEqual(result['road_minutes'],12)
        self.assertAlmostEqual(result['events'][0]['offset_from_wing_origin_min'],3.8)
        self.assertAlmostEqual(result['events'][2]['offset_from_wing_origin_min'],8.7)
        self.assertEqual(loops['a']['road_minutes'],10)

    def test_zero_dwell_promising_window_fails_half_minute_stress(self):
        a=json.loads((Path(__file__).resolve().parents[1]/'outputs/phase2/rt031_line8_local_shortcuts_v3/dwell_sensitivity.json').read_text(encoding='utf-8'))
        self.assertEqual(len(a['cases']),810)
        self.assertEqual(a['hypothetical_distinct_nonhub_road_node_occurrences_by_loop']['west_A'],15)
        passing={}
        for dwell in (0,.5,1):
            passing[dwell]=[r['morning_advance_min'] for r in a['cases'] if r['runtime_multiplier']==1
                and r['dwell_per_hypothetical_event_min']==dwell and r['recovery_per_wing_min']==5
                and r['first_fs_arrival_min']['west']+3<=446 and r['maximum_optimistic_identity_gap_min']<=60]
        self.assertEqual(passing[0],[3,4,5,6,7,8])
        self.assertEqual(passing[.5],[])
        self.assertEqual(passing[1],[])
        for key in ('observed_dwell_available','actual_timetable_certified','network_selected','primary_selection_authorised','runner_up_selection_authorised'):
            self.assertFalse(a[key])
        self.assertIsNone(a['decision_budget_km'])
        self.assertIsNone(a['uncertainty_band_min'])


if __name__=='__main__':
    unittest.main()
