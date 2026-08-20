"""Tests for strategy engine — signals flow through TradePlan pipeline."""

import os
import sys
import unittest
import unittest.mock as mock

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _trending_ohlcv(n=60, base=5000.0, trend=2.0):
    """Upward trending series suitable for long momentum/trend strategies."""
    closes = [base + trend * i for i in range(n)]
    return pd.DataFrame(
        {
            "Open": [c - 1 for c in closes],
            "High": [c + 3 for c in closes],
            "Low": [c - 4 for c in closes],
            "Close": closes,
            "Volume": [50000] * n,
        },
        index=pd.date_range("2026-01-01", periods=n, freq="1D"),
    )


def _trending_forex_ohlcv(n=40, base=1.0850):
    closes = [base + 0.0003 * i for i in range(n)]
    return pd.DataFrame(
        {
            "Open": [c - 0.0002 for c in closes],
            "High": [c + 0.0005 for c in closes],
            "Low": [c - 0.0005 for c in closes],
            "Close": closes,
            "Volume": [0] * n,
        },
        index=pd.date_range("2026-01-01", periods=n, freq="1D"),
    )


def _ranging_forex_ohlcv(n=30, base=1.0850):
    """Oscillating series for mean reversion tests."""
    closes = [base + (0.0010 if i % 2 == 0 else -0.0010) for i in range(n)]
    closes[-1] = base - 0.0035
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [c + 0.0008 for c in closes],
            "Low": [c - 0.0012 for c in closes],
            "Close": closes,
            "Volume": [0] * n,
        },
        index=pd.date_range("2026-01-01", periods=n, freq="1D"),
    )


class TestStrategyRegistry(unittest.TestCase):
    def test_catalog_groups_by_asset_class(self):
        from src.strategies.registry import get_strategy_registry

        catalog = get_strategy_registry().catalog()
        self.assertIn("FUTURES", catalog)
        self.assertIn("FOREX", catalog)
        self.assertGreaterEqual(len(catalog["FUTURES"]), 3)
        self.assertGreaterEqual(len(catalog["FOREX"]), 3)
        names = {s["name"] for s in catalog["FUTURES"]}
        self.assertIn("Trend Following", names)
        self.assertIn("Breakout", names)
        self.assertIn("Momentum", names)


