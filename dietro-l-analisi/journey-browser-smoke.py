from base64 import b64decode
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8765/dietro-l-analisi/'
OUT = Path('dietro-l-analisi/qa')
OUT.mkdir(parents=True, exist_ok=True)
TRANSPARENT_PNG = b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
)
ALLOWED_EXTERNAL_HOSTS = {
    'tile.openstreetmap.org', 'fonts.googleapis.com', 'fonts.gstatic.com'
}


def prepare(page, errors, console, failed, urls):
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.on('console', lambda msg: console.append(f'{msg.type}: {msg.text}'))
    page.on('request', lambda req: urls.append(req.url))
    page.on('requestfailed', lambda req: failed.append(f'{req.method} {req.url} :: {req.failure}'))
    page.route(
        'https://tile.openstreetmap.org/**',
        lambda route: route.fulfill(status=200, content_type='image/png', body=TRANSPARENT_PNG),
    )
    page.route('https://raw.githubusercontent.com/**', lambda route: route.abort())
    page.route('https://cdn.jsdelivr.net/**', lambda route: route.abort())


def ready(page):
    page.goto(BASE, wait_until='domcontentloaded', timeout=60000)
    page.wait_for_function("document.querySelector('.loader')?.classList.contains('hidden')", timeout=60000)
    page.wait_for_function("window.__analysisJourneyMap?.getLayer('buildings-extrude')", timeout=30000)
    page.wait_for_function(
        "document.querySelector('.departure-strip') && window.__analysisJourneyMap.getLayer('service-movers') && window.__analysisJourneyMap.getLayer('dasymetric-sparks')",
        timeout=60000,
    )
    page.wait_for_function("window.__analysisJourneyLens && document.querySelector('.depth-stack')", timeout=60000)
    page.wait_for_function(
        "window.__analysisJourneyLineage?.installed === true && window.__analysisJourneyLineage?.exactRoutes === true",
        timeout=60000,
    )
    page.wait_for_function("window.__analysisJourneyCurrentKmlExact?.installed === true", timeout=30000)
    page.wait_for_function("window.__analysisJourneyExplore?.installed === true", timeout=30000)


def scene(page, name, frac=.55, prefix=''):
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
    page.screenshot(path=str(OUT / f'{prefix}{name}.png'), full_page=False)


