import json
from pathlib import Path
import unittest


class JointPhaseTests(unittest.TestCase):
    def test_joint_witness_and_limits(self):
        a=json.loads((Path(__file__).resolve().parents[1]/'outputs/phase2/rt031_line8_local_shortcuts_v3/joint_phases.json').read_text(encoding='utf-8'))
        w=a['illustrative_witness']
        self.assertEqual(len(w['trips']),34)
        self.assertEqual(w['annual_km_before_extras'],109285.99)
        for m in w['wing_metrics'].values():
            self.assertLessEqual(m['first_fs_arrival_min']+3,446)
            self.assertGreaterEqual(m['last_fs_departure_min'],1112+3)
            self.assertLessEqual(m['max_optimistic_identity_gap_min'],60.000001)
        self.assertEqual([b['minimum_vehicle_count_conditional'] for b in w['blocks']],[4,4,4])
        for r in a['phase_tables']:
            if r['dwell_min_assumption']==.5:
                self.assertTrue(r['feasible_phases'])
            elif r['wing']=='west':
                self.assertEqual(r['feasible_phases'],[])
        for key in ('network_selected','primary_selection_authorised','runner_up_selection_authorised','requested_peak_windows_certified','actual_timetable_certified'):
            self.assertFalse(a[key])
        self.assertIsNone(a['decision_budget_km'])
        self.assertIsNone(a['uncertainty_band_min'])


if __name__=='__main__':
    unittest.main()
