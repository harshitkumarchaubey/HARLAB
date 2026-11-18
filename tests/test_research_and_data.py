"""Tests for data layer, experiment framework, leakage checks, backtester, and regimes."""
from __future__ import annotations

import json
import unittest

from harlab.data.market_data import dataset_from_simulation, load_ohlcv_csv
from harlab.execution.backtester import run_cost_aware_backtest
from harlab.ml.regime_detection import VolatilityLiquidityRegimeClassifier
from harlab.research.experiments import ExperimentConfig, ExperimentRunner, ExperimentStore
from harlab.simulation.market_simulator import MarketSimulator, SimulationConfig


VALID_OHLCV = """timestamp,open,high,low,close,volume
2026-01-01T09:30:00Z,100.0,101.0,99.5,100.5,1000
2026-01-01T09:31:00Z,100.5,101.5,100.0,101.0,1200
2026-01-01T09:32:00Z,101.0,101.2,100.2,100.4,900
"""


class TestResearchAndData(unittest.TestCase):
    def test_ohlcv_validation_and_guardrail(self) -> None:
        ds = load_ohlcv_csv(VALID_OHLCV, "ds1", "Test OHLCV", is_synthetic=True)
        self.assertEqual(ds.metadata.row_count, 3)
        self.assertFalse(ds.metadata.has_order_book_depth)

        # Bad high < close rejected
        bad_bar = "timestamp,open,high,low,close,volume\n2026-01-01T09:30:00Z,100,99,98,101,10\n"
        with self.assertRaises(ValueError):
            load_ohlcv_csv(bad_bar, "bad", "Bad Bar")

        # Out-of-order timestamps rejected
        bad_ts = (
            "timestamp,open,high,low,close,volume\n"
            "2026-01-01T09:31:00Z,100,101,99,100.5,10\n"
            "2026-01-01T09:30:00Z,100,101,99,100.5,10\n"
        )
        with self.assertRaises(ValueError):
            load_ohlcv_csv(bad_ts, "badts", "Bad TS")

        # Guardrail: H1 imbalance experiment MUST fail on OHLCV-only dataset
        runner = ExperimentRunner()
        with self.assertRaises(ValueError):
            runner.run(ds, ExperimentConfig(hypothesis_id="H1_IMBALANCE_RETURN", dataset_id="ds1"))

    def test_experiment_workflow_leakage_walkforward_and_export(self) -> None:
        sim = MarketSimulator(SimulationConfig(seed=42, steps=180)).run()
        ds = dataset_from_simulation(sim, "sim_test", "Synthetic LOB Test")

        runner = ExperimentRunner()
        res = runner.run(
            ds,
            ExperimentConfig(
                hypothesis_id="H1_IMBALANCE_RETURN",
                dataset_id="sim_test",
                horizon=2,
                train_ratio=0.70,
                walk_forward_folds=3,
                fee_bps=1.0,
                slippage_bps=2.0,
            ),
        )
        self.assertTrue(res.leakage_check["passed"])
        self.assertTrue(res.leakage_check["causal_ordering_ok"])
        self.assertTrue(res.leakage_check["temporal_boundary_ok"])
        self.assertGreaterEqual(len(res.walk_forward), 2)
        self.assertIsNotNone(res.cost_aware_backtest)
        self.assertTrue(any("SYNTHETIC" in w for w in res.warnings))

        store = ExperimentStore()
        store.save(res)
        exported_json = json.loads(store.export_json(res.experiment_id))
        self.assertEqual(exported_json["experiment_id"], res.experiment_id)
        exported_csv = store.export_csv(res.experiment_id)
        self.assertIn("out_of_sample,pearson_r", exported_csv)

    def test_cost_aware_backtester_accounts_for_costs(self) -> None:
        # Flat price -> gross return = 0, net return = -round_trip_cost per trade
        prices = [100.0, 100.0, 100.0, 100.0]
        signals = [1, -1, 0, 0]
        bt = run_cost_aware_backtest(prices, signals, horizon=1, fee_bps=1.5, slippage_bps=2.5)
        self.assertEqual(bt.trade_count, 2)
        self.assertEqual(bt.gross_return_bps, 0.0)
        # Round-trip cost per trade = 2 * (1.5 + 2.5) = 8 bps -> 2 trades = 16 bps
        self.assertEqual(bt.total_cost_bps, 16.0)
        self.assertEqual(bt.net_return_bps, -16.0)

    def test_regime_classifier_requires_fit_before_classify(self) -> None:
        clf = VolatilityLiquidityRegimeClassifier(window=5)
        with self.assertRaises(RuntimeError):
            clf.classify([100.0] * 10)
        prices = [100.0 + (i % 5) * 0.1 for i in range(40)]
        clf.fit(prices[:28])
        labels = clf.classify(prices)
        self.assertEqual(len(labels), len(prices))
        self.assertEqual(labels[0], "warmup")


if __name__ == "__main__":
    unittest.main()
