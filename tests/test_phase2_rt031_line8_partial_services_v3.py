import copy
import json
import unittest
import itertools
import numpy as np
import tempfile
from pathlib import Path

from scripts.phase2_probe_rt031_line8_partial_services_v3 import OUTPUT as POOL, subsets
from scripts.phase2_solve_rt031_line8_partial_services_v3 import OUTPUT, missing_cuts, cut_matrix, checkpoint_signature, solve_lazy
from scripts.phase2_audit_rt031_line8_robustness_cost_v3 import digest
from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import BASE, FLAGS, load_sources
from scripts.phase2_compare_rt031_line8_shorter_span_v3 import SPANS
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import family_inputs, prepare, verify, events_by_site


class PartialServicesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pool = json.loads(POOL.read_text(encoding='utf-8'))
        cls.result = json.loads(OUTPUT.read_text(encoding='utf-8'))
        cls.family = cls.pool['family']
        cls.baseline = next(f for f in family_inputs(load_sources()) if f['name'] == 'fast_local_both_directions')
        spec = SPANS['last_fs_1940']
        kwargs = dict(ready_span=(390, 1180), pm_arrivals=spec['pm_arrivals'])
        reference = prepare(cls.baseline, 60, False, **kwargs)
        cls.problem = prepare(cls.family, 60, False, **kwargs, am_wait_ceiling_comparison_min=reference['wait_ceiling'])

    def test_full_retention_sources_and_no_selection(self):
        self.assertEqual(self.result['source_sha256_normalized_newlines'], {
            'pool': digest(POOL), 'reference': digest(BASE / 'shorter_span_comparison.json')})
        self.assertEqual(len(self.pool['reference_site_ids']), 28)
        for p, loop in self.baseline['loops'].items():
            self.assertEqual(self.family['loops'][p], loop)
        self.assertEqual(self.family['rail_anchor_scope'], 'each_declared_site')
        for doc in (self.pool, self.result):
            for key in FLAGS:
                self.assertIs(doc[key], False)
            self.assertIsNone(doc['decision_budget_km'])
            self.assertIsNone(doc['uncertainty_band_min'])

    def test_prefix_suffix_domain_and_bound_events(self):
        loop = {'events': [{'stop_place_id': sid, 'path_node_index': i} for i, sid in enumerate(('a', 'b', 'c', 'LOCAL'))]}
        self.assertEqual(set(subsets(loop, 'LOCAL')), {(), ('a',), ('a', 'b'), ('b', 'c'), ('c',)})
        for request in self.pool['requests']:
            if not request['reachable']:
                continue
            pattern = request['pattern_id']
            loop = self.family['loops'][pattern]
            served = {e['stop_place_id'] for e in loop['events']}
            self.assertTrue(set(request['required_nonlocal_site_sequence']) | {request['required_local_site_id']} <= served)
            for event in loop['events']:
                self.assertEqual(event['incoming_edge'], loop['edge_ids'][event['path_node_index'] - 1])
                self.assertFalse(event['boarding_authorised'])
                self.assertFalse(event['passenger_continuity_certified'])

    def test_short_trip_cannot_credit_missing_site_train_anchor(self):
        self.assertEqual(len(self.problem['anchors']), 27 * 11)
        self.assertTrue(all(anchor['eligible'] for anchor in self.problem['anchors']))
        for anchor in self.problem['anchors']:
            for index in anchor['eligible']:
                loop = self.family['loops'][self.problem['trips'][index]['loop']]
                self.assertIn(anchor['stop_place_id'], {e['stop_place_id'] for e in loop['events']})
        bad = copy.deepcopy(self.family)
        bad.pop('rail_anchor_scope')
        with self.assertRaisesRegex(ValueError, 'per-site rail anchors'):
            prepare(bad, 60, False)
        bad = copy.deepcopy(self.family)
        bad['joins']['west_A>east_A'] = False
        with self.assertRaisesRegex(ValueError, 'every represented FS join'):
            prepare(bad, 60, False)

    def test_independent_full_verification_and_cost(self):
        case = self.result['case']
        scenarios = verify(self.problem, case['trips'], case['comparison_peak_windows'], 4)
        self.assertEqual(scenarios, case['conditional_scenarios'])
        annual = sum(self.family['loops'][t['loop']]['distance_m'] * .26 for t in case['trips'])
        self.assertAlmostEqual(annual, case['annual_service_km'], places=5)
        self.assertLessEqual(case['annual_service_km_lower_bound_in_domain'], annual + 1e-4)
        self.assertFalse(case['policy_adopted'])
        if case['optimality_proven_in_this_domain']:
            self.assertAlmostEqual(case['annual_service_km_lower_bound_in_domain'], annual, places=3)
        candidates = {key: events_by_site(self.problem['trips'], loops) for key, loops in self.problem['adjusted'].items()}
        self.assertFalse(missing_cuts(self.problem, case['trips'], case['comparison_peak_windows'], candidates))

    def test_midpoint_cuts_reject_unserved_sites(self):
        problem = {'adjusted': {'nominal': {}}, 'ready_span': (0, 60), 'offpeak_wait': 60}
        cuts = missing_cuts(problem, [], [], {'nominal': {('SITE', 'from_fs'): [(0, 60), (1, 120)]}})
        self.assertEqual(cuts, {(0,)})

    def test_peak_cuts_are_conditional_on_their_own_phase(self):
        problem = {'adjusted': {'nominal': {}}, 'ready_span': (390, 450), 'offpeak_wait': 60}
        phases = [{'peak': 'AM', 'start_min': 390, 'end_min': 510}]
        candidates = {'nominal': {('SITE', 'from_fs'): [(0, 450), (1, 465), (2, 480)]}}
        cuts = missing_cuts(problem, [], phases, candidates, phase_scoped=True)
        self.assertIn(((0, 1, 2), -1), cuts)
        self.assertIn(((0, 1, 2), 0), cuts)

    def test_lifted_cut_is_applied_to_every_containing_phase_only(self):
        problem = {'adjusted': {'nominal': {}}, 'ready_span': (390, 450), 'offpeak_wait': 60}
        phases = [{'peak': 'AM', 'start_min': 390, 'end_min': 510}]
        candidates = {'nominal': {('SITE', 'from_fs'): [(0, 450), (1, 465), (2, 480)]}}
        cuts = missing_cuts(problem, [], phases, candidates, phase_scoped=True, lift_phases=True)
        self.assertEqual(cuts, {((0, 1, 2), p) for p in (-1, *range(7))})

    def test_merged_cut_matrix_preserves_every_binary_phase_choice(self):
        cuts = {((0, 1), phase) for phase in (0, 1, 7, 8)}
        matrix, lower = cut_matrix(cuts, 2, True)
        self.assertEqual(matrix.shape, (2, 16))
        for trips in itertools.product((0, 1), repeat=2):
            for am, pm in itertools.product(range(7), range(7, 14)):
                vector = np.array([*trips, *[int(p in (am, pm)) for p in range(14)]])
                expected = all(sum(trips) >= int(p in (am, pm)) for p in (0, 1, 7, 8))
                self.assertEqual(bool(np.all(matrix @ vector >= lower)), expected)
        matrix, lower = cut_matrix(cuts | {((0, 1), -1)}, 2, True)
        self.assertEqual(matrix.shape, (1, 16))
        self.assertEqual(lower.tolist(), [1.])
        self.assertFalse(np.any(matrix.toarray()[0, 2:]))

    def test_checkpoint_signature_rejects_domain_changes(self):
        phases = self.result['case']['comparison_peak_windows']
        original = checkpoint_signature(self.problem, True, phases)
        changed = dict(self.problem, offpeak_wait=90)
        self.assertNotEqual(original, checkpoint_signature(changed, True, phases))
        changed = dict(self.problem, ready_span=(390, 1240))
        self.assertNotEqual(original, checkpoint_signature(changed, True, phases))
        self.assertNotEqual(original, checkpoint_signature(self.problem, False, phases))

    def test_flexible_phase_witness_and_bound(self):
        result = json.loads((BASE / 'partial_services_flexible_peaks.json').read_text(encoding='utf-8'))
        self.assertEqual(result['source_sha256_normalized_newlines'], self.result['source_sha256_normalized_newlines'])
        case = result['case']
        self.assertTrue(case['flexible_peak_phases'])
        verify(self.problem, case['trips'], case['comparison_peak_windows'], 4)
        self.assertLessEqual(case['annual_service_km_lower_bound_in_domain'], case['annual_service_km'] + 1e-4)
        if case['optimality_proven_in_this_domain']:
            self.assertAlmostEqual(case['annual_service_km_lower_bound_in_domain'], case['annual_service_km'], places=3)

    def test_strengthened_witness_and_actual_road_export(self):
        from scripts.phase2_export_rt031_line8_partial_phase_closure_v3 import build
        result = json.loads((BASE / 'partial_services_phase_closure.json').read_text(encoding='utf-8'))
        case = result['case']
        verify(self.problem, case['trips'], case['comparison_peak_windows'], 4)
        self.assertTrue(case['flexible_peak_phases'])
        self.assertLess(case['annual_service_km'], self.result['case']['annual_service_km'])
        self.assertLessEqual(case['annual_service_km_lower_bound_in_domain'], case['annual_service_km'] + 1e-4)
        if case['optimality_proven_in_this_domain']:
            self.assertAlmostEqual(case['annual_service_km_lower_bound_in_domain'], case['annual_service_km'], places=3)
        ledger, shape = build()
        self.assertEqual(ledger, json.loads((BASE / 'partial_services_phase_witness.json').read_text(encoding='utf-8')))
        self.assertEqual(shape, json.loads((BASE / 'partial_services_phase_witness.geojson').read_text(encoding='utf-8')))
        self.assertEqual(ledger['site_count_including_fs'], 28)
        self.assertEqual({f['properties']['pattern'] for f in shape['features'] if f['geometry']['type'] == 'LineString'},
                         set(case['patterns_used']))
        self.assertAlmostEqual(sum(t['service_km'] for t in ledger['trips']) * 260, case['annual_service_km'], places=5)

    def test_resume_rechecks_and_preserves_better_incumbent_on_zero_time(self):
        reference = self.result['case']
        better = json.loads((BASE / 'partial_services_phase_closure.json').read_text(encoding='utf-8'))['case']
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'checkpoint.json'
            saved = {'domain_sha256': checkpoint_signature(self.problem, True, reference['comparison_peak_windows']),
                     'relaxation_witnesses': [{'trips': [], 'phases': reference['comparison_peak_windows']},
                                             {'trips': better['trips'], 'phases': better['comparison_peak_windows']}]}
            path.write_text(json.dumps(saved), encoding='utf-8')
            resumed = solve_lazy(self.problem, reference, time_limit=0, flexible_peaks=True,
                                  checkpoint_path=path, strengthen=True)
            self.assertAlmostEqual(resumed['annual_service_km'], better['annual_service_km'], places=5)
            self.assertFalse(resumed['optimality_proven_in_this_domain'])
            saved['domain_sha256'] = 'wrong-domain'
            path.write_text(json.dumps(saved), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'checkpoint domain mismatch'):
                solve_lazy(self.problem, reference, time_limit=0, flexible_peaks=True, checkpoint_path=path)
            saved = copy.deepcopy(saved)
            saved['domain_sha256'] = checkpoint_signature(self.problem, True, reference['comparison_peak_windows'])
            saved['relaxation_witnesses'][0]['phases'][0]['end_min'] -= 1
            path.write_text(json.dumps(saved), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'checkpoint phase domain mismatch'):
                solve_lazy(self.problem, reference, time_limit=0, flexible_peaks=True, checkpoint_path=path)
            saved = {'domain_sha256': checkpoint_signature(self.problem, False, reference['comparison_peak_windows']),
                     'relaxation_witnesses': [{'trips': better['trips'], 'phases': better['comparison_peak_windows']}]}
            path.write_text(json.dumps(saved), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'checkpoint changes fixed peak phases'):
                solve_lazy(self.problem, reference, time_limit=0, flexible_peaks=False, checkpoint_path=path)


if __name__ == '__main__':
    unittest.main()
