"""Tests for Phase 14C futures contract mechanics."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.market.asset_class import AssetClass
from src.market.contract import parse_contract_code
from src.market.contract_specs import FUTURES_CONTRACTS, get_contract_spec
from src.market.futures import (
    calculate_futures_size,
    margin_required,
    pnl,
    risk_amount,
    tick_distance,
    tick_value,
)
from src.models.position import Position, PositionUnit
from src.trading.futures_risk import mixed_asset_max_loss, validate_futures_margin, validate_futures_risk
from src.trading.risk import max_loss
from src.trading.trade_plan import TradePlanManager


class TestContractSpecs(unittest.TestCase):
    def test_catalog_has_core_contracts(self):
        for root in ("ES", "NQ", "CL", "GC"):
            self.assertIn(root, FUTURES_CONTRACTS)

    def test_es_spec(self):
        spec = get_contract_spec("ES")
        self.assertEqual(spec["tick_size"], 0.25)
        self.assertEqual(spec["tick_value"], 12.50)
        self.assertEqual(spec["point_value"], 50.0)


class TestEsTickMath(unittest.TestCase):
    def test_tick_distance(self):
        self.assertEqual(tick_distance(5000.00, 4995.00, "ESZ26"), 20.0)

    def test_risk_two_contracts(self):
        self.assertEqual(risk_amount(5000.00, 4995.00, 2, "ESZ26"), 500.0)

    def test_pnl_five_points(self):
        self.assertEqual(pnl(5000.00, 5005.00, 1, "ESZ26"), 250.0)


class TestNqTickMath(unittest.TestCase):
    def test_nq_tick_value(self):
        self.assertEqual(tick_value("NQZ26"), 5.0)

    def test_nq_risk(self):
        # 4 points = 16 ticks × $5 = $80 per contract
        self.assertEqual(risk_amount(18000.00, 17996.00, 1, "NQZ26"), 80.0)


class TestContractParsing(unittest.TestCase):
    def test_parse_esz26(self):
        c = parse_contract_code("ESZ26")
        self.assertEqual(c.contract, "ESZ26")
        self.assertEqual(c.margin, 13200)

    def test_margin_required(self):
        self.assertEqual(margin_required(2, "ESZ26"), 26400.0)


class TestFuturesPositionSizing(unittest.TestCase):
    def test_size_from_account_risk(self):
        result = calculate_futures_size(
            account_balance=50_000,
            risk_percent=1.0,
            entry=5000.00,
            stop=4995.00,
            instrument_id="ESZ26",
        )
        self.assertEqual(result["contracts"], 2)
        self.assertEqual(result["risk_amount"], 500.0)
        self.assertEqual(result["tick_risk"], 20.0)


class TestFuturesRiskValidation(unittest.TestCase):
    def test_margin_validation_ok(self):
        result = validate_futures_margin(1, "ESZ26", 50_000)
        self.assertTrue(result["within_margin"])

    def test_margin_validation_fail(self):
        result = validate_futures_margin(10, "ESZ26", 50_000)
        self.assertFalse(result["within_margin"])
        self.assertTrue(result["warnings"])

    def test_validate_futures_risk(self):
        plan = {
            "instrument_id": "ESZ26",
            "entry": {"price": 5000},
            "stop_loss": {"price": 4995},
            "contracts": 2,
            "risk_amount": 500,
            "tick_risk": 20,
        }
        result = validate_futures_risk(plan, 50_000)
        self.assertTrue(result["within_limit"])


class TestMixedAssetRisk(unittest.TestCase):
    def test_forex_max_loss(self):
        loss = mixed_asset_max_loss(1.0850, 1.0800, 1.0, AssetClass.FOREX, "EURUSD")
        self.assertEqual(loss, 500.0)

    def test_futures_max_loss(self):
        loss = mixed_asset_max_loss(5000, 4995, 2, AssetClass.FUTURES, "ESZ26")
        self.assertEqual(loss, 500.0)

    def test_stock_max_loss_via_risk_module(self):
        loss = max_loss(185, 180, 10, AssetClass.STOCK, "AAPL")
        self.assertEqual(loss, 50.0)


class TestFuturesTradePlan(unittest.TestCase):
    def setUp(self):
        self.mgr = TradePlanManager()

    def test_futures_plan_with_risk_sizing(self):
        plan = self.mgr.create_plan({
            "symbol": "ESZ26",
            "direction": "LONG",
            "thesis": "Trend continuation",
            "entry": {"price": 5000.00},
            "stop_loss": {"price": 4995.00},
            "target": {"price": 5010.00},
            "account_balance": 50_000,
            "risk_percent": 1.0,
        })
        self.assertEqual(plan["asset_class"], "FUTURES")
        self.assertEqual(plan["instrument_id"], "ESZ26")
        self.assertEqual(plan["contracts"], 2)
        self.assertEqual(plan["quantity_unit"], "contracts")
        self.assertEqual(plan["stop_unit"], "ticks")
        self.assertEqual(plan["tick_risk"], 20.0)
        self.assertEqual(plan["risk_amount"], 500.0)


class TestPositionUnits(unittest.TestCase):
    def test_shares_position(self):
        pos = Position("AAPL", AssetClass.STOCK, "LONG", 185.0, 100, PositionUnit.SHARES)
        self.assertEqual(pos.unit, PositionUnit.SHARES)

    def test_lots_position(self):
        pos = Position("EURUSD", AssetClass.FOREX, "LONG", 1.085, 1.0, PositionUnit.LOTS)
        self.assertEqual(pos.unit, PositionUnit.LOTS)

    def test_contracts_position(self):
        pos = Position("ESZ26", AssetClass.FUTURES, "LONG", 5000.0, 2, PositionUnit.CONTRACTS)
        self.assertEqual(pos.unit, PositionUnit.CONTRACTS)

    def test_from_futures_trade_plan(self):
        plan = {
            "symbol": "ESZ26",
            "asset_class": "FUTURES",
            "instrument_id": "ESZ26",
            "direction": "LONG",
            "entry": {"price": 5000},
            "stop_loss": {"price": 4995},
            "target": {"price": 5010},
            "contracts": 2,
        }
        pos = Position.from_trade_plan(plan)
        self.assertEqual(pos.quantity_unit, PositionUnit.CONTRACTS)
        self.assertEqual(pos.quantity, 2.0)


if __name__ == "__main__":
    unittest.main()