def assert_network(urls, label):
    assert not any('raw.githubusercontent.com' in u for u in urls), f'GitHub Raw request in {label}'
    assert not any('cdn.jsdelivr.net' in u for u in urls), f'jsDelivr request in {label}'
    unexpected = set()
    for url in urls:
        parsed = urlparse(url)
        if parsed.scheme not in {'http', 'https'}:
            continue
        host = parsed.hostname
        if host in {'127.0.0.1', 'localhost'} or host in ALLOWED_EXTERNAL_HOSTS:
            continue
        unexpected.add(host or url)
    assert not unexpected, f'unexpected external runtime hosts in {label}: {sorted(unexpected)}'


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors, console, failed, urls = [], [], [], []
    prepare(page, errors, console, failed, urls)
    ready(page)

    core = page.evaluate("""() => ({
      layers: [
        'worldpop-columns','sections-fill','buildings-extrude','piece-halo','candidates',
        'service-movers','dasymetric-sparks','worldpop-stack','sections-stack','buildings-stack',
        'final-routes-exact','final-anchors-exact','explore-final-routes','explore-final-anchors'
      ].every(id => !!window.__analysisJourneyMap.getLayer(id)),
      kml: window.__analysisJourneyCurrentKmlExact,
      currentSource: window.__analysisJourneyLineage.currentSource,
      exploreKeys: Object.keys(window.__analysisJourneyExplore.layers).sort(),
      chapters: document.querySelectorAll('.chapter').length,
    })""")
    assert core['layers'], core
    assert core['kml']['variants'] == {'D184': 7, 'D185': 11}, core
    assert core['kml']['coordinateCounts'] == {'D184': 2268, 'D185': 3618}, core
    assert core['kml']['graphReconstruction'] is False, core
    assert core['currentSource'] == 'USER_SUPPLIED_AGENCY_KML_LINESTRINGS_EXACT', core
    assert core['chapters'] == 12, core
    assert core['exploreKeys'] == sorted([
        'worldpop','sections','buildings','walk','roads','candidates','current','proposals','stops'
    ]), core

    # Exercise the complete cinematic narrative before handing control to the map.
    for name, frac in [
        ('grid', .55), ('sections', .55), ('buildings', .58), ('walk', .62),
        ('roads', .55), ('baseline', .55), ('candidates', .53),
        ('finalists', .58), ('time', .58), ('end', .58), ('explore', .52),
    ]:
        scene(page, name, frac)

    # Gate D road graph remains local and loads when the narrative reaches roads.
    page.evaluate("window.__analysisJourneyExplore.ensureRoadGraph()")
    page.wait_for_function("!!window.__analysisJourneyMap.getLayer('road-network')", timeout=30000)
    assert not page.evaluate("document.body.classList.contains('road-fallback')")

    # Exploded representations from the scroll still render.
    scene(page, 'sections', .62, prefix='stack-')
    stack = page.evaluate(
        "['worldpop-stack','sections-stack','buildings-stack'].map(id => Number(window.__analysisJourneyMap.getPaintProperty(id,'fill-extrusion-opacity') || 0))"
    )
    assert max(stack) > .15, stack

    # Existing inspection lens still explains the dasymetric building representation.
    scene(page, 'buildings', .58, prefix='inspect-')
    props = page.evaluate("window.__analysisJourneyMap.querySourceFeatures('buildings')[0]?.properties || null")
    assert props, 'no building feature available for inspection'
    page.evaluate("p => window.__analysisJourneyLens.inspect('building', p, {x:720,y:360})", props)
    page.wait_for_timeout(120)
    lens = page.locator('.analysis-lens').inner_text().lower()
    assert 'residenti modellati' in lens and 'dato anagrafico' in lens, lens
    page.evaluate("window.__analysisJourneyLens.hide()")

    # Exact finalist geometry never receives a screen-space offset.
    exact_offset = page.evaluate("Number(window.__analysisJourneyMap.getPaintProperty('final-routes-exact','line-offset') || 0)")
    assert abs(exact_offset) < 1e-9, exact_offset

    # Explore is a preview until the user explicitly enters free-map mode.
    scene(page, 'explore', .52, prefix='preview-')
    assert page.locator('[data-explore-enter]').count() == 1
    assert page.evaluate("window.__analysisJourneyExplore.isActive()") is False
    page.locator('[data-explore-enter]').click()
    page.wait_for_function("window.__analysisJourneyExplore.isActive() === true", timeout=5000)
    assert page.evaluate("document.body.classList.contains('is-map-exploring')")
    page.locator('.explore-controls [data-action="exit"]').click()
    page.wait_for_function("window.__analysisJourneyExplore.isActive() === false", timeout=5000)

    assert page.locator('.representation-meter').count() == 1
    assert page.locator('.search-compression').count() == 1
    assert page.locator('.service-clock').count() == 1
    assert page.locator('.departure-strip').count() == 1
    assert page.locator('.evidence-stack').count() == 1
    assert page.evaluate("document.documentElement.dataset.journeyMotion") == 'full'
    assert_network(urls, 'desktop')
    assert not errors, 'desktop errors: ' + ' | '.join(errors) + '\nconsole:\n' + '\n'.join(console)
    page.close()

    mobile = browser.new_page(viewport={'width': 390, 'height': 844})
    m_errors, m_console, m_failed, m_urls = [], [], [], []
    prepare(mobile, m_errors, m_console, m_failed, m_urls)
    ready(mobile)
    for name, frac in [('grid', .55), ('walk', .62), ('candidates', .53), ('time', .58), ('end', .58), ('explore', .52)]:
        scene(mobile, name, frac, prefix='mobile-')
        overflow = mobile.evaluate('document.documentElement.scrollWidth - window.innerWidth')
        assert overflow <= 2, f'mobile overflow in {name}: {overflow}px'
    mobile.locator('[data-explore-enter]').click()
    mobile.wait_for_function("window.__analysisJourneyExplore.isActive() === true", timeout=5000)
    assert mobile.evaluate('document.documentElement.scrollWidth - window.innerWidth') <= 2
    mobile.locator('.explore-controls [data-action="exit"]').click()
    assert_network(m_urls, 'mobile')
    assert not m_errors, 'mobile errors: ' + ' | '.join(m_errors)
    mobile.close()

    reduced_context = browser.new_context(viewport={'width': 1280, 'height': 900}, reduced_motion='reduce')
    reduced = reduced_context.new_page()
    r_errors, r_console, r_failed, r_urls = [], [], [], []
    prepare(reduced, r_errors, r_console, r_failed, r_urls)
    ready(reduced)
    assert reduced.evaluate("document.documentElement.dataset.journeyMotion") == 'reduced'
    assert reduced.evaluate("window.__analysisJourneyReduceMotion === true")
    scene(reduced, 'time', .58, prefix='reduced-')
    before = reduced.locator('.service-clock__minute b').inner_text()
    reduced.wait_for_timeout(650)
    after = reduced.locator('.service-clock__minute b').inner_text()
    assert before == after, f'reduced-motion clock advanced: {before} -> {after}'
    assert_network(r_urls, 'reduced motion')
    assert not r_errors, 'reduced errors: ' + ' | '.join(r_errors)
    reduced_context.close()

    browser.close()

print('journey source-closed + exact lineage + full exploration browser smoke PASS')
