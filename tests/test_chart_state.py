"""Tests for chart workspace state."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.charting.chart_state import ChartStateManager


class TestChartState(unittest.TestCase):
    def setUp(self):
        self.state = ChartStateManager()

    def test_default_state(self):
        s = self.state.get_state()
        self.assertEqual(s["symbol"], "AAPL")
        self.assertEqual(s["timeframe"], "1d")
        self.assertEqual(s["indicators"], [])
        self.assertEqual(s["drawings"], [])

    def test_update_symbol(self):
        updated = self.state.update(symbol="tsla")
        self.assertEqual(updated["symbol"], "TSLA")

    def test_update_timeframe(self):
        updated = self.state.update(timeframe="15m", period="1mo")
        self.assertEqual(updated["timeframe"], "15m")
        self.assertEqual(updated["period"], "1mo")

    def test_update_zoom(self):
        updated = self.state.update(zoom={"start": "2026-01-01", "end": "2026-08-01"})
        self.assertEqual(updated["zoom"]["start"], "2026-01-01")
        self.assertEqual(updated["zoom"]["end"], "2026-08-01")

    def test_add_indicator_stored(self):
        ind = self.state.add_indicator({"type": "SMA", "period": 20})
        s = self.state.get_state()
        self.assertEqual(len(s["indicators"]), 1)
        self.assertEqual(s["indicators"][0]["type"], "SMA")
        self.assertEqual(ind["period"], 20)

    def test_add_drawing_stored(self):
        d = self.state.add_drawing({"type": "horizontal", "price": 215, "label": "Resistance"})
        s = self.state.get_state()
        self.assertEqual(len(s["drawings"]), 1)
        self.assertEqual(d["price"], 215)

    def test_reset(self):
        self.state.update(symbol="NVDA")
        self.state.reset()
        self.assertEqual(self.state.get_state()["symbol"], "AAPL")

    def test_invalid_timeframe_raises(self):
        with self.assertRaises(ValueError):
            self.state.update(timeframe="invalid")


class TestChartStateAPI(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.app = create_app()
        self.client = self.app.test_client()
        from src.charting.chart_state import get_chart_state
        get_chart_state().reset()

    def test_get_state(self):
        resp = self.client.get("/api/chart/state")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["symbol"], "AAPL")

    def test_put_state(self):
        resp = self.client.put("/api/chart/state", json={"symbol": "MSFT", "timeframe": "1h"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["state"]["symbol"], "MSFT")
        self.assertEqual(data["state"]["timeframe"], "1h")


if __name__ == "__main__":
    unittest.main()
