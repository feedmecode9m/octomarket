"""Tests for forex pip, lot, and position sizing."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.market.forex import (
    lot_to_units,
    pip_distance,
    pip_size,
    pip_value,
    units_to_lots,
)
from src.models.position import Position
from src.trading.position_sizing import calculate_forex_size
from src.trading.risk import account_risk_percent, max_loss, reward_ratio, validate_forex_risk
from src.trading.trade_plan import TradePlanManager


class TestForexMath(unittest.TestCase):
    def test_pip_size_eurusd(self):
        self.assertEqual(pip_size("EURUSD"), 0.0001)
        self.assertEqual(pip_size("EUR/USD"), 0.0001)

    def test_pip_size_usdjpy(self):
        self.assertEqual(pip_size("USDJPY"), 0.01)

    def test_pip_distance(self):
        self.assertAlmostEqual(pip_distance(1.0850, 1.0800, "EURUSD"), 50.0)

    def test_pip_value_eurusd(self):
        self.assertAlmostEqual(pip_value("EURUSD", 1.0850, lots=1.0), 10.0)

    def test_lot_to_units(self):
        self.assertEqual(lot_to_units(1.0), 100_000)
        self.assertEqual(lot_to_units(0.1), 10_000)
        self.assertAlmostEqual(units_to_lots(100_000), 1.0)


class TestForexPositionSizing(unittest.TestCase):
    def test_standard_lot_from_risk(self):
        """$50k account, 1% risk, 50 pip stop → 1 standard lot."""
        result = calculate_forex_size(
            account_balance=50_000,
            risk_percent=1.0,
            entry=1.0850,
            stop=1.0800,
            symbol="EURUSD",
        )
        self.assertEqual(result["lots"], 1.0)
        self.assertEqual(result["units"], 100_000)
        self.assertEqual(result["risk_amount"], 500.0)
        self.assertEqual(result["pip_risk"], 50.0)

    def test_rejects_non_forex(self):
        with self.assertRaises(ValueError):
            calculate_forex_size(10_000, 1.0, 185, 180, "AAPL")


class TestForexRisk(unittest.TestCase):
    def test_max_loss_forex(self):
        loss = max_loss(1.0850, 1.0800, 1.0, __import__("src.market.asset_class", fromlist=["AssetClass"]).AssetClass.FOREX, "EURUSD")
        self.assertEqual(loss, 500.0)

    def test_reward_ratio(self):
        self.assertEqual(reward_ratio(500, 1000), 2.0)

    def test_account_risk_percent(self):
        self.assertEqual(account_risk_percent(500, 50_000), 1.0)

    def test_validate_forex_risk_within_limit(self):
        plan = {
            "entry": {"price": 1.0850},
            "stop_loss": {"price": 1.0800},
            "position_lots": 1.0,
            "instrument_id": "EURUSD",
            "risk_amount": 500,
        }
        result = validate_forex_risk(plan, 50_000, max_risk_percent=2.0)
        self.assertTrue(result["within_limit"])
        self.assertEqual(result["account_risk_percent"], 1.0)


class TestForexTradePlan(unittest.TestCase):
    def setUp(self):
        self.mgr = TradePlanManager()

    def test_forex_plan_with_risk_sizing(self):
        plan = self.mgr.create_plan({
            "symbol": "EUR/USD",
            "direction": "LONG",
            "thesis": "Pullback to support",
            "entry": {"price": 1.08500},
            "stop_loss": {"price": 1.08000},
            "target": {"price": 1.09500},
            "account_balance": 50_000,
            "risk_percent": 1.0,
        })
        self.assertEqual(plan["asset_class"], "FOREX")
        self.assertEqual(plan["instrument_id"], "EURUSD")
        self.assertEqual(plan["position_lots"], 1.0)
        self.assertEqual(plan["pip_risk"], 50.0)
        self.assertEqual(plan["reward_pips"], 100.0)
        self.assertEqual(plan["risk_reward"], 2.0)
        self.assertEqual(plan["risk_amount"], 500.0)
        self.assertEqual(plan["quantity_unit"], "lots")

    def test_stock_plan_unchanged(self):
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
        self.assertEqual(plan["risk_reward"], 2.0)


class TestPositionModel(unittest.TestCase):
    def test_from_forex_trade_plan(self):
        plan = {
            "symbol": "EURUSD",
            "asset_class": "FOREX",
            "instrument_id": "EURUSD",
            "direction": "LONG",
            "entry": {"price": 1.085},
            "stop_loss": {"price": 1.08},
            "target": {"price": 1.095},
            "position_lots": 0.5,
        }
        pos = Position.from_trade_plan(plan)
        self.assertEqual(pos.quantity_unit, "lots")
        self.assertEqual(pos.quantity, 0.5)
        self.assertEqual(pos.instrument_id, "EURUSD")


if __name__ == "__main__":
    unittest.main()
