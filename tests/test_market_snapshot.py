"""Tests for market snapshot capture (Gate 15B)."""

import json
import os
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.market.asset_class import AssetClass
from src.replay.market_snapshot import capture_market_snapshot
from src.replay.replay_record import build_replay_record_from_plan
from src.replay.replay_store import ReplayStore


def _candle_payload(symbol="AAPL", closes=None):
    closes = closes or [180.0, 182.0, 185.0, 184.0, 186.0]
    n = len(closes)
    return {
        "symbol": symbol,
        "timeframe": "1d",
        "period": "5d",
        "count": n,
        "session_capped": False,
        "cap_index": n - 1,
        "timestamps": [f"2024-06-0{i+1}T00:00:00" for i in range(n)],
        "open": [c - 1 for c in closes],
        "high": [c + 1 for c in closes],
        "low": [c - 2 for c in closes],
        "close": closes,
        "volume": [1_000_000 + i * 1000 for i in range(n)],
    }


def _chart_state(**overrides):
    base = {
        "symbol": "AAPL",
        "instrument_id": "AAPL",
        "asset_class": "STOCK",
        "display_symbol": "AAPL",
        "timeframe": "1d",
        "period": "5d",
        "zoom": {"start": None, "end": None},
        "indicators": [{"id": "i1", "type": "SMA", "period": 20, "pane": "main"}],
        "drawings": [{"id": "d1", "type": "horizontal", "price": 185.0, "label": "Resistance"}],
        "session": {"venue": "NASDAQ", "is_24h": False},
    }
    base.update(overrides)
    return base


class TestMarketSnapshotCapture(unittest.TestCase):
    @unittest.mock.patch("src.replay.market_snapshot._load_candles")
    def test_stock_snapshot(self, mock_load):
        closes = [180.0 + i * 0.5 for i in range(25)]
        mock_load.return_value = _candle_payload("AAPL", closes)
        snapshot = capture_market_snapshot(
            "AAPL",
            chart_state=_chart_state(
                indicators=[
                    {"id": "i1", "type": "SMA", "period": 20, "pane": "main"},
                    {"id": "i2", "type": "RSI", "period": 14, "pane": "sub"},
                ]
            ),
        )

        self.assertEqual(snapshot["instrument"]["instrument_id"], "AAPL")
        self.assertEqual(snapshot["instrument"]["asset_class"], "STOCK")
        self.assertNotIn("continuous_id", snapshot["instrument"])
        self.assertEqual(snapshot["price"]["current"], closes[-1])
        self.assertEqual(snapshot["structure"]["drawing_count"], 1)
        self.assertIn("SMA20", snapshot["indicators"]["latest"])
        self.assertIn("RSI", snapshot["indicators"]["latest"])

    @unittest.mock.patch("src.replay.market_snapshot._load_candles")
    def test_forex_snapshot(self, mock_load):
        mock_load.return_value = _candle_payload("EURUSD", [1.0840, 1.0850, 1.0860])
        snapshot = capture_market_snapshot(
            "EURUSD",
            chart_state=_chart_state(
                symbol="EURUSD",
                instrument_id="EURUSD",
                asset_class="FOREX",
                display_symbol="EUR/USD",
                session={"venue": "FX", "is_24h": True},
            ),
        )
        self.assertEqual(snapshot["instrument"]["asset_class"], "FOREX")
        self.assertNotIn("continuous_id", snapshot["instrument"])
        self.assertTrue(snapshot["instrument"]["session"]["is_24h"])

    @unittest.mock.patch("src.replay.market_snapshot._load_candles")
    def test_futures_snapshot_with_continuous_id(self, mock_load):
        mock_load.return_value = _candle_payload("ES", [4990.0, 5000.0, 5005.0])
        snapshot = capture_market_snapshot(
            "ESZ26",
            chart_state=_chart_state(
                symbol="ES",
                instrument_id="ESZ26",
                asset_class="FUTURES",
                display_symbol="ESZ26",
                session={"venue": "CME_GLOBEX", "is_24h": False},
            ),
        )
        self.assertEqual(snapshot["instrument"]["continuous_id"], "ES")
        self.assertEqual(snapshot["instrument"]["contract"], "ESZ26")

    @unittest.mock.patch("src.replay.market_snapshot._load_candles")
    def test_recent_candles_limited(self, mock_load):
        closes = [float(i) for i in range(30)]
        mock_load.return_value = _candle_payload("AAPL", closes)
        snapshot = capture_market_snapshot("AAPL", chart_state=_chart_state(), recent_candle_limit=10)
        recent = snapshot["price"]["recent_candles"]
        self.assertEqual(recent["count"], 10)
        self.assertEqual(recent["close"][-1], 29.0)


class TestSnapshotInReplayRecord(unittest.TestCase):
    @unittest.mock.patch("src.replay.market_snapshot._load_candles")
    def test_plan_record_embeds_snapshot(self, mock_load):
        mock_load.return_value = _candle_payload("MSFT", [400.0, 402.0, 405.0])
        plan = {
            "id": "plan-1",
            "symbol": "MSFT",
            "instrument_id": "MSFT",
            "asset_class": AssetClass.STOCK.value,
            "direction": "LONG",
            "entry": {"price": 405},
            "stop_loss": {"price": 400},
            "target": {"price": 415},
            "quantity": 5,
        }
        record = build_replay_record_from_plan(plan, chart_state=_chart_state(symbol="MSFT", instrument_id="MSFT"))
        snapshot = record["decision_context"]["market_snapshot"]
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["instrument"]["instrument_id"], "MSFT")
        self.assertEqual(record["metadata"]["schema_version"], 2)


class TestBackwardCompatiblePersistence(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.temp_dir.name) / "records.jsonl"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_legacy_record_without_snapshot_loads(self):
        legacy = {
            "id": "legacy-1",
            "status": "planned",
            "plan_id": "plan-old",
            "market": {"instrument_id": "AAPL", "asset_class": "STOCK", "symbol": "AAPL"},
            "decision_context": {
                "timeframe": "1d",
                "period": "5d",
                "captured_at": "2026-08-19T10:00:00",
                "indicators": [],
                "drawings": [],
            },
            "metadata": {"schema_version": 1, "created_at": "2026-08-19T10:00:00"},
        }
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        with self.store_path.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(legacy))
            handle.write("\n")

        store = ReplayStore(path=self.store_path)
        loaded = store.get("legacy-1")
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertNotIn("market_snapshot", loaded["decision_context"])
        self.assertEqual(loaded["metadata"]["schema_version"], 1)

    @unittest.mock.patch("src.replay.market_snapshot._load_candles")
    def test_snapshot_record_persists_and_reloads(self, mock_load):
        mock_load.return_value = _candle_payload("AAPL")
        record = build_replay_record_from_plan(
            {
                "id": "plan-new",
                "symbol": "AAPL",
                "instrument_id": "AAPL",
                "direction": "LONG",
                "entry": {"price": 185},
                "stop_loss": {"price": 180},
                "target": {"price": 195},
                "quantity": 10,
            },
            chart_state=_chart_state(),
        )
        store = ReplayStore(path=self.store_path)
        store.save(record)
        reloaded = ReplayStore(path=self.store_path).get(record["id"])
        assert reloaded is not None
        self.assertIn("market_snapshot", reloaded["decision_context"])
        self.assertEqual(
            reloaded["decision_context"]["market_snapshot"]["instrument"]["instrument_id"],
            "AAPL",
        )


if __name__ == "__main__":
    unittest.main()
