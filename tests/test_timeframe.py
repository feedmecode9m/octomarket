"""Tests for timeframe validation and normalization."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.charting.timeframe import (
    get_default_period,
    normalize_interval,
    validate_timeframe,
)


class TestTimeframe(unittest.TestCase):
    def test_normalize_interval(self):
        self.assertEqual(normalize_interval("1d"), "1d")
        self.assertEqual(normalize_interval("daily"), "1d")
        self.assertEqual(normalize_interval("15m"), "15m")

    def test_invalid_interval(self):
        with self.assertRaises(ValueError):
            normalize_interval("2h")

    def test_default_period_for_interval(self):
        self.assertEqual(get_default_period("15m"), "5d")
        self.assertEqual(get_default_period("1d"), "6mo")

    def test_validate_timeframe(self):
        interval, period = validate_timeframe("15m", "1mo")
        self.assertEqual(interval, "15m")
        self.assertEqual(period, "1mo")

    def test_validate_uses_default_period(self):
        interval, period = validate_timeframe("1d")
        self.assertEqual(interval, "1d")
        self.assertEqual(period, "6mo")

    def test_invalid_period(self):
        with self.assertRaises(ValueError):
            validate_timeframe("1d", "not-a-period")


if __name__ == "__main__":
    unittest.main()