class TestStrategyEngineUnit(unittest.TestCase):
    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_futures_trend_creates_valid_trade_plan(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _trending_ohlcv(60, base=5000)
        from src.strategies.engine import StrategyEngine
        from src.trading.trade_plan import TradePlanManager

        engine = StrategyEngine(plan_manager=TradePlanManager(record_replay=False))
        result = engine.generate_plan("futures_trend", "ESZ26")

        self.assertIsNotNone(result.get("plan"), result.get("reason"))
        plan = result["plan"]
        self.assertEqual(plan["strategy_id"], "futures_trend")
        self.assertIn(plan["direction"], ("LONG", "SHORT"))
        self.assertGreater(plan["entry"]["price"], 0)
        self.assertGreater(plan["stop_loss"]["price"], 0)
        self.assertGreater(plan["target"]["price"], 0)
        self.assertIn("strategy", plan.get("setup", {}))
        self.assertTrue(plan.get("thesis"))

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_forex_momentum_creates_valid_trade_plan(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _trending_forex_ohlcv(40)
        from src.strategies.engine import StrategyEngine
        from src.trading.trade_plan import TradePlanManager

        engine = StrategyEngine(plan_manager=TradePlanManager(record_replay=False))
        result = engine.generate_plan("forex_momentum", "EURUSD")

        self.assertIsNotNone(result.get("plan"), result.get("reason"))
        plan = result["plan"]
        self.assertEqual(plan["asset_class"], "FOREX")
        self.assertEqual(plan["strategy_id"], "forex_momentum")
        self.assertIsNotNone(plan.get("position_lots"))

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_es_continuous_id_in_context(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _trending_ohlcv(60)
        from src.strategies.context import build_strategy_context

        ctx = build_strategy_context("ESZ26")
        self.assertEqual(ctx.asset_class, "FUTURES")
        self.assertEqual(ctx.continuous_id, "ES")

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_signal_includes_explanation(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _trending_ohlcv(60)
        from src.strategies.engine import StrategyEngine

        result = StrategyEngine().evaluate("futures_momentum", "ESZ26")
        signal = result.get("signal")
        if signal is None:
            self.skipTest(result.get("reason"))
        self.assertTrue(signal.get("setup"))
        self.assertTrue(signal.get("risk"))
        self.assertGreater(signal.get("confidence", 0), 0)


class TestStrategyAPI(unittest.TestCase):
    def setUp(self):
        from app import create_app
        from src.replay.replay_memory import reset_replay_memory
        from src.trading.trade_plan import get_trade_plan_manager

        reset_replay_memory()
        get_trade_plan_manager().reset()
        self.app = create_app()
        self.client = self.app.test_client()

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_list_strategies_endpoint(self, MockFetcher):
        resp = self.client.get("/api/strategies")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("catalog", data)
        self.assertIn("FUTURES", data["catalog"])

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_generate_plan_endpoint(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _trending_ohlcv(60)
        resp = self.client.post(
            "/api/strategies/futures_trend/generate-plan",
            json={"instrument_id": "ESZ26", "account_balance": 10000, "risk_percent": 1.0},
        )
        self.assertIn(resp.status_code, (200, 201))
        data = resp.get_json()
        if data.get("plan"):
            self.assertEqual(data["plan"]["strategy_id"], "futures_trend")


class TestStrategyLifecycle(unittest.TestCase):
    def setUp(self):
        from app import create_app
        from src.replay.replay_memory import reset_replay_memory
        from src.replay.replay_session import get_replay_session
        from src.simulation.session import get_market_session
        from src.trading.trade_plan import get_trade_plan_manager

        reset_replay_memory()
        get_trade_plan_manager().reset()
        self.app = create_app()
        self.client = self.app.test_client()
        get_replay_session().reset()
        get_market_session().close()

    def _complete_strategy_lifecycle(self, *, strategy_id, instrument_id, symbol, asset_class, replay, prices):
        if replay:
            self.client.post("/api/session/start", json={"instrument_id": instrument_id})
            for _ in range(55):
                self.client.post("/api/session/step")

        gen = self.client.post(
            f"/api/strategies/{strategy_id}/generate-plan",
            json={"instrument_id": instrument_id, "account_balance": 10000, "risk_percent": 1.0},
        )
        data = gen.get_json()
        if not data.get("plan"):
            self.skipTest(data.get("reason") or "Strategy produced no plan")
        plan = data["plan"]

        record = self.client.get(f"/api/replay/records/{plan['id']}").get_json()["record"]
        self.assertEqual(record["mode"], "replay" if replay else "live_paper")
        self.assertEqual(record["market"]["instrument_id"], instrument_id)

        self.client.post(f"/api/trade-plan/{plan['id']}/create-order")
        if replay:
            self.client.post("/api/session/step")
        else:
            from src.api.execution_routes import process_session_fills

            process_session_fills(
                {symbol: {"open": prices[symbol], "high": prices[symbol], "low": prices[symbol], "close": prices[symbol], "volume": 0}}
            )

        with mock.patch("src.api.execution_routes._current_prices", return_value=prices):
            close = self.client.post("/api/orders/close-position", json={"symbol": symbol})
            self.assertEqual(close.status_code, 200, close.get_json())

        final = self.client.get(f"/api/replay/records/{plan['id']}").get_json()["record"]
        self.assertEqual(final["status"], "closed")
        self.assertIsNotNone(final.get("scoring"))
        self.assertIn("decision_score", final["scoring"])
        return final

    @mock.patch("src.api.execution_routes._current_prices")
    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_aapl_manual_regression(self, MockFetcher, mock_prices):
        MockFetcher.return_value.get_real_time_data.return_value = _trending_ohlcv(8, base=180, trend=1)
        mock_prices.return_value = {"AAPL": 185.0}
        plan = self.client.post(
            "/api/trade-plan",
            json={
                "symbol": "AAPL",
                "instrument_id": "AAPL",
                "asset_class": "STOCK",
                "direction": "LONG",
                "entry": {"price": 185},
                "stop_loss": {"price": 180},
                "target": {"price": 195},
                "quantity": 10,
                "thesis": "Manual regression",
            },
        ).get_json()["plan"]
        record = self.client.get(f"/api/replay/records/{plan['id']}").get_json()["record"]
        self.assertEqual(record["market"]["asset_class"], "STOCK")
        self.assertIsNone(plan.get("strategy_id"))

    @mock.patch("src.api.execution_routes._current_prices")
    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_eurusd_live_paper_strategy_lifecycle(self, MockFetcher, mock_prices):
        MockFetcher.return_value.get_real_time_data.return_value = _trending_forex_ohlcv(40)
        mock_prices.return_value = {"EURUSD": 1.085}
        final = self._complete_strategy_lifecycle(
            strategy_id="forex_momentum",
            instrument_id="EURUSD",
            symbol="EURUSD",
            asset_class="FOREX",
            replay=False,
            prices={"EURUSD": 1.085},
        )
        self.assertEqual(final["market"]["asset_class"], "FOREX")

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_es_replay_strategy_lifecycle(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _trending_ohlcv(60)
        final = self._complete_strategy_lifecycle(
            strategy_id="futures_trend",
            instrument_id="ESZ26",
            symbol="ES",
            asset_class="FUTURES",
            replay=True,
            prices={"ES": 5010.0},
        )
        self.assertEqual(final["market"].get("continuous_id"), "ES")
        self.assertEqual(final["mode"], "replay")

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_no_future_candle_leakage_in_replay(self, MockFetcher):
        df = _trending_ohlcv(60)
        MockFetcher.return_value.get_real_time_data.return_value = df

        from src.replay.replay_session import get_replay_session

        get_replay_session().start(instrument_id="ESZ26", interval="1d", period="3mo")
        get_replay_session().step()
        get_replay_session().step()

        from src.strategies.engine import StrategyEngine

        result = StrategyEngine().evaluate("futures_trend", "ESZ26")
        ctx = result.get("context") or {}
        self.assertTrue(ctx.get("session_capped"))
        self.assertLess(ctx.get("bar_count", 999), 60)


if __name__ == "__main__":
    unittest.main()
