"""Tests for Gate 16E — Human replay and strategy decision interface."""

import os
import sys
import unittest
import unittest.mock as mock

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _ohlcv(n=40, base=5000.0, step=2.0):
    closes = [base + step * i for i in range(n)]
    return pd.DataFrame(
        {
            "Open": [c - 1 for c in closes],
            "High": [c + 4 for c in closes],
            "Low": [c - 3 for c in closes],
            "Close": closes,
            "Volume": [50000] * n,
        },
        index=pd.date_range("2024-01-01", periods=n, freq="1D"),
    )


def _recommendation_payload(strategy_id="futures_trend"):
    return {
        "decision_support_only": True,
        "instrument_id": "ESZ26",
        "asset_class": "FUTURES",
        "market_context": {
            "trend_state": "trending",
            "volatility_state": "high",
            "session_quality": "high",
            "active_regimes": ["trending", "high_volatility"],
            "data_quality": {"bars": 80, "data_quality": "complete"},
        },
        "recommendation": {
            "strategy_family": "trend_following",
            "confidence": "high",
            "historical_conditions": {
                "matched_strategies": [
                    {
                        "strategy_id": strategy_id,
                        "strategy_name": "Trend Following",
                        "trade_count": 220,
                        "profit_factor": 1.55,
                        "oos_profit_factor": 1.05,
                        "average_decision_score": 84,
                    }
                ]
            },
            "supporting_records": ["rec-1"],
            "warnings": ["Performance degradation detected"],
            "narrative": "Trend family historically matched these conditions.",
        },
        "candidates": [{"strategy_id": strategy_id, "strategy_family": "trend_following"}],
        "rejected": [],
        "warnings": [],
    }


