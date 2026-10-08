"""Integration checks: narrative/history/current proposal are distinct pages and sources."""
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
JOURNEY = ROOT / "dietro-l-analisi"


class AssetsParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids, self.scenes, self.assets = [], [], [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if "data-scene" in attrs:
            self.scenes.append(attrs["data-scene"])
        if tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])
        if tag == "script" and "src" in attrs:
            self.assets.append(attrs["src"])
        if tag == "link" and "href" in attrs:
            self.assets.append(attrs["href"])


def parse(path):
    page = AssetsParser()
    page.feed(path.read_text(encoding="utf-8"))
    return page


def test_pages_link_to_each_other_and_every_local_target_exists():
    root = parse(ROOT / "index.html")
    journey = parse(JOURNEY / "index.html")
    assert "dietro-l-analisi/" in root.links
    assert "../index.html#proposta" in journey.links
    for base, page in ((ROOT, root), (JOURNEY, journey)):
        assert len(page.ids) == len(set(page.ids))
        for target in page.links + page.assets:
            url = urlsplit(target)
            if url.scheme or url.netloc:
                continue
            if url.path:
                resolved = (base / unquote(url.path)).resolve()
                assert resolved.is_file() or (resolved / "index.html").is_file(), target
            elif url.fragment:
                assert url.fragment in page.ids


def test_story_preserves_historical_chapters_and_adds_current_proposal():
    page = parse(JOURNEY / "index.html")
    assert page.scenes == [
        "intro", "grid", "sections", "buildings", "walk", "roads", "baseline",
        "candidates", "finalists", "nodo8", "nodo8-time", "end"
    ]
    assert "time" not in page.scenes
    html = " ".join((JOURNEY / "index.html").read_text(encoding="utf-8").split())
    assert "una fase precedente" in html
    assert "non copertura di Nodo8" in html
    assert "100% delle coincidenze" not in html
    assert "48,57%" not in html


def test_existing_territory_assets_and_vendors_match_checked_in_hashes():
    manifest = json.loads((JOURNEY / "upstream-import.json").read_text(encoding="utf-8"))
    assert manifest["upstream_commit"] == "104e8f2f0a801cffb15698aa06a8c2bd98c0dc6e"
    for entry in manifest["preserved_assets"]:
        assert hashlib.sha256((JOURNEY / entry["path"]).read_bytes()).hexdigest() == entry["sha256"]


def test_overlay_never_overwrites_historical_sources():
    module = (JOURNEY / "journey-nodo8.mjs").read_text(encoding="utf-8")
    assert 'fetch("../assets/nodo8-proposal.json")' in module
    assert 'addSource("nodo8-routes"' in module
    assert 'addSource("nodo8-sites"' in module
    assert 'getSource("final-routes-exact")' not in module
    assert ".setData(" not in module
    assert "nominal_occurrence_to_next_fs_in_vehicle_min" in module


def test_exploration_defaults_to_nodo8_not_the_old_four_alternatives():
    js = (JOURNEY / "journey-explore-v2.js").read_text(encoding="utf-8")
    assert "proposals: false" in js
    assert "nodo8: true" in js
    assert "Alternative storiche" in js
    assert 'showSite(f.properties.site_id)' in js
    assert 'journey-explore-ready' in js


def test_old_autonomous_service_animation_cannot_describe_nodo8():
    effects = (JOURNEY / "journey-effects.js").read_text(encoding="utf-8")
    assert "dataset.scene==='legacy-time'" in effects
    assert "dataset.scene==='time'" not in effects
    bootstrap = (JOURNEY / "journey-bootstrap.mjs").read_text(encoding="utf-8")
    assert bootstrap.rindex("journey-explore-prelude.js") < bootstrap.rindex("journey.js")
    assert "journey-nodo8.mjs" in bootstrap
    assert "journey-runtime-unavailable" in bootstrap


def test_historical_controls_are_in_flow_and_do_not_call_old_alternatives_final():
    controls = (JOURNEY / "journey-lineage.js").read_text(encoding="utf-8")
    assert "Alternative della fase storica · non Nodo8" in controls
    assert "Le quattro linee finali" not in controls
    assert "[data-scene=\"baseline\"] .copy" in controls
    assert "[data-scene=\"finalists\"] .copy" in controls
    kml = (JOURNEY / "journey-current-kml-exact.mjs").read_text(encoding="utf-8")
    assert "Tracciati KML ufficiali · fermate da GTFS ufficiale" in kml
