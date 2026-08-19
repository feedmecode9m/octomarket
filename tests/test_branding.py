"""Tests for OctoMarket branding and navigation."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.config.product import (
    PRODUCT_NAME,
    TAGLINE,
    VERSION,
    get_product,
    get_product_context,
)


class TestProductConfig(unittest.TestCase):
    def test_product_name(self):
        self.assertEqual(PRODUCT_NAME, "OctoMarket")

    def test_version(self):
        self.assertEqual(VERSION, "0.1.0")

    def test_tagline(self):
        self.assertEqual(TAGLINE, "Practice. Analyze. Execute. Improve.")

    def test_get_product(self):
        product = get_product()
        self.assertIn("name", product)
        self.assertIn("nav", product)
        self.assertEqual(len(product["nav"]), 6)

    def test_module_labels(self):
        ctx = get_product_context()
        self.assertEqual(ctx["module_labels"]["terminal"], "OctoMarket Terminal")
        self.assertEqual(ctx["module_labels"]["mentor"], "OctoMarket Mentor")
        self.assertEqual(ctx["module_labels"]["lab"], "OctoMarket Lab")

    def test_nav_paths(self):
        paths = {item["path"] for item in get_product()["nav"]}
        expected = {"/terminal", "/mentor", "/strategy-lab", "/replay", "/academy", "/journal"}
        self.assertEqual(paths, expected)


class TestBrandingRoutes(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.app = create_app()
        self.client = self.app.test_client()

    def test_home_page(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"OctoMarket", resp.data)

    def test_replay_page(self):
        resp = self.client.get("/replay")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"OctoMarket", resp.data)

    def test_terminal_page(self):
        resp = self.client.get("/terminal")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"OctoMarket", resp.data)

    def test_mentor_page(self):
        resp = self.client.get("/mentor")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"OctoMarket", resp.data)

    def test_lab_page(self):
        resp = self.client.get("/strategy-lab")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"OctoMarket", resp.data)

    def test_academy_page(self):
        resp = self.client.get("/academy")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"OctoMarket", resp.data)

    def test_journal_page(self):
        resp = self.client.get("/journal")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"OctoMarket", resp.data)

    def test_api_still_works(self):
        resp = self.client.get("/api/terminal/account")
        self.assertEqual(resp.status_code, 200)

    def test_tagline_on_home(self):
        resp = self.client.get("/")
        self.assertIn(b"Practice. Analyze. Execute. Improve.", resp.data)


class TestBrandingAssets(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.app = create_app()
        self.client = self.app.test_client()

    def test_logo_loads(self):
        resp = self.client.get("/static/assets/branding/logo.svg")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"svg", resp.data)

    def test_theme_css_loads(self):
        resp = self.client.get("/static/assets/branding/theme.css")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"--om-accent", resp.data)

    def test_icon_terminal_loads(self):
        resp = self.client.get("/static/assets/branding/icon-terminal.svg")
        self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
