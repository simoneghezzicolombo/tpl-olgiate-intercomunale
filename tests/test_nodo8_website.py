"""The public showcase must not rewrite the confirmed transport proposal."""
import hashlib
import importlib.util
import json
import shutil
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_nodo8", ROOT / "scripts/build_nodo8_website_data.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def read_source(key):
    return json.loads((ROOT / builder.SOURCES[key]).read_text(encoding="utf-8"))


def test_checked_in_asset_is_reproducible():
    assert (ROOT / "assets/nodo8-proposal.json").read_text(encoding="utf-8") == builder.serialise(builder.build_data())


def test_sources_are_hash_pinned():
    for source in builder.build_data()["sources"].values():
        assert source["sha256"] == hashlib.sha256((ROOT / source["path"]).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        assert source["sha256_semantics"] == "SOURCE_BYTES_WITH_CRLF_NORMALISED_TO_LF"


def test_source_digest_is_identical_for_lf_and_crlf_checkouts(tmp_path):
    lf, crlf = tmp_path / "lf.json", tmp_path / "crlf.json"
    lf.write_bytes(b'{\n  "value": 16\n}\n')
    crlf.write_bytes(b'{\r\n  "value": 16\r\n}\r\n')
    assert builder.source_digest(lf) == builder.source_digest(crlf)


def test_map_uses_complete_confirmed_geometries_without_removed_site():
    data, geo = builder.build_data(), read_source("geometry")
    expected = [{"wing": f["properties"]["wing"], "coordinates": f["geometry"]["coordinates"]}
                for f in geo["features"] if f["geometry"]["type"] == "LineString"]
    assert data["routes"] == expected
    assert all(site["site_id"] != "ASF::SANTA_MARIA_HOE_VIA_COMO" for site in data["sites"])


def test_sites_and_occurrences_are_not_collapsed():
    data, design = builder.build_data(), read_source("design")
    assert data["sites"] == design["design_stop_register"]
    assert len(data["sites"]) == 27
    assert sum(site["proposed_new_site"] for site in data["sites"]) == 4
    assert sum(len(site["ordered_occurrences"]) for site in data["sites"]) == 28
    for name in ("Olgiate sud", "San Zeno/Via Cantu"):
        site = next(site for site in data["sites"] if site["name"] == name)
        assert len(site["ordered_occurrences"]) == 2
        assert len({event["occurrence_id"] for event in site["ordered_occurrences"]}) == 2


def test_timetable_is_copied_not_synthesised():
    data, design = builder.build_data(), read_source("design")
    assert len(data["trips"]) == 16
    for shown, original in zip(data["trips"], design["full_trips"]):
        for key, value in original.items():
            assert shown[key] == value
        assert shown["return_fs_min"] == original["second_fs_min"] + design["nominal_wing_duration_min"]["west_B"]
    assert sum(trip["peak_bank"] for trip in data["trips"]) == 10
    assert [trip["first_fs_min"] for trip in data["trips"] if trip["peak_bank"]] == [
        365, 395, 425, 455, 485, 1000, 1030, 1060, 1090, 1120]


def test_coverage_and_calendar_preserve_semantics():
    data = builder.build_data()
    assert data["coverage"] == read_source("design")["coverage_percent"]
    assert data["coverage_semantics"] == read_source("design")["coverage_semantics"]
    assert len(data["municipalities"]) == 5
    assert data["calendar"]["weekday_base_day_count_before_local_exceptions"] == 254
    assert data["calendar"]["weekday_base_commercial_km"] == pytest.approx(110229.93602459409)
    assert data["calendar"]["weekday_base_complete_trip_count"] == 4064
    assert data["calendar"]["saturday_service_policy_adopted"] is False
    for key in ("annual_noncommercial_km", "full_annual_operating_cost"):
        assert data["calendar"][key] is None
    for key in ("decision_budget_km", "uncertainty_band_min", "missed_connection_probability", "demand_weighted_gjt_improvement_min"):
        assert data["authority"][key] is None
    for key in ("public_operating_timetable_authorised", "network_selected", "primary_selection_authorised", "runner_up_selection_authorised"):
        assert data["authority"][key] is False


@pytest.mark.parametrize("source,key,value", [
    ("design", "public_operating_timetable_authorised", True),
    ("calendar", "funding_secured", True),
    ("design", "all_trips_same_complete_path", False),
    ("calendar", "service_year", 2028),
    ("calendar", "weekday_base_day_count_before_local_exceptions", 260),
])
def test_builder_fails_closed_when_public_basis_changes(tmp_path, source, key, value):
    for path in builder.SOURCES.values():
        dest = tmp_path / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / path, dest)
    path = tmp_path / builder.SOURCES[source]
    changed = json.loads(path.read_text(encoding="utf-8"))
    changed[key] = value
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError):
        builder.build_data(tmp_path)


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links, self.headings = [], [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])
        if tag in ("h1", "h2"):
            self.headings.append(tag)


def test_page_has_accessible_structure_and_resolvable_local_links():
    page = PageParser()
    page.feed((ROOT / "index.html").read_text(encoding="utf-8"))
    assert len(page.ids) == len(set(page.ids))
    assert page.headings.count("h1") == 1
    for link in page.links:
        parsed = urlsplit(link)
        if parsed.scheme or parsed.netloc:
            continue
        if parsed.path:
            target = ROOT / unquote(parsed.path)
            assert target.is_file() or (target / "index.html").is_file(), link
        elif parsed.fragment:
            assert parsed.fragment in page.ids, link


def test_legacy_promises_are_not_served():
    page = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "app.js").read_text(encoding="utf-8")
    for phrase in ("Piena sostenibilità economica", "Saldo Zero", "55–60 min", "303 gg feriali", "+117%", "SEMAFORO VERDE"):
        assert phrase not in page
    for legacy in ("SCENARIOS", "FRAZIONI_DATA", "sliderKm", "s8Milano", "s8Lecco"):
        assert legacy not in js
    assert "innerHTML" not in js
    assert "prefers-reduced-motion" in (ROOT / "styles.css").read_text(encoding="utf-8")
