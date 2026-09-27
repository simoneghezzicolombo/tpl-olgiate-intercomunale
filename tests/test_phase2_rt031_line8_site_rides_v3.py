import copy
import json
import unittest

from scripts.phase2_audit_rt031_line8_site_rides_v3 import BASE, DOC, SOURCE, FLAGS, audit, build, report


class SiteRidesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = json.loads(SOURCE.read_text(encoding='utf-8'))

    def test_committed_outputs_are_reproducible(self):
        result = build()
        self.assertEqual(result, json.loads((BASE / 'site_rides_audit.json').read_text(encoding='utf-8')))
        self.assertEqual(report(result), DOC.read_text(encoding='utf-8'))
        self.assertEqual(result['site_count_including_fs'], 28)
        self.assertEqual(sum(len(r['journeys']) for r in result['sites']), 27 * 17)
        self.assertTrue(all(not result[k] for k in FLAGS))
        self.assertIsNone(result['decision_budget_km'])

    def test_local_occurrences_match_existing_bindings_not_early_long_rides(self):
        rows = {r['stop_place_id']: r for r in audit(self.ledger)['sites']}
        for binding in self.ledger['local_event_bindings_nominal']:
            if binding['pattern'] not in ('west_B', 'east_A'):
                continue
            for journey in rows[binding['stop_place_id']]['journeys']:
                for field in ('from_fs_alighting_occurrence_id', 'to_fs_boarding_occurrence_id'):
                    self.assertEqual(journey[field], binding[field])
                for field in ('from_fs_ride_min', 'to_fs_ride_min'):
                    self.assertAlmostEqual(journey[field], binding[field], delta=1/60)
                self.assertTrue(journey['distinct_occurrences_required'])
                self.assertFalse(journey['boarding_authorised'])
                self.assertFalse(journey['passenger_continuity_certified'])

    def test_longer_other_site_rides_are_not_hidden(self):
        rows = {r['stop_place_id']: r for r in audit(self.ledger)['sites']}
        self.assertGreater(rows['ASF::OLGIATE_MOLGORA_SCARPONE']['to_fs_ride_min_range'][0], 30)
        self.assertGreater(rows['ASF::CALCO_VIA_GARIBALDI']['from_fs_ride_min_range'][0], 30)

    def test_input_order_does_not_merge_occurrences(self):
        changed = copy.deepcopy(self.ledger)
        changed['nominal_stop_occurrence_events'].reverse()
        self.assertEqual(audit(changed), audit(self.ledger))

    def test_bad_trip_order_unknown_sites_and_duplicate_events_fail_closed(self):
        for mutation in ('time', 'site', 'duplicate', 'pattern', 'missing'):
            changed = copy.deepcopy(self.ledger)
            event = changed['nominal_stop_occurrence_events'][0]
            if mutation == 'time':
                event['departure_nominal'] = '23:59:00'
            elif mutation == 'site':
                event['stop_place_id'] = 'UNKNOWN'
            elif mutation == 'duplicate':
                changed['nominal_stop_occurrence_events'].append(copy.deepcopy(event))
            elif mutation == 'pattern':
                event['pattern'] = 'OTHER'
            else:
                sid = event['stop_place_id']
                changed['nominal_stop_occurrence_events'] = [e for e in changed['nominal_stop_occurrence_events'] if e['stop_place_id'] != sid]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                audit(changed)

    def test_selected_input_rejected(self):
        changed = copy.deepcopy(self.ledger)
        changed['network_selected'] = True
        with self.assertRaises(ValueError):
            audit(changed)


if __name__ == '__main__':
    unittest.main()
