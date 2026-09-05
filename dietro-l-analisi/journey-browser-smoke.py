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
    'tile.openstreetmap.org',
    'fonts.googleapis.com',
    'fonts.gstatic.com',
}


def prepare_page(page, page_errors, console_log, failed_requests, requested_urls):
    page.on('pageerror', lambda exc: page_errors.append(str(exc)))
    page.on('console', lambda msg: console_log.append(f'{msg.type}: {msg.text}'))
    page.on('request', lambda req: requested_urls.append(req.url))
    page.on('requestfailed', lambda req: failed_requests.append(f'{req.method} {req.url} :: {req.failure}'))
    page.route(
        'https://tile.openstreetmap.org/**',
        lambda route: route.fulfill(status=200, content_type='image/png', body=TRANSPARENT_PNG),
    )
    page.route('https://raw.githubusercontent.com/**', lambda route: route.abort())
    page.route('https://cdn.jsdelivr.net/**', lambda route: route.abort())


def wait_ready(page, page_errors, console_log, failed_requests):
    try:
        page.goto(BASE, wait_until='domcontentloaded', timeout=60000)
        page.wait_for_function(
            "document.querySelector('.loader') && document.querySelector('.loader').classList.contains('hidden')",
            timeout=60000,
        )
        page.wait_for_function(
            "window.__analysisJourneyMap && window.__analysisJourneyMap.getLayer('buildings-extrude')",
            timeout=30000,
        )
        page.wait_for_function(
            "document.querySelector('.departure-strip') && window.__analysisJourneyMap.getLayer('service-movers') && window.__analysisJourneyMap.getLayer('dasymetric-sparks')",
            timeout=120000,
        )
        page.wait_for_function(
            "window.__analysisJourneyLens && document.querySelector('.analysis-lens') && document.querySelector('.depth-stack') && ['worldpop-stack','sections-stack','buildings-stack'].every(id => window.__analysisJourneyMap.getLayer(id))",
            timeout=120000,
        )
        page.wait_for_function(
            "window.__analysisJourneyLineage && ['lineage-16-fig','lineage-16-two','lineage-185-fig','lineage-185-two'].every(id => window.__analysisJourneyMap.getLayer(id))",
            timeout=120000,
        )
    except Exception as exc:
        state = page.evaluate(
            """() => ({
              readyState: document.readyState,
              loaderClass: document.querySelector('.loader')?.className || null,
              loaderText: document.querySelector('.loader p')?.textContent || null,
              hasMapLibre: !!window.maplibregl,
              hasGsap: !!window.gsap,
              hasScrollTrigger: !!window.ScrollTrigger,
              hasPako: !!window.pako,
              hasJourneyData: !!window.ANALYSIS_JOURNEY_DATA,
              hasGeoData: !!window.TRA_PAESI_GEO,
              hasMap: !!window.__analysisJourneyMap,
              styleLoaded: !!window.__analysisJourneyMap?.isStyleLoaded?.(),
              motion: document.documentElement.dataset.journeyMotion || null,
              hasDirectorStrip: !!document.querySelector('.departure-strip'),
              hasServiceMovers: !!window.__analysisJourneyMap?.getLayer?.('service-movers'),
              hasDasymetricSparks: !!window.__analysisJourneyMap?.getLayer?.('dasymetric-sparks'),
              hasRoadNetwork: !!window.__analysisJourneyMap?.getLayer?.('road-network'),
              hasLens: !!window.__analysisJourneyLens,
              hasLineage: !!window.__analysisJourneyLineage,
              hasDepthStack: !!document.querySelector('.depth-stack'),
              stackLayers: ['worldpop-stack','sections-stack','buildings-stack'].map(id => [id, !!window.__analysisJourneyMap?.getLayer?.(id)]),
              lineageLayers: ['lineage-16-fig','lineage-16-two','lineage-185-fig','lineage-185-two'].map(id => [id, !!window.__analysisJourneyMap?.getLayer?.(id)]),
              roadFallback: document.body.classList.contains('road-fallback'),
              localAssets: window.ANALYSIS_JOURNEY_DATA?.meta?.localAssets || null,
              mapLayers: window.__analysisJourneyMap?.getStyle?.()?.layers?.map(x => x.id) || []
            })"""
        )
        diagnostic = [
            f'EXCEPTION: {exc}', '', 'RUNTIME STATE:', repr(state), '',
            'PAGE ERRORS:', *page_errors, '',
            'FAILED REQUESTS:', *failed_requests, '',
            'CONSOLE:', *console_log,
        ]
        text = '\n'.join(diagnostic)
        print(text)
        (OUT / 'runtime-diagnostic.txt').write_text(text, encoding='utf-8')
        page.screenshot(path=str(OUT / 'runtime-failure.png'), full_page=False)
        raise


