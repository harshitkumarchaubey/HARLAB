"""Tests for deterministic synthetic MarketSimulator."""
from __future__ import annotations

import unittest
from decimal import Decimal

from harlab.market.matching_engine import MatchingEngine
from harlab.simulation.market_simulator import (
    MarketSimulator,
    SimulationConfig,
    seed_demo_market,
)


class TestSimulator(unittest.TestCase):
    def test_seed_demo_market(self) -> None:
        engine = MatchingEngine()
        seed_demo_market(engine)
        self.assertEqual(engine.book.best_bid, Decimal("99.90"))
        self.assertEqual(engine.book.best_ask, Decimal("100.10"))
        self.assertEqual(engine.book.spread, Decimal("0.20"))

    def test_reproducibility_with_same_seed(self) -> None:
        cfg = SimulationConfig(seed=123, steps=80)
        out1 = MarketSimulator(cfg).run()
        out2 = MarketSimulator(cfg).run()
        self.assertEqual(out1["series"], out2["series"])
        self.assertEqual(out1["trades"], out2["trades"])
        self.assertEqual(out1["data_origin"], "SYNTHETIC")
        self.assertTrue(out1["is_synthetic"])

    def test_invalid_probabilities_rejected(self) -> None:
        cfg = SimulationConfig(limit_order_prob=0.5, marketable_order_prob=0.5, cancel_prob=0.5)
        with self.assertRaises(ValueError):
            MarketSimulator(cfg)


if __name__ == "__main__":
    unittest.main()
