"""Optional Playwright smoke test for terminal candlestick chart."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


@unittest.skipUnless(sync_playwright is not None, "playwright not installed")
class TestTerminalChartSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import create_app

        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.server = cls.app.test_client()
        cls.base_url = os.environ.get("OCTOMARKET_E2E_URL", "http://127.0.0.1:5050")

    def test_terminal_chart_shell_renders(self):
        """Smoke: terminal page loads chart container and timeframe controls."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(self.base_url + "/terminal", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_selector("#chartDiv", timeout=10000)
            page.wait_for_selector("#chartTimeframe", timeout=5000)
            self.assertIn("AAPL", page.locator("#chartSymbol").inner_text())
            browser.close()


if __name__ == "__main__":
    unittest.main()
