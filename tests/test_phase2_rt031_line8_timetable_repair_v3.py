import copy
import csv
import json
from pathlib import Path
import random
import unittest

from scripts.phase2_solve_rt031_line8_flexible_peaks_v3 import interval_covers
from scripts.phase2_close_rt031_line8_timetable_repair_v3 import build as close_build
from scripts.phase2_build_rt031_line8_regular_compromise_v3 import build as regular_build


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'outputs/phase2/rt031_line8_local_shortcuts_v3'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


class TimetableRepairTests(unittest.TestCase):
    def test_interval_sweep_matches_brute_force(self):
        rng=random.Random(31)
        for _ in range(50):
            events=[(rng.randrange(5),rng.randrange(-20,121)) for _ in range(30)]
            wait=rng.choice((30,60))
            points=sorted({0,100}|{x for _,t in events for x in (t-wait,t) if 0<x<100})
            expected={tuple(sorted({i for i,t in events if t-wait <= (a+b)/2 <= t}))
                      for a,b in zip(points,points[1:])}
            self.assertEqual(interval_covers(events,0,100,wait),expected)

    def test_overlapping_same_trip_occurrences_are_not_removed_early(self):
        self.assertEqual(interval_covers([(0,30),(0,40)],0,40,30),{(0,)})
        self.assertIn((),interval_covers([(0,30)],0,40,30))

    def test_independent_wing_floor_and_fail_closed(self):
        wings=read(DATA/'independent_wings.json')
        west=read(DATA/'flexible_peaks_west_max17.json')
        east=read(DATA/'flexible_peaks_east_max17.json')
        policy=read(ROOT/'config/phase2_final_policy_contract_v3.json')
        result=close_build(wings,west,east,policy)
        self.assertAlmostEqual(result['annual_service_km_lower_bound'],114741.185305,places=5)
        self.assertFalse(result['lower_bound_is_attainable_timetable'])
        bad=copy.deepcopy(east); bad['solver_status']=1
        with self.assertRaises(ValueError):
            close_build(wings,west,bad,policy)
        bad=copy.deepcopy(east); bad['departure_grid_min']=1
        with self.assertRaises(ValueError):
            close_build(wings,west,bad,policy)
        shared=copy.deepcopy(wings)
        shared['loops']['west_A']['events'].append(copy.deepcopy(shared['loops']['east_A']['events'][0]))
        with self.assertRaises(ValueError):
            close_build(shared,west,east,policy)

    def test_regular_compromise_reproduces_without_hiding_concessions(self):
        wings=read(DATA/'independent_wings.json')
        with (ROOT/'outputs/phase2/s8_events.csv').open(encoding='utf-8',newline='') as f:
            rail=list(csv.DictReader(f))
        result=regular_build(wings,rail,read(ROOT/'outputs/phase2/s8_interchange_contract.json'),
                             read(ROOT/'config/phase2_final_policy_contract_v3.json'))
        committed=read(DATA/'regular_12h_compromise.json'); committed.pop('source_sha256')
        self.assertEqual(result,committed)
        self.assertEqual(result['first_last_departure_span_hours'],12)
        self.assertFalse(result['user_acceptance_recorded'])
        self.assertFalse(result['actual_timetable_certified'])
        self.assertEqual(len(result['fs_departures_min']),17)
        for case in result['cases']:
            self.assertEqual(len(case['trips']),34)
            self.assertEqual(case['stop_identity_count_including_fs'],28)
            self.assertFalse(case['reference_13h_windows_satisfied'])
            self.assertTrue(case['reference_window_failures'])
            self.assertTrue(all(w['duration_min']<120 for w in case['common_h30_ready_time_windows']))
            self.assertTrue(all(b['minimum_vehicle_count_conditional']<=4 for b in case['conditional_fleet_sensitivity']))
            for stream in case['occurrence_streams']:
                for bank in ('AM_five_departure_bank_min','PM_five_departure_bank_min'):
                    self.assertAlmostEqual(stream[bank][1]-stream[bank][0],120,places=5)
                self.assertFalse(stream['boarding_authorised'])

    def test_prohibition_on_decision_is_retained(self):
        for file in ('flexible_peak_km_floor.json','regular_12h_compromise.json',
                     'flexible_peaks_west_max17.json','flexible_peaks_east_max17.json'):
            result=read(DATA/file)
            for flag in ('network_selected','primary_selection_authorised','runner_up_selection_authorised'):
                self.assertIs(result[flag],False)
            for field in ('decision_budget_km','uncertainty_band_min'):
                self.assertIsNone(result[field])


if __name__=='__main__':
    unittest.main()
