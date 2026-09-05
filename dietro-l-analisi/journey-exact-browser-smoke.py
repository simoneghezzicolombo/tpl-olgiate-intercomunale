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
        "['current-routes','current-gtfs-stops','final-routes-exact','final-anchors-exact'].every(id => !!window.__analysisJourneyMap.getLayer(id))",
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
          return {
            currentCount: L.currentData.features.length,
            currentRoutes: [...new Set(L.currentData.features.map(f => f.properties.route))].sort(),
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
          };
        }"""
    )
    assert contract['currentCount'] == 18, contract
    assert contract['currentRoutes'] == ['D184', 'D185'], contract
    assert contract['stops'] == 44, contract
    assert contract['finalCount'] == 4, contract
    assert set(contract['finalIds']) == FINAL_IDS, contract
    assert contract['anchors'] == 11 and contract['hasHub'], contract
    assert all(x['coords'] == x['edges'] + 1 for x in contract['continuity']), contract

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
    assert not mobile_errors, 'mobile page errors: ' + ' | '.join(mobile_errors) + '\nconsole:\n' + '\n'.join(mobile_console)
    mobile.close()

    browser.close()

print('journey exact route lineage browser smoke PASS')
