"""Tests for Phase 15F pattern memory and performance queries."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.market.asset_class import AssetClass
from src.replay.pattern_features import extract_pattern_features
from src.replay.pattern_service import PatternService
from src.replay.pattern_store import PatternStore
from src.replay.replay_record import apply_exit_fill
from src.replay.replay_store import ReplayStore
from src.replay.scoring_service import apply_scoring


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


def _closed_record(
    record_id: str,
    plan_id: str,
    asset_class: str,
    plan: dict,
    market: dict,
    *,
    exit_price=None,
) -> dict:
    record = {
        "id": record_id,
        "status": "filled",
        "plan_id": plan_id,
        "mode": "live_paper",
        "market": market,
        "decision_context": {"market_snapshot": _snapshot(asset_class), "timeframe": "1d"},
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
    exit_px = exit_price if exit_price is not None else plan.get("_exit_price", plan["target"]["price"])
    closed = apply_exit_fill(
        record,
        {"id": f"exit-{record_id}", "side": "sell"},
        {"fill_price": exit_px, "quantity": plan.get("quantity", 1)},
        exit_reason="take_profit",
    )
    return apply_scoring(closed)


def _stock_plan(**overrides):
    base = {
        "id": "plan-aapl",
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
        "_exit_price": 192.0,
    }
    base.update(overrides)
    return base


class TestPatternMemory(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        base = Path(self._temp.name)
        self.record_store = ReplayStore(path=base / "records.jsonl")
        self.pattern_store = PatternStore(path=base / "patterns.jsonl")
        self.service = PatternService(
            pattern_store=self.pattern_store,
            record_store=self.record_store,
        )

    def tearDown(self):
        self._temp.cleanup()

    def _persist_and_index(self, record):
        self.record_store.save(record)
        return self.service.index_record(record)

    def test_aapl_similar_stock_setups(self):
        market = {"instrument_id": "AAPL", "asset_class": "STOCK", "symbol": "AAPL", "session": {"venue": "NYSE"}}
        current = _closed_record("rec-current", "plan-current", AssetClass.STOCK.value, _stock_plan(id="plan-current"), market)
        peer1 = _closed_record("rec-peer-1", "plan-peer-1", AssetClass.STOCK.value, _stock_plan(id="plan-peer-1"), market)
        peer2 = _closed_record("rec-peer-2", "plan-peer-2", AssetClass.STOCK.value, _stock_plan(id="plan-peer-2", _exit_price=190.0), market)
        other = _closed_record(
            "rec-msft",
            "plan-msft",
            AssetClass.STOCK.value,
            _stock_plan(id="plan-msft", symbol="MSFT", instrument_id="MSFT"),
            {"instrument_id": "MSFT", "asset_class": "STOCK", "symbol": "MSFT", "session": {"venue": "NYSE"}},
        )

        for rec in (peer1, peer2, other):
            self._persist_and_index(rec)
        self.record_store.save(current)

        result = self.service.find_similar(current, limit=5)
        self.assertEqual(result["match_count"], 2)
        self.assertEqual(result["summary"]["trade_count"], 2)
        matched_ids = {m["record_id"] for m in result["matches"]}
        self.assertIn("rec-peer-1", matched_ids)
        self.assertIn("rec-peer-2", matched_ids)
        self.assertNotIn("rec-msft", matched_ids)
        self.assertIsNotNone(result["summary"]["average_decision_score"])

    def test_eurusd_session_filtering(self):
        market = {
            "instrument_id": "EURUSD",
            "asset_class": "FOREX",
            "symbol": "EURUSD",
            "session": {"venue": "FX", "is_24h": True},
        }
        plan = {
            "id": "plan-fx",
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
            "_exit_price": 1.0920,
        }
        record = _closed_record("rec-fx", "plan-fx", AssetClass.FOREX.value, plan, market)
        pattern = self._persist_and_index(record)

        self.assertEqual(pattern["market"]["session_venue"], "FX")
        query = self.service.query({"instrument_id": "EURUSD", "session_venue": "FX"})
        self.assertEqual(query["match_count"], 1)
        self.assertEqual(query["matches"][0]["record_id"], "rec-fx")

        empty = self.service.query({"instrument_id": "EURUSD", "session_venue": "NYSE"})
        self.assertEqual(empty["match_count"], 0)
        self.assertEqual(empty["summary"]["trade_count"], 0)

    def test_es_continuous_identity_preserved(self):
        market = {
            "instrument_id": "ESZ26",
            "asset_class": "FUTURES",
            "symbol": "ES",
            "continuous_id": "ES",
            "session": {"venue": "CME_GLOBEX"},
        }
        plan = {
            "id": "plan-es",
            "symbol": "ES",
            "instrument_id": "ESZ26",
            "direction": "LONG",
            "thesis": "Trend continuation",
            "entry": {"price": 5000.0},
            "stop_loss": {"price": 4990.0},
            "target": {"price": 5020.0},
            "contracts": 2,
            "quantity": 2,
            "tick_risk": 10,
            "risk_reward": 2.0,
            "risk_amount": 1000.0,
            "_exit_price": 5015.0,
        }
        current = _closed_record("rec-es-current", "plan-es-current", AssetClass.FUTURES.value, plan, market)
        peer_market = dict(market)
        peer_market["instrument_id"] = "ESH26"
        peer = _closed_record(
            "rec-es-peer",
            "plan-es-peer",
            AssetClass.FUTURES.value,
            {**plan, "id": "plan-es-peer", "instrument_id": "ESH26"},
            peer_market,
        )
        self._persist_and_index(peer)
        self.record_store.save(current)

        pattern = extract_pattern_features(current)
        self.assertEqual(pattern["market"]["continuous_id"], "ES")

        result = self.service.find_similar(current, limit=5)
        self.assertEqual(result["match_count"], 1)
        self.assertEqual(result["criteria"]["continuous_id"], "ES")

    def test_high_quality_decision_retrievable(self):
        market = {"instrument_id": "AAPL", "asset_class": "STOCK", "symbol": "AAPL", "session": {"venue": "NYSE"}}
        good = _closed_record("rec-good", "plan-good", AssetClass.STOCK.value, _stock_plan(id="plan-good"), market)
        self._persist_and_index(good)

        query = self.service.query({"instrument_id": "AAPL", "min_decision_score": 70})
        self.assertGreaterEqual(query["match_count"], 1)
        self.assertGreaterEqual(query["matches"][0]["decision"]["decision_score"], 70)

    def test_poor_decision_retrievable(self):
        market = {"instrument_id": "AAPL", "asset_class": "STOCK", "symbol": "AAPL", "session": {"venue": "NYSE"}}
        bad_plan = _stock_plan(
            id="plan-bad",
            thesis="",
            entry={"price": 200.0},
            stop_loss={"price": 205.0},
            target={"price": 195.0},
            risk_reward=0.5,
            _exit_price=198.0,
        )
        bad = _closed_record("rec-bad", "plan-bad", AssetClass.STOCK.value, bad_plan, market)
        bad = apply_scoring(bad)
        self._persist_and_index(bad)

        query = self.service.query({"instrument_id": "AAPL", "max_decision_score": 65})
        self.assertGreaterEqual(query["match_count"], 1)
        self.assertLessEqual(query["matches"][0]["decision"]["decision_score"], 65)
        self.assertTrue(bad["scoring"]["decision_score"] < 65)

    def test_no_matching_pattern_safe_empty(self):
        market = {"instrument_id": "AAPL", "asset_class": "STOCK", "symbol": "AAPL", "session": {"venue": "NYSE"}}
        current = _closed_record("rec-lone", "plan-lone", AssetClass.STOCK.value, _stock_plan(id="plan-lone"), market)
        self.record_store.save(current)

        result = self.service.find_similar(current, limit=5)
        self.assertEqual(result["match_count"], 0)
        self.assertEqual(result["summary"]["trade_count"], 0)
        self.assertIsNone(result["summary"]["average_r_multiple"])
        self.assertIsNone(result["summary"]["average_decision_score"])

    def test_pattern_index_does_not_copy_full_record(self):
        market = {"instrument_id": "AAPL", "asset_class": "STOCK", "symbol": "AAPL", "session": {"venue": "NYSE"}}
        record = _closed_record("rec-index", "plan-index", AssetClass.STOCK.value, _stock_plan(id="plan-index"), market)
        pattern = self._persist_and_index(record)

        self.assertEqual(pattern["record_id"], "rec-index")
        self.assertNotIn("trade_intent", pattern)
        self.assertNotIn("decision_context", pattern)
        self.assertNotIn("execution", pattern)
        self.assertIn("market", pattern)
        self.assertIn("decision", pattern)
        self.assertIn("outcome", pattern)

    def test_winners_vs_losers_query(self):
        market = {"instrument_id": "AAPL", "asset_class": "STOCK", "symbol": "AAPL", "session": {"venue": "NYSE"}}
        winner = _closed_record("rec-win", "plan-win", AssetClass.STOCK.value, _stock_plan(id="plan-win"), market)
        loser = _closed_record(
            "rec-loss",
            "plan-loss",
            AssetClass.STOCK.value,
            _stock_plan(id="plan-loss"),
            market,
            exit_price=181.0,
        )
        self._persist_and_index(winner)
        self._persist_and_index(loser)

        winners = self.service.query({"instrument_id": "AAPL", "winners_only": True})
        losers = self.service.query({"instrument_id": "AAPL", "losers_only": True})
        self.assertEqual(winners["match_count"], 1)
        self.assertEqual(losers["match_count"], 1)
        self.assertEqual(winners["matches"][0]["outcome"]["win_loss"], "win")
        self.assertEqual(losers["matches"][0]["outcome"]["win_loss"], "loss")


if __name__ == "__main__":
    unittest.main()
