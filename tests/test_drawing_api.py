"""Tests for chart drawing API and terminal integration."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestDrawingAPI(unittest.TestCase):
    def setUp(self):
        from app import create_app
        from src.charting.chart_state import get_chart_state
        from src.charting.drawing_store import get_drawing_store

        self.app = create_app()
        self.client = self.app.test_client()
        get_chart_state().reset()
        get_drawing_store().reset()

    def test_get_drawings_empty(self):
        resp = self.client.get("/api/chart/AAPL/drawings")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), [])

    def test_post_horizontal_drawing(self):
        resp = self.client.post(
            "/api/chart/AAPL/drawings",
            json={"type": "horizontal", "price": 182.5, "label": "Resistance", "color": "red"},
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertIn("drawing", data)
        self.assertEqual(data["drawing"]["price"], 182.5)
        self.assertIn("id", data["drawing"])

    def test_get_drawings_after_create(self):
        self.client.post("/api/chart/AAPL/drawings", json={"type": "horizontal", "price": 180})
        resp = self.client.get("/api/chart/AAPL/drawings")
        self.assertEqual(len(resp.get_json()), 1)

    def test_put_update_drawing(self):
        create = self.client.post(
            "/api/chart/AAPL/drawings",
            json={"type": "horizontal", "price": 180},
        )
        drawing_id = create.get_json()["drawing"]["id"]
        resp = self.client.put(
            f"/api/chart/AAPL/drawings/{drawing_id}",
            json={"price": 185, "label": "Support"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["drawing"]["price"], 185)

    def test_put_not_found(self):
        resp = self.client.put("/api/chart/AAPL/drawings/missing-id", json={"price": 1})
        self.assertEqual(resp.status_code, 404)

    def test_delete_drawing(self):
        create = self.client.post(
            "/api/chart/AAPL/drawings",
            json={"type": "horizontal", "price": 180},
        )
        drawing_id = create.get_json()["drawing"]["id"]
        resp = self.client.delete(f"/api/chart/AAPL/drawings/{drawing_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.client.get("/api/chart/AAPL/drawings").get_json(), [])

    def test_delete_not_found(self):
        resp = self.client.delete("/api/chart/AAPL/drawings/missing-id")
        self.assertEqual(resp.status_code, 404)

    def test_post_invalid_trendline(self):
        resp = self.client.post(
            "/api/chart/AAPL/drawings",
            json={"type": "trendline", "start": {"time": "2026-08-01", "price": 1}},
        )
        self.assertEqual(resp.status_code, 400)

    def test_post_invalid_zone(self):
        resp = self.client.post(
            "/api/chart/AAPL/drawings",
            json={"type": "zone", "top": 180, "bottom": 190},
        )
        self.assertEqual(resp.status_code, 400)

    def test_post_trendline_success(self):
        resp = self.client.post(
            "/api/chart/AAPL/drawings",
            json={
                "type": "trendline",
                "start": {"time": "2026-08-01", "price": 170},
                "end": {"time": "2026-08-19", "price": 185},
            },
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.get_json()["drawing"]["type"], "trendline")

    def test_post_zone_success(self):
        resp = self.client.post(
            "/api/chart/AAPL/drawings",
            json={"type": "zone", "top": 185, "bottom": 180, "label": "Demand Zone"},
        )
        self.assertEqual(resp.status_code, 201)

    def test_symbol_isolation_api(self):
        self.client.post("/api/chart/AAPL/drawings", json={"type": "horizontal", "price": 180})
        self.client.post("/api/chart/MSFT/drawings", json={"type": "horizontal", "price": 400})
        aapl = self.client.get("/api/chart/AAPL/drawings").get_json()
        msft = self.client.get("/api/chart/MSFT/drawings").get_json()
        self.assertEqual(len(aapl), 1)
        self.assertEqual(aapl[0]["price"], 180)
        self.assertEqual(msft[0]["price"], 400)

    def test_workspace_state_includes_drawings(self):
        self.client.put("/api/chart/state", json={"symbol": "AAPL"})
        self.client.post("/api/chart/AAPL/drawings", json={"type": "horizontal", "price": 180})
        state = self.client.get("/api/chart/state").get_json()
        self.assertEqual(len(state["drawings"]), 1)

    def test_workspace_drawings_change_with_symbol(self):
        self.client.post("/api/chart/AAPL/drawings", json={"type": "horizontal", "price": 180})
        self.client.post("/api/chart/MSFT/drawings", json={"type": "horizontal", "price": 400})
        self.client.put("/api/chart/state", json={"symbol": "MSFT"})
        state = self.client.get("/api/chart/state").get_json()
        self.assertEqual(state["symbol"], "MSFT")
        self.assertEqual(state["drawings"][0]["price"], 400)


class TestTerminalDrawingIntegration(unittest.TestCase):
    def setUp(self):
        from app import create_app

        self.app = create_app()
        self.client = self.app.test_client()

    def test_terminal_has_draw_toolbar(self):
        resp = self.client.get("/terminal")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode()
        self.assertIn('id="drawToolbar"', html)
        self.assertIn('data-draw-tool="horizontal"', html)
        self.assertIn('data-draw-tool="trendline"', html)
        self.assertIn('data-draw-tool="zone"', html)

    def test_terminal_chart_js_drawing_support(self):
        resp = self.client.get("/static/js/terminal_chart.js")
        body = resp.data.decode()
        self.assertIn("loadDrawings", body)
        self.assertIn("createDrawing", body)
        self.assertIn("setDrawingTool", body)
        self.assertIn("renderDrawings", body)


if __name__ == "__main__":
    unittest.main()
