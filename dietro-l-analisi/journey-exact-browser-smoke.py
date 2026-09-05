from base64 import b64decode
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8765/dietro-l-analisi/'
OUT = Path('dietro-l-analisi/qa')
OUT.mkdir(parents=True, exist_ok=True)
TRANSPARENT_PNG = b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
)
FINAL_IDS = {
    'R2_23d58cd05658247380d7',
    'R2_65db885119e69d50c7d4',
    'R2_b2032eeb31cba06561f0',
    'R2_2ffb6743b10bb3f0a97d',
}
EXPLORE_KEYS = {
    'worldpop', 'sections', 'buildings', 'walk', 'roads',
    'candidates', 'current', 'proposals', 'stops',
}


def prepare(page, errors, console):
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.on('console', lambda msg: console.append(f'{msg.type}: {msg.text}'))
    for pattern in ['https://tile.openstreetmap.org/**', 'https://*.basemaps.cartocdn.com/**']:
        page.route(pattern, lambda route: route.fulfill(
            status=200, content_type='image/png', body=TRANSPARENT_PNG
        ))


def ready(page):
    page.goto(BASE, wait_until='domcontentloaded', timeout=60000)
    page.wait_for_function("document.querySelector('.loader')?.classList.contains('hidden')", timeout=60000)
    page.wait_for_function("window.__analysisJourneyLineage?.installed === true", timeout=120000)
    page.wait_for_function("window.__analysisJourneyCurrentKmlExact?.installed === true", timeout=30000)
    page.wait_for_function("window.__analysisJourneyExplore?.installed === true", timeout=30000)


def scene(page, name, frac=.55):
    page.evaluate(
        """([name, frac]) => {
          const el = document.querySelector(`[data-scene="${name}"]`);
          if (!el) throw new Error(`missing scene ${name}`);
          window.scrollTo(0, el.offsetTop + el.offsetHeight * frac - innerHeight / 2);
        }""",
        [name, frac],
    )
    page.wait_for_function("name => document.body.dataset.scene === name", arg=name, timeout=15000)
    page.wait_for_timeout(850)


