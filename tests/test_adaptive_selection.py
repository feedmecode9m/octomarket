"""Tests for Gate 16D — Adaptive Strategy Selection (decision support)."""

import os
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.strategies.context import StrategyContext


def _closes_trend(n=80, base=5000.0, step=3.0):
    return [base + step * i for i in range(n)]


def _closes_range(n=80, base=1.0850):
    closes = []
    for i in range(n):
        cycle = i % 16
        offset = 0.00025 * cycle if cycle < 8 else 0.00025 * (15 - cycle)
        closes.append(base + offset)
    return closes


def _context(instrument_id, asset_class, closes, symbol=None):
    highs = [c + abs(c) * 0.002 + 0.5 for c in closes]
    lows = [c - abs(c) * 0.002 - 0.5 for c in closes]
    opens = list(closes)
    return StrategyContext(
        instrument_id=instrument_id,
        asset_class=asset_class,
        symbol=symbol or instrument_id,
        timeframe="1d",
        period="3mo",
        closes=closes,
        opens=opens,
        highs=highs,
        lows=lows,
        volumes=[10000] * len(closes),
        current_price=closes[-1],
        bar_count=len(closes),
        continuous_id="ES" if asset_class == "FUTURES" else None,
    )


def _regime_bucket(trade_count, pf, decision, level):
    from src.research.confidence import assess_sample_confidence

    return {
        "trade_count": trade_count,
        "profit_factor": pf,
        "average_decision_score": decision,
        "confidence": assess_sample_confidence(trade_count),
        "confidence_level": level,
    }


def _strategy_report(**kwargs):
    payload = {
        "schema_version": 3,
        "report_type": "strategy",
        "report_id": kwargs.get("report_id", "r1"),
        "strategy_id": "futures_trend",
        "strategy_name": "Trend Following",
        "instrument_id": "ESZ26",
        "asset_class": "FUTURES",
        "trade_count": 220,
        "profit_factor": 1.55,
        "average_decision_score": 84,
        "confidence": {"confidence_level": "high", "trade_count": 220, "warnings": []},
        "gross_metrics": {"profit_factor_gross": 1.72},
        "regime_performance": {
            "trending": _regime_bucket(220, 1.72, 85, "high"),
        },
        "record_ids": [f"rec-{i}" for i in range(12)],
        "best_conditions": ["Best trend state: aligned"],
    }
    payload.update(kwargs)
    return payload


def _walk_forward(strategy_id, research_pf, validation_pf, oos_pf):
    return {
        "report_type": "walk_forward",
        "strategy_id": strategy_id,
        "windows": [
            {"window": {"name": "research"}, "report": {"profit_factor": research_pf, "trade_count": 80}},
            {"window": {"name": "validation"}, "report": {"profit_factor": validation_pf, "trade_count": 40}},
            {"window": {"name": "out_of_sample"}, "report": {"profit_factor": oos_pf, "trade_count": 40}},
        ],
    }


class TestMarketContext(unittest.TestCase):
    def test_es_trend_condition(self):
        from src.research.market_context import context_from_strategy

        ctx = _context("ESZ26", "FUTURES", _closes_trend())
        detected = context_from_strategy(ctx)
        self.assertEqual(detected["trend_state"], "trending")
        self.assertIn("trending", detected["active_regimes"])
        self.assertEqual(detected["asset_class"], "FUTURES")
        self.assertIn("data_quality", detected)

    def test_eurusd_range_condition(self):
        from src.research.market_context import context_from_strategy

        ctx = _context("EURUSD", "FOREX", _closes_range(), symbol="EURUSD")
        detected = context_from_strategy(ctx)
        self.assertEqual(detected["trend_state"], "ranging")
        self.assertIn("ranging", detected["active_regimes"])


class TestDataQuality(unittest.TestCase):
    def test_complete_daily_series(self):
        from src.research.data_quality import assess_ohlcv_quality

        df = pd.DataFrame(
            {"Close": list(range(20))},
            index=pd.bdate_range("2024-01-01", periods=20),
        )
        quality = assess_ohlcv_quality(df, instrument_id="ES", interval="1d")
        self.assertEqual(quality["bars"], 20)
        self.assertEqual(quality["missing_bars"], 0)
        self.assertIn(quality["data_quality"], ("complete", "thin"))


class TestDegradation(unittest.TestCase):
    def test_oos_degradation_flagged_not_rejected(self):
        from src.research.degradation import assess_performance_degradation

        result = assess_performance_degradation(_walk_forward("futures_trend", 1.70, 1.40, 1.05)["windows"])
        self.assertTrue(result["detected"])
        self.assertTrue(any("degradation" in w.lower() for w in result["warnings"]))


