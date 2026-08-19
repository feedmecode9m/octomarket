"""Tests for technical indicator calculations."""

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.charting.indicator_models import BollingerResult, MacdResult, SeriesResult
from src.charting.indicators import (
    compute_bollinger,
    compute_ema,
    compute_indicator,
    compute_indicators_for_candles,
    compute_macd,
    compute_rsi,
    compute_sma,
    parse_indicator_token,
    parse_indicators_query,
)


def _closes(n=50, start=100.0):
    return [start + i * 0.5 + (i % 3) * 0.2 for i in range(n)]


class TestSMA(unittest.TestCase):
    def test_sma_basic(self):
        closes = [1.0, 2.0, 3.0, 4.0, 5.0]
        values = compute_sma(closes, 3)
        self.assertEqual(len(values), 5)
        self.assertIsNone(values[0])
        self.assertIsNone(values[1])
        self.assertAlmostEqual(values[2], 2.0)
        self.assertAlmostEqual(values[4], 4.0)

    def test_sma_empty(self):
        self.assertEqual(compute_sma([], 20), [])

    def test_sma_invalid_period(self):
        with self.assertRaises(ValueError):
            compute_sma([1.0, 2.0], 0)


class TestEMA(unittest.TestCase):
    def test_ema_produces_values_after_warmup(self):
        closes = _closes(30)
        values = compute_ema(closes, 9)
        self.assertEqual(len(values), 30)
        self.assertTrue(any(v is not None for v in values))
        self.assertIsNone(values[0])

    def test_ema_presets(self):
        closes = _closes(250)
        for period in (9, 20, 50, 200):
            values = compute_ema(closes, period)
            self.assertEqual(len(values), 250)
            self.assertIsNotNone(values[-1])

    def test_ema_invalid_period(self):
        with self.assertRaises(ValueError):
            compute_ema([1.0], 5000)


class TestRSI(unittest.TestCase):
    def test_rsi_default_period(self):
        closes = _closes(40)
        values = compute_rsi(closes)
        self.assertEqual(len(values), 40)
        self.assertIsNone(values[0])
        last = values[-1]
        self.assertIsNotNone(last)
        self.assertGreaterEqual(last, 0)
        self.assertLessEqual(last, 100)

    def test_rsi_empty(self):
        self.assertEqual(compute_rsi([]), [])

    def test_rsi_invalid_period(self):
        with self.assertRaises(ValueError):
            compute_rsi([1.0, 2.0], period=-1)


class TestMACD(unittest.TestCase):
    def test_macd_structure(self):
        closes = _closes(60)
        result = compute_macd(closes)
        self.assertIsInstance(result, MacdResult)
        self.assertEqual(len(result.macd), 60)
        self.assertEqual(len(result.signal_line), 60)
        self.assertEqual(len(result.histogram), 60)
        payload = result.to_dict()
        self.assertIn("macd", payload)
        self.assertIn("signal", payload)
        self.assertIn("histogram", payload)

    def test_macd_empty(self):
        result = compute_macd([])
        self.assertEqual(result.macd, [])

    def test_macd_fast_must_be_less_than_slow(self):
        with self.assertRaises(ValueError):
            compute_macd([1.0, 2.0, 3.0], fast=26, slow=12)


class TestBollinger(unittest.TestCase):
    def test_bollinger_bands(self):
        closes = _closes(40)
        result = compute_bollinger(closes, period=20, stddev=2)
        self.assertIsInstance(result, BollingerResult)
        self.assertEqual(len(result.upper), 40)
        idx = 25
        self.assertIsNotNone(result.upper[idx])
        self.assertIsNotNone(result.middle[idx])
        self.assertIsNotNone(result.lower[idx])
        self.assertGreater(result.upper[idx], result.middle[idx])
        self.assertLess(result.lower[idx], result.middle[idx])

    def test_bollinger_empty(self):
        result = compute_bollinger([])
        self.assertEqual(result.upper, [])

    def test_bollinger_invalid_stddev(self):
        with self.assertRaises(ValueError):
            compute_bollinger([1.0, 2.0], stddev=0)


class TestIndicatorParsing(unittest.TestCase):
    def test_parse_sma20(self):
        spec = parse_indicator_token("SMA20")
        self.assertEqual(spec.indicator_type, "SMA")
        self.assertEqual(spec.period, 20)
        self.assertEqual(spec.key, "SMA20")

    def test_parse_ema9(self):
        spec = parse_indicator_token("ema9")
        self.assertEqual(spec.key, "EMA9")
        self.assertEqual(spec.period, 9)

    def test_parse_rsi(self):
        spec = parse_indicator_token("RSI")
        self.assertEqual(spec.indicator_type, "RSI")
        self.assertEqual(spec.period, 14)

    def test_parse_macd(self):
        spec = parse_indicator_token("MACD")
        self.assertEqual(spec.indicator_type, "MACD")

    def test_parse_bb(self):
        spec = parse_indicator_token("BB")
        self.assertEqual(spec.indicator_type, "BB")

    def test_parse_unknown(self):
        with self.assertRaises(ValueError):
            parse_indicator_token("VWAP")

    def test_parse_empty(self):
        with self.assertRaises(ValueError):
            parse_indicator_token("")

    def test_parse_query_dedup(self):
        specs = parse_indicators_query("SMA20,SMA20,RSI")
        self.assertEqual(len(specs), 2)
        self.assertEqual(specs[0].key, "SMA20")
        self.assertEqual(specs[1].key, "RSI")


class TestIndicatorCompute(unittest.TestCase):
    def test_compute_sma_result_format(self):
        spec = parse_indicator_token("SMA20")
        result = compute_indicator(_closes(30), spec)
        self.assertIsInstance(result, SeriesResult)
        payload = result.to_dict()
        self.assertEqual(payload["indicator"], "SMA")
        self.assertEqual(payload["period"], 20)
        self.assertEqual(len(payload["values"]), 30)

    def test_compute_indicator_empty_closes(self):
        spec = parse_indicator_token("RSI")
        result = compute_indicator([], spec)
        self.assertEqual(result.values, [])

    def test_compute_indicators_for_candles(self):
        candle_payload = {
            "symbol": "AAPL",
            "timeframe": "1d",
            "period": "5d",
            "count": 5,
            "timestamps": [f"2024-06-0{i+1}T00:00:00" for i in range(5)],
            "close": _closes(5),
        }
        out = compute_indicators_for_candles(candle_payload, "SMA20,RSI")
        self.assertEqual(out["symbol"], "AAPL")
        self.assertIn("SMA20", out["indicators"])
        self.assertIn("RSI", out["indicators"])


class TestIndicatorNumerics(unittest.TestCase):
    def test_sma_matches_numpy(self):
        closes = _closes(25)
        period = 5
        expected = np.convolve(closes, np.ones(period) / period, mode="valid")
        values = compute_sma(closes, period)
        self.assertAlmostEqual(values[-1], float(expected[-1]), places=5)


if __name__ == "__main__":
    unittest.main()
