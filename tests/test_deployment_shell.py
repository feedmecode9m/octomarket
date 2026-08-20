"""18A Phase 1 — deployment shell (health + prod config). No trading logic changes."""

import os
import unittest
from unittest import mock


class TestHealthEndpoint(unittest.TestCase):
    def test_health_is_cheap_and_ok(self):
        from app import create_app

        client = create_app().test_client()
        resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["service"], "OctoMarket")
        self.assertEqual(body["version"], "17B")


class TestProductionConfigDefaults(unittest.TestCase):
    def test_production_env_disables_debug_by_default(self):
        with mock.patch.dict(
            os.environ,
            {"ENV": "production", "FLASK_DEBUG": ""},
            clear=False,
        ):
            # Remove FLASK_DEBUG so default applies
            os.environ.pop("FLASK_DEBUG", None)
            from src.utils.config import Config

            cfg = Config()
            self.assertFalse(cfg.flask.debug)

    def test_development_keeps_debug_default(self):
        with mock.patch.dict(os.environ, {"ENV": "development"}, clear=False):
            os.environ.pop("FLASK_DEBUG", None)
            from src.utils.config import Config

            cfg = Config()
            self.assertTrue(cfg.flask.debug)


class TestDataDirOverride(unittest.TestCase):
    def test_data_dir_env_overrides_default(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"DATA_DIR": tmp}):
                from src.utils.paths import get_data_dir

                self.assertEqual(get_data_dir(), Path(tmp))


if __name__ == "__main__":
    unittest.main()
