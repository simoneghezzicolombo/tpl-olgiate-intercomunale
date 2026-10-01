import json
import unittest
from pathlib import Path

from scripts.phase2_compare_rt031_line8_deep_offpeak_v3 import OUTPUT,WINDOWS,build_problem
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import validate_service_windows,verify,FLAGS
from scripts.phase2_export_rt031_line8_deep_offpeak_v3 import build,LEDGER
from scripts.phase2_solve_rt031_line8_partial_services_v3 import missing_cuts,checkpoint_signature
from scripts.phase2_audit_rt031_line8_passenger_peaks_v3 import uncovered_intervals
from scripts.phase2_solve_rt031_line8_flexible_peaks_v3 import interval_covers


class DeepOffpeakTests(unittest.TestCase):
    def test_partition_has_no_holes_or_overlaps(self):
        self.assertEqual(validate_service_windows(None,(390,1180),60),[(390,1180,60)])
        for windows in ([],[(390,660,60),(661,1180,90)],[(390,700,60),(660,1180,90)],
                        [(390,1181,60)],[(390,1180,45)],[(390,900,90)]):
            with self.assertRaises(ValueError):validate_service_windows(windows,(390,1180),60)

    def test_ready_time_boundary_not_departure_label(self):
        # Ready at 10:59 is still entitled to H60 even if the next departure is
        # inside the H120 window. Ready at 15:00 returns to H60 immediately.
        trips=[660,780,900,1020]
        self.assertTrue(uncovered_intervals(trips,900,960,60))
        self.assertFalse(uncovered_intervals(trips,660,900,120))
        self.assertTrue(uncovered_intervals([780],600,660,60))
        cover=interval_covers(list(enumerate(trips)),900,960,60)
        self.assertIn((),cover)

    def test_lazy_cuts_use_each_service_window(self):
        p={'adjusted':{'nominal':{}},'ready_span':(0,180),'offpeak_wait':60,
           'offpeak_windows':[(0,60,60),(60,120,120),(120,180,60)]}
        candidate={'nominal':{('SITE','from_fs'):[(0,60),(1,180)]}}
        cuts=missing_cuts(p,[],[],candidate)
        self.assertEqual(cuts,{(0,),(1,)})

    def test_rail_anchors_and_peak_domain_unchanged(self):
        reference=build_problem()
        alternative=build_problem(WINDOWS['11_15'],120)
        self.assertEqual(reference['anchors'],alternative['anchors'])
        self.assertEqual(len(alternative['anchors']),297)
        self.assertEqual(reference['wait_ceiling'],alternative['wait_ceiling'])
        self.assertEqual(reference['trips'],alternative['trips'])
        self.assertEqual(reference['timing_grid'],alternative['timing_grid'])
        self.assertNotEqual(checkpoint_signature(reference,True,[]),checkpoint_signature(alternative,True,[]))

    def test_all_witnesses_rechecked(self):
        r=json.loads(OUTPUT.read_text(encoding='utf-8'))
        self.assertTrue(r['all_five_cases_checked']);self.assertEqual(len(r['cases']),5)
        for c in r['cases']:
            p=build_problem(c['midday_window_comparison_min'],c['midday_wait_comparison_min'])
            self.assertEqual(c['per_site_rail_anchor_count'],297)
            if not c['witness_found']:continue
            self.assertEqual(c['conditional_scenarios'],verify(p,c['trips'],c['comparison_peak_windows'],4))
            self.assertAlmostEqual(sum(p['family']['loops'][t['loop']]['distance_m']*.26 for t in c['trips']),c['annual_service_km'],places=5)
            if c['case_id']!='h60_reference':
                with self.assertRaisesRegex(ValueError,'off-peak'):
                    verify(build_problem(),c['trips'],c['comparison_peak_windows'],4)
        self.assertTrue(all(not r[k] for k in FLAGS))
        self.assertIsNone(r['decision_budget_km']);self.assertIsNone(r['uncertainty_band_min'])

    def test_audit_preserves_rail_and_limits_new_authorisation(self):
        root=Path(__file__).resolve().parents[1]
        audit=json.loads((root/'config/rt031_requirements_audit_v3.json').read_text(encoding='utf-8'))
        ids={r['id']:r for r in audit['requirements']}
        self.assertEqual(ids['railway_interchange']['classification'],'USER_REQUIREMENT_REAFFIRMED')
        self.assertEqual(ids['deep_offpeak']['classification'],'USER_ACCEPTED_SERVICE_FLEXIBILITY_WINDOWS_NOT_SELECTED')
        self.assertEqual(ids['calendar']['classification'],'ENGINEERING_ASSUMPTION')
        self.assertTrue(all(not audit[k] for k in FLAGS))

    def test_export_reproduces_actual_trips_events_and_shape(self):
        ledger,shape=build()
        # Normalise tuples exactly as the JSON writer does.
        self.assertEqual(json.loads(json.dumps(ledger)),json.loads(LEDGER.read_text(encoding='utf-8')))
        self.assertEqual(shape,json.loads(LEDGER.with_suffix('.geojson').read_text(encoding='utf-8')))
        self.assertEqual(ledger['patterns_used'],{'east_A':17,'west_B':17})
        self.assertEqual(ledger['site_count_including_fs'],28)
        self.assertEqual(sum(f['geometry']['type']=='Point' for f in shape['features']),28)
        self.assertEqual(sum(f['geometry']['type']=='LineString' for f in shape['features']),2)
        self.assertTrue(all(not ledger[k] for k in FLAGS))
        self.assertFalse(ledger['window_selection_authorised'])


if __name__=='__main__':unittest.main()
