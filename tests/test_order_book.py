"""Unit and regression tests for exact-tick OrderBook."""
from __future__ import annotations

import math
import unittest
from decimal import Decimal

from harlab.market.order_book import OrderBook


class TestOrderBook(unittest.TestCase):
    def test_best_prices_exact_spread_and_depth(self) -> None:
        book = OrderBook(tick_size=Decimal("0.01"))
        book.add_limit_order("b1", "buy", 99.9, 10)
        book.add_limit_order("a1", "sell", 100.1, 7)
        self.assertEqual(book.best_bid, Decimal("99.90"))
        self.assertEqual(book.best_ask, Decimal("100.10"))
        # Regression: IEEE-754 float gave 0.19999999999998863
        self.assertEqual(book.spread, Decimal("0.20"))
        self.assertEqual(book.depth("buy", 1), [(Decimal("99.90"), 10)])
        self.assertEqual(book.depth("sell", 1), [(Decimal("100.10"), 7)])

    def test_float_sum_maps_to_same_price_level(self) -> None:
        # Regression for Audit Finding 4: 100.1 + 0.2 == 100.30000000000001 in IEEE-754
        book = OrderBook(tick_size=Decimal("0.01"))
        book.add_limit_order("b1", "buy", Decimal("100.30"), 5)
        book.add_limit_order("b2", "buy", "100.30", 7)
        book.add_limit_order("b3", "buy", 100.3, 3)
        self.assertEqual(book.depth("buy", 5), [(Decimal("100.30"), 15)])

    def test_price_time_queue_and_cancel(self) -> None:
        book = OrderBook()
        o1 = book.add_limit_order("b1", "buy", 99, 5)
        o2 = book.add_limit_order("b2", "buy", 99, 8)
        self.assertLess(o1.timestamp, o2.timestamp)
        self.assertTrue(book.cancel_order("b1"))
        self.assertEqual(o1.status, "cancelled")
        self.assertEqual(book.depth("buy", 1), [(Decimal("99.00"), 8)])
        self.assertFalse(book.cancel_order("b1"))
        self.assertFalse(book.cancel_order("missing"))

    def test_cannot_reuse_cancelled_order_id(self) -> None:
        book = OrderBook()
        book.add_limit_order("o1", "buy", 100, 10)
        self.assertTrue(book.cancel_order("o1"))
        with self.assertRaises(ValueError):
            book.add_limit_order("o1", "buy", 100, 10)

    def test_validation_edge_cases(self) -> None:
        book = OrderBook(tick_size=Decimal("0.05"))
        # Negative, zero, NaN, Inf, boolean prices
        for bad_price in (-1, 0, math.nan, math.inf, -math.inf, True, False, "abc"):
            with self.assertRaises(ValueError):
                book.add_limit_order("x", "buy", bad_price, 5)  # type: ignore[arg-type]

        # Off-tick price (0.01 is not a multiple of 0.05)
        with self.assertRaises(ValueError):
            book.add_limit_order("x", "buy", Decimal("100.01"), 5)

        # Invalid quantities including booleans (True == 1 in Python)
        for bad_qty in (0, -5, True, False, 1.5, "10"):
            with self.assertRaises(ValueError):
                book.add_limit_order("x", "buy", Decimal("100.00"), bad_qty)  # type: ignore[arg-type]

        # Invalid side & empty order_id
        with self.assertRaises(ValueError):
            book.add_limit_order("x", "hold", Decimal("100.00"), 5)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            book.add_limit_order("   ", "buy", Decimal("100.00"), 5)

    def test_invalid_tick_size_rejected(self) -> None:
        for bad_tick in (0, -0.01, math.nan, math.inf, True, "bad"):
            with self.assertRaises(ValueError):
                OrderBook(tick_size=bad_tick)  # type: ignore[arg-type]

    def test_empty_book_properties(self) -> None:
        book = OrderBook()
        self.assertIsNone(book.best_bid)
        self.assertIsNone(book.best_ask)
        self.assertIsNone(book.spread)
        self.assertEqual(book.snapshot(5), {"bids": [], "asks": []})


if __name__ == "__main__":
    unittest.main()
