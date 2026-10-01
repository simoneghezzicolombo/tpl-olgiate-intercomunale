import json
import unittest

from scripts.phase2_audit_rt031_line8_full_trip_vehicles_v3 import OUTPUT, build


class FullTripVehicleBlocksTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = json.loads(OUTPUT.read_text(encoding='utf-8'))

    def test_reproduces_committed_evidence(self):
        self.assertEqual(build(), self.result)

    def test_one_line_two_full_trip_orderings_not_two_fleets(self):
        r = self.result
        self.assertEqual(r['contract'], 'RT031_LINE8_FULL_TRIP_VEHICLE_BLOCKS_V3')
        self.assertFalse(r['wing_separate_vehicle_assignment'])
        self.assertTrue(r['same_model_vehicle_through_intermediate_fs'])
        self.assertFalse(r['physical_vehicle_and_passenger_continuity_certified'])
        self.assertFalse(r['operating_plan_adopted'])
        self.assertFalse(r['network_selected'])
        self.assertFalse(r['primary_selection_authorised'])
        self.assertFalse(r['runner_up_selection_authorised'])
        self.assertIsNone(r['decision_budget_km'])
        self.assertIsNone(r['uncertainty_band_min'])
        self.assertEqual({c['uniform_full_pattern_id'] for c in r['cases']},
                         {'west_B>east_A', 'east_A>west_B'})

    def test_nominal_and_stress_fleet_counts(self):
        cases = {c['first_wing']: c for c in self.result['cases']}
        self.assertEqual(cases['west_B']['scenario_vehicle_count_distribution_27'],
                         {'4': 26, '5': 1})
        self.assertEqual(cases['east_A']['scenario_vehicle_count_distribution_27'],
                         {'3': 1, '4': 26})
        for wing in ('west_B', 'east_A'):
            nominal = cases[wing]['detailed_scenarios']['nominal']
            self.assertEqual(nominal['minimum_vehicle_count_conditional'], 4)
            self.assertEqual(nominal['interval_overlap_lower_bound_vehicles'], 4)
            self.assertEqual(sorted(t['full_trip_number'] for v in nominal['vehicles']
                                    for t in v['trips']), list(range(1, 17)))
        west_stress = cases['west_B']['detailed_scenarios']['slower_dwell_and_recovery']
        east_stress = cases['east_A']['detailed_scenarios']['slower_dwell_and_recovery']
        self.assertGreater(west_stress['full_trip_cycle_with_terminal_recovery_min'], 120)
        self.assertLess(east_stress['full_trip_cycle_with_terminal_recovery_min'], 120)
        self.assertEqual(west_stress['minimum_vehicle_count_conditional'], 5)
        self.assertEqual(east_stress['minimum_vehicle_count_conditional'], 4)


if __name__ == '__main__':
    unittest.main()
