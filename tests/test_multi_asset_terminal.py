"""Tests for Phase 14D multi-asset terminal integration."""

import os
import sys
import unittest
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.charting.chart_state import ChartStateManager
from src.market.symbol_map import data_feed_symbol
from src.trading.trade_plan import TradePlanManager


class TestInstrumentAPI(unittest.TestCase):
    def setUp(self):
        from app import create_app

        self.app = create_app()
        self.client = self.app.test_client()

    def test_list_instruments(self):
        resp = self.client.get("/api/instruments")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        classes = {i["asset_class"] for i in data["instruments"]}
        self.assertIn("STOCK", classes)
        self.assertIn("FOREX", classes)
        self.assertIn("FUTURES", classes)
        self.assertGreaterEqual(data["count"], 10)

    def test_filter_forex(self):
        resp = self.client.get("/api/instruments?asset_class=FOREX")
        self.assertEqual(resp.status_code, 200)
        items = resp.get_json()["instruments"]
        self.assertTrue(all(i["asset_class"] == "FOREX" for i in items))

    def test_filter_futures(self):
        resp = self.client.get("/api/instruments?asset_class=FUTURES")
        self.assertEqual(resp.status_code, 200)
        items = resp.get_json()["instruments"]
        self.assertGreaterEqual(len(items), 4)
        self.assertTrue(all(i["asset_class"] == "FUTURES" for i in items))

    def test_filter_stock(self):
        resp = self.client.get("/api/instruments?asset_class=STOCK")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.get_json()["instruments"]), 3)

    def test_resolve_esz26(self):
        resp = self.client.get("/api/instruments/ESZ26")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["instrument_id"], "ESZ26")
        self.assertEqual(data["asset_class"], "FUTURES")
        self.assertIn("session", data)
        self.assertEqual(data["session"]["venue"], "CME_GLOBEX")

    def test_resolve_eurusd_session_24h(self):
        resp = self.client.get("/api/instruments/EURUSD")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["session"]["is_24h"])

    def test_resolve_cl_and_gc(self):
        for code in ("CLZ26", "GCZ26"):
            resp = self.client.get(f"/api/instruments/{code}")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.get_json()["asset_class"], "FUTURES")

    def test_stock_session_regular_hours(self):
        resp = self.client.get("/api/instruments/AAPL")
        session = resp.get_json()["session"]
        self.assertFalse(session["is_24h"])
        self.assertIn(session["venue"], ("NYSE", "NASDAQ"))


class TestChartStateMultiAsset(unittest.TestCase):
    def setUp(self):
        self.state = ChartStateManager()

    def test_switch_stock_to_forex(self):
        self.state.update(instrument_id="AAPL")
        self.state.update(instrument_id="EUR/USD")
        s = self.state.get_state()
        self.assertEqual(s["instrument_id"], "EURUSD")
        self.assertEqual(s["asset_class"], "FOREX")
        self.assertTrue(s["session"]["is_24h"])

    def test_switch_to_futures(self):
        self.state.update(instrument_id="NQZ26")
        s = self.state.get_state()
        self.assertEqual(s["instrument_id"], "NQZ26")
        self.assertEqual(s["symbol"], "NQ")
        self.assertEqual(s["asset_class"], "FUTURES")

    def test_default_includes_session(self):
        s = self.state.get_state()
        self.assertIn("session", s)
        self.assertFalse(s["session"]["is_24h"])

    @mock.patch("src.charting.candle_engine.DataFetcher")
    def test_chart_api_state_after_futures_switch(self, MockFetcher):
        import pandas as pd
        from app import create_app

        MockFetcher.return_value.get_real_time_data.return_value = pd.DataFrame(
            {
                "Open": [5000, 5001],
                "High": [5002, 5003],
                "Low": [4999, 5000],
                "Close": [5001, 5002],
                "Volume": [1000, 1000],
            },
            index=pd.date_range("2024-06-01", periods=2, freq="1D"),
        )
        app = create_app()
        client = app.test_client()
        client.put("/api/chart/state", json={"instrument_id": "ESZ26"})
        state = client.get("/api/chart/state").get_json()
        self.assertEqual(state["instrument_id"], "ESZ26")
        self.assertEqual(state["asset_class"], "FUTURES")


