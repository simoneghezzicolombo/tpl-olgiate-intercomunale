import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import (
    BASE, CASES, FLAGS, build, load_sources, make_trips, reproduce, source_paths,
)


class EveningReallocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = load_sources()
        cls.result = reproduce()

    def test_reproduces_committed_artifact_without_source_mutation(self):
        original = copy.deepcopy(self.sources)
        again = build(**self.sources)
        self.assertEqual(original, self.sources)
        committed = json.loads((BASE / 'evening_reallocation.json').read_text(encoding='utf-8'))
        self.assertEqual(committed, self.result)
        self.assertEqual(again['families'], self.result['families'])

    def test_two_hours_at_same_km_preserves_peak_banks_and_sites(self):
        for family in self.result['families']:
            cases = {c['case_id']: c for c in family['cases']}
            baseline = cases['baseline']
            self.assertEqual(family['site_count_including_fs'], 28)
            for key in ('move_one_smooth_1940', 'move_two_smooth_2040', 'move_two_holes_2040'):
                row = cases[key]
                self.assertEqual(row['daily_trip_count'], 36)
                self.assertEqual(row['annual_service_km_delta'], 0)
                self.assertEqual(row['pattern_counts'], baseline['pattern_counts'])
                self.assertEqual(row['annual_service_km'], baseline['annual_service_km'])
            for row in cases.values():
                self.assertEqual(len(row['conditional_scenarios']), 27)
                self.assertTrue(row['all_scenarios_morning_targets_retained'])
                self.assertEqual(row['changed_road_paths'], [])
                self.assertTrue(row['geographic_sites_and_ordered_road_patterns_unchanged'])
                for wing in row['by_wing'].values():
                    self.assertTrue(wing['am_bank_unchanged'])
                    self.assertTrue(wing['pm_bank_unchanged'])
            self.assertEqual(cases['move_two_smooth_2040']['last_fs_departure_min'], 1240)
            self.assertEqual(cases['move_two_smooth_2040']['first_fs_departure_min'], baseline['first_fs_departure_min'])

    def test_headway_relaxation_is_not_hidden(self):
        expected = dict(baseline=60, move_one_smooth_1940=90, move_two_smooth_2040=90,
                        move_two_holes_2040=120, one_moved_one_added_2040=90, add_two_h60_2040=60)
        for family in self.result['families']:
            for row in family['cases']:
                gap = expected[row['case_id']]
                self.assertEqual(max(r['max_optimistic_identity_gap_min'] for r in row['conditional_scenarios']), gap)
                self.assertEqual(row['all_scenarios_optimistic_h60'], gap == 60)
                self.assertFalse(row['common_clock_two_hour_h30_certified'])
                for wing in row['by_wing'].values():
                    self.assertEqual(max(g['gap_min'] for g in wing['gaps']), gap)

    def test_added_trips_cost_the_actual_rest_patterns(self):
        for family, loops in zip(self.result['families'], (self.sources['wings']['loops'], self.sources['counterflow']['candidate_loops'])):
            cases = {c['case_id']: c for c in family['cases']}
            cost = sum(loops[k]['distance_m'] for k in ('west_B', 'east_A')) / 1000 * 260
            for key, pairs in (('one_moved_one_added_2040', 1), ('add_two_h60_2040', 2)):
                self.assertAlmostEqual(cases[key]['annual_service_km_delta'], cost * pairs, places=5)
                self.assertEqual(cases[key]['daily_trip_count'], 36 + 2 * pairs)
            self.assertGreater(cases['baseline']['annual_service_km'], 111419)

    def test_ordered_occurrences_and_hypothetical_boarding_preserved(self):
        for family in self.result['families']:
            baseline = family['cases'][0]['nominal_occurrence_streams']
            expected = {(s['pattern'], s['occurrence_id'], s['path_node_index'], s['stop_place_id']) for s in baseline}
            for row in family['cases']:
                streams = row['nominal_occurrence_streams']
                self.assertEqual({(s['pattern'], s['occurrence_id'], s['path_node_index'], s['stop_place_id']) for s in streams}, expected)
                self.assertEqual(len(streams), len(expected))
                self.assertTrue(all(not s['boarding_authorised'] and not s['passenger_continuity_certified'] for s in streams))
                self.assertGreater(row['last_nonhub_event_departure_min_nominal'], row['last_fs_departure_min'])
        repeated = [s for s in self.result['families'][0]['cases'][0]['nominal_occurrence_streams']
                    if s['pattern'] == 'east_B' and s['stop_place_id'] == 'FROZEN::300956']
        self.assertGreater(len(repeated), 1)

    def test_frozen_rail_and_conditional_fleet_not_overclaimed(self):
        self.assertEqual(self.result['frozen_rail_service_date'], '2026-09-03')
        self.assertEqual([(r['train_arrival_min'], r['bus_departure_min'], r['residual_after_three_min_walk'])
                          for r in self.result['evening_rail_comparisons']], [(1172, 1180, 5), (1232, 1240, 5)])
        for family, worst in zip(self.result['families'], (5, 6)):
            for row in family['cases']:
                self.assertEqual(max(s['minimum_vehicle_count_conditional'] for s in row['conditional_scenarios']), worst)
                for scenario in row['conditional_scenarios']:
                    indices = [i for block in scenario['trip_index_blocks'] for i in block]
                    self.assertEqual(sorted(indices), list(range(row['daily_trip_count'])))
                    self.assertGreater(scenario['last_fs_return_min'], row['last_fs_departure_min'])
        for flag in (*FLAGS, 'actual_timetable_certified'):
            self.assertIs(self.result[flag], False)
        for key in ('decision_budget_km', 'uncertainty_band_min', 'approved_uplift_percent', 'total_operating_km'):
            self.assertIsNone(self.result[key])

    def test_fail_closed_on_source_or_inventory_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = source_paths()
            tampered = Path(temporary) / 'wings.json'
            tampered.write_bytes(paths['wings'].read_bytes() + b' ')
            paths['wings'] = tampered
            with self.assertRaisesRegex(ValueError, 'frozen evidence drift'):
                load_sources(paths)
        bad = copy.deepcopy(self.sources)
        bad['timetable']['primary_selection_authorised'] = True
        with self.assertRaises(ValueError):
            build(**bad)
        bad = copy.deepcopy(self.sources['timetable']['trips'])
        bad.pop()
        with self.assertRaises(ValueError):
            make_trips(bad, 'baseline')
        self.assertEqual(len(CASES), 6)


if __name__ == '__main__':
    unittest.main()
