"""Tests for Phase 14A instrument abstraction."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.market.asset_class import AssetClass
from src.market.contract import build_contract, parse_contract_code
from src.market.instrument import (
    detect_asset_class,
    list_instruments,
    normalize_symbol,
    resolve_instrument,
)
from src.market.session_rules import get_session_rules


class TestSymbolNormalization(unittest.TestCase):
    def test_forex_slash_format(self):
        self.assertEqual(normalize_symbol("EUR/USD"), "EURUSD")
        self.assertEqual(normalize_symbol("gbp/usd"), "GBPUSD")

    def test_stock_unchanged(self):
        self.assertEqual(normalize_symbol("AAPL"), "AAPL")


class TestAssetClassDetection(unittest.TestCase):
    def test_detect_forex(self):
        self.assertEqual(detect_asset_class("EUR/USD"), AssetClass.FOREX)

    def test_detect_futures_contract(self):
        self.assertEqual(detect_asset_class("ESZ26"), AssetClass.FUTURES)

    def test_detect_stock(self):
        self.assertEqual(detect_asset_class("AAPL"), AssetClass.STOCK)


class TestInstrumentModel(unittest.TestCase):
    def test_stock_instrument(self):
        inst = resolve_instrument("AAPL")
        self.assertEqual(inst.asset_class, AssetClass.STOCK)
        self.assertEqual(inst.exchange, "NASDAQ")
        self.assertEqual(inst.tick_size, 0.01)
        self.assertIsNotNone(inst.session)

    def test_forex_instrument(self):
        inst = resolve_instrument("EUR/USD")
        self.assertEqual(inst.symbol, "EURUSD")
        self.assertEqual(inst.display_symbol(), "EUR/USD")
        self.assertEqual(inst.asset_class, AssetClass.FOREX)
        self.assertEqual(inst.pip_size, 0.0001)
        self.assertTrue(inst.session.is_24h)

    def test_forex_pip_math(self):
        inst = resolve_instrument("EURUSD")
        self.assertAlmostEqual(inst.pips_between(1.08500, 1.08600), 10.0)
        self.assertAlmostEqual(inst.pip_value(), 10.0)

    def test_usdjpy_pip_size(self):
        inst = resolve_instrument("USDJPY")
        self.assertEqual(inst.pip_size, 0.01)

    def test_futures_contract_instrument(self):
        inst = resolve_instrument("ESZ26")
        self.assertEqual(inst.asset_class, AssetClass.FUTURES)
        self.assertEqual(inst.contract, "ESZ26")
        self.assertEqual(inst.contract_month, "2026-12")
        self.assertEqual(inst.point_value, 50.0)
        self.assertEqual(inst.tick_value, 12.50)

    def test_instrument_to_dict(self):
        data = resolve_instrument("ESZ26").to_dict()
        self.assertEqual(data["asset_class"], "FUTURES")
        self.assertIn("session", data)


class TestFuturesContract(unittest.TestCase):
    def test_parse_esz26(self):
        contract = parse_contract_code("ESZ26")
        self.assertEqual(contract.root, "ES")
        self.assertEqual(contract.contract_month, "2026-12")

    def test_futures_pnl(self):
        contract = parse_contract_code("ESZ26")
        self.assertEqual(contract.pnl(5000.00, 5005.00, contracts=1), 250.0)
        self.assertEqual(contract.pnl(5000.00, 5005.00, contracts=2), 500.0)

    def test_build_contract(self):
        contract = build_contract("ES", "2026-12")
        self.assertEqual(contract.contract, "ESZ26")


class TestSessionRules(unittest.TestCase):
    def test_stock_nyse_not_24h(self):
        rules = get_session_rules(AssetClass.STOCK, "NYSE")
        self.assertFalse(rules.is_24h)
        self.assertEqual(rules.venue, "NYSE")

    def test_forex_24h(self):
        rules = get_session_rules(AssetClass.FOREX, "FX")
        self.assertTrue(rules.is_24h)

    def test_futures_globex(self):
        rules = get_session_rules(AssetClass.FUTURES, "CME")
        self.assertEqual(rules.venue, "CME_GLOBEX")


class TestInstrumentCatalog(unittest.TestCase):
    def test_list_all(self):
        items = list_instruments()
        classes = {i["asset_class"] for i in items}
        self.assertIn("STOCK", classes)
        self.assertIn("FOREX", classes)
        self.assertIn("FUTURES", classes)

    def test_list_forex_only(self):
        items = list_instruments(AssetClass.FOREX)
        self.assertTrue(all(i["asset_class"] == "FOREX" for i in items))
        self.assertGreaterEqual(len(items), 4)


if __name__ == "__main__":
    unittest.main()
