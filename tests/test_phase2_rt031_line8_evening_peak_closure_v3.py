import copy
import itertools
import json
import unittest
from collections import Counter

from scripts.phase2_audit_rt031_line8_evening_peak_closure_v3 import (
    BASE, build, describe, intersect, opportunities, ready_intervals, reproduce,
)
from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import FLAGS, load_sources
from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops
from scripts.phase2_audit_rt031_line8_passenger_peaks_v3 import uncovered_intervals


class EveningPeakClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = load_sources()
        cls.result = reproduce()

    def test_five_trip_banks_are_not_automatically_two_common_hours(self):
        a = ready_intervals([400, 430, 460, 490, 520], 300, 650)
        b = ready_intervals([440, 470, 500, 530, 560], 300, 650)
        self.assertEqual(a, [[370, 520]])
        self.assertEqual(b, [[410, 560]])
        self.assertEqual(intersect(a, b), [[410, 520]])
        self.assertFalse(describe(intersect(a, b))['exists_common_two_hour_window_in_model'])
        self.assertFalse(describe([[0, 70], [90, 160]])['exists_common_two_hour_window_in_model'])
        self.assertEqual(describe([[400, 520]])['illustrative_whole_minute_two_hour_window'], [400, 520])

    def test_grid_uses_one_window_not_different_phases_per_scenario(self):
        self.assertTrue(describe([[400, 530]])['exists_common_two_hour_window_in_model'])
        self.assertTrue(describe([[430, 560]])['exists_common_two_hour_window_in_model'])
        self.assertFalse(describe(intersect([[400, 530]], [[430, 560]]))['exists_common_two_hour_window_in_model'])

    def test_finite_add_only_domain_is_exhaustive_and_scoped(self):
        for family, baseline_km, repaired_km in zip(self.result['families'], (115800.435154, 130567.294131), (128717.050568, 145166.426276)):
            self.assertEqual(len(family['cases']), 16)
            self.assertEqual({c['case_id'] for c in family['cases']}, {''.join(map(str, bits)) for bits in itertools.product((0, 1), repeat=4)})
            self.assertEqual(family['passing_case_count'], 1)
            self.assertEqual(family['least_km_case_ids_in_this_add_only_domain'], ['1111'])
            self.assertEqual(family['minimum_service_km_in_this_add_only_domain'], repaired_km)
            self.assertEqual(family['cases'][0]['annual_service_km'], baseline_km)
            original = Counter((t['loop'], t['departure_min']) for t in family['cases'][0]['trips'])
            for case in family['cases']:
                self.assertFalse(original - Counter((t['loop'], t['departure_min']) for t in case['trips']))
                self.assertEqual(case['removed_trips'], [])
                self.assertEqual(case['changed_paths'], [])
                self.assertEqual(case['daily_trip_count'], 36 + len(case['added_trips']))
            self.assertEqual(family['cases'][-1]['daily_trip_count'], 40)

    def test_baseline_actual_common_windows_are_reported(self):
        for family, am in zip(self.result['families'], (105.812903, 109.773879)):
            case = family['cases'][0]
            self.assertFalse(case['two_hour_both_directions_in_both_peaks_model_pass'])
            self.assertAlmostEqual(case['grid_common_windows']['AM']['both']['longest_common_interval_min'], am, places=4)
            self.assertAlmostEqual(case['grid_common_windows']['PM']['both']['longest_common_interval_min'], 108.76619, places=4)
            self.assertTrue(case['grid_common_windows']['PM']['from_fs']['exists_common_two_hour_window_in_model'])

    def test_same_km_retimings_preserve_inventory_but_not_headway_or_fleet(self):
        for family, stress_fleet in zip(self.result['families'], (7, 8)):
            baseline = family['cases'][0]
            for case, gap in zip(family['same_km_redistribution_witnesses'], (120, 111)):
                self.assertTrue(case['two_hour_both_directions_in_both_peaks_model_pass'])
                self.assertEqual(case['annual_service_km'], baseline['annual_service_km'])
                self.assertEqual(Counter(t['loop'] for t in case['trips']), Counter(t['loop'] for t in baseline['trips']))
                for pattern in ('west_A', 'east_B'):
                    self.assertEqual([t for t in case['trips'] if t['loop'] == pattern], [t for t in baseline['trips'] if t['loop'] == pattern])
                for pattern in ('west_B', 'east_A'):
                    times = {t['departure_min'] for t in case['trips'] if t['loop'] == pattern}
                    self.assertTrue({1000, 1030, 1060, 1090, 1120, 1180, 1240} <= times)
                self.assertEqual(max(g['max_optimistic_identity_gap_min'] for g in case['conditional_fleet_grid']), gap)
                self.assertEqual(max(v['minimum_vehicle_count_conditional'] for g in case['conditional_fleet_grid'] for v in g['minimum_vehicle_counts_by_recovery']), stress_fleet)

    def test_same_km_windows_independently_verified_at_every_site_across_grid(self):
        for family, raw in zip(self.result['families'], (self.sources['wings']['loops'], self.sources['counterflow']['candidate_loops'])):
            for case in family['same_km_redistribution_witnesses']:
                for multiplier, dwell in itertools.product((.9, 1., 1.1), (0., .5, 1.)):
                    sites = opportunities(case['trips'], adjusted_loops(raw, multiplier, dwell))
                    self.assertEqual(len(sites), 27)
                    for site in sites.values():
                        for events in site.values():
                            for lo, hi in ((405, 525), (990, 1110)):
                                self.assertEqual(uncovered_intervals([e['minute'] for e in events], lo, hi), [])

    def test_reproduction_no_mutation_no_authorisation(self):
        before = copy.deepcopy(self.sources)
        self.assertEqual(build(self.sources), self.result)
        self.assertEqual(before, self.sources)
        committed = json.loads((BASE / 'evening_peak_closure.json').read_text(encoding='utf-8'))
        self.assertEqual(committed, self.result)
        for key in (*FLAGS, 'actual_timetable_certified', 'boarding_authorised'):
            self.assertIs(self.result[key], False)
        for key in ('decision_budget_km', 'uncertainty_band_min', 'approved_uplift_percent', 'total_operating_km'):
            self.assertIsNone(self.result[key])
        bad = copy.deepcopy(self.sources)
        bad['timetable']['primary_selection_authorised'] = True
        with self.assertRaises(ValueError):
            build(bad)


if __name__ == '__main__':
    unittest.main()
