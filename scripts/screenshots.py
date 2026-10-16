"""Screenshot every page in dark + light mode (desktop + mobile) for UI review.

Requires: pip install playwright  (uses the installed Google Chrome, no download)
Run the app first (streamlit run app.py), then: python scripts/screenshots.py
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8501"
PAGES = {"home": "", "single_ticker": "single_ticker", "portfolio": "portfolio",
         "paper_trade": "paper_trade", "about": "about"}
OUT = Path(__file__).resolve().parent.parent / "screenshots"


def settle(page, marker):
    """Wait for the page's own content (not just the shell) and for spinners to clear."""
    page.wait_for_selector(marker, timeout=180000)
    page.wait_for_function("!document.querySelector('[data-testid=\"stMain\"] [data-testid=\"stSpinner\"]')",
                           timeout=180000)
    page.wait_for_timeout(2000)


def shoot(page, path):
    """Full-content screenshot: Streamlit scrolls an inner div, so grow the viewport to fit it."""
    vp = page.viewport_size
    h = page.evaluate("document.querySelector('[data-testid=\"stMain\"]').scrollHeight")
    page.set_viewport_size({"width": vp["width"], "height": max(vp["height"], h + 80)})
    page.wait_for_timeout(600)
    page.screenshot(path=path)
    page.set_viewport_size(vp)


def main():
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        for theme in ("dark", "light"):
            for size, vp in (("desktop", (1440, 900)), ("mobile", (390, 844))):
                ctx = browser.new_context(viewport={"width": vp[0], "height": vp[1]}, device_scale_factor=1)
                page = ctx.new_page()
                for name, path in PAGES.items():
                    if size == "mobile" and name not in ("home", "single_ticker"):
                        continue
                    page.goto(f"{BASE}/{path}?theme={theme}")
                    settle(page, ".hero" if name == "home" else ".page-head")
                    shoot(page, str(OUT / f"{name}_{theme}_{size}.png"))
                    if name == "single_ticker" and size == "desktop":
                        page.get_by_role("button", name="Run backtest").click()
                        page.wait_for_selector('[data-testid="stPlotlyChart"]', timeout=180000)
                        page.wait_for_timeout(3500)
                        shoot(page, str(OUT / f"single_ticker_results_{theme}_{size}.png"))
                    if name == "home" and size == "mobile":
                        ctl = page.locator('[data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapsedControl"] button').first
                        if ctl.count():
                            ctl.click(); page.wait_for_timeout(1200)
                            page.screenshot(path=str(OUT / f"home_navmenu_{theme}_mobile.png"))
                            page.keyboard.press("Escape"); page.goto(f"{BASE}/?theme={theme}"); settle(page, ".hero")
                    print("shot", name, theme, size)
                ctx.close()
        browser.close()


if __name__ == "__main__":
    main()
