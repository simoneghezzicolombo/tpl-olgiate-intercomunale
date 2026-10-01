import gzip
import hashlib
import json
import unittest

from scripts.phase2_close_rt031_line8_fixed_order_timetable_v3 import OUTPUT, ROAD


class FixedOrderTimetableTests(unittest.TestCase):
    def test_sources_and_no_implicit_adoption(self):
        r=json.loads(gzip.decompress(OUTPUT.read_bytes()))
        self.assertEqual(r['road_source_sha256'],hashlib.sha256(ROAD.read_bytes()).hexdigest())
        self.assertFalse(r['network_selected'])
        self.assertFalse(r['stop_omission_adopted'])
        self.assertIsNone(r['decision_budget_km'])
        baseline=r['baseline_case_not_adopted']
        self.assertTrue(baseline['witness_found'])
        self.assertEqual(len(baseline['full_trips']),16)
        self.assertLessEqual(baseline['original_22_target_compatibility_full_timetable']['compatible_count'],22)
        for c in r['cases']:
            self.assertTrue(c['comparison_not_adopted'])
            self.assertEqual(c['infeasibility_proven'],c['solver_status']==2)
            if c['infeasibility_proven']:
                self.assertFalse(c['witness_found'])
            if c['witness_found']:
                self.assertEqual(len(c['full_trips']),c['full_trip_count'])
                self.assertEqual(len(c['rail_assignments']),20)

    def test_bounded_h60_proof_is_not_global_impossibility(self):
        r=json.loads(gzip.decompress(OUTPUT.read_bytes()))
        cases=[c for c in r['cases'] if c['full_trip_count']==16
               and c['shoulder_headway_cap_min']==60]
        self.assertEqual(len(cases),4)
        self.assertTrue(all(c['infeasibility_proven'] for c in cases))
        self.assertIn('ONLY',r['scope'])


if __name__=='__main__':
    unittest.main()
