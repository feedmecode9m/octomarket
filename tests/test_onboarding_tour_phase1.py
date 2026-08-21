"""UX-P1 onboarding tour — Phase 1/2 frontend safety and Terminal wiring."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
TOUR_JS = ROOT / "static" / "js" / "onboarding_tour.js"


class TestOnboardingTourPhase2(unittest.TestCase):
    def setUp(self):
        from app import create_app

        self.app = create_app()
        self.client = self.app.test_client()

    def test_terminal_loads_tour_assets_and_host_binding(self):
        html = self.client.get("/terminal").get_data(as_text=True)
        self.assertIn("/static/js/onboarding_tour.js", html)
        self.assertIn("/static/css/onboarding_tour.css", html)
        self.assertIn("OctoOnboarding.bindHost", html)
        self.assertIn("instrument_id: id", html)
        self.assertIn('id="startTourBtn"', html)

    def test_tour_js_phase2_contract(self):
        js = self.client.get("/static/js/onboarding_tour.js")
        self.assertEqual(js.status_code, 200)
        body = js.get_data(as_text=True)
        self.assertIn('data-tour-phase', body)
        self.assertIn("bindHost", body)
        self.assertIn("ensureReplayStarted", body)
        self.assertIn("instrument_id is required", body)
        self.assertIn("DEFAULT_INSTRUMENT", body)
        for state in [
            "WELCOME",
            "REPLAY_INTRO",
            "MARKET_EVENT",
            "PLAN_CREATION",
            "CONTROLS",
            "DECISION_REVIEW",
            "JOURNAL_LOOP",
            "COMPLETE",
        ]:
            self.assertIn(state, body)
        # Temporary plan fill only — no trade-plan POST in tour module
        self.assertNotIn("/api/trade-plan", body)
        self.assertNotIn("/api/orders", body)
        self.assertNotIn("/api/learning/journal", body)

    def test_tour_never_posts_empty_session_start(self):
        body = TOUR_JS.read_text(encoding="utf-8")
        self.assertNotRegex(body, r"session/start[^\n]{0,80}\{\}")
        self.assertIn("resolveInstrumentId", body)
        self.assertIn("never a silent default", body.lower())

    def test_host_binding_requires_instrument_id_field(self):
        html = self.client.get("/terminal").get_data(as_text=True)
        # Critical A1: startReplay must send instrument_id in JSON body
        self.assertRegex(
            html,
            r"session/start[\s\S]{0,280}instrument_id",
        )
        self.assertNotRegex(
            html,
            r"startReplay:[\s\S]{0,200}body:\s*JSON\.stringify\(\s*\{\s*\}\s*\)",
        )

    def test_skip_allowed_and_review_demo_cleanup_markers(self):
        body = TOUR_JS.read_text(encoding="utf-8")
        self.assertIn("data-tour-demo-open", body)
        self.assertIn("listenersBound", body)
        # skip must clear busy so Esc works mid-action
        self.assertRegex(body, r"function skip\(\)\s*\{[\s\S]*?setBusy\(false\)")

    def test_a1_session_start_still_requires_instrument(self):
        resp = self.client.post("/api/session/start", json={})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("instrument_id", (resp.get_json() or {}).get("error", "").lower())

    def test_no_backend_onboarding_routes(self):
        for path in ("/api/onboarding", "/api/tour", "/api/training"):
            resp = self.client.get(path)
            self.assertIn(resp.status_code, (404, 405, 500))

    def test_onboarding_init_decoupled_from_chart_boot(self):
        """Pre-UX-P2 gate: tour must init even if chart throws."""
        html = self.client.get("/terminal").get_data(as_text=True)
        self.assertIn("function initGuidedOnboarding", html)
        self.assertIn("initGuidedOnboarding()", html)
        self.assertIn("Chart init failed; Terminal continues without chart.", html)
        # Chart await is isolated; onboarding runs from finally
        self.assertRegex(
            html,
            r"try\s*\{\s*await initTerminalChart\(\);\s*\}\s*catch",
        )
        self.assertRegex(
            html,
            r"finally\s*\{\s*initGuidedOnboarding\(\);\s*\}",
        )

    def test_volume_scale_margins_sum_less_than_one(self):
        """Lightweight Charts rejects scaleMargins when top+bottom >= 1."""
        chart_js = (ROOT / "static" / "js" / "terminal_chart.js").read_text(encoding="utf-8")
        self.assertIn("_applyMainScaleMargins", chart_js)
        self.assertIn("scaleMargins: { top: 0.82, bottom: 0 }", chart_js)
        self.assertNotRegex(
            chart_js,
            r"priceScale\('volume'\)\.applyOptions\(\{[\s\S]*?"
            r"bottom:\s*Math\.min\(bottom",
        )


if __name__ == "__main__":
    unittest.main()
