import copy
import json
import unittest

from scripts.phase2_compare_rt031_line8_peak_directions_v3 import (
    OUTPUT, BASE, EXPECTED, FLAGS, PEAKS, POLICIES, SPANS, load_sources, family_inputs,
    prepare, verify, constrain_anchors, ride_profiles, vector, bindings, document, preserve_reference_tie,
)
from scripts.phase2_export_rt031_line8_peak_directions_v3 import DOC, report, geometry


class PeakDirectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.family = next(f for f in family_inputs(load_sources()) if f['name'] == 'fast_local_both_directions')
        cls.result = json.loads(OUTPUT.read_text(encoding='utf-8'))
        cls.bases = {h: prepare(cls.family, h, False, ready_span=(390, 1180),
                              pm_arrivals=SPANS['last_fs_1940']['pm_arrivals']) for h in (60, 90)}

    def test_32_cases_proven_and_document_provenance(self):
        self.assertEqual(self.result, document(self.result['cases'], ride_profiles(self.family)))
        self.assertTrue(self.result['all_cases_attempted'])
        self.assertTrue(self.result['all_cases_proven_optimal'])
        self.assertEqual(self.result['source_sha256_normalized_newlines'], EXPECTED)
        self.assertFalse(document(self.result['cases'][:-1], ride_profiles(self.family))['all_cases_attempted'])
        self.assertTrue(all(not self.result[k] for k in FLAGS))
        self.assertIsNone(self.result['decision_budget_km'])

    def test_all_witnesses_independently_rechecked_with_direction_anchors(self):
        for case in self.result['cases']:
            policy = POLICIES[case['direction_policy_id']]
            problem = constrain_anchors(self.bases[case['offpeak_wait_comparison_min']], policy)
            with self.subTest(h=case['offpeak_wait_comparison_min'], policy=case['direction_policy_id']):
                self.assertEqual(verify(problem, case['trips'], case['comparison_peak_windows'], 4), case['conditional_scenarios'])
                self.assertEqual(bindings(problem, case), case['rail_anchor_dispatch_bindings'])
                self.assertEqual(case['rail_anchor_pattern_comparison'], policy)
                self.assertEqual({p['peak']: p['start_min'] for p in case['comparison_peak_windows']}, PEAKS)
                cost = sum(self.family['loops'][t['loop']]['distance_m'] for t in case['trips']) * .26
                self.assertAlmostEqual(cost, case['annual_service_km'], places=5)
                self.assertAlmostEqual(cost, case['annual_service_km_lower_bound_in_domain'], places=5)
                for anchor in case['rail_anchor_dispatch_bindings']:
                    self.assertTrue(anchor['qualifying_dispatches'])
                    self.assertTrue(all(t['loop'] == anchor['required_pattern'] for t in anchor['qualifying_dispatches']))

    def test_restrictions_cannot_improve_unrestricted_km_minimum(self):
        for h, floor in ((60, 143929.083516), (90, 122339.720989)):
            costs = [c['annual_service_km'] for c in self.result['cases'] if c['offpeak_wait_comparison_min'] == h]
            self.assertAlmostEqual(min(costs), floor, places=5)
            self.assertTrue(all(c > 111419 for c in costs))

    def test_profiles_keep_all_sites_and_directional_occurrences(self):
        profiles = self.result['nominal_ride_profiles']
        self.assertEqual(profiles, ride_profiles(self.family))
        for wing in ('west', 'east'):
            self.assertEqual({s['stop_place_id'] for s in profiles[wing + '_A']['sites']},
                             {s['stop_place_id'] for s in profiles[wing + '_B']['sites']})
        for policy in POLICIES.values():
            self.assertEqual(len(vector(profiles, policy)), 54)
        for pattern, values in profiles.items():
            for row in values['sites']:
                self.assertTrue(row['to_fs_boarding_occurrence_id'].startswith(pattern + ':'))
                self.assertTrue(row['from_fs_alighting_occurrence_id'].startswith(pattern + ':'))
                self.assertFalse(row['boarding_authorised'])

    def test_no_uniformly_better_reversal_hidden_by_average(self):
        vectors = self.result['nominal_peak_site_vectors']
        base, reverse = vectors['BA_BA'], vectors['AB_BA']
        self.assertLess(reverse['AM|ASF::OLGIATE_MOLGORA_SCARPONE'], base['AM|ASF::OLGIATE_MOLGORA_SCARPONE'])
        self.assertGreater(reverse['AM|ASF::OLGIATE_MOLGORA_VIA_DELLA_SALUTE'], base['AM|ASF::OLGIATE_MOLGORA_VIA_DELLA_SALUTE'])
        self.assertLess(reverse['AM|FROZEN::300086'], base['AM|FROZEN::300086'])
        self.assertGreater(reverse['AM|ASF::CALCO_VIA_GARIBALDI'], base['AM|ASF::CALCO_VIA_GARIBALDI'])

    def test_bad_direction_and_witness_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'unsupported direction'):
            constrain_anchors(self.bases[90], {'AM': {'west': 'east_A'}})
        old = next(c for c in self.result['cases'] if c['direction_policy_id'] == 'BA_BA' and c['offpeak_wait_comparison_min'] == 90)
        problem = constrain_anchors(self.bases[90], POLICIES['AB_BA'])
        with self.assertRaisesRegex(ValueError, 'rail anchor verification'):
            verify(problem, old['trips'], old['comparison_peak_windows'], 4)

    def test_same_cost_lower_stress_reference_is_not_lost_to_solver_tie(self):
        case = next(c for c in self.result['cases'] if c['direction_policy_id'] == 'BA_BA' and c['offpeak_wait_comparison_min'] == 90)
        reference = preserve_reference_tie(constrain_anchors(self.bases[90], POLICIES['BA_BA']), case)
        self.assertEqual(reference, case['same_cost_verified_reference_witness'])
        self.assertEqual(reference['worst_grid_vehicle_count_conditional'], 5)
        self.assertEqual(reference['annual_service_km'], case['annual_service_km'])

    def test_report_and_real_shape_match_evidence(self):
        self.assertEqual(report(self.result), DOC.read_text(encoding='utf-8'))
        derived = geometry(self.result)
        self.assertEqual(derived, json.loads((BASE / 'peak_direction_comparison.geojson').read_text(encoding='utf-8')))
        lines = [f for f in derived['features'] if f['geometry']['type'] == 'LineString']
        self.assertEqual(len(lines), 4)
        self.assertTrue(all(f['properties']['comparison_witnesses_using_pattern'] for f in lines))
        self.assertEqual(len(derived['features']), 32)
        incomplete = copy.deepcopy(self.result)
        incomplete['all_cases_proven_optimal'] = False
        with self.assertRaises(ValueError):
            report(incomplete)
        selected = copy.deepcopy(self.result)
        selected['network_selected'] = True
        with self.assertRaises(ValueError):
            geometry(selected)
        with self.assertRaises(ValueError):
            report(selected)


if __name__ == '__main__':
    unittest.main()
