"""Unit tests for all 12 documented market microstructure metrics."""
from __future__ import annotations

import unittest
from decimal import Decimal

from harlab.market.market_metrics import (
    ask_depth,
    bid_ask_spread,
    bid_depth,
    execution_statistics,
    microprice,
    mid_price,
    order_imbalance,
    price_changes,
    relative_spread,
    simple_returns,
    snapshot_metrics,
    total_displayed_depth,
    trade_volume,
    weighted_mid_price,
)
from harlab.market.matching_engine import MatchingEngine
from harlab.market.order_book import OrderBook


class TestMarketMetrics(unittest.TestCase):
    def test_known_examples_all_metrics(self) -> None:
        book = OrderBook(tick_size=Decimal("0.01"))
        book.add_limit_order("b1", "buy", Decimal("99.90"), 30)
        book.add_limit_order("b2", "buy", Decimal("99.80"), 20)
        book.add_limit_order("a1", "sell", Decimal("100.10"), 10)
        book.add_limit_order("a2", "sell", Decimal("100.20"), 40)

        self.assertEqual(bid_ask_spread(book), Decimal("0.20"))
        self.assertEqual(mid_price(book), Decimal("100.00"))
        self.assertEqual(relative_spread(book), Decimal("0.002"))
        self.assertEqual(order_imbalance(book, levels=1), 0.5)  # (30-10)/40
        self.assertEqual(order_imbalance(book, levels=2), 0.0)  # (50-50)/100
        self.assertEqual(bid_depth(book, levels=1), 30)
        self.assertEqual(bid_depth(book, levels=None), 50)
        self.assertEqual(ask_depth(book, levels=1), 10)
        self.assertEqual(ask_depth(book, levels=None), 50)
        self.assertEqual(total_displayed_depth(book), 100)

        # Weighted mid L1 = (99.90*30 + 100.10*10) / 40 = 3998 / 40 = 99.95
        self.assertEqual(weighted_mid_price(book, levels=1), Decimal("99.95"))

        # Microprice = (99.90*10 + 100.10*30) / 40 = 4002 / 40 = 100.05
        self.assertEqual(microprice(book), Decimal("100.05"))

    def test_empty_and_one_sided_book_guards(self) -> None:
        empty = OrderBook()
        self.assertIsNone(bid_ask_spread(empty))
        self.assertIsNone(mid_price(empty))
        self.assertIsNone(relative_spread(empty))
        self.assertIsNone(order_imbalance(empty))
        self.assertIsNone(weighted_mid_price(empty))
        self.assertIsNone(microprice(empty))
        self.assertEqual(bid_depth(empty), 0)
        self.assertEqual(ask_depth(empty), 0)
        self.assertEqual(total_displayed_depth(empty), 0)

        one_sided = OrderBook()
        one_sided.add_limit_order("b1", "buy", Decimal("100.00"), 10)
        self.assertEqual(order_imbalance(one_sided), 1.0)
        self.assertIsNone(mid_price(one_sided))
        self.assertIsNone(weighted_mid_price(one_sided))
        self.assertIsNone(microprice(one_sided))

    def test_price_changes_returns_and_execution_stats(self) -> None:
        prices = [Decimal("100.00"), Decimal("100.50"), Decimal("100.00")]
        self.assertEqual(price_changes(prices), [Decimal("0.50"), Decimal("-0.50")])
        rets = simple_returns(prices)
        self.assertAlmostEqual(rets[0], 0.005, places=6)
        self.assertEqual(simple_returns([Decimal("0"), Decimal("10")]), [None])

        engine = MatchingEngine()
        engine.submit_limit_order("s1", "sell", Decimal("100.00"), 10)
        engine.submit_limit_order("b1", "buy", Decimal("100.00"), 4)
        vol = trade_volume(engine.trades)
        self.assertEqual(vol["trade_count"], 1)
        self.assertEqual(vol["total_quantity"], 4)
        self.assertEqual(vol["vwap"], Decimal("100.00"))

        stats = execution_statistics(engine)
        self.assertEqual(stats["trade_count"], 1)
        self.assertEqual(stats["buy_aggressor_volume"], 4)
        self.assertEqual(stats["sell_aggressor_volume"], 0)
        snap = snapshot_metrics(engine.book, engine=engine)
        self.assertIn("execution", snap)


if __name__ == "__main__":
    unittest.main()
