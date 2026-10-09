"""Independent, stdlib-only regressions for the redesigned public experience.

The website may change its layout and wording, but it must preserve accessible
controls, the explicit publication boundary, and the certified proposal's
event/authority semantics. No invented demand, fleet or approval is permitted.
"""
from collections import Counter
from hashlib import sha256
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
PAGES = ("index.html", "dietro-l-analisi/index.html")


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.elements = []
        self.feed(path.read_text(encoding="utf-8"))

    def handle_starttag(self, tag, attributes):
        self.elements.append((tag, dict(attributes)))

    @property
    def ids(self):
        return [attrs["id"] for _, attrs in self.elements if "id" in attrs]

    @property
    def runtime_ids(self):
        # The story assigns IDs before it creates its chapter navigation.
        return {
            "capitolo-" + attrs["data-scene"]
            for _, attrs in self.elements
            if "data-scene" in attrs
        }


class RedesignRegressionTests(unittest.TestCase):
    def test_benefits_and_historical_pdb_evidence_keep_dates_and_scope(self):
        for name in PAGES:
            text=(ROOT/name).read_text(encoding='utf-8')
            self.assertIn('data-resident-comparison',text)
            self.assertIn('data-hero-coverage',text)
            self.assertIn('data-pdb-note',text)
        service=json.loads((ROOT/'assets/nodo8-service-comparison.json').read_text(encoding='utf-8'))
        for axis,name in [('west','D184'),('east','D185')]:
            pdf=ROOT/f'cache/current_timetable_audit_20261007/{name}.pdf'
            if pdf.exists():
                self.assertEqual(sha256(pdf.read_bytes()).hexdigest(),service[axis]['source_sha256'])
        pdb=ROOT/'cache/PdB_COLCVA_Allegato2_SchedeInterventoLecco_20180608.pdf'
        if pdb.exists():
            self.assertEqual(sha256(pdb.read_bytes()).hexdigest(),service['pdb']['source_sha256'])
        self.assertFalse(service['pdb']['automatic_km_entitlement_certified'])
        self.assertFalse(service['pdb']['automatic_funding_transfer_certified'])
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "assets/nodo8-proposal.json").read_text(encoding="utf-8"))
        cls.pages = {name: Page(ROOT / name) for name in PAGES}

    def test_accessible_controls_reference_unique_existing_targets(self):
        for name, page in self.pages.items():
            with self.subTest(page=name):
                counts = Counter(page.ids)
                self.assertFalse([key for key, count in counts.items() if count > 1])
                self.assertEqual(sum(tag == "h1" for tag, _ in page.elements), 1)
                self.assertEqual(sum(tag == "main" for tag, _ in page.elements), 1)
                for tag, attrs in page.elements:
                    for key in ("aria-controls", "aria-labelledby", "aria-describedby"):
                        for target in attrs.get(key, "").split():
                            self.assertIn(target, page.ids, (name, key, target))
                    if tag == "label" and "for" in attrs:
                        self.assertIn(attrs["for"], page.ids, (name, attrs["for"]))
                    if tag == "button":
                        self.assertEqual(attrs.get("type"), "button", (name, attrs))

    def test_both_pages_use_the_shared_nodo8_favicon_and_no_em_dashes(self):
        for name, page in self.pages.items():
            with self.subTest(page=name):
                icons = [attrs for tag, attrs in page.elements if tag == "link" and attrs.get("rel") == "icon"]
                self.assertEqual(len(icons), 1)
                icon_path = ((ROOT / name).parent / urlsplit(icons[0]["href"]).path).resolve()
                self.assertEqual(icon_path, (ROOT / "favicon.svg").resolve())
                self.assertEqual(icons[0].get("type"), "image/svg+xml")
                self.assertNotIn("\u2014", (ROOT / name).read_text(encoding="utf-8"))
        self.assertIn('viewBox="0 0 64 64"', (ROOT / "favicon.svg").read_text(encoding="utf-8"))
        bootstrap = (ROOT / "dietro-l-analisi/journey-bootstrap.mjs").read_text(encoding="utf-8")
        self.assertNotIn('favicon.href = "./favicon.svg"', bootstrap)

    def test_glance_views_keep_the_full_experience_and_event_order(self):
        root = self.pages["index.html"]
        selected = [attrs["id"] for _, attrs in root.elements if attrs.get("role") == "tab" and attrs.get("aria-selected") == "true"]
        self.assertIn("localitiesTab", selected)
        for name in ("routeMap", "routePlayback", "stopRegister", "journeyInspector", "stopsDiagram", "localitiesDiagram", "timetableBody", "coverageBars", "proposta", "confronto"):
            self.assertIn(name, root.ids)
        story = self.pages["dietro-l-analisi/index.html"]
        scenes = [attrs["data-scene"] for _, attrs in story.elements if "data-scene" in attrs]
        self.assertEqual(scenes, ["intro", "grid", "sections", "buildings", "walk", "roads", "baseline", "candidates", "finalists", "nodo8", "nodo8-time", "end"])
        html = (ROOT / "dietro-l-analisi/index.html").read_text(encoding="utf-8")
        for value in ("22.820,84", "93,16", "4.348", "1.686", "1.074", "292", "155", "FIG", "TWO"):
            self.assertIn(value, html)
        for cls in ("story-flow", "story-search", "story-frequency"):
            self.assertIn(cls, html)

    def test_local_assets_are_published_and_cross_page_anchors_resolve(self):
        policy = json.loads((ROOT / "config/nodo8_publication_allowlist.json").read_text(encoding="utf-8"))
        included = set(policy["include_files"])
        self.assertEqual({name for name in included if name.endswith(".html")}, set(PAGES))
        prelude = (ROOT / "dietro-l-analisi/journey-explore-prelude.js").read_text(encoding="utf-8")
        runtime_ids = set(re.findall(r'\bid\s*=\s*["\']([^"\']+)', prelude))
        for name, page in self.pages.items():
            for tag, attrs in page.elements:
                reference = attrs.get("href") if tag in ("a", "link") else attrs.get("src")
                if not reference:
                    continue
                url = urlsplit(reference)
                if url.scheme or url.netloc:
                    continue
                path = (ROOT / name).parent / unquote(url.path) if url.path else ROOT / name
                if path.is_dir():
                    path = path / "index.html"
                relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
                self.assertIn(relative, included, (name, reference))
                if url.fragment and relative in self.pages:
                    target_page = self.pages[relative]
                    known = set(target_page.ids) | target_page.runtime_ids
                    if relative == "dietro-l-analisi/index.html":
                        known |= runtime_ids
                    self.assertIn(unquote(url.fragment), known, (name, reference))

    def test_story_uses_one_population_legend_without_losing_its_evidence(self):
        director = (ROOT / "dietro-l-analisi/journey-director.js").read_text(encoding="utf-8")
        lens = (ROOT / "dietro-l-analisi/journey-lens.js").read_text(encoding="utf-8")
        html = (ROOT / "dietro-l-analisi/index.html").read_text(encoding="utf-8")
        self.assertEqual(director.count("representation.className = 'representation-meter'"), 1)
        self.assertNotIn("depth.className = 'depth-stack'", lens)
        self.assertNotIn("document.body.appendChild(evidence)", director)
        for source in ("WorldPop", "ISTAT", "DBGT"):
            self.assertIn(source, director)
        self.assertIn("el.setAttribute('aria-current','step')", director)
        for layer in ("worldpop-stack", "sections-stack", "buildings-stack"):
            self.assertIn(layer, lens)
        self.assertIn(".representation-meter [data-stage]", lens)
        # Explanations formerly repeated over the map are still reachable in
        # the native disclosures, rather than silently discarded or falsified.
        self.assertIn("con geometrie e vincoli diversi", html)
        self.assertIn("fino a una casa", html)
        self.assertIn("non le posizioni dei punti scartati", html)
        self.assertIn('class="journey-final-actions"', html)

    def test_spatial_comparison_preserves_denominators_and_does_not_infer_passengers(self):
        comparison = json.loads((ROOT / "assets/nodo8-coverage-comparison.json").read_text(encoding="utf-8"))
        self.assertIs(comparison["proposal_coverage_reproduced"], True)
        self.assertIs(comparison["baseline_trip_level_current_activation_certified"], False)
        self.assertIs(comparison["additional_resident_count_inferred"], False)
        self.assertIs(comparison["temporary_bridge_disruption_included"], False)
        self.assertEqual(comparison["official_physical_cluster_count"], 44)
        self.assertEqual(comparison["thresholds_min"], [5, 8, 10])
        for code, row in comparison["baseline_percent"].items():
            for time, before in row.items():
                after = comparison["proposal_percent"][code][time]
                self.assertAlmostEqual(after, self.data["coverage"][code][time], places=7)
                self.assertAlmostEqual(comparison["delta_percentage_points"][code][time], after - before, places=7)
        for point in comparison["distant_unattached_points"]:
            self.assertGreater(point["minimum_core_distance_lower_bound_m"], 800)
        for source in comparison["sources"].values():
            path = ROOT / source["path"]
            if path.is_file():
                self.assertEqual(sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest(), source["sha256"])

    def test_certification_and_caller_declared_inputs_are_not_manufactured(self):
        authority = self.data["authority"]
        for key in ("public_operating_timetable_authorised", "network_selected", "primary_selection_authorised", "runner_up_selection_authorised", "physical_boarding_authorised", "funding_secured"):
            self.assertIs(authority[key], False, key)
        for key in ("decision_budget_km", "uncertainty_band_min", "missed_connection_probability", "demand_weighted_gjt_improvement_min"):
            self.assertIsNone(authority[key], key)
        self.assertIs(self.data["playback"]["physical_vehicle_and_passenger_continuity_certified"], False)
        self.assertIn("not observed passengers", self.data["coverage_semantics"])
        self.assertIn("route-downscaled municipal OD", self.data["coverage_semantics"])

    def test_upstream_source_hashes_remain_authoritative(self):
        expected = {
            "design": "2dc2299112211694433b5d637ef97183e9c15e0e2f5719b1ad4c5aa6f2f51a3c",
            "calendar": "86e12d0e5bbd8a3c77fed7b3844bcf84a3305c70e92f2a74a42300c6cbf04c5b",
            "geometry": "47148a1aa91c1e290084718f93da47b23bb4e05f90e07a1d1af6412f590fe4e3",
            "blocks": "61aa5561fafec7b204ea1fa34ab3c496bda40d41d18ca7dfe9840f27fb045017",
        }
        self.assertEqual(set(self.data["sources"]), set(expected))
        for source, evidence in self.data["sources"].items():
            with self.subTest(source=source):
                self.assertEqual(evidence["sha256_semantics"], "SOURCE_BYTES_WITH_CRLF_NORMALISED_TO_LF")
                self.assertEqual(evidence["sha256"], expected[source])
                # The source checkout contains all upstream evidence; the
                # deliberately restricted Pages checkout only ships geometry.
                source_path = ROOT / evidence["path"]
                if source_path.is_file():
                    payload = source_path.read_bytes().replace(b"\r\n", b"\n")
                    self.assertEqual(sha256(payload).hexdigest(), evidence["sha256"])

    def test_same_site_does_not_collapse_ordered_passenger_events(self):
        sites = self.data["sites"]
        self.assertEqual(len(sites), 27)
        occurrences = [event for site in sites for event in site["ordered_occurrences"]]
        self.assertEqual(len(occurrences), 28)
        self.assertEqual(sorted(e["ordered_nonhub_event_number"] for e in occurrences), list(range(1, 29)))
        self.assertEqual(len({e["occurrence_id"] for e in occurrences}), 28)
        repeated = [site for site in sites if len(site["ordered_occurrences"]) > 1]
        self.assertEqual(len(repeated), 2)
        routes = {route["wing"]: route["coordinates"] for route in self.data["routes"]}
        self.assertEqual(routes["east_A"][-1], routes["west_B"][0])
        complete = routes["east_A"] + routes["west_B"][1:]
        middle = len(routes["east_A"]) - 1
        by_id = {e["occurrence_id"]: (site, e) for site in sites for e in site["ordered_occurrences"]}
        expected_order = [e["occurrence_id"] for e in sorted(occurrences, key=lambda e: e["ordered_nonhub_event_number"])]
        for ledger in self.data["playback"]["ledger"]:
            events = ledger["events"]
            self.assertEqual(len(events), 31)
            self.assertEqual([events[i]["role"] for i in (0, 15, 30)], ["FULL_TRIP_START_FS", "INTERMEDIATE_FS_STAY_ONBOARD_DESIGN", "FULL_TRIP_END_FS"])
            self.assertIs(events[15]["physical_continuity_certified"], False)
            actual_order = []
            for event in events:
                if event["role"] != "DESIGN_STOP_OCCURRENCE":
                    continue
                actual_order.append(event["occurrence_id"])
                site, occurrence = by_id[event["occurrence_id"]]
                index = occurrence["path_node_index"] + (middle if event["wing"] == "west_B" else 0)
                self.assertEqual(index, event["full_path_edge_index"])
                self.assertEqual(complete[index], site["coordinates_lon_lat"])
                self.assertIs(event["physical_boarding_authorised"], False)
            self.assertEqual(actual_order, expected_order)

    def test_four_nominal_carriers_are_full_trip_assignments_not_two_lines(self):
        playback = self.data["playback"]
        vehicles = playback["vehicles"]
        self.assertEqual({v["model_vehicle_id"] for v in vehicles}, {"B1", "B2", "B3", "B4"})
        assigned = []
        for vehicle in vehicles:
            self.assertIsNone(vehicle["actual_vehicle_identity"])
            self.assertIsNone(vehicle["driver_duty_assignment"])
            self.assertIs(vehicle["same_model_vehicle_through_intermediate_fs"], True)
            blocks = vehicle["trips"]
            self.assertEqual(vehicle["complete_trip_numbers"], [b["full_trip_number"] for b in blocks])
            for index, block in enumerate(blocks):
                assigned.append(block["full_trip_number"])
                trip = self.data["trips"][block["full_trip_number"] - 1]
                self.assertEqual(block["fs_start_min"], trip["first_fs_min"])
                self.assertEqual(block["fs_end_min"], trip["return_fs_min"])
                self.assertEqual(block["intermediate_fs_departure_min"], trip["second_fs_min"])
                self.assertAlmostEqual(block["released_after_terminal_recovery_min"] - block["fs_end_min"], playback["terminal_recovery_min"])
                if index:
                    self.assertGreaterEqual(block["fs_start_min"], blocks[index - 1]["released_after_terminal_recovery_min"])
        self.assertEqual(sorted(assigned), list(range(1, 17)))

    def test_commercial_km_do_not_claim_cost_or_transferable_budget(self):
        calendar = self.data["calendar"]
        trips = self.data["trips"]
        self.assertEqual(calendar["weekday_base_complete_trip_count"], len(trips) * calendar["weekday_base_day_count_before_local_exceptions"])
        expected = calendar["weekday_base_complete_trip_count"] * self.data["complete_path_distance_m"] / 1000
        self.assertTrue(math.isclose(calendar["weekday_base_commercial_km"], expected, abs_tol=1e-8))
        self.assertIs(calendar["saturday_service_policy_adopted"], False)
        self.assertIsNone(calendar["annual_noncommercial_km"])
        self.assertIsNone(calendar["full_annual_operating_cost"])


if __name__ == "__main__":
    unittest.main()
