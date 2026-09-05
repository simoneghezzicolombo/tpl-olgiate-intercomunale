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
EXPLORE_LAYERS = {
    'worldpop', 'sections', 'buildings', 'walk', 'roads',
    'candidates', 'current', 'proposals', 'stops',
}


def prepare(page, errors, console):
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.on('console', lambda msg: console.append(f'{msg.type}: {msg.text}'))
    page.route(
        'https://tile.openstreetmap.org/**',
        lambda route: route.fulfill(status=200, content_type='image/png', body=TRANSPARENT_PNG),
    )
    page.route(
        'https://*.basemaps.cartocdn.com/**',
        lambda route: route.fulfill(status=200, content_type='image/png', body=TRANSPARENT_PNG),
    )


def wait_ready(page):
    page.goto(BASE, wait_until='domcontentloaded', timeout=60000)
    page.wait_for_function(
        "document.querySelector('.loader')?.classList.contains('hidden')",
        timeout=60000,
    )
    page.wait_for_function(
        "window.__analysisJourneyLineage?.installed === true && window.__analysisJourneyLineage?.exactRoutes === true",
        timeout=120000,
    )
    page.wait_for_function(
        "window.__analysisJourneyCurrentKmlExact?.installed === true",
        timeout=30000,
    )
    page.wait_for_function(
        "window.__analysisJourneyExplore?.installed === true",
        timeout=30000,
    )
    page.wait_for_function(
        "['current-routes','current-gtfs-stops','final-routes-exact','final-anchors-exact','explore-final-routes','explore-final-anchors'].every(id => !!window.__analysisJourneyMap.getLayer(id))",
        timeout=30000,
    )


