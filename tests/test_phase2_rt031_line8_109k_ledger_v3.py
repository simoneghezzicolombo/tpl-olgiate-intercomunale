import copy
import json
from collections import Counter
from pathlib import Path
import tempfile
import unittest

from scripts.phase2_export_rt031_line8_109k_ledger_v3 import build, markdown


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'outputs/phase2/rt031_line8_local_shortcuts_v3'


class FrozenLedgerTests(unittest.TestCase):
    def setUp(self):
        self.sources = [json.loads((DATA / name).read_text(encoding='utf-8'))
                        for name in ('independent_wings.json', 'joint_phases.json', 'rebuilt_peak_comparison.json')]
        self.ledger = build(*self.sources)

    def test_counts_and_full_precision_accounting(self):
        a = self.ledger
        self.assertEqual(Counter(t['wing'] for t in a['trips']), {'west': 17, 'east': 17})
        self.assertEqual(len(a['events_by_site']), 27)
        self.assertAlmostEqual(a['annual_service_km'], sum(t['distance_m'] for t in a['trips']) / 1000 * 260, places=6)
        self.assertAlmostEqual(a['annual_service_km'], 109285.990, places=3)
        bridge = a['historical_comparison_only']
        self.assertAlmostEqual(a['annual_service_km'] + sum(r['annual_km_delta'] for r in bridge['pattern_count_bridge']), bridge['annual_km_before_extras'], places=3)

    def test_shifting_clocks_cannot_change_km(self):
        sources = copy.deepcopy(self.sources)
        for t in sources[1]['illustrative_witness']['trips']:
            t['departure_min'] += 10
        shifted = build(*sources)
        self.assertEqual(shifted['annual_service_km'], self.ledger['annual_service_km'])
        self.assertEqual(shifted['daily_service_km'], self.ledger['daily_service_km'])
        for before, after in zip(self.ledger['trips'], shifted['trips']):
            self.assertEqual(after['departure_min'] - before['departure_min'], 10)

    def test_occurrences_not_collapsed_and_sorted(self):
        a = self.ledger
        events = [e for values in a['events_by_site'].values() for e in values]
        self.assertEqual(len(events), 463)
        self.assertEqual(len({e['occurrence_id'] for e in events}), len(events))
        repeated = [e for e in a['events_by_site']['FROZEN::300956'] if e['trip_id'] == 'E01']
        self.assertEqual(len(repeated), 2)
        self.assertNotEqual(repeated[0]['path_node_index'], repeated[1]['path_node_index'])
        south = a['events_by_site']['RT031::P2V2S_0031_PROJECTED_ROAD_POINT']
        self.assertAlmostEqual(south[4]['gap_since_previous_encounter_min'], 1.428307, places=5)
        self.assertEqual(south[5]['gap_since_previous_encounter_min'], 60)
        zeno = a['events_by_site']['PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE']
        self.assertLess(next(e['departure_min'] for e in zeno if e['trip_id']=='E05'), next(e['departure_min'] for e in zeno if e['trip_id']=='E04'))

    def test_fail_closed_and_no_selection(self):
        for flag in ('network_selected', 'primary_selection_authorised', 'runner_up_selection_authorised', 'actual_timetable_certified'):
            self.assertFalse(self.ledger[flag])
        for key in ('decision_budget_km', 'uncertainty_band_min'):
            self.assertIsNone(self.ledger[key])
        for index in range(3):
            sources = copy.deepcopy(self.sources)
            sources[index]['primary_selection_authorised'] = True
            with self.assertRaises(ValueError):
                build(*sources)
        sources = copy.deepcopy(self.sources)
        sources[1]['illustrative_witness']['trips'].pop()
        with self.assertRaises(ValueError):
            build(*sources)

    def test_committed_export_and_reports_reproduce(self):
        committed = json.loads((DATA / 'frozen_109k_trip_ledger.json').read_text(encoding='utf-8'))
        committed.pop('source_sha256')
        self.assertEqual(committed, self.ledger)
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / name for name in ('RT031_LINEA8_109K_CONTO_CORSE_V3.md', 'RT031_LINEA8_109K_PASSAGGI_PER_LOCALITA_V3.md')]
            markdown(self.ledger, *paths)
            for path in paths:
                self.assertEqual(path.read_text(encoding='utf-8'), (ROOT / 'docs' / path.name).read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
