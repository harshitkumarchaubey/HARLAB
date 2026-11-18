"""Unit, regression, and randomized invariant tests for MatchingEngine."""
from __future__ import annotations

import random
import unittest
from decimal import Decimal

from harlab.market.matching_engine import MatchingEngine
from harlab.market.order_book import OrderBook


class TestMatchingEngine(unittest.TestCase):
    def test_crossing_order_matches_at_resting_price(self) -> None:
        engine = MatchingEngine()
        engine.submit_limit_order("seller", "sell", 100, 5)
        trades = engine.submit_limit_order("buyer", "buy", 101, 3)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].price, Decimal("100.00"))
        self.assertEqual(trades[0].quantity, 3)
        self.assertEqual(trades[0].aggressor_side, "buy")
        self.assertEqual(engine.book.best_ask, Decimal("100.00"))
        self.assertEqual(engine.book.depth("sell", 1), [(Decimal("100.00"), 2)])

    def test_unfilled_remainder_rests_in_book_with_monotonic_timestamp(self) -> None:
        engine = MatchingEngine()
        engine.submit_limit_order("seller", "sell", 100, 2)
        engine.submit_limit_order("buyer", "buy", 100, 5)
        self.assertEqual(engine.book.best_bid, Decimal("100.00"))
        self.assertEqual(engine.book.depth("buy", 1), [(Decimal("100.00"), 3)])
        resting = engine.book.get_order("buyer")
        self.assertIsNotNone(resting)
        assert resting is not None
        self.assertGreater(resting.timestamp, 0)
        self.assertEqual(resting.status, "partial")

    def test_price_priority(self) -> None:
        engine = MatchingEngine()
        engine.submit_limit_order("s1", "sell", 101, 2)
        engine.submit_limit_order("s2", "sell", 100, 2)
        trades = engine.submit_limit_order("b1", "buy", 102, 3)
        self.assertEqual([t.price for t in trades], [Decimal("100.00"), Decimal("101.00")])
        self.assertEqual([t.quantity for t in trades], [2, 1])

    def test_fifo_priority_within_same_price_and_resting_partial_fill(self) -> None:
        engine = MatchingEngine()
        engine.submit_limit_order("s1", "sell", 100, 5)
        engine.submit_limit_order("s2", "sell", 100, 5)
        # Partially fill s1 (2 of 5); s1 must keep front-of-queue priority over s2
        t1 = engine.submit_limit_order("b1", "buy", 100, 2)
        self.assertEqual(t1[0].sell_order_id, "s1")
        # Next buy of 4 must finish remaining 3 of s1 BEFORE touching s2
        t2 = engine.submit_limit_order("b2", "buy", 100, 4)
        self.assertEqual([(t.sell_order_id, t.quantity) for t in t2], [("s1", 3), ("s2", 1)])

    def test_cancel_partially_filled_resting_order(self) -> None:
        engine = MatchingEngine()
        engine.submit_limit_order("s1", "sell", 100, 10)
        engine.submit_limit_order("b1", "buy", 100, 4)
        self.assertTrue(engine.cancel_order("s1"))
        self.assertEqual(engine.total_cancelled_quantity, 6)
        self.assertIsNone(engine.book.best_ask)
        # Conservation: submitted (14) == resting (0) + cancelled (6) + 2*executed (8)
        self.assertEqual(
            engine.total_submitted_quantity,
            engine.book.total_resting_quantity()
            + engine.total_cancelled_quantity
            + 2 * engine.total_executed_quantity,
        )

    def test_randomized_invariants_1500_operations(self) -> None:
        """Property/invariant fuzz test over 1,500 random inserts, matches, and cancels."""
        rng = random.Random(2026)
        tick = Decimal("0.05")
        engine = MatchingEngine(OrderBook(tick_size=tick))
        active_ids: list[str] = []

        for step in range(1, 1501):
            if active_ids and rng.random() < 0.25:
                oid = rng.choice(active_ids)
                engine.cancel_order(oid)
                if engine.book.get_order(oid) is None:
                    active_ids.remove(oid)
            else:
                oid = f"ORD-{step}"
                side = "buy" if rng.random() < 0.5 else "sell"
                price = Decimal(rng.randint(1980, 2020)) * tick
                qty = rng.randint(1, 50)
                engine.submit_limit_order(oid, side, price, qty)
                if engine.book.get_order(oid) is not None:
                    active_ids.append(oid)

            # Invariant 1: Resting book is NEVER crossed after continuous matching
            self.assertFalse(engine.book.is_crossed)

            # Invariant 2: Strict quantity conservation
            resting_qty = engine.book.total_resting_quantity()
            self.assertEqual(
                engine.total_submitted_quantity,
                resting_qty
                + engine.total_cancelled_quantity
                + 2 * engine.total_executed_quantity,
            )

            # Invariant 3: All resting orders have positive quantity & unique IDs
            orders = engine.book.active_orders()
            ids = [o.order_id for o in orders]
            self.assertEqual(len(ids), len(set(ids)))
            for o in orders:
                self.assertGreater(o.quantity, 0)
                self.assertLessEqual(o.quantity, o.initial_quantity)


if __name__ == "__main__":
    unittest.main()
