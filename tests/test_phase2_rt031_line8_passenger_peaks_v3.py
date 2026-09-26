import json
from pathlib import Path
import unittest
from scripts.phase2_audit_rt031_line8_passenger_peaks_v3 import uncovered_intervals
from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops

BASE=Path(__file__).resolve().parents[1]/'outputs/phase2/rt031_line8_local_shortcuts_v3'


class PassengerPeakTests(unittest.TestCase):
    def test_advanced_peaks_are_compared_not_selected(self):
        a=json.loads((BASE/'rebuilt_peak_comparison.json').read_text(encoding='utf-8'))
        self.assertEqual([c['peak_window_advance_min'] for c in a['comparisons']],[0,15,30])
        self.assertAlmostEqual(min(c['annual_km_before_extras'] for c in a['comparisons']),121115.696,places=3)
        self.assertTrue(all(c['continuous_ready_time_recheck_passed'] for c in a['comparisons']))
        self.assertFalse(a['network_selected'])

    def test_rebuilt_witness_covers_continuous_ready_windows(self):
        a=json.loads((BASE/'rebuilt_timetable.json').read_text(encoding='utf-8'))
        wings=json.loads((BASE/'independent_wings.json').read_text(encoding='utf-8'))
        loops=adjusted_loops(wings['loops'],1.1,.5)
        events={}
        for t in a['trip_witness']:
            for e in loops[t['loop']]['events']:
                for d,time in (('to_fs',t['departure_min']+e['offset_from_wing_origin_min']),('from_fs',t['departure_min'])):
                    events.setdefault((e['stop_place_id'],d),[]).append(time)
        self.assertEqual(len(events),54)
        for times in events.values():
            for w in a['ready_time_windows']:
                self.assertEqual(uncovered_intervals(times,w['start_min'],w['end_min'],w['max_wait_min']),[])
        self.assertEqual(a['candidate_trip_count'],676)
        self.assertAlmostEqual(a['annual_km_before_extras'],127490.206,places=3)
        self.assertFalse(a['network_selected'])

    def test_four_half_hour_departures_do_not_cover_late_ready_times(self):
        self.assertEqual(uncovered_intervals([420,450,480,510],420,540),[[510,540]])
        self.assertEqual(uncovered_intervals([450,480,510,540],420,540),[])

    def test_first_and_last_departure_boundaries(self):
        self.assertEqual(uncovered_intervals([],420,540),[[420,540]])
        self.assertEqual(uncovered_intervals([480],420,540),[[420,450],[480,540]])

    def test_optimistic_peak_failure_and_repair_scope(self):
        a=json.loads((BASE/'passenger_peaks.json').read_text(encoding='utf-8'))
        self.assertEqual(len(a['sites']),27)
        self.assertTrue(all(not d['optimistic_max_wait_30_satisfied'] for s in a['sites'] for d in s['diagnostics'] if d['window']=='AM_REFERENCE'))
        r=json.loads((BASE/'peak_repair.json').read_text(encoding='utf-8'))
        self.assertEqual(r['candidate_domain_count'],344)
        self.assertEqual(r['solver_status'],0)
        self.assertTrue(r['continuous_ready_time_recheck_passed'])
        self.assertAlmostEqual(r['annual_km_before_extras_after_repair'],128577.116,places=3)
        self.assertFalse(r['network_selected'])
        self.assertFalse(r['primary_selection_authorised'])
        self.assertFalse(r['runner_up_selection_authorised'])
        self.assertIsNone(r['decision_budget_km'])
        self.assertIsNone(r['uncertainty_band_min'])


if __name__=='__main__':
    unittest.main()
