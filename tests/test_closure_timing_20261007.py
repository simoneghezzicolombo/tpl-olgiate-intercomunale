import copy
import json
import math
import unittest

from scripts.phase2_closure_timing_20261007 import BASE, build, budgets, check_measurement, verify_sources


class ClosureTimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = build()
        cls.case = next(c for c in cls.report['cases'] if (c['moving_multiplier'], c['dwell_min'], c['terminal_recovery_assumption_min']) == (1.1, .5, 10))

    def observation(self, row, **overrides):
        values = dict(east_running_min=row['east_running_min'], east_nonfs_dwell_min=row['east_nonfs_dwell_min'],
                      intermediate_fs_dwell_min=1, west_running_min=row['west_running_min'],
                      west_nonfs_dwell_min=row['west_nonfs_dwell_min'], terminal_recovery_min=10)
        values.update(overrides)
        return check_measurement(row, **values)

    def test_all_cases_and_trips(self):
        self.assertEqual(len(self.report['cases']), 27)
        for case in self.report['cases']:
            self.assertEqual([r['full_trip_number'] for r in case['trips']], list(range(1, 17)))

    def test_nominal_budgets(self):
        rows = self.case['trips']
        self.assertEqual([r['east_running_plus_nonfs_dwell_budget_min'] for r in rows], [54]*6+[49]+[54]*8+[49])
        self.assertAlmostEqual(rows[0]['next_use_headroom_min'], 16.6972961954551)
        self.assertAlmostEqual(rows[0]['west_scenario_arrival_budget_min'], 38.3027038045449)

    def test_east_cannot_borrow_terminal_gap(self):
        row = self.case['trips'][0]
        result = self.observation(row, east_running_min=48)
        self.assertFalse(result['meets_fixed_intermediate_departure'])
        self.assertTrue(result['meets_next_use'])

    def test_nominal_arrival_target_and_next_use_are_separate(self):
        row = self.case['trips'][0]
        result = self.observation(row, west_running_min=row['west_running_min']+1)
        self.assertLess(result['west_scenario_arrival_slack_min'], 0)
        self.assertTrue(result['meets_next_use'])

    def test_recovery_consumes_gap(self):
        result = self.observation(self.case['trips'][0], terminal_recovery_min=27)
        self.assertFalse(result['meets_next_use'])

    def test_last_trip_has_no_fabricated_deadline(self):
        result = self.observation(self.case['trips'][-1], west_running_min=500)
        self.assertIsNone(result['meets_next_use'])
        self.assertLess(result['west_scenario_arrival_slack_min'], 0)

    def test_invalid_measurements(self):
        for value in [-1, math.nan, math.inf, True, '3', None]:
            with self.assertRaises(ValueError):
                self.observation(self.case['trips'][0], east_running_min=value)

    def test_timetable_and_duplicate_assignment_rejected(self):
        original = json.loads((BASE/'caller_confirmed_vehicle_blocks_accounting_20261001.json').read_text())['nominal_case']
        for mutation in ['time', 'duplicate', 'recovery']:
            case = copy.deepcopy(original)
            if mutation == 'time':
                case['vehicles'][0]['trips'][0]['fs_start_min'] += 1
            elif mutation == 'recovery':
                case['vehicles'][0]['trips'][0]['released_after_terminal_recovery_min'] -= 1
            else:
                case['vehicles'][0]['trips'].append(copy.deepcopy(case['vehicles'][0]['trips'][0]))
                case['vehicles'][0]['complete_trip_numbers'].append(1)
            with self.assertRaises(ValueError):
                budgets(case, {'east_A': 14, 'west_B': 14})

    def test_saved_block_edit_with_unchanged_source_references_rejected(self):
        original = json.loads((BASE/'caller_confirmed_vehicle_blocks_accounting_20261001.json').read_text())
        handoff = json.loads((BASE/'caller_confirmed_design_handoff_20261001.json').read_text())
        changed = copy.deepcopy(original)
        changed['all_27_resource_cases'][0]['vehicles'][0]['model_vehicle_id'] = 'EDITED'
        self.assertEqual(changed['source_canonical_sha256'], original['source_canonical_sha256'])
        with self.assertRaisesRegex(ValueError, 'Entire saved blocks'):
            verify_sources(changed, handoff, blocks_producer=lambda: original, handoff_producer=lambda: handoff)

    def test_saved_handoff_edit_rejected(self):
        blocks = json.loads((BASE/'caller_confirmed_vehicle_blocks_accounting_20261001.json').read_text())
        original = json.loads((BASE/'caller_confirmed_design_handoff_20261001.json').read_text())
        changed = copy.deepcopy(original)
        changed['full_trips'][0]['first_fs_min'] += 1
        with self.assertRaisesRegex(ValueError, 'Entire saved handoff'):
            verify_sources(blocks, changed, blocks_producer=lambda: blocks, handoff_producer=lambda: original)

    def test_missing_measurement_in_every_cost_fails_closed(self):
        for key in ['east_running_min', 'east_nonfs_dwell_min', 'intermediate_fs_dwell_min',
                    'west_running_min', 'west_nonfs_dwell_min', 'terminal_recovery_min']:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.observation(self.case['trips'][0], **{key: None})


if __name__ == '__main__':
    unittest.main()
