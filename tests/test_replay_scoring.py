"""Tests for deterministic replay scoring (Gate 15D)."""

import os
import sys
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.market.asset_class import AssetClass
from src.replay.replay_memory import ReplayMemory
from src.replay.replay_record import apply_exit_fill, build_replay_record_from_plan
from src.replay.replay_scoring import score_replay_record
from src.replay.replay_store import ReplayStore


def _snapshot(asset_class: str, **overrides):
    base = {
        "instrument": {"asset_class": asset_class, "session": {"is_24h": False, "venue": "NYSE"}},
        "price": {"current": 186.0, "volatility": {"last_bar_range": 2.0}},
        "indicators": {"latest": {"SMA20": 184.0, "RSI": 58.0}},
        "structure": {"drawing_count": 1},
    }
    if asset_class == AssetClass.FOREX.value:
        base["instrument"] = {"asset_class": "FOREX", "session": {"is_24h": True, "venue": "FX"}}
        base["price"]["current"] = 1.0860
    if asset_class == AssetClass.FUTURES.value:
        base["instrument"] = {
            "asset_class": "FUTURES",
            "continuous_id": "ES",
            "session": {"is_24h": False, "venue": "CME_GLOBEX"},
        }
        base["price"]["current"] = 5005.0
        base["indicators"]["latest"] = {"SMA20": 5000.0, "RSI": 55.0}
    base.update(overrides)
    return base


def _closed_record(asset_class: str, plan: dict, market: dict) -> dict:
    record = {
        "id": "rec-1",
        "status": "filled",
        "plan_id": plan.get("id", "plan-1"),
        "market": market,
        "decision_context": {"market_snapshot": _snapshot(asset_class)},
        "trade_intent": plan,
        "execution": {
            "status": "filled",
            "entry": {"price": plan["entry"]["price"], "quantity": plan.get("quantity", 1)},
            "exit": None,
            "fills": [],
        },
        "outcome": {},
        "metadata": {"created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00"},
    }
    return apply_exit_fill(
        record,
        {"id": "exit-1", "side": "sell"},
        {"fill_price": plan.get("_exit_price", plan["target"]["price"]), "quantity": plan.get("quantity", 1)},
        exit_reason="take_profit",
    )


