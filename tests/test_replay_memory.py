"""Tests for durable replay memory (Gate 15A)."""

import os
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.market.asset_class import AssetClass
from src.replay.replay_memory import ReplayMemory
from src.replay.replay_record import (
    apply_entry_fill,
    apply_exit_fill,
    apply_order_submitted,
    build_replay_record_from_plan,
    calculate_outcome,
)
from src.replay.replay_store import ReplayStore
from src.trading.trade_plan import TradePlanManager


def _stock_plan(**overrides):
    base = {
        "id": "plan-stock-1",
        "symbol": "AAPL",
        "instrument_id": "AAPL",
        "asset_class": AssetClass.STOCK.value,
        "direction": "LONG",
        "thesis": "Breakout",
        "entry": {"price": 185.0},
        "stop_loss": {"price": 180.0},
        "target": {"price": 195.0},
        "quantity": 10,
        "risk_amount": 50.0,
        "dollar_risk": 50.0,
        "risk_reward": 2.0,
        "status": "DRAFT",
    }
    base.update(overrides)
    return base


def _futures_plan(**overrides):
    base = {
        "id": "plan-futures-1",
        "symbol": "ES",
        "instrument_id": "ESZ26",
        "asset_class": AssetClass.FUTURES.value,
        "direction": "LONG",
        "thesis": "Trend continuation",
        "entry": {"price": 5000.0},
        "stop_loss": {"price": 4990.0},
        "target": {"price": 5020.0},
        "contracts": 2,
        "quantity": 2,
        "risk_amount": 1000.0,
        "status": "DRAFT",
    }
    base.update(overrides)
    return base


def _forex_plan(**overrides):
    base = {
        "id": "plan-forex-1",
        "symbol": "EURUSD",
        "instrument_id": "EURUSD",
        "asset_class": AssetClass.FOREX.value,
        "direction": "LONG",
        "thesis": "Support bounce",
        "entry": {"price": 1.0850},
        "stop_loss": {"price": 1.0800},
        "target": {"price": 1.0950},
        "position_lots": 1.0,
        "quantity": 100000,
        "risk_amount": 500.0,
        "status": "DRAFT",
    }
    base.update(overrides)
    return base


class TestReplayRecordModel(unittest.TestCase):
    def test_stock_record_has_no_continuous_id(self):
        record = build_replay_record_from_plan(_stock_plan())
        self.assertEqual(record["market"]["instrument_id"], "AAPL")
        self.assertNotIn("continuous_id", record["market"])

    def test_forex_record_has_no_continuous_id(self):
        record = build_replay_record_from_plan(_forex_plan())
        self.assertEqual(record["market"]["asset_class"], "FOREX")
        self.assertNotIn("continuous_id", record["market"])

    def test_futures_record_preserves_continuous_identity(self):
        record = build_replay_record_from_plan(_futures_plan())
        self.assertEqual(record["market"]["continuous_id"], "ES")
        self.assertEqual(record["market"]["instrument_id"], "ESZ26")
        self.assertEqual(record["market"]["contract"], "ESZ26")

    def test_outcome_calculation_stock(self):
        record = build_replay_record_from_plan(_stock_plan())
        apply_entry_fill(record, {"id": "o1", "side": "buy", "quantity": 10}, {"fill_price": 185.0, "quantity": 10})
        outcome = calculate_outcome(record, exit_price=190.0, exit_reason="take_profit")
        self.assertEqual(outcome["pnl"], 50.0)
        self.assertEqual(outcome["win_loss"], "win")
        self.assertEqual(outcome["r_multiple"], 1.0)


