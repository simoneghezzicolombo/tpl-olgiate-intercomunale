import copy
import csv
import json
from collections import Counter
from pathlib import Path
import unittest

from scripts.phase2_retime_rt031_line8_peak_direction_v3 import build

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'outputs/phase2/rt031_line8_local_shortcuts_v3'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


class RetimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wings=read(DATA/'independent_wings.json')
        cls.source=read(DATA/'peak_direction_18_trips.json')
        with (ROOT/'outputs/phase2/s8_events.csv').open(encoding='utf-8',newline='') as f:
            cls.rail=list(csv.DictReader(f))
        cls.contract=read(ROOT/'outputs/phase2/s8_interchange_contract.json')
        cls.result=build(cls.wings,cls.source,cls.rail,cls.contract)

    def test_same_inventory_distance_and_priority_rides(self):
        a=self.result
        self.assertEqual(Counter(t['loop'] for t in a['trips']),Counter(t['loop'] for t in self.source['trips']))
        self.assertEqual(len(a['trips']),36)
        self.assertEqual(len(a['retimed_trips']),12)
        self.assertEqual(a['annual_service_km'],self.source['annual_service_km'])
        self.assertEqual(a['annual_service_km_delta'],0)
        self.assertEqual(a['priority_locality_rides_unchanged'],self.source['priority_locality_rides'])
        self.assertEqual(a['first_last_fs_departure_span_min'],733)
        for key in ('added_trips','removed_trips','changed_paths'):
            self.assertEqual(a[key],[])

    def test_all_scenarios_h60_and_new_targets_not_old_targets(self):
        a=self.result
        self.assertTrue(a['all_scenarios_optimistic_h60'])
        self.assertTrue(a['all_scenarios_new_morning_targets_retained'])
        self.assertFalse(a['old_first_train_target_retained_across_grid'])
        self.assertEqual(a['old_first_train_target_min'],416)
        self.assertEqual(a['new_morning_train_targets_min'],[446,476,506,536,566])
        self.assertEqual(len(a['conditional_scenarios']),27)
        for r in a['conditional_scenarios']:
            self.assertLessEqual(r['max_optimistic_identity_gap_min'],60.000001)
            self.assertGreaterEqual(min(t['residual_after_three_min_walk'] for t in r['morning_target_rows']),5.97)
        # Four nominal vehicles must not be presented as a robust fleet of four.
        nominal=[r for r in a['conditional_scenarios'] if r['moving_multiplier']==1.1 and r['dwell_min']==.5]
        self.assertEqual([r['minimum_vehicle_count_conditional'] for r in nominal],[4,4,4])
        self.assertEqual(a['worst_minimum_vehicle_count_conditional'],5)

    def test_early_train_bound_is_scoped_and_necessary_not_global(self):
        west,east=self.result['original_early_train_bound']['rows']
        self.assertEqual(west['wing'],'west')
        self.assertTrue(west['incompatible'])
        self.assertAlmostEqual(west['incompatibility_margin_min'],3.157384,places=5)
        self.assertFalse(east['incompatible'])
        self.assertEqual(west['maximum_span_inside_rest_block_min'],8*60+4*30)

    def test_ordered_occurrences_and_common_window_failures_preserved(self):
        streams=self.result['occurrence_streams']
        self.assertEqual(len({s['stop_place_id'] for s in streams}),27)
        for s in streams:
            self.assertFalse(s['boarding_authorised'])
            self.assertFalse(s['passenger_continuity_certified'])
            self.assertEqual(len(s['peak_bank_departures_min']),5)
            for a,b in zip(s['peak_bank_departures_min'],s['peak_bank_departures_min'][1:]):
                self.assertAlmostEqual(b-a,30,places=5)
        self.assertTrue(any(r['sites_passing']<r['sites_tested'] for r in self.result['common_clock_peak_diagnostics']))

    def test_reproduction_nonmutation_and_fail_closed(self):
        before=copy.deepcopy(self.source)
        result=build(self.wings,self.source,self.rail,self.contract)
        self.assertEqual(before,self.source)
        committed=read(DATA/'peak_direction_retimed.json'); committed.pop('source_sha256')
        self.assertEqual(result,committed)
        bad=copy.deepcopy(self.source); bad['trips'].pop()
        with self.assertRaises(ValueError):
            build(self.wings,bad,self.rail,self.contract)
        bad=copy.deepcopy(self.source); bad['primary_selection_authorised']=True
        with self.assertRaises(ValueError):
            build(self.wings,bad,self.rail,self.contract)
        for flag in ('actual_timetable_certified','network_selected','primary_selection_authorised','runner_up_selection_authorised'):
            self.assertFalse(result[flag])
        for key in ('approved_uplift_percent','total_operating_km','decision_budget_km','uncertainty_band_min'):
            self.assertIsNone(result[key])


if __name__=='__main__':
    unittest.main()
