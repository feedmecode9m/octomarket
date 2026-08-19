"""Tests for chart indicator API and terminal integration."""

import os
import sys
import unittest
import unittest.mock as mock

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _sample_ohlcv(n=30):
    return pd.DataFrame(
        {
            "Open": [100.0 + i for i in range(n)],
            "High": [102.0 + i for i in range(n)],
            "Low": [99.0 + i for i in range(n)],
            "Close": [101.0 + i for i in range(n)],
            "Volume": [1_000_000 + i * 1000 for i in range(n)],
        },
        index=pd.date_range("2024-06-01", periods=n, freq="1D"),
    )


class TestIndicatorAPI(unittest.TestCase):
    def setUp(self):
        from app import create_app
        from src.charting.chart_state import get_chart_state
        from src.charting.candle_engine import get_candle_engine

        self.app = create_app()
        self.client = self.app.test_client()
        get_chart_state().reset()
        get_candle_engine().clear_cache()

    def test_requires_indicators_param(self):
        resp = self.client.get("/api/chart/AAPL/indicators")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("indicators", resp.get_json()["error"])

    def test_invalid_indicator_token(self):
        resp = self.client.get("/api/chart/AAPL/indicators?indicators=VWAP")
        self.assertEqual(resp.status_code, 400)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_sma20_indicator_payload(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(25)
        resp = self.client.get("/api/chart/AAPL/indicators?indicators=SMA20")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["symbol"], "AAPL")
        self.assertIn("SMA20", data["indicators"])
        sma = data["indicators"]["SMA20"]
        self.assertEqual(sma["indicator"], "SMA")
        self.assertEqual(sma["period"], 20)
        self.assertEqual(len(sma["values"]), 25)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_rsi_indicator_payload(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(30)
        resp = self.client.get("/api/chart/AAPL/indicators?indicators=RSI")
        self.assertEqual(resp.status_code, 200)
        rsi = resp.get_json()["indicators"]["RSI"]
        self.assertEqual(rsi["indicator"], "RSI")
        self.assertEqual(rsi["period"], 14)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_macd_indicator_payload(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(40)
        resp = self.client.get("/api/chart/AAPL/indicators?indicators=MACD")
        self.assertEqual(resp.status_code, 200)
        macd = resp.get_json()["indicators"]["MACD"]
        self.assertEqual(macd["indicator"], "MACD")
        self.assertIn("macd", macd)
        self.assertIn("signal", macd)
        self.assertIn("histogram", macd)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_bollinger_indicator_payload(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(30)
        resp = self.client.get("/api/chart/AAPL/indicators?indicators=BB")
        self.assertEqual(resp.status_code, 200)
        bb = resp.get_json()["indicators"]["BB"]
        self.assertEqual(bb["indicator"], "BB")
        self.assertIn("upper", bb)
        self.assertIn("middle", bb)
        self.assertIn("lower", bb)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_multiple_indicators(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(35)
        resp = self.client.get("/api/chart/AAPL/indicators?indicators=SMA20,EMA9,RSI,MACD,BB")
        self.assertEqual(resp.status_code, 200)
        indicators = resp.get_json()["indicators"]
        for key in ("SMA20", "EMA9", "RSI", "MACD", "BB"):
            self.assertIn(key, indicators)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_ema_presets_via_api(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(50)
        resp = self.client.get("/api/chart/AAPL/indicators?indicators=EMA9,EMA20,EMA50,EMA200")
        self.assertEqual(resp.status_code, 200)
        indicators = resp.get_json()["indicators"]
        self.assertEqual(indicators["EMA9"]["period"], 9)
        self.assertEqual(indicators["EMA200"]["period"], 200)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_timeframe_query_param(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(20)
        resp = self.client.get("/api/chart/AAPL/indicators?indicators=RSI&timeframe=1d")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["timeframe"], "1d")

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_no_data_returns_404(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = pd.DataFrame()
        resp = self.client.get("/api/chart/ZZZZ/indicators?indicators=RSI&respect_session=false")
        self.assertEqual(resp.status_code, 404)


class TestTerminalIndicatorIntegration(unittest.TestCase):
    def setUp(self):
        from app import create_app

        self.app = create_app()
        self.client = self.app.test_client()

    def test_terminal_has_indicator_toggles(self):
        resp = self.client.get("/terminal")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode()
        self.assertIn('id="indicatorToggles"', html)
        self.assertIn('data-indicator="SMA20"', html)
        self.assertIn('data-indicator="MACD"', html)
        self.assertIn('id="rsiChartDiv"', html)
        self.assertIn('id="macdChartDiv"', html)

    def test_terminal_chart_js_indicator_support(self):
        resp = self.client.get("/static/js/terminal_chart.js")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode()
        self.assertIn("loadIndicators", body)
        self.assertIn("applyIndicatorPayload", body)
        self.assertIn("/indicators", body)


if __name__ == "__main__":
    unittest.main()
