import copy
import json
import unittest

from scripts.phase2_compare_rt031_line8_mixed_local_v3 import OUTPUT, qualify, local_rides
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import (
    BASE, GRID, LOCAL_SITES, FLAGS, family_inputs, load_sources, events_by_site, prepare, verify)
from scripts.phase2_compare_rt031_line8_shorter_span_v3 import SPANS


class MixedLocalTests(unittest.TestCase):
    def test_directions_are_not_interchangeable(self):
        sid = LOCAL_SITES[0]
        loop = {'events': [{'stop_place_id': sid, 'offset_from_wing_origin_min': 3}],
                'local_service_directions': {sid: ['from_fs']}}
        trips = [{'loop': 'west_demo', 'departure_min': 400}]
        self.assertEqual(dict(events_by_site(trips, {'west_demo': loop})), {(sid, 'from_fs'): [(0, 400)]})
        loop['local_service_directions'][sid] = ['to_fs']
        self.assertEqual(dict(events_by_site(trips, {'west_demo': loop})), {(sid, 'to_fs'): [(0, 403)]})

    def test_slow_ride_is_not_qualified_by_stop_identity(self):
        original, corrected = family_inputs(load_sources())
        loops, audit = qualify(original['loops'], corrected['loops'])
        for p, allowed in [('west_A', 'to_fs'), ('west_B', 'from_fs'), ('east_A', 'from_fs'), ('east_B', 'to_fs')]:
            permissions = next(iter(loops[p]['local_service_directions'].values()))
            self.assertEqual(permissions, [allowed])
        self.assertEqual(len(audit), 8)
        self.assertTrue(all(len(a['scenarios']) == len(GRID) for a in audit))

    def test_missing_or_implicit_eligibility_fails_closed(self):
        f = copy.deepcopy(family_inputs(load_sources())[1])
        f['local_direction_contract'] = 'REFERENCE_FAST_RIDE_ENVELOPE_V3'
        f['rail_anchor_scope'] = 'each_declared_site'
        with self.assertRaisesRegex(ValueError, 'eligibility'):
            prepare(f, 60, False)
        del f['local_direction_contract']
        f['loops']['west_A']['local_service_directions'] = {}
        with self.assertRaisesRegex(ValueError, 'explicit contract'):
            prepare(f, 60, False)

    def test_output_independent_recheck_and_anchors(self):
        r = json.loads(OUTPUT.read_text(encoding='utf-8'))
        self.assertEqual(len(r['family']['loops']), 68)
        corrected = family_inputs(load_sources())[1]
        kwargs = dict(ready_span=(390, 1180), pm_arrivals=SPANS['last_fs_1940']['pm_arrivals'])
        ceiling = prepare(corrected, 60, False, **kwargs)['wait_ceiling']
        p = prepare(r['family'], 60, False, **kwargs, am_wait_ceiling_comparison_min=ceiling)
        self.assertEqual(len(p['anchors']), 297)
        for anchor in p['anchors']:
            sid = anchor['stop_place_id']
            direction = 'to_fs' if anchor['kind'] == 'bus_to_rail' else 'from_fs'
            for i in anchor['eligible']:
                loop = p['family']['loops'][p['trips'][i]['loop']]
                if sid in LOCAL_SITES:
                    self.assertIn(direction, loop['local_service_directions'][sid])
        case = r['case']
        self.assertEqual(verify(p, case['trips'], case['comparison_peak_windows'], 4), case['conditional_scenarios'])
        self.assertAlmostEqual(sum(r['family']['loops'][t['loop']]['distance_m'] * .26 for t in case['trips']), case['annual_service_km'], places=6)
        self.assertLessEqual(case['annual_service_km_lower_bound_in_domain'], case['annual_service_km'] + 1e-4)
        self.assertTrue(all(not r[k] for k in FLAGS))
        self.assertIsNone(r['decision_budget_km'])
        self.assertIsNone(r['uncertainty_band_min'])

    def test_saved_eligibility_recomputed_not_trusted(self):
        r = json.loads(OUTPUT.read_text(encoding='utf-8'))
        loops, audit = qualify(r['family']['loops'], family_inputs(load_sources())[1]['loops'])
        order = lambda a: (a['pattern'], a['site_id'], a['direction'])
        self.assertEqual(sorted(audit, key=order), sorted(r['local_direction_audit'], key=order))
        self.assertEqual(loops, r['family']['loops'])

    def test_false_fast_label_rejected_by_solver(self):
        r = json.loads(OUTPUT.read_text(encoding='utf-8'))
        r['family']['loops']['west_B_original']['local_service_directions'][LOCAL_SITES[0]].append('to_fs')
        with self.assertRaisesRegex(ValueError, 'exceeds reference fast envelope'):
            prepare(r['family'], 60, False)


if __name__ == '__main__':
    unittest.main()