class TestAdaptiveSelection(unittest.TestCase):
    def test_es_trend_recommends_trend_family(self):
        from src.research.market_context import context_from_strategy
        from src.research.selection import AdaptiveStrategySelector

        context = context_from_strategy(_context("ESZ26", "FUTURES", _closes_trend()))
        selector = AdaptiveStrategySelector()
        result = selector.recommend(
            "ESZ26",
            market_context=context,
            strategy_reports=[
                _strategy_report(),
                _strategy_report(
                    report_id="r2",
                    strategy_id="futures_breakout",
                    strategy_name="Breakout",
                    trade_count=160,
                    profit_factor=1.42,
                    average_decision_score=81,
                    regime_performance={"trending": _regime_bucket(160, 1.60, 82, "high")},
                    confidence={"confidence_level": "high", "trade_count": 160, "warnings": []},
                ),
            ],
            walk_forward_reports=[],
        )
        rec = result["recommendation"]
        self.assertEqual(rec["strategy_family"], "trend_following")
        self.assertTrue(result["decision_support_only"])
        self.assertIn("supporting_records", rec)
        self.assertNotIn("winner", str(result).lower())

    def test_eurusd_range_recommends_mean_reversion(self):
        from src.research.market_context import context_from_strategy
        from src.research.selection import AdaptiveStrategySelector

        context = context_from_strategy(_context("EURUSD", "FOREX", _closes_range(), symbol="EURUSD"))
        selector = AdaptiveStrategySelector()
        result = selector.recommend(
            "EURUSD",
            market_context=context,
            strategy_reports=[
                _strategy_report(
                    report_id="fx-mr",
                    strategy_id="forex_mean_reversion",
                    strategy_name="Mean Reversion",
                    instrument_id="EURUSD",
                    asset_class="FOREX",
                    trade_count=90,
                    profit_factor=1.28,
                    average_decision_score=80,
                    confidence={"confidence_level": "high", "trade_count": 90, "warnings": []},
                    regime_performance={"ranging": _regime_bucket(90, 1.35, 80, "high")},
                ),
                _strategy_report(
                    report_id="fx-mom",
                    strategy_id="forex_momentum",
                    strategy_name="Currency Momentum",
                    instrument_id="EURUSD",
                    asset_class="FOREX",
                    trade_count=70,
                    profit_factor=1.10,
                    average_decision_score=74,
                    confidence={"confidence_level": "high", "trade_count": 70, "warnings": []},
                    regime_performance={"trending": _regime_bucket(70, 1.40, 78, "high")},
                ),
            ],
            walk_forward_reports=[],
        )
        self.assertEqual(result["recommendation"]["strategy_family"], "mean_reversion")

    def test_low_confidence_rejection(self):
        from src.research.market_context import context_from_strategy
        from src.research.selection import AdaptiveStrategySelector

        context = context_from_strategy(_context("ESZ26", "FUTURES", _closes_trend()))
        selector = AdaptiveStrategySelector()
        result = selector.recommend(
            "ESZ26",
            market_context=context,
            strategy_reports=[
                _strategy_report(
                    trade_count=5,
                    profit_factor=2.5,
                    average_decision_score=90,
                    confidence={"confidence_level": "low", "trade_count": 5, "warnings": ["tiny sample"]},
                    regime_performance={"trending": _regime_bucket(5, 2.5, 90, "low")},
                    record_ids=["a", "b", "c", "d", "e"],
                )
            ],
            walk_forward_reports=[],
        )
        self.assertIsNone(result["recommendation"]["strategy_family"])
        self.assertEqual(result["recommendation"]["confidence"], "none")
        self.assertTrue(result["rejected"])
        self.assertTrue(any("low confidence" in (r.get("reason") or "") for r in result["rejected"]))

    def test_oos_degradation_warning_on_recommendation(self):
        from src.research.market_context import context_from_strategy
        from src.research.selection import AdaptiveStrategySelector

        context = context_from_strategy(_context("ESZ26", "FUTURES", _closes_trend()))
        selector = AdaptiveStrategySelector()
        result = selector.recommend(
            "ESZ26",
            market_context=context,
            strategy_reports=[_strategy_report()],
            walk_forward_reports=[_walk_forward("futures_trend", 1.70, 1.40, 1.05)],
        )
        rec = result["recommendation"]
        self.assertEqual(rec["strategy_family"], "trend_following")
        text = " ".join(rec["warnings"]).lower()
        self.assertIn("degradation", text)


class TestRegimeSampleConfidence(unittest.TestCase):
    def test_regime_bucket_includes_confidence(self):
        from src.research.regime import aggregate_regime_performance

        records = []
        for i in range(12):
            records.append({
                "id": f"r{i}",
                "status": "closed",
                "market": {"instrument_id": "ESZ26", "asset_class": "FUTURES"},
                "decision_context": {
                    "market_snapshot": {
                        "price": {"current": 5000, "volatility": {"last_bar_range": 5}},
                        "indicators": {"latest": {"SMA20": 4990, "RSI": 58}},
                    }
                },
                "trade_intent": {
                    "direction": "LONG",
                    "entry": {"price": 5000},
                    "stop_loss": {"price": 4990},
                    "target": {"price": 5020},
                    "risk_reward": 2.0,
                },
                "outcome": {"pnl": 100, "win_loss": "win"},
                "scoring": {
                    "decision_score": 82,
                    "outcome_score": 70,
                    "dimensions": {
                        "trend_alignment": {"score": 80, "reasons_positive": ["Price aligned above SMA20"]},
                        "volatility_context": {"score": 75, "reasons_positive": ["Stop distance respected recent bar volatility."]},
                    },
                },
            })
        perf = aggregate_regime_performance(records)
        self.assertIn("trending", perf)
        self.assertEqual(perf["trending"]["confidence_level"], "moderate")
        self.assertIn("confidence", perf["trending"])


if __name__ == "__main__":
    unittest.main()
