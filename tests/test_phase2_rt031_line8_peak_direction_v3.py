import copy
import csv
import json
from collections import Counter
from pathlib import Path
import unittest

from scripts.phase2_build_rt031_line8_peak_direction_v3 import build

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'outputs/phase2/rt031_line8_local_shortcuts_v3'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


class PeakDirectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wings=read(DATA/'independent_wings.json')
        cls.joint=read(DATA/'joint_phases.json')
        with (ROOT/'outputs/phase2/s8_events.csv').open(encoding='utf-8',newline='') as f:
            cls.rail=list(csv.DictReader(f))
        cls.contract=read(ROOT/'outputs/phase2/s8_interchange_contract.json')
        cls.policy=read(ROOT/'config/phase2_final_policy_contract_v3.json')
        cls.result=build(cls.wings,cls.joint,cls.rail,cls.contract,cls.policy)

    def test_only_two_added_trips_no_hidden_retiming(self):
        baseline=Counter((t['loop'],t['departure_min']) for t in self.joint['illustrative_witness']['trips'])
        new=Counter((t['loop'],t['departure_min']) for t in self.result['trips'])
        self.assertFalse(baseline-new)
        self.assertEqual(new-baseline,{('west_A',372):1,('east_B',372):1})
        self.assertEqual(Counter(t['loop'].split('_')[0] for t in self.result['trips']),{'west':18,'east':18})
        self.assertEqual(self.result['stop_identity_count_including_fs'],28)
        self.assertEqual(self.result['first_last_fs_departure_span_min'],748)

    def test_km_and_original_cap_are_separate(self):
        self.assertAlmostEqual(self.result['annual_service_km'],115800.435154,places=5)
        self.assertAlmostEqual(self.result['service_km_excess_percent'],3.932395,places=5)
        added_km=sum(self.wings['loops'][p]['distance_m'] for p in ('west_A','east_B'))/1000*260
        self.assertAlmostEqual(self.result['change_from_frozen_109k']['annual_service_km_delta'],added_km,places=5)
        self.assertEqual(self.result['reference_cap_unchanged'],111419)
        self.assertFalse(self.result['reference_cap_changed'])
        self.assertIsNone(self.result['total_operating_km'])
        self.assertIsNone(self.result['approved_uplift_percent'])

    def test_fast_peak_direction_does_not_hide_slow_opposite_direction(self):
        for r in self.result['priority_locality_rides']:
            fast='to_fs_ride_min' if r['operating_phase']=='AM' else 'from_fs_arrival_ride_min'
            slow='from_fs_arrival_ride_min' if r['operating_phase']=='AM' else 'to_fs_ride_min'
            self.assertLess(r[fast],5)
            self.assertGreater(r[slow],30)

    def test_ordered_peak_banks_and_conditional_switch(self):
        for s in self.result['occurrence_streams']:
            bank=s['peak_bank_departures_min']
            self.assertEqual(len(bank),5)
            for a,b in zip(bank,bank[1:]):
                self.assertAlmostEqual(b-a,30,places=5)
            self.assertFalse(s['boarding_authorised'])
        for r in self.result['nominal_wing_metrics'].values():
            self.assertLessEqual(r['max_optimistic_identity_gap_min'],60.000001)
        # Do not silently replace the strict common-window promise.
        self.assertTrue(any(r['sites_passing']<r['sites_tested'] for r in self.result['stricter_common_clock_window_pass_counts']))

    def test_sensitivity_and_frozen_trains_not_empirical_guarantee(self):
        scenarios=self.result['conditional_operating_sensitivity']
        self.assertEqual(len(scenarios),27)
        nominal=[r for r in scenarios if r['moving_multiplier']==1.1 and r['dwell_min']==.5]
        self.assertEqual([r['minimum_vehicle_count_conditional'] for r in nominal],[4,4,4])
        self.assertEqual(max(r['minimum_vehicle_count_conditional'] for r in scenarios),5)
        self.assertGreater(max(r['max_optimistic_identity_gap_min'] for r in scenarios),60)
        for r in scenarios:
            self.assertIsNone(r['empirical_missed_connection_probability'])
        for pattern in ('west_A','east_B'):
            self.assertEqual([r['train_departure_min'] for r in self.result['frozen_day_rail_peak_matches'] if r['pattern']==pattern], [416,446,476,506,536])

    def test_reproducibility_and_nonmutation(self):
        before=copy.deepcopy(self.joint)
        result=build(self.wings,self.joint,self.rail,self.contract,self.policy)
        self.assertEqual(before,self.joint)
        committed=read(DATA/'peak_direction_18_trips.json'); committed.pop('source_sha256')
        self.assertEqual(result,committed)
        for flag in ('network_selected','primary_selection_authorised','runner_up_selection_authorised','actual_timetable_certified'):
            self.assertFalse(result[flag])
        bad=copy.deepcopy(self.joint); bad['illustrative_witness']['trips'].pop()
        with self.assertRaises(ValueError):
            build(self.wings,bad,self.rail,self.contract,self.policy)


if __name__=='__main__':
    unittest.main()