class TestReplayScoring(unittest.TestCase):
    def test_stock_scoring_explainable(self):
        plan = {
            "id": "p1",
            "symbol": "AAPL",
            "instrument_id": "AAPL",
            "direction": "LONG",
            "thesis": "Breakout",
            "entry": {"price": 185.0},
            "stop_loss": {"price": 180.0},
            "target": {"price": 195.0},
            "quantity": 10,
            "risk_reward": 2.0,
            "risk_amount": 50.0,
            "quantity_unit": "shares",
            "_exit_price": 192.0,
        }
        market = {"instrument_id": "AAPL", "asset_class": "STOCK", "symbol": "AAPL"}
        record = _closed_record(AssetClass.STOCK.value, plan, market)
        scoring = score_replay_record(record)

        self.assertGreaterEqual(scoring["total_score"], 0)
        self.assertLessEqual(scoring["total_score"], 100)
        self.assertIn("grade", scoring)
        self.assertIn("trend_alignment", scoring["dimensions"])
        self.assertTrue(scoring["reasons_positive"])
        self.assertEqual(scoring["completeness"], "full")
        self.assertIsNone(scoring.get("continuous_id"))

    def test_forex_scoring(self):
        plan = {
            "id": "p2",
            "symbol": "EURUSD",
            "instrument_id": "EURUSD",
            "direction": "LONG",
            "thesis": "Support bounce",
            "entry": {"price": 1.0850},
            "stop_loss": {"price": 1.0800},
            "target": {"price": 1.0950},
            "position_lots": 1.0,
            "pip_risk": 50.0,
            "risk_reward": 2.0,
            "risk_amount": 500.0,
            "quantity_unit": "lots",
            "_exit_price": 1.0920,
        }
        market = {"instrument_id": "EURUSD", "asset_class": "FOREX", "symbol": "EURUSD"}
        record = _closed_record(AssetClass.FOREX.value, plan, market)
        scoring = score_replay_record(record)

        self.assertEqual(scoring["asset_class"], "FOREX")
        self.assertIn("Forex", " ".join(scoring["reasons_positive"]))
        session = scoring["dimensions"]["session_quality"]
        self.assertGreater(session["score"], 70)

    def test_futures_scoring_preserves_continuous_id(self):
        plan = {
            "id": "p3",
            "symbol": "ES",
            "instrument_id": "ESZ26",
            "direction": "LONG",
            "thesis": "Trend",
            "entry": {"price": 5000.0},
            "stop_loss": {"price": 4990.0},
            "target": {"price": 5020.0},
            "contracts": 2,
            "tick_risk": 40.0,
            "risk_reward": 2.0,
            "risk_amount": 1000.0,
            "quantity_unit": "contracts",
            "_exit_price": 5015.0,
        }
        market = {
            "instrument_id": "ESZ26",
            "asset_class": "FUTURES",
            "symbol": "ES",
            "continuous_id": "ES",
        }
        record = _closed_record(AssetClass.FUTURES.value, plan, market)
        scoring = score_replay_record(record)

        self.assertEqual(scoring["continuous_id"], "ES")
        rr = scoring["dimensions"]["risk_reward"]
        self.assertTrue(any("tick" in r.lower() for r in rr["reasons_positive"]))

    def test_incomplete_record_partial_scoring(self):
        plan = {
            "id": "p4",
            "symbol": "MSFT",
            "direction": "LONG",
            "thesis": "",
            "entry": {"price": 400},
            "stop_loss": {"price": 390},
            "target": {"price": 420},
            "risk_reward": 2.0,
        }
        record = {
            "id": "rec-partial",
            "status": "planned",
            "market": {"instrument_id": "MSFT", "asset_class": "STOCK", "symbol": "MSFT"},
            "decision_context": {"market_snapshot": _snapshot(AssetClass.STOCK.value)},
            "trade_intent": plan,
            "execution": {"status": "pending"},
            "outcome": {},
        }
        scoring = score_replay_record(record)

        self.assertEqual(scoring["completeness"], "partial")
        self.assertTrue(scoring["dimensions"]["execution_quality"]["skipped"])
        self.assertIn("Execution incomplete", " ".join(scoring["reasons_negative"]))

    @mock.patch("src.replay.market_snapshot._load_candles")
    def test_scoring_persists_on_close(self, mock_load):
        mock_load.return_value = {
            "symbol": "AAPL", "timeframe": "1d", "period": "5d", "count": 0,
            "timestamps": [], "open": [], "high": [], "low": [], "close": [], "volume": [],
        }
        temp = tempfile.TemporaryDirectory()
        store = ReplayStore(path=Path(temp.name) / "records.jsonl")
        memory = ReplayMemory(store=store)

        plan = {
            "id": "plan-score-1",
            "symbol": "AAPL",
            "direction": "LONG",
            "thesis": "Test",
            "entry": {"price": 185},
            "stop_loss": {"price": 180},
            "target": {"price": 195},
            "quantity": 10,
            "risk_reward": 2.0,
            "risk_amount": 50,
        }
        from src.trading.trade_plan import TradePlanManager

        mgr = TradePlanManager(record_replay=False)
        created = mgr.create_plan(plan)
        created["id"] = plan["id"]
        record = memory.on_plan_created(created)
        memory.on_entry_fill(
            {"id": "ord-1", "side": "buy", "quantity": 10, "trade_plan": {"plan_id": plan["id"]}},
            {"fill_price": 185, "quantity": 10},
        )
        closed = memory.on_exit_fill(
            {"id": "exit-1", "parent_id": "ord-1", "side": "sell", "quantity": 10},
            {"fill_price": 190, "quantity": 10},
            exit_reason="take_profit",
        )
        assert closed is not None
        self.assertIsNotNone(closed.get("scoring"))
        self.assertIn("total_score", closed["scoring"])

        reloaded = store.get(record["id"])
        assert reloaded is not None
        self.assertIsNotNone(reloaded.get("scoring"))
        temp.cleanup()


if __name__ == "__main__":
    unittest.main()