def activate_scene(page, name, frac=0.55):
    page.evaluate(
        """([name, frac]) => {
          const el = document.querySelector(`[data-scene="${name}"]`);
          if (!el) throw new Error(`missing scene ${name}`);
          window.scrollTo(0, el.offsetTop + el.offsetHeight * frac - innerHeight / 2);
        }""",
        [name, frac],
    )
    page.wait_for_function("name => document.body.dataset.scene === name", arg=name, timeout=15000)
    page.wait_for_timeout(900)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000}, device_scale_factor=1)
    errors, console = [], []
    prepare(page, errors, console)
    wait_ready(page)

    contract = page.evaluate(
        """() => {
          const L = window.__analysisJourneyLineage;
          const K = window.__analysisJourneyCurrentKmlExact;
          return {
            currentCount: L.currentData.features.length,
            currentRoutes: [...new Set(L.currentData.features.map(f => f.properties.route))].sort(),
            currentSource: L.currentSource,
            kmlContract: K.contract,
            kmlVariants: K.variants,
            kmlCoordinateCounts: K.coordinateCounts,
            graphReconstruction: K.graphReconstruction,
            stops: L.stopData.features.length,
            finalCount: L.finalData.features.length,
            finalIds: L.finalData.features.map(f => f.properties.route_id).sort(),
            anchors: L.anchorData.features.length,
            hasHub: L.anchorData.features.some(f => f.properties.anchor_id === 'rail:S01514'),
            continuity: L.finalData.features.map(f => ({
              id: f.properties.route_id,
              coords: f.geometry.coordinates.length,
              edges: Number(f.properties.edge_count),
            })),
            chapters: document.querySelectorAll('.chapter').length,
            hasExplore: !!document.querySelector('[data-scene="explore"]'),
          };
        }"""
    )
    assert contract['currentCount'] == 18, contract
    assert contract['currentRoutes'] == ['D184', 'D185'], contract
    assert contract['currentSource'] == 'USER_SUPPLIED_OFFICIAL_AGENCY_KML_EXACT', contract
    assert contract['kmlContract'] == 'CURRENT_SERVICE_KML_GEOMETRY_V1', contract
    assert contract['kmlVariants'] == {'D184': 7, 'D185': 11}, contract
    assert contract['kmlCoordinateCounts'] == {'D184': 2268, 'D185': 3618}, contract
    assert contract['graphReconstruction'] is False, contract
    assert contract['stops'] == 44, contract
    assert contract['finalCount'] == 4, contract
    assert set(contract['finalIds']) == FINAL_IDS, contract
    assert contract['anchors'] == 11 and contract['hasHub'], contract
    assert all(x['coords'] == x['edges'] + 1 for x in contract['continuity']), contract
    assert contract['chapters'] == 12 and contract['hasExplore'], contract

    line_offset = page.evaluate(
        "Number(window.__analysisJourneyMap.getPaintProperty('final-routes-exact','line-offset') || 0)"
    )
    assert abs(line_offset) < 1e-9, f'exact finalist geometry has screen-space offset: {line_offset}'

    activate_scene(page, 'baseline')
    assert page.locator('.route-controls.current').count() == 1
    page.locator('.route-controls.current button[data-r="D184"]').click()
    page.wait_for_timeout(100)
    current_filter = page.evaluate("window.__analysisJourneyMap.getFilter('current-routes')")
    assert 'D184' in repr(current_filter), current_filter
    stop_filter = page.evaluate("window.__analysisJourneyMap.getFilter('current-gtfs-stops')")
    assert 'D184' in repr(stop_filter), stop_filter
    d184_color = page.evaluate("window.__analysisJourneyMap.getPaintProperty('current-gtfs-stops','circle-color')")
    assert '#4ca5ff' in repr(d184_color).lower(), d184_color

    page.locator('.route-controls.current button[data-r="D185"]').click()
    page.wait_for_timeout(100)
    current_filter = page.evaluate("window.__analysisJourneyMap.getFilter('current-routes')")
    assert 'D185' in repr(current_filter), current_filter
    stop_filter = page.evaluate("window.__analysisJourneyMap.getFilter('current-gtfs-stops')")
    assert 'D185' in repr(stop_filter), stop_filter
    d185_color = page.evaluate("window.__analysisJourneyMap.getPaintProperty('current-gtfs-stops','circle-color')")
    assert '#ff9b61' in repr(d185_color).lower(), d185_color
    page.screenshot(path=str(OUT / 'exact-baseline.png'), full_page=False)

    activate_scene(page, 'finalists', 0.58)
    assert page.locator('.route-controls.final').count() == 1
    for route_id in sorted(FINAL_IDS):
        page.locator(f'.route-controls.final button[data-f="{route_id}"]').click()
        page.wait_for_timeout(80)
        filt = page.evaluate("window.__analysisJourneyMap.getFilter('final-routes-exact')")
        assert route_id in repr(filt), (route_id, filt)
    page.locator('.route-controls.final button[data-f="ALL"]').click()
    page.screenshot(path=str(OUT / 'exact-finalists.png'), full_page=False)

    # The last chapter is first a cinematic preview. The free map is entered
    # explicitly, so scroll narrative and direct map interaction never fight.
    activate_scene(page, 'explore', 0.52)
    assert page.locator('[data-explore-enter]').count() == 1
    assert page.locator('.explore-controls').count() == 1
    compatibility_state = page.evaluate("window.__analysisJourneyExplore.state")
    assert compatibility_state == {'proposals': True, 'current': False, 'stops': True}, compatibility_state
    full_state = page.evaluate("window.__analysisJourneyExplore.layers")
    assert set(full_state) == EXPLORE_LAYERS, full_state
    assert full_state['proposals'] is True and full_state['stops'] is True and full_state['current'] is False, full_state
    assert page.evaluate("window.__analysisJourneyExplore.isActive()") is False

    final_opacity = page.evaluate("window.__analysisJourneyMap.getPaintProperty('explore-final-routes','line-opacity')")
    current_opacity = page.evaluate("window.__analysisJourneyMap.getPaintProperty('explore-current-routes','line-opacity')")
    anchor_opacity = page.evaluate("window.__analysisJourneyMap.getPaintProperty('explore-final-anchors','circle-opacity')")
    assert float(final_opacity) > 0.9 and float(anchor_opacity) > 0.9, (final_opacity, anchor_opacity)
    assert float(current_opacity) == 0, current_opacity

    page.locator('[data-explore-enter]').click()
    page.wait_for_function("window.__analysisJourneyExplore.isActive() === true", timeout=5000)
    page.wait_for_function("document.body.classList.contains('is-map-exploring')", timeout=5000)
    assert page.evaluate("document.documentElement.classList.contains('is-map-exploring')") is True

    # Current KML lines and GTFS stops are independently toggleable in free mode.
    page.locator('.explore-controls button[data-layer="current"]').click()
    page.wait_for_timeout(160)
    current_opacity = page.evaluate("window.__analysisJourneyMap.getPaintProperty('explore-current-routes','line-opacity')")
    current_stop_opacity = page.evaluate("window.__analysisJourneyMap.getPaintProperty('explore-current-stops','circle-opacity')")
    assert float(current_opacity) > 0.5 and float(current_stop_opacity) > 0.9, (current_opacity, current_stop_opacity)

    # Every analytical representation shown in the scroll is available here.
    for key, layer_id, paint in [
        ('worldpop', 'worldpop-columns', 'fill-extrusion-opacity'),
        ('sections', 'sections-fill', 'fill-extrusion-opacity'),
        ('buildings', 'buildings-extrude', 'fill-extrusion-opacity'),
        ('walk', 'piece-halo', 'circle-opacity'),
        ('candidates', 'candidates', 'circle-opacity'),
    ]:
        page.locator(f'.explore-controls button[data-layer="{key}"]').click()
        page.wait_for_timeout(90)
        value = page.evaluate("([layer, paint]) => window.__analysisJourneyMap.getPaintProperty(layer, paint)", [layer_id, paint])
        assert float(value) > 0, (key, layer_id, value)

    page.locator('.explore-controls button[data-layer="roads"]').click()
    page.wait_for_function("!!window.__analysisJourneyMap.getLayer('road-network')", timeout=30000)
    page.wait_for_timeout(100)
    road_opacity = page.evaluate("window.__analysisJourneyMap.getPaintProperty('road-network','line-opacity')")
    assert float(road_opacity) > 0.5, road_opacity

    assert page.evaluate("window.__analysisJourneyExplore.showAnchor('P2V2S_0089')") is True
    page.wait_for_timeout(120)
    assert page.locator('.maplibregl-popup .map-card__eyebrow').count() == 1
    popup_text = page.locator('.maplibregl-popup').inner_text()
    popup_upper = popup_text.upper()
    assert 'NUOVA FERMATA CANDIDATA' in popup_upper and 'FIELD CHECK PENDING' in popup_upper, popup_text
    page.screenshot(path=str(OUT / 'exact-explore.png'), full_page=False)

    page.locator('.explore-controls [data-action="exit"]').click()
    page.wait_for_function("window.__analysisJourneyExplore.isActive() === false", timeout=5000)
    assert page.evaluate("document.body.classList.contains('is-map-exploring')") is False

    assert not errors, 'page errors: ' + ' | '.join(errors) + '\nconsole:\n' + '\n'.join(console)
    page.close()

    mobile = browser.new_page(viewport={'width': 390, 'height': 844}, device_scale_factor=1)
    mobile_errors, mobile_console = [], []
    prepare(mobile, mobile_errors, mobile_console)
    wait_ready(mobile)
    activate_scene(mobile, 'baseline')
    overflow = mobile.evaluate('document.documentElement.scrollWidth - window.innerWidth')
    assert overflow <= 2, f'mobile overflow baseline: {overflow}px'
    activate_scene(mobile, 'finalists', 0.58)
    overflow = mobile.evaluate('document.documentElement.scrollWidth - window.innerWidth')
    assert overflow <= 2, f'mobile overflow finalists: {overflow}px'
    assert mobile.locator('.route-controls.final').count() == 1
    activate_scene(mobile, 'explore', 0.52)
    overflow = mobile.evaluate('document.documentElement.scrollWidth - window.innerWidth')
    assert overflow <= 2, f'mobile overflow explore preview: {overflow}px'
    assert mobile.locator('[data-explore-enter]').count() == 1
    mobile.locator('[data-explore-enter]').click()
    mobile.wait_for_function("window.__analysisJourneyExplore.isActive() === true", timeout=5000)
    mobile.wait_for_timeout(180)
    overflow = mobile.evaluate('document.documentElement.scrollWidth - window.innerWidth')
    assert overflow <= 2, f'mobile overflow explore active: {overflow}px'
    assert mobile.locator('.explore-controls').count() == 1
    mobile.locator('.explore-controls [data-action="exit"]').click()
    mobile.wait_for_function("window.__analysisJourneyExplore.isActive() === false", timeout=5000)
    assert not mobile_errors, 'mobile page errors: ' + ' | '.join(mobile_errors) + '\nconsole:\n' + '\n'.join(mobile_console)
    mobile.close()

    browser.close()

print('journey exact KML + full click-to-explore browser smoke PASS')