class TestChartStatePersistence(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.client = create_app().test_client()

    def test_instrument_id_persists_on_get(self):
        self.client.put("/api/chart/state", json={"instrument_id": "EURUSD"})
        state = self.client.get("/api/chart/state").get_json()
        self.assertEqual(state["instrument_id"], "EURUSD")
        self.assertEqual(state["display_symbol"], "EUR/USD")

    def test_symbol_only_update_backwards_compatible(self):
        self.client.put("/api/chart/state", json={"symbol": "MSFT"})
        state = self.client.get("/api/chart/state").get_json()
        self.assertEqual(state["instrument_id"], "MSFT")
        self.assertEqual(state["asset_class"], "STOCK")

    def test_futures_switch_preserves_timeframe(self):
        self.client.put("/api/chart/state", json={"instrument_id": "AAPL", "timeframe": "1h"})
        self.client.put("/api/chart/state", json={"instrument_id": "ESZ26"})
        state = self.client.get("/api/chart/state").get_json()
        self.assertEqual(state["timeframe"], "1h")
        self.assertEqual(state["instrument_id"], "ESZ26")


class TestSymbolMap(unittest.TestCase):
    def test_stock_feed(self):
        self.assertEqual(data_feed_symbol("AAPL"), "AAPL")

    def test_forex_feed(self):
        self.assertEqual(data_feed_symbol("EURUSD"), "EURUSD=X")

    def test_futures_feed(self):
        self.assertEqual(data_feed_symbol("ESZ26"), "ES=F")


class TestTradePlanMultiAsset(unittest.TestCase):
    def setUp(self):
        self.mgr = TradePlanManager()

    def test_stock_plan_regression(self):
        plan = self.mgr.create_plan({
            "symbol": "AAPL",
            "direction": "LONG",
            "entry": {"price": 185},
            "stop_loss": {"price": 180},
            "target": {"price": 195},
            "quantity": 10,
        })
        self.assertEqual(plan["asset_class"], "STOCK")
        self.assertEqual(plan["quantity_unit"], "shares")

    def test_forex_plan_via_api(self):
        from app import create_app

        app = create_app()
        client = app.test_client()
        resp = client.post("/api/trade-plan", json={
            "instrument_id": "EURUSD",
            "direction": "LONG",
            "entry": {"price": 1.0850},
            "stop_loss": {"price": 1.0800},
            "target": {"price": 1.0950},
            "account_balance": 50000,
            "risk_percent": 1.0,
        })
        self.assertEqual(resp.status_code, 201)
        plan = resp.get_json()["plan"]
        self.assertEqual(plan["asset_class"], "FOREX")
        self.assertEqual(plan["pip_risk"], 50.0)

    def test_futures_plan_via_api(self):
        from app import create_app

        app = create_app()
        client = app.test_client()
        resp = client.post("/api/trade-plan", json={
            "instrument_id": "ESZ26",
            "direction": "LONG",
            "entry": {"price": 5000},
            "stop_loss": {"price": 4995},
            "target": {"price": 5010},
            "account_balance": 50000,
            "risk_percent": 1.0,
        })
        self.assertEqual(resp.status_code, 201)
        plan = resp.get_json()["plan"]
        self.assertEqual(plan["asset_class"], "FUTURES")
        self.assertEqual(plan["contracts"], 2)
        self.assertEqual(plan["tick_risk"], 20.0)

    def test_get_plan_by_instrument_id(self):
        plan = self.mgr.create_plan({
            "instrument_id": "ESZ26",
            "direction": "LONG",
            "entry": {"price": 5000},
            "stop_loss": {"price": 4995},
            "target": {"price": 5010},
            "account_balance": 50000,
            "risk_percent": 1.0,
        })
        items = self.mgr.get_plans_for_symbol("ESZ26")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], plan["id"])


class TestTerminalPageMultiAsset(unittest.TestCase):
    def setUp(self):
        from app import create_app

        self.app = create_app()
        self.client = self.app.test_client()

    def test_terminal_has_asset_selectors(self):
        resp = self.client.get("/terminal")
        html = resp.data.decode()
        self.assertIn('id="assetClassSelect"', html)
        self.assertIn('id="instrumentSelect"', html)
        self.assertIn('id="marketSessionBadge"', html)
        self.assertIn('id="planQtyLabel"', html)


if __name__ == "__main__":
    unittest.main()
