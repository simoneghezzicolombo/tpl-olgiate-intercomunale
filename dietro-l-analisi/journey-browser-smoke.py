from base64 import b64decode
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8765/dietro-l-analisi/'
OUT = Path('dietro-l-analisi/qa')
OUT.mkdir(parents=True, exist_ok=True)
TRANSPARENT_PNG = b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000}, device_scale_factor=1)
    page_errors = []
    console_log = []
    failed_requests = []
    requested_urls = []
    page.on('pageerror', lambda exc: page_errors.append(str(exc)))
    page.on('console', lambda msg: console_log.append(f'{msg.type}: {msg.text}'))
    page.on('request', lambda req: requested_urls.append(req.url))
    page.on('requestfailed', lambda req: failed_requests.append(f'{req.method} {req.url} :: {req.failure}'))

    # CI must not consume community OSM raster capacity. Human visitors can use
    # the contextual basemap normally; the visual test receives a local blank
    # tile and therefore evaluates only the evidence-driven journey layers.
    page.route(
        'https://tile.openstreetmap.org/**',
        lambda route: route.fulfill(status=200, content_type='image/png', body=TRANSPARENT_PNG),
    )

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
              mapLayers: window.__analysisJourneyMap?.getStyle?.()?.layers?.map(x => x.id) || [],
              scripts: [...document.scripts].map(s => ({src:s.src, loaded:!!s.src}))
            })"""
        )
        diagnostic = [
            f'EXCEPTION: {exc}',
            '',
            'RUNTIME STATE:',
            repr(state),
            '',
            'PAGE ERRORS:',
            *page_errors,
            '',
            'FAILED REQUESTS:',
            *failed_requests,
            '',
            'CONSOLE:',
            *console_log,
        ]
        text = '\n'.join(diagnostic)
        print(text)
        (OUT / 'runtime-diagnostic.txt').write_text(text, encoding='utf-8')
        page.screenshot(path=str(OUT / 'runtime-failure.png'), full_page=False)
        browser.close()
        raise

    layers = page.evaluate(
        """() => ['worldpop-columns','sections-fill','buildings-extrude','piece-halo','candidates','final16','final185'].every(id => !!window.__analysisJourneyMap.getLayer(id))"""
    )
    assert layers, 'core MapLibre layers missing'

    def scene(name, frac=.5):
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
        page.screenshot(path=str(OUT / f'{name}.png'), full_page=False)

    for name, frac in [
        ('grid', .55),
        ('sections', .55),
        ('buildings', .58),
        ('walk', .62),
        ('roads', .55),
        ('baseline', .55),
        ('candidates', .53),
        ('finalists', .58),
        ('time', .58),
        ('end', .58),
    ]:
        scene(name, frac)

    assert page.locator('.representation-meter').count() == 1
    assert page.locator('.search-compression').count() == 1
    assert page.locator('.service-clock').count() == 1
    assert page.locator('.departure-strip').count() == 1
    assert page.locator('.evidence-stack').count() == 1
    assert not any('basemaps.cartocdn.com' in url for url in requested_urls), 'legacy CARTO basemap request detected'
    assert not page_errors, 'page errors: ' + ' | '.join(page_errors)
    browser.close()

print('journey browser smoke PASS')