class TestRecommendationDoesNotCreateTrades(unittest.TestCase):
    def setUp(self):
        from app import create_app
        from src.trading.order_engine import get_order_engine
        from src.trading.trade_plan import get_trade_plan_manager

        self.app = create_app()
        self.client = self.app.test_client()
        get_trade_plan_manager().reset()
        get_order_engine().clear()

    @mock.patch("src.research.selection.detect_market_context")
    def test_recommend_endpoint_is_read_only(self, mock_ctx):
        from src.trading.order_engine import get_order_engine
        from src.trading.trade_plan import get_trade_plan_manager

        mock_ctx.return_value = {
            "asset_class": "FUTURES",
            "trend_state": "trending",
            "volatility_state": "high",
            "active_regimes": ["trending"],
            "data_quality": {"warnings": []},
        }
        plans_before = len(get_trade_plan_manager()._plans)
        orders_before = len(get_order_engine().get_all())
        resp = self.client.post(
            "/api/research/recommend",
            json={"instrument_id": "ESZ26", "period": "3mo", "timeframe": "1d"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["recommendation"]["decision_support_only"])
        self.assertEqual(len(get_trade_plan_manager()._plans), plans_before)
        self.assertEqual(len(get_order_engine().get_all()), orders_before)


class TestCreatePlanFromRecommendation(unittest.TestCase):
    def setUp(self):
        from app import create_app
        from src.replay.replay_memory import reset_replay_memory
        from src.trading.order_engine import get_order_engine
        from src.trading.trade_plan import get_trade_plan_manager

        reset_replay_memory()
        get_trade_plan_manager().reset()
        get_order_engine().clear()
        self.app = create_app()
        self.client = self.app.test_client()

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_create_plan_uses_trade_plan_manager_not_orders(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _ohlcv(80)
        from src.trading.order_engine import get_order_engine
        from src.trading.trade_plan import get_trade_plan_manager

        resp = self.client.post(
            "/api/research/recommend/create-plan",
            json={
                "instrument_id": "ESZ26",
                "recommendation": _recommendation_payload(),
                "account_balance": 10000,
                "risk_percent": 1.0,
            },
        )
        self.assertIn(resp.status_code, (200, 201))
        data = resp.get_json()
        self.assertTrue(data.get("created_from_recommendation"))
        self.assertTrue(data.get("decision_support_only"))
        if data.get("plan"):
            plan = data["plan"]
            self.assertEqual(plan["strategy_id"], "futures_trend")
            self.assertIn(plan["id"], get_trade_plan_manager()._plans)
            record = self.client.get(f"/api/replay/records/{plan['id']}").get_json()
            self.assertIn("record", record)
        self.assertEqual(len(get_order_engine().get_all()), 0)

    def test_preferred_strategy_helper(self):
        from src.research.selection import preferred_strategy_from_recommendation

        self.assertEqual(
            preferred_strategy_from_recommendation(_recommendation_payload("futures_breakout")),
            "futures_breakout",
        )


class TestReplayViewer(unittest.TestCase):
    def setUp(self):
        from app import create_app
        from src.replay.replay_session import get_replay_session
        from src.simulation.session import get_market_session

        self.app = create_app()
        self.client = self.app.test_client()
        get_replay_session().reset()
        get_market_session().close()

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_start_step_updates_chart_visibility(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _ohlcv(20, base=180, step=1)
        start = self.client.post(
            "/api/session/start",
            json={"instrument_id": "AAPL", "period": "1mo", "interval": "1d"},
        )
        self.assertEqual(start.status_code, 200)
        state = start.get_json()["state"]
        self.assertEqual(state["mode"], "replay")
        self.assertIn("visible_candle_count", state)

        step1 = self.client.post("/api/session/step")
        self.assertEqual(step1.status_code, 200)
        s1 = step1.get_json()
        self.assertEqual(s1["visible_candle_count"], 1)
        self.assertIsNotNone(s1.get("current_timestamp"))

        chart = self.client.get("/api/chart/AAPL?interval=1d&period=1mo").get_json()
        self.assertTrue(chart.get("session_capped"))
        self.assertEqual(chart.get("count"), 1)

        step2 = self.client.post("/api/session/step")
        chart2 = self.client.get("/api/chart/AAPL?interval=1d&period=1mo").get_json()
        self.assertEqual(chart2.get("count"), 2)
        self.assertLess(chart2.get("count"), 20)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_future_candles_remain_hidden(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _ohlcv(15, base=180, step=1)
        self.client.post("/api/session/start", json={"instrument_id": "AAPL"})
        self.client.post("/api/session/step")
        candles = self.client.get("/api/replay/candles/AAPL").get_json()
        self.assertTrue(candles.get("session_capped"))
        self.assertEqual(candles.get("count"), 1)
        self.assertGreater(candles.get("hidden_count", 0), 0)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_reset_returns_to_live_paper(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _ohlcv(10, base=180, step=1)
        self.client.post("/api/session/start", json={"instrument_id": "AAPL"})
        self.client.post("/api/session/step")
        reset = self.client.post("/api/session/reset")
        self.assertEqual(reset.status_code, 200)
        state = reset.get_json()["state"]
        self.assertEqual(state["mode"], "live_paper")
        self.assertFalse(state.get("replay_mode"))


class TestLivePaperNotContaminated(unittest.TestCase):
    def setUp(self):
        from app import create_app
        from src.replay.replay_session import get_replay_session
        from src.simulation.session import get_market_session

        self.app = create_app()
        self.client = self.app.test_client()
        get_replay_session().reset()
        get_market_session().close()

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_research_recommend_does_not_force_replay_mode(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _ohlcv(30)
        from src.replay.replay_session import get_replay_session

        get_replay_session().set_mode("live_paper")
        with mock.patch("src.research.selection.detect_market_context") as mock_ctx:
            mock_ctx.return_value = {
                "asset_class": "FUTURES",
                "trend_state": "trending",
                "volatility_state": "normal",
                "active_regimes": ["trending"],
                "data_quality": {"warnings": []},
            }
            self.client.post("/api/research/recommend", json={"instrument_id": "ESZ26"})
        self.assertFalse(get_replay_session().is_replay_mode())


class TestReplayTradeCreatesScoredRecord(unittest.TestCase):
    def setUp(self):
        from app import create_app
        from src.replay.replay_memory import reset_replay_memory
        from src.replay.replay_session import get_replay_session
        from src.simulation.session import get_market_session
        from src.trading.order_engine import get_order_engine
        from src.trading.trade_plan import get_trade_plan_manager

        reset_replay_memory()
        get_trade_plan_manager().reset()
        get_order_engine().clear()
        get_replay_session().reset()
        get_market_session().close()
        self.app = create_app()
        self.client = self.app.test_client()

    @mock.patch("src.api.execution_routes._current_prices")
    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_close_creates_replay_record_and_decision_score(self, MockFetcher, mock_prices):
        MockFetcher.return_value.get_real_time_data.return_value = _ohlcv(12, base=5000, step=2)
        mock_prices.return_value = {"ES": 5010.0}

        self.client.post("/api/session/start", json={"instrument_id": "ESZ26", "initial_cash": 100000})
        self.client.post("/api/session/step")
        self.client.post("/api/session/step")

        plan = self.client.post(
            "/api/trade-plan",
            json={
                "symbol": "ES",
                "instrument_id": "ESZ26",
                "asset_class": "FUTURES",
                "direction": "LONG",
                "entry": {"price": 5010},
                "stop_loss": {"price": 5000},
                "target": {"price": 5030},
                "contracts": 1,
                "quantity": 1,
                "thesis": "16E replay close",
            },
        ).get_json()["plan"]
        self.client.post(f"/api/trade-plan/{plan['id']}/approve")
        order_resp = self.client.post(f"/api/trade-plan/{plan['id']}/create-order")
        self.assertEqual(order_resp.status_code, 201)

        self.client.post("/api/session/step")
        close = self.client.post("/api/orders/close-position", json={"symbol": "ES"})
        self.assertIn(close.status_code, (200, 201))

        record_resp = self.client.get(f"/api/replay/records/{plan['id']}")
        self.assertEqual(record_resp.status_code, 200)
        record = record_resp.get_json()["record"]
        self.assertEqual(record["mode"], "replay")
        self.assertEqual(record["status"], "closed")
        self.assertIn("scoring", record)
        self.assertIsNotNone(record["scoring"].get("decision_score"))


class TestTerminalUIExposesDecisionWorkflow(unittest.TestCase):
    def setUp(self):
        from app import create_app

        self.app = create_app()
        self.client = self.app.test_client()

    def test_terminal_has_recommendation_and_replay_controls(self):
        html = self.client.get("/terminal").get_data(as_text=True)
        self.assertIn("RECOMMEND FAMILY", html)
        self.assertIn("CREATE PLAN", html)
        self.assertIn("IGNORE", html)
        self.assertIn("playSessionBtn", html)
        self.assertIn("resetSessionBtn", html)
        self.assertIn("Start Replay", html)
        self.assertIn("/api/research/recommend/create-plan", html)


if __name__ == "__main__":
    unittest.main()
