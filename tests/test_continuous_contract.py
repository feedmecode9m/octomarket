"""Tests for futures continuous contract abstraction (Gate 15.0D)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.market.continuous_contract import (
    ContinuousContract,
    continuous_id_for,
    get_active_contract,
    is_futures_root,
    resolve_continuous,
)
from src.market.instrument import resolve_instrument


class TestContinuousContractResolution(unittest.TestCase):
    def test_esz26_resolves_to_es(self):
        cc = resolve_continuous("ESZ26")
        self.assertIsNotNone(cc)
        assert cc is not None
        self.assertEqual(cc.continuous_id, "ES")
        self.assertEqual(cc.root_symbol, "ES")
        self.assertEqual(cc.exchange, "CME")
        self.assertEqual(cc.active_contract, "ESZ26")
        self.assertEqual(cc.contract_month, "2026-12")

    def test_nqz26_resolves_to_nq(self):
        cc = resolve_continuous("NQZ26")
        self.assertIsNotNone(cc)
        assert cc is not None
        self.assertEqual(cc.continuous_id, "NQ")
        self.assertEqual(cc.active_contract, "NQZ26")

    def test_clz26_resolves_to_cl(self):
        cc = resolve_continuous("CLZ26")
        self.assertIsNotNone(cc)
        assert cc is not None
        self.assertEqual(cc.continuous_id, "CL")
        self.assertEqual(cc.exchange, "NYMEX")
        self.assertEqual(cc.active_contract, "CLZ26")

    def test_gcz26_resolves_to_gc(self):
        cc = resolve_continuous("GCZ26")
        self.assertIsNotNone(cc)
        assert cc is not None
        self.assertEqual(cc.continuous_id, "GC")
        self.assertEqual(cc.exchange, "COMEX")
        self.assertEqual(cc.active_contract, "GCZ26")

    def test_different_expirations_share_continuous_identity(self):
        es_dec = resolve_continuous("ESZ26")
        es_mar = resolve_continuous("ESH27")
        self.assertIsNotNone(es_dec)
        self.assertIsNotNone(es_mar)
        assert es_dec is not None and es_mar is not None
        self.assertEqual(es_dec.continuous_id, "ES")
        self.assertEqual(es_mar.continuous_id, "ES")
        self.assertEqual(es_dec.active_contract, es_mar.active_contract)

    def test_futures_root_resolves_without_expiration_code(self):
        cc = resolve_continuous("ES")
        self.assertIsNotNone(cc)
        assert cc is not None
        self.assertEqual(cc.continuous_id, "ES")
        self.assertEqual(cc.active_contract, "ESZ26")


class TestNonFuturesUnchanged(unittest.TestCase):
    def test_stock_has_no_continuous_metadata(self):
        inst = resolve_instrument("AAPL")
        self.assertIsNone(inst.continuous_id)
        self.assertIsNone(resolve_continuous("AAPL"))
        self.assertIsNone(continuous_id_for("AAPL"))
        self.assertNotIn("continuous_id", inst.to_dict())

    def test_forex_has_no_continuous_metadata(self):
        inst = resolve_instrument("EURUSD")
        self.assertIsNone(inst.continuous_id)
        self.assertIsNone(resolve_continuous("EURUSD"))
        self.assertNotIn("continuous_id", inst.to_dict())


class TestInstrumentContinuousMetadata(unittest.TestCase):
    def test_futures_instrument_includes_continuous_id(self):
        inst = resolve_instrument("ESZ26")
        self.assertEqual(inst.continuous_id, "ES")
        self.assertEqual(inst.instrument_id, "ESZ26")
        data = inst.to_dict()
        self.assertEqual(data["continuous_id"], "ES")
        self.assertEqual(data["contract"], "ESZ26")

    def test_get_active_contract_from_catalog(self):
        active = get_active_contract("NQ")
        self.assertEqual(active.contract, "NQZ26")
        self.assertEqual(active.contract_month, "2026-12")

    def test_is_futures_root(self):
        self.assertTrue(is_futures_root("ES"))
        self.assertTrue(is_futures_root("gc"))
        self.assertFalse(is_futures_root("AAPL"))

    def test_continuous_contract_to_dict(self):
        cc = resolve_continuous("ESZ26")
        self.assertIsNotNone(cc)
        assert cc is not None
        data = cc.to_dict()
        self.assertIsInstance(cc, ContinuousContract)
        self.assertEqual(data["continuous_id"], "ES")
        self.assertEqual(data["active_contract"], "ESZ26")


if __name__ == "__main__":
    unittest.main()
