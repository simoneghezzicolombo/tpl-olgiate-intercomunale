from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8765/dietro-l-analisi/'
OUT = Path('dietro-l-analisi/qa')
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000}, device_scale_factor=1)
    page_errors = []
    page.on('pageerror', lambda exc: page_errors.append(str(exc)))

    page.goto(BASE, wait_until='domcontentloaded', timeout=60000)
    page.wait_for_function(
        "document.querySelector('.loader') && document.querySelector('.loader').classList.contains('hidden')",
        timeout=60000,
    )
    page.wait_for_function(
        "window.__analysisJourneyMap && window.__analysisJourneyMap.getLayer('buildings-extrude')",
        timeout=30000,
    )

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
        ('candidates', .68),
        ('finalists', .62),
        ('time', .58),
        ('end', .58),
    ]:
        scene(name, frac)

    assert page.locator('.representation-meter').count() == 1
    assert page.locator('.search-compression').count() == 1
    assert page.locator('.service-clock').count() == 1
    assert page.locator('.departure-strip').count() == 1
    assert page.locator('.evidence-stack').count() == 1
    assert not page_errors, 'page errors: ' + ' | '.join(page_errors)
    browser.close()

print('journey browser smoke PASS')