def opacity(page, layer, prop):
    return float(page.evaluate(
        "([layer, prop]) => window.__analysisJourneyMap.getPaintProperty(layer, prop)",
        [layer, prop],
    ))


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors, console = [], []
    prepare(page, errors, console)
    ready(page)

    contract = page.evaluate("""() => {
      const L = window.__analysisJourneyLineage;
      const K = window.__analysisJourneyCurrentKmlExact;
      return {
        currentCount: L.currentData.features.length,
        currentSource: L.currentSource,
        variants: K.variants,
        coordinateCounts: K.coordinateCounts,
        graphReconstruction: K.graphReconstruction,
        stops: L.stopData.features.length,
        finalIds: L.finalData.features.map(f => f.properties.route_id),
        finalistContinuity: L.finalData.features.map(f => [f.geometry.coordinates.length, Number(f.properties.edge_count)]),
        anchors: L.anchorData.features.length,
        chapters: document.querySelectorAll('.chapter').length,
      };
    }""")
    assert contract['currentCount'] == 18, contract
    assert contract['currentSource'] == 'USER_SUPPLIED_AGENCY_KML_LINESTRINGS_EXACT', contract
    assert contract['variants'] == {'D184': 7, 'D185': 11}, contract
    assert contract['coordinateCounts'] == {'D184': 2268, 'D185': 3618}, contract
    assert contract['graphReconstruction'] is False, contract
    assert contract['stops'] == 44, contract
    assert set(contract['finalIds']) == FINAL_IDS, contract
    assert all(coords == edges + 1 for coords, edges in contract['finalistContinuity']), contract
    assert contract['anchors'] == 11 and contract['chapters'] == 12, contract

    # Exact current-service KML is also what the rendered current source holds.
    rendered = page.evaluate("""() => {
      const d = window.__analysisJourneyLineage.currentData.features;
      return {
        d184: d.filter(f => f.properties.route === 'D184').reduce((s,f) => s + f.geometry.coordinates.length, 0),
        d185: d.filter(f => f.properties.route === 'D185').reduce((s,f) => s + f.geometry.coordinates.length, 0),
      };
    }""")
    assert rendered == {'d184': 2268, 'd185': 3618}, rendered

    scene(page, 'explore', .52)
    assert page.locator('[data-explore-enter]').count() == 1
    assert page.locator('.explore-controls').count() == 1
    assert page.evaluate("window.__analysisJourneyExplore.isActive()") is False
    assert set(page.evaluate("window.__analysisJourneyExplore.layers")) == EXPLORE_KEYS

    # Preview is cinematic: exact finalists visible, current network off.
    assert opacity(page, 'explore-final-routes', 'line-opacity') > .9
    assert opacity(page, 'explore-current-routes', 'line-opacity') == 0

    # Explicit click hands control from scroll to the map.
    page.locator('[data-explore-enter]').click()
    page.wait_for_function("window.__analysisJourneyExplore.isActive() === true", timeout=5000)
    assert page.evaluate("document.body.classList.contains('is-map-exploring')") is True
    assert page.evaluate("document.documentElement.classList.contains('is-map-exploring')") is True

    # Current KML and all analytical layers from the scroll can be switched on.
    checks = [
        ('current', 'explore-current-routes', 'line-opacity', .5),
        ('worldpop', 'worldpop-columns', 'fill-extrusion-opacity', .1),
        ('sections', 'sections-fill', 'fill-extrusion-opacity', .1),
        ('buildings', 'buildings-extrude', 'fill-extrusion-opacity', .1),
        ('walk', 'piece-halo', 'circle-opacity', .1),
        ('candidates', 'candidates', 'circle-opacity', .1),
    ]
    for key, layer, prop, minimum in checks:
        page.locator(f'.explore-controls button[data-layer="{key}"]').click()
        page.wait_for_timeout(100)
        assert opacity(page, layer, prop) > minimum, (key, layer, opacity(page, layer, prop))

    page.locator('.explore-controls button[data-layer="roads"]').click()
    page.wait_for_function("!!window.__analysisJourneyMap.getLayer('road-network')", timeout=30000)
    page.wait_for_timeout(100)
    assert opacity(page, 'road-network', 'line-opacity') > .5

    # Certified proposed stop remains inspectable and correctly labelled.
    assert page.evaluate("window.__analysisJourneyExplore.showAnchor('P2V2S_0089')") is True
    page.wait_for_timeout(100)
    popup = page.locator('.maplibregl-popup').inner_text().upper()
    assert 'NUOVA FERMATA CANDIDATA' in popup and 'FIELD CHECK PENDING' in popup, popup
    page.screenshot(path=str(OUT / 'exact-explore.png'), full_page=False)

    # Exit returns ownership to the scroll narrative.
    page.locator('.explore-controls [data-action="exit"]').click()
    page.wait_for_function("window.__analysisJourneyExplore.isActive() === false", timeout=5000)
    assert page.evaluate("document.body.classList.contains('is-map-exploring')") is False
    assert not errors, 'page errors: ' + ' | '.join(errors) + '\nconsole:\n' + '\n'.join(console)
    page.close()

    # Mobile: same explicit enter/exit contract and no horizontal overflow.
    mobile = browser.new_page(viewport={'width': 390, 'height': 844})
    mobile_errors, mobile_console = [], []
    prepare(mobile, mobile_errors, mobile_console)
    ready(mobile)
    scene(mobile, 'explore', .52)
    assert mobile.evaluate('document.documentElement.scrollWidth - window.innerWidth') <= 2
    mobile.locator('[data-explore-enter]').click()
    mobile.wait_for_function("window.__analysisJourneyExplore.isActive() === true", timeout=5000)
    mobile.wait_for_timeout(150)
    assert mobile.evaluate('document.documentElement.scrollWidth - window.innerWidth') <= 2
    mobile.locator('.explore-controls [data-action="exit"]').click()
    mobile.wait_for_function("window.__analysisJourneyExplore.isActive() === false", timeout=5000)
    assert not mobile_errors, 'mobile errors: ' + ' | '.join(mobile_errors) + '\nconsole:\n' + '\n'.join(mobile_console)
    mobile.close()
    browser.close()

print('journey exact KML + full click-to-explore browser smoke PASS')