def scene(page, name, frac=.5, prefix=''):
    page.evaluate(
        """([name,frac]) => {
          const el=document.querySelector(`[data-scene="${name}"]`);
          window.scrollTo(0, el.offsetTop + el.offsetHeight*frac - innerHeight/2);
        }""",
        [name, frac],
    )
    page.wait_for_timeout(1800)
    actual = page.evaluate("document.body.dataset.scene")
    assert actual == name, f'scene {name} did not activate, got {actual}'
    page.screenshot(path=str(OUT / f'{prefix}{name}.png'), full_page=False)


def assert_runtime_network_contract(urls, label):
    assert not any('raw.githubusercontent.com' in url for url in urls), f'runtime GitHub Raw request detected in {label}'
    assert not any('cdn.jsdelivr.net' in url for url in urls), f'runtime jsDelivr request detected in {label}'
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

    page = browser.new_page(viewport={'width': 1440, 'height': 1000}, device_scale_factor=1)
    page_errors, console_log, failed_requests, requested_urls = [], [], [], []
    prepare_page(page, page_errors, console_log, failed_requests, requested_urls)
    wait_ready(page, page_errors, console_log, failed_requests)

    layers = page.evaluate(
        """() => ['worldpop-columns','sections-fill','buildings-extrude','piece-halo','candidates','final16','final185','service-movers','dasymetric-sparks','worldpop-stack','sections-stack','buildings-stack','lineage-16-fig','lineage-16-two','lineage-185-fig','lineage-185-two'].every(id => !!window.__analysisJourneyMap.getLayer(id))"""
    )
    assert layers, 'core, cinematic, exploded-stack or lineage layers missing'

    for name, frac in [
        ('grid', .55), ('sections', .55), ('buildings', .58), ('walk', .62),
        ('roads', .55), ('baseline', .55), ('candidates', .53),
        ('finalists', .58), ('time', .58), ('end', .58),
    ]:
        scene(page, name, frac)

    scene(page, 'sections', .62, prefix='stack-')
    stack_opacity = page.evaluate(
        """() => ['worldpop-stack','sections-stack','buildings-stack'].map(id => Number(window.__analysisJourneyMap.getPaintProperty(id,'fill-extrusion-opacity') || 0))"""
    )
    assert max(stack_opacity) > .15, f'exploded stack never became visible: {stack_opacity}'
    assert page.locator('.depth-stack').count() == 1

    scene(page, 'buildings', .58, prefix='inspect-')
    building_props = page.evaluate(
        """() => window.__analysisJourneyMap.querySourceFeatures('buildings')[0]?.properties || null"""
    )
    assert building_props, 'no real building feature available for inspection QA'
    page.evaluate("p => window.__analysisJourneyLens.inspect('building', p, {x:720,y:360})", building_props)
    page.wait_for_timeout(150)
    assert page.locator('.analysis-lens.is-visible').count() == 1
    lens_text = page.locator('.analysis-lens').inner_text().lower()
    assert 'residenti modellati' in lens_text and 'dato anagrafico' in lens_text, lens_text
    page.screenshot(path=str(OUT / 'inspection-building.png'), full_page=False)
    page.evaluate("window.__analysisJourneyLens.hide()")

    # Four lineage are intentionally offset only in screen space so identical
    # public geometries can be seen, then collapse back to the same routes.
    scene(page, 'finalists', .5, prefix='lineage-')
    page.evaluate("window.__analysisJourneyLineage.apply(0)")
    offsets_start = page.evaluate(
        """() => ['lineage-16-fig','lineage-16-two','lineage-185-fig','lineage-185-two'].map(id => Number(window.__analysisJourneyMap.getPaintProperty(id,'line-offset') || 0))"""
    )
    assert min(offsets_start) <= -9 and max(offsets_start) >= 9, offsets_start
    assert 'offset solo grafico' in page.locator('.lineage-collapse__caption').inner_text().lower()
    page.screenshot(path=str(OUT / 'lineage-separated.png'), full_page=False)
    page.evaluate("window.__analysisJourneyLineage.apply(1)")
    offsets_end = page.evaluate(
        """() => ['lineage-16-fig','lineage-16-two','lineage-185-fig','lineage-185-two'].map(id => Number(window.__analysisJourneyMap.getPaintProperty(id,'line-offset') || 0))"""
    )
    assert max(abs(v) for v in offsets_end) < .01, offsets_end
    assert page.evaluate("document.body.dataset.lineageCollapse") == 'merged'
    page.screenshot(path=str(OUT / 'lineage-collapsed.png'), full_page=False)

    assert page.evaluate("!!window.__analysisJourneyMap.getLayer('road-network')"), 'local Gate D road layer missing'
    assert not page.evaluate("document.body.classList.contains('road-fallback')"), 'Gate D road layer fell back'
    assert page.locator('.representation-meter').count() == 1
    assert page.locator('.search-compression').count() == 1
    assert page.locator('.service-clock').count() == 1
    assert page.locator('.departure-strip').count() == 1
    assert page.locator('.evidence-stack').count() == 1
    assert page.evaluate("document.documentElement.dataset.journeyMotion") == 'full'
    assert not any('basemaps.cartocdn.com' in url for url in requested_urls), 'legacy CARTO basemap request detected'
    assert_runtime_network_contract(requested_urls, 'desktop pass')
    assert not page_errors, 'desktop page errors: ' + ' | '.join(page_errors)
    page.close()

    mobile = browser.new_page(viewport={'width': 390, 'height': 844}, device_scale_factor=1)
    mobile_errors, mobile_console, mobile_failed, mobile_urls = [], [], [], []
    prepare_page(mobile, mobile_errors, mobile_console, mobile_failed, mobile_urls)
    wait_ready(mobile, mobile_errors, mobile_console, mobile_failed)
    for name, frac in [('grid', .55), ('walk', .62), ('candidates', .53), ('time', .58), ('end', .58)]:
        scene(mobile, name, frac, prefix='mobile-')
        overflow = mobile.evaluate('document.documentElement.scrollWidth - window.innerWidth')
        assert overflow <= 2, f'mobile horizontal overflow in {name}: {overflow}px'
    assert mobile.locator('.topbar').count() == 1
    assert mobile.locator('.chapter-rail').count() == 1
    assert mobile.locator('.analysis-lens').count() == 1
    assert not mobile_errors, 'mobile page errors: ' + ' | '.join(mobile_errors)
    assert not any('basemaps.cartocdn.com' in url for url in mobile_urls), 'legacy CARTO basemap request detected on mobile'
    assert_runtime_network_contract(mobile_urls, 'mobile pass')
    mobile.close()

    reduced_context = browser.new_context(
        viewport={'width': 1280, 'height': 900},
        reduced_motion='reduce',
        device_scale_factor=1,
    )
    reduced = reduced_context.new_page()
    reduced_errors, reduced_console, reduced_failed, reduced_urls = [], [], [], []
    prepare_page(reduced, reduced_errors, reduced_console, reduced_failed, reduced_urls)
    wait_ready(reduced, reduced_errors, reduced_console, reduced_failed)
    assert reduced.evaluate("document.documentElement.dataset.journeyMotion") == 'reduced'
    assert reduced.evaluate("window.__analysisJourneyReduceMotion === true")
    assert reduced.evaluate("window.__analysisJourneyLens.reducedMotion === true")
    assert reduced.evaluate("window.__analysisJourneyLineage.reducedMotion === true")
    scene(reduced, 'time', .58, prefix='reduced-')
    clock_before = reduced.locator('.service-clock__minute b').inner_text()
    reduced.wait_for_timeout(700)
    clock_after = reduced.locator('.service-clock__minute b').inner_text()
    assert clock_before == clock_after, f'reduced-motion service clock advanced: {clock_before} -> {clock_after}'
    reduced.evaluate(
        "window.__analysisJourneyMap.easeTo({center:[9.41,45.73],zoom:12,duration:5000,essential:true})"
    )
    reduced.wait_for_timeout(80)
    assert reduced.evaluate("window.__analysisJourneyMap.isEasing ? !window.__analysisJourneyMap.isEasing() : true"), 'reduced-motion camera is still easing'
    rendered_movers = reduced.evaluate(
        "window.__analysisJourneyMap.queryRenderedFeatures({layers:['service-movers']}).length"
    )
    assert rendered_movers == 0, f'reduced-motion service movers still rendered: {rendered_movers}'
    reduced_stack = reduced.evaluate(
        """() => ['worldpop-stack','sections-stack','buildings-stack'].map(id => Number(window.__analysisJourneyMap.getPaintProperty(id,'fill-extrusion-opacity') || 0))"""
    )
    assert max(reduced_stack) == 0, f'reduced-motion exploded stack animated: {reduced_stack}'
    assert_runtime_network_contract(reduced_urls, 'reduced-motion pass')
    assert not reduced_errors, 'reduced-motion page errors: ' + ' | '.join(reduced_errors)
    reduced_context.close()

    browser.close()

print('journey source-closed + exploded-stack + inspection-lens + lineage-collapse browser smoke PASS')