class TestReplayStorePersistence(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.temp_dir.name) / "records.jsonl"
        self.store = ReplayStore(path=self.store_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_and_reload(self):
        record = build_replay_record_from_plan(_stock_plan())
        self.store.save(record)
        reloaded = ReplayStore(path=self.store_path)
        loaded = reloaded.get(record["id"])
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded["plan_id"], "plan-stock-1")
        self.assertEqual(loaded["market"]["instrument_id"], "AAPL")

    def test_list_by_instrument(self):
        self.store.save(build_replay_record_from_plan(_stock_plan()))
        self.store.save(build_replay_record_from_plan(_futures_plan(id="plan-futures-2")))
        es_items = self.store.list_by_instrument("ESZ26")
        aapl_items = self.store.list_by_instrument("AAPL")
        self.assertEqual(len(es_items), 1)
        self.assertEqual(len(aapl_items), 1)


class TestReplayMemoryLifecycle(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.temp_dir.name) / "records.jsonl"
        self.store = ReplayStore(path=self.store_path)
        self.memory = ReplayMemory(store=self.store)
        self.plans = TradePlanManager(record_replay=False)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_plan_to_close_lifecycle(self):
        plan = self.plans.create_plan({
            "symbol": "AAPL",
            "direction": "LONG",
            "thesis": "Breakout",
            "entry": {"price": 185},
            "stop_loss": {"price": 180},
            "target": {"price": 195},
            "quantity": 10,
        })
        created = self.memory.on_plan_created(plan)
        self.assertEqual(created["status"], "planned")

        order = {"id": "order-1", "created_at": "2026-08-19T10:00:00", "side": "buy", "quantity": 10}
        submitted = self.memory.on_order_submitted(plan["id"], order["id"], order)
        assert submitted is not None
        self.assertEqual(submitted["status"], "submitted")

        filled = self.memory.on_entry_fill(
            {"id": "order-1", "side": "buy", "quantity": 10, "trade_plan": {"plan_id": plan["id"]}},
            {"fill_price": 185.0, "quantity": 10},
        )
        assert filled is not None
        self.assertEqual(filled["status"], "filled")
        self.assertEqual(filled["execution"]["entry"]["price"], 185.0)

        closed = self.memory.on_exit_fill(
            {"id": "exit-1", "parent_id": "order-1", "side": "sell", "quantity": 10},
            {"fill_price": 190.0, "quantity": 10},
            exit_reason="take_profit",
        )
        assert closed is not None
        self.assertEqual(closed["status"], "closed")
        self.assertEqual(closed["outcome"]["win_loss"], "win")

        reloaded = ReplayStore(path=self.store_path)
        persisted = reloaded.get(closed["id"])
        assert persisted is not None
        self.assertEqual(persisted["outcome"]["pnl"], 50.0)

    def test_futures_lifecycle_preserves_continuous_id(self):
        plan = self.plans.create_plan({
            "instrument_id": "ESZ26",
            "direction": "LONG",
            "thesis": "Trend",
            "entry": {"price": 5000},
            "stop_loss": {"price": 4990},
            "target": {"price": 5020},
            "contracts": 1,
            "account_balance": 100000,
            "risk_percent": 1,
        })
        record = self.memory.on_plan_created(plan)
        self.assertEqual(record["market"]["continuous_id"], "ES")


class TestTradePlanReplayIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.temp_dir.name) / "records.jsonl"
        self.store = ReplayStore(path=self.store_path)
        self.memory = ReplayMemory(store=self.store)

    def tearDown(self):
        self.temp_dir.cleanup()

    @unittest.mock.patch("src.replay.replay_memory.get_replay_memory")
    def test_create_plan_initializes_record(self, mock_get_memory):
        mock_get_memory.return_value = self.memory
        mgr = TradePlanManager(record_replay=True)
        plan = mgr.create_plan({
            "symbol": "MSFT",
            "direction": "LONG",
            "thesis": "Pullback",
            "entry": {"price": 400},
            "stop_loss": {"price": 390},
            "target": {"price": 420},
            "quantity": 5,
        })
        record = self.store.get_by_plan_id(plan["id"])
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["status"], "planned")
        self.assertEqual(record["market"]["instrument_id"], "MSFT")
        self.assertNotIn("continuous_id", record["market"])


if __name__ == "__main__":
    unittest.main()
