"""Screenshots of every page as on a phone (run in CI, where Streamlit can be installed).

    streamlit run app.py --server.headless true &
    python tools/mobile_audit.py http://localhost:8501 shots/
"""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL, OUT = sys.argv[1], Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
PAGES = ['La tua settimana', 'Matchday', 'Convocati', 'Full Time', 'Classifica', 'Calendario',
         'Video con transizioni', 'Didascalie', 'Wrapped', 'Squadra e copertine']
TABS = ['Stile', 'Esporta']


def settle(page, seconds=6):
    time.sleep(1)
    for _ in range(int(seconds*2)):
        if page.locator('[data-testid="stStatusWidget"]').count() == 0:
            break
        time.sleep(.5)
    time.sleep(1.5)


def shot(page, name, tall=True):
    """The whole page: the viewport is made very tall (Streamlit scrolls inside its own container)."""
    page.screenshot(path=str(OUT/f'{name}_schermo.png'))
    if tall:
        height = page.evaluate("""() => {
            const m = document.querySelector('[data-testid="stMain"]') || document.querySelector('section.main');
            return m ? m.scrollHeight : document.body.scrollHeight }""")
        page.set_viewport_size({'width': 390, 'height': min(16000, int(height)+60)})
        time.sleep(2)
        page.screenshot(path=str(OUT/f'{name}.png'))
        page.set_viewport_size({'width': 390, 'height': 664})
        time.sleep(1)
    print('shot', name, flush=True)


with sync_playwright() as p:
    browser = p.chromium.launch()
    phone = p.devices['iPhone 13']
    context = browser.new_context(**phone, locale='it-IT')
    page = context.new_page()
    page.set_default_timeout(20000)
    page.goto(URL)
    page.wait_for_selector('h1', timeout=120000)
    settle(page, 20)
    skip = page.get_by_text('Continua senza archivio')
    if skip.count() and skip.first.is_visible():
        skip.first.click()
        settle(page, 10)
    shot(page, '00_apertura')
    # The phone menu at the top (3.6): try it once.
    menu = page.locator('.st-key-mobile_nav')
    print('menu in alto visibile:', menu.count() and menu.first.is_visible(), flush=True)
    for i, name in enumerate(PAGES):
        try:
            opener = page.locator('[data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapsedControl"] button')
            if opener.count():
                opener.first.click()
                time.sleep(1)
            if i == 0:
                shot(page, '01_menu_aperto', tall=False)
            page.locator('[data-testid="stSidebar"]').get_by_text(name, exact=False).first.click()
            settle(page, 25)
            closer = page.locator('[data-testid="stSidebarCollapseButton"] button, [data-testid="stSidebar"] button[kind="headerNoPadding"]')
            if closer.count() and closer.first.is_visible():
                closer.first.click()
                time.sleep(1)
            shot(page, f'{i+2:02d}_{name.replace(" ", "_")}')
            if name in ('Matchday', 'Full Time', 'Classifica'):
                for tab in TABS:
                    tabs = page.get_by_role('tab').filter(has_text=tab)
                    if tabs.count():
                        tabs.first.click()
                        settle(page, 15)
                        shot(page, f'{i+2:02d}_{name.replace(" ", "_")}_{tab}')
                        if tab == 'Stile':   # scrolled: the phone preview must still be at the top
                            page.evaluate("""() => { const m = document.querySelector('[data-testid="stMain"]');
                                if (m) m.scrollTop = 1400; else window.scrollTo(0, 1400) }""")
                            time.sleep(1.5)
                            page.screenshot(path=str(OUT/f'{i+2:02d}_{name.replace(" ", "_")}_scorrendo.png'))
                            page.evaluate("""() => { const m = document.querySelector('[data-testid="stMain"]');
                                if (m) m.scrollTop = 0; else window.scrollTo(0, 0) }""")
        except Exception as exc:     # keep going: a broken page is itself a finding
            print('ERRORE', name, exc, flush=True)
            shot(page, f'{i+2:02d}_{name.replace(" ", "_")}_errore')
    browser.close()
