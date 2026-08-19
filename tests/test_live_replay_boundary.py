"""Regression tests for LIVE PAPER vs REPLAY operating mode boundary."""

import os
import sys
import unittest
import unittest.mock as mock

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _sample_ohlcv(n=8, base=180):
    return pd.DataFrame(
        {
            "Open": [base + i for i in range(n)],
            "High": [base + 5 + i for i in range(n)],
            "Low": [base - 2 + i for i in range(n)],
            "Close": [base + 3 + i for i in range(n)],
            "Volume": [1000000] * n,
        },
        index=pd.date_range("2026-01-01", periods=n, freq="1D"),
    )


class TestLiveReplayBoundary(unittest.TestCase):
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

    def _plan_payload(self, symbol, instrument_id, asset_class):
        if asset_class == "FOREX":
            entry, stop, target = 1.085, 1.08, 1.09
        elif asset_class == "FUTURES":
            entry, stop, target = 5010, 5000, 5030
        else:
            entry, stop, target = 185, 180, 195
        payload = {
            "symbol": symbol,
            "instrument_id": instrument_id,
            "asset_class": asset_class,
            "direction": "LONG",
            "entry": {"price": entry},
            "stop_loss": {"price": stop},
            "target": {"price": target},
            "thesis": "Boundary test",
        }
        if asset_class == "FOREX":
            payload["position_lots"] = 0.1
        elif asset_class == "FUTURES":
            payload["contracts"] = 1
            payload["quantity"] = 1
        else:
            payload["quantity"] = 10
        return payload

    def _complete_lifecycle(self, *, symbol, instrument_id, asset_class, replay, prices):
        expected_mode = "replay" if replay else "live_paper"
        if replay:
            self.client.post("/api/session/start", json={"instrument_id": instrument_id})
            self.client.post("/api/session/step")
            self.client.post("/api/session/step")

        plan = self.client.post(
            "/api/trade-plan",
            json=self._plan_payload(symbol, instrument_id, asset_class),
        ).get_json()["plan"]

        record = self.client.get(f"/api/replay/records/{plan['id']}").get_json()["record"]
        self.assertEqual(record["mode"], expected_mode)
        self.assertEqual(record["market"]["instrument_id"], instrument_id)

        if replay:
            self.client.post(f"/api/trade-plan/{plan['id']}/create-order")
            self.client.post("/api/session/step")
        else:
            self.client.post(f"/api/trade-plan/{plan['id']}/create-order")
            price = prices[symbol]
            from src.api.execution_routes import process_session_fills

            process_session_fills(
                {
                    symbol: {
                        "open": price,
                        "high": price,
                        "low": price,
                        "close": price,
                        "volume": 0,
                    }
                }
            )

        with mock.patch("src.api.execution_routes._current_prices", return_value=prices):
            close = self.client.post("/api/orders/close-position", json={"symbol": symbol})
            self.assertEqual(close.status_code, 200, close.get_json())

        final = self.client.get(f"/api/replay/records/{plan['id']}").get_json()["record"]
        self.assertEqual(final["status"], "closed")
        self.assertEqual(final["mode"], expected_mode)
        self.assertIsNotNone(final.get("scoring"))
        return final

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_aapl_live_full_candles_replay_capped(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(8)
        live_chart = self.client.get("/api/chart/AAPL?timeframe=1d&period=1mo").get_json()
        self.assertFalse(live_chart["session_capped"])
        self.assertEqual(live_chart["count"], 8)

        self.client.post("/api/session/start", json={"instrument_id": "AAPL"})
        self.client.post("/api/session/step")
        replay_chart = self.client.get("/api/chart/AAPL?timeframe=1d").get_json()
        self.assertTrue(replay_chart["session_capped"])
        self.assertEqual(replay_chart["count"], 1)

    @mock.patch("src.api.execution_routes._current_prices")
    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_aapl_live_paper_lifecycle(self, MockFetcher, mock_prices):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(8)
        mock_prices.return_value = {"AAPL": 185.0}
        final = self._complete_lifecycle(
            symbol="AAPL",
            instrument_id="AAPL",
            asset_class="STOCK",
            replay=False,
            prices={"AAPL": 185.0},
        )
        self.assertEqual(final["market"]["asset_class"], "STOCK")

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_aapl_replay_lifecycle(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(8)
        final = self._complete_lifecycle(
            symbol="AAPL",
            instrument_id="AAPL",
            asset_class="STOCK",
            replay=True,
            prices={"AAPL": 185.0},
        )
        self.assertEqual(final["outcome"]["exit_reason"], "manual_close")

    @mock.patch("src.api.execution_routes._current_prices")
    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_eurusd_both_modes(self, MockFetcher, mock_prices):
        from src.replay.replay_session import get_replay_session
        from src.simulation.session import get_market_session

        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(8, base=1.08)
        mock_prices.return_value = {"EURUSD": 1.085}
        for replay in (False, True):
            get_replay_session().reset()
            get_market_session().close()
            final = self._complete_lifecycle(
                symbol="EURUSD",
                instrument_id="EURUSD",
                asset_class="FOREX",
                replay=replay,
                prices={"EURUSD": 1.085},
            )
            self.assertEqual(final["market"]["asset_class"], "FOREX")

    @mock.patch("src.api.execution_routes._current_prices")
    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_es_continuous_id_both_modes(self, MockFetcher, mock_prices):
        from src.replay.replay_session import get_replay_session
        from src.simulation.session import get_market_session

        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(8, base=5000)
        mock_prices.return_value = {"ES": 5010.0}
        for replay in (False, True):
            get_replay_session().reset()
            get_market_session().close()
            final = self._complete_lifecycle(
                symbol="ES",
                instrument_id="ESZ26",
                asset_class="FUTURES",
                replay=replay,
                prices={"ES": 5010.0},
            )
            self.assertEqual(final["market"]["continuous_id"], "ES")
            self.assertEqual(final["market"]["instrument_id"], "ESZ26")

    @mock.patch("src.replay.replay_session.is_replay_mode", return_value=False)
    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_live_snapshot_never_session_capped(self, MockFetcher, _mock_replay):
        from src.simulation.session import get_market_session

        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(6)
        self.client.post("/api/session/start", json={"instrument_id": "AAPL"})
        get_market_session().step()

        plan = self.client.post(
            "/api/trade-plan",
            json=self._plan_payload("AAPL", "AAPL", "STOCK"),
        ).get_json()["plan"]
        record = self.client.get(f"/api/replay/records/{plan['id']}").get_json()["record"]
        ctx = record["decision_context"]["market_snapshot"]["session_context"]
        self.assertEqual(ctx["mode"], "live_paper")
        self.assertFalse(ctx["session_capped"])
