"""Tests for chart drawing models, validation, and store."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.charting.drawing_models import drawing_from_dict
from src.charting.drawing_store import DrawingStore
from src.charting.drawings import (
    normalize_drawing,
    validate_drawing,
    validate_drawing_update,
    validate_horizontal,
    validate_trendline,
    validate_zone,
)


class TestDrawingValidation(unittest.TestCase):
    def test_horizontal_valid(self):
        validate_horizontal({"price": 180.5})
        d = normalize_drawing({"type": "horizontal", "price": 180.5, "label": "Resistance"})
        self.assertEqual(d["type"], "horizontal")
        self.assertEqual(d["price"], 180.5)

    def test_horizontal_missing_price(self):
        with self.assertRaises(ValueError):
            validate_horizontal({})

    def test_trendline_valid(self):
        data = {
            "type": "trendline",
            "start": {"time": "2026-08-01", "price": 170},
            "end": {"time": "2026-08-19", "price": 185},
        }
        validate_trendline(data)
        d = normalize_drawing(data)
        self.assertEqual(d["start"]["price"], 170)

    def test_trendline_same_points_rejected(self):
        data = {
            "type": "trendline",
            "start": {"time": "2026-08-01", "price": 170},
            "end": {"time": "2026-08-01", "price": 170},
        }
        with self.assertRaises(ValueError):
            validate_trendline(data)

    def test_trendline_missing_start(self):
        with self.assertRaises(ValueError):
            validate_trendline({"type": "trendline", "end": {"time": "x", "price": 1}})

    def test_zone_valid(self):
        d = normalize_drawing({"type": "zone", "top": 185, "bottom": 180, "label": "Demand"})
        self.assertEqual(d["top"], 185)
        self.assertEqual(d["bottom"], 180)

    def test_zone_top_must_exceed_bottom(self):
        with self.assertRaises(ValueError):
            validate_zone({"top": 180, "bottom": 185})

    def test_unknown_type(self):
        with self.assertRaises(ValueError):
            validate_drawing({"type": "fibonacci", "price": 1})

    def test_empty_payload(self):
        with self.assertRaises(ValueError):
            normalize_drawing({})


class TestDrawingUpdate(unittest.TestCase):
    def test_update_horizontal_price(self):
        existing = normalize_drawing({"type": "horizontal", "price": 180})
        existing["id"] = "abc"
        updated = validate_drawing_update(existing, {"price": 182.5})
        self.assertEqual(updated["price"], 182.5)
        self.assertEqual(updated["type"], "horizontal")


class TestDrawingStore(unittest.TestCase):
    def setUp(self):
        self.store = DrawingStore()

    def test_create_horizontal_line(self):
        d = self.store.create_drawing("AAPL", {"type": "horizontal", "price": 180})
        self.assertIn("id", d)
        self.assertEqual(d["price"], 180)

    def test_list_by_symbol(self):
        self.store.create_drawing("AAPL", {"type": "horizontal", "price": 180})
        items = self.store.list_drawings("AAPL")
        self.assertEqual(len(items), 1)

    def test_update_line(self):
        d = self.store.create_drawing("AAPL", {"type": "horizontal", "price": 180})
        updated = self.store.update_drawing("AAPL", d["id"], {"price": 185, "label": "Resistance"})
        self.assertEqual(updated["price"], 185)
        self.assertEqual(updated["label"], "Resistance")

    def test_delete_line(self):
        d = self.store.create_drawing("AAPL", {"type": "horizontal", "price": 180})
        self.assertTrue(self.store.delete_drawing("AAPL", d["id"]))
        self.assertEqual(self.store.list_drawings("AAPL"), [])

    def test_delete_missing_returns_false(self):
        self.assertFalse(self.store.delete_drawing("AAPL", "missing"))

    def test_update_missing_raises(self):
        with self.assertRaises(KeyError):
            self.store.update_drawing("AAPL", "missing", {"price": 1})

    def test_symbol_isolation(self):
        self.store.create_drawing("AAPL", {"type": "horizontal", "price": 180})
        self.store.create_drawing("MSFT", {"type": "horizontal", "price": 400})
        self.assertEqual(len(self.store.list_drawings("AAPL")), 1)
        self.assertEqual(len(self.store.list_drawings("MSFT")), 1)
        self.assertEqual(self.store.list_drawings("AAPL")[0]["price"], 180)

    def test_trendline_persisted(self):
        d = self.store.create_drawing("AAPL", {
            "type": "trendline",
            "start": {"time": "2026-08-01T00:00:00", "price": 170},
            "end": {"time": "2026-08-19T00:00:00", "price": 185},
        })
        fetched = self.store.get_drawing("AAPL", d["id"])
        self.assertEqual(fetched["start"]["price"], 170)

    def test_zone_persisted(self):
        d = self.store.create_drawing("AAPL", {"type": "zone", "top": 190, "bottom": 185})
        self.assertEqual(d["top"], 190)

    def test_reset_clears_all(self):
        self.store.create_drawing("AAPL", {"type": "horizontal", "price": 1})
        self.store.reset()
        self.assertEqual(self.store.list_drawings("AAPL"), [])


class TestDrawingModels(unittest.TestCase):
    def test_drawing_from_dict_zone(self):
        d = drawing_from_dict({"type": "zone", "top": 10, "bottom": 5})
        self.assertEqual(d["type"], "zone")


if __name__ == "__main__":
    unittest.main()
