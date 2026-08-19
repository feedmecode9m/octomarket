"""Phase 13B — terminal candlestick workspace tests."""

import os
import sys
import unittest
import unittest.mock as mock

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.charting.candle_adapter import (
    bars_from_candle_payload,
    is_intraday_timeframe,
    to_chart_time,
)


def _sample_payload(count=5, timeframe="1d"):
    return {
        "symbol": "AAPL",
        "timeframe": timeframe,
        "period": "5d",
        "count": count,
        "session_capped": False,
        "timestamps": [f"2024-06-0{i+1}T00:00:00" for i in range(count)],
        "open": [100.0 + i for i in range(count)],
        "high": [102.0 + i for i in range(count)],
        "low": [99.0 + i for i in range(count)],
        "close": [101.0 + i for i in range(count)],
        "volume": [1000000 + i * 1000 for i in range(count)],
    }


class TestCandleAdapter(unittest.TestCase):
    def test_is_intraday(self):
        self.assertTrue(is_intraday_timeframe("5m"))
        self.assertTrue(is_intraday_timeframe("1h"))
        self.assertFalse(is_intraday_timeframe("1d"))

    def test_daily_chart_time(self):
        self.assertEqual(to_chart_time("2024-06-01T00:00:00", "1d"), "2024-06-01")

    def test_intraday_chart_time(self):
        ts = to_chart_time("2024-06-01T14:30:00", "5m")
        self.assertIsInstance(ts, int)
        self.assertGreater(ts, 0)

    def test_bars_from_payload_daily(self):
        result = bars_from_candle_payload(_sample_payload(3))
        self.assertEqual(result["count"], 3)
        self.assertEqual(len(result["candles"]), 3)
        self.assertEqual(len(result["volume"]), 3)
        self.assertEqual(result["candles"][0]["time"], "2024-06-01")
        self.assertIn("open", result["candles"][0])
        self.assertIn("color", result["volume"][0])

    def test_volume_color_follows_close_vs_open(self):
        payload = _sample_payload(1)
        payload["close"][0] = 95.0
        payload["open"][0] = 100.0
        result = bars_from_candle_payload(payload)
        self.assertIn("255,71,87", result["volume"][0]["color"])


class TestTerminalChartPage(unittest.TestCase):
    def setUp(self):
        from app import create_app

        self.app = create_app()
        self.client = self.app.test_client()

    def test_terminal_includes_lightweight_charts(self):
        resp = self.client.get("/terminal")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode()
        self.assertIn("lightweight-charts", html)
        self.assertIn("terminal_chart.js", html)
        self.assertNotIn("plotly-latest", html)

    def test_terminal_has_timeframe_selector(self):
        resp = self.client.get("/terminal")
        html = resp.data.decode()
        self.assertIn('id="chartTimeframe"', html)
        self.assertIn('id="crosshairReadout"', html)

    def test_terminal_chart_js_served(self):
        resp = self.client.get("/static/js/terminal_chart.js")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode()
        self.assertIn("OctoMarketTerminalChart", body)
        self.assertIn("addCandlestickSeries", body)


class TestTerminalChartAPIIntegration(unittest.TestCase):
    def setUp(self):
        from app import create_app
        from src.charting.chart_state import get_chart_state

        self.app = create_app()
        self.client = self.app.test_client()
        get_chart_state().reset()

    @mock.patch("src.charting.candle_engine.DataFetcher")
    def test_symbol_and_timeframe_flow(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = pd.DataFrame(
            {
                "Open": [100.0, 101.0],
                "High": [102.0, 103.0],
                "Low": [99.0, 100.0],
                "Close": [101.0, 102.0],
                "Volume": [1_000_000, 1_100_000],
            },
            index=pd.date_range("2024-06-01", periods=2, freq="1D"),
        )

        put = self.client.put("/api/chart/state", json={"symbol": "AAPL", "timeframe": "1d"})
        self.assertEqual(put.status_code, 200)

        resp = self.client.get("/api/chart/AAPL?timeframe=1d")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["symbol"], "AAPL")
        self.assertGreaterEqual(data["count"], 1)

        bars = bars_from_candle_payload(data)
        self.assertEqual(len(bars["candles"]), data["count"])
        self.assertEqual(len(bars["volume"]), data["count"])

    @mock.patch("src.charting.candle_engine.DataFetcher")
    def test_timeframe_switch_updates_state(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = pd.DataFrame(
            {
                "Open": [100.0],
                "High": [102.0],
                "Low": [99.0],
                "Close": [101.0],
                "Volume": [500_000],
            },
            index=pd.date_range("2024-06-01", periods=1, freq="1h"),
        )

        self.client.put("/api/chart/state", json={"timeframe": "1h"})
        resp = self.client.get("/api/chart/AAPL?timeframe=1h")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["timeframe"], "1h")

        state = self.client.get("/api/chart/state").get_json()
        self.assertEqual(state["timeframe"], "1h")


if __name__ == "__main__":
    unittest.main()
