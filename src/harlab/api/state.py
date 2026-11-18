"""In-memory research session state backing the HARLAB FastAPI server."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from ..ai.ai_assistant import ResearchAssistant
from ..ai.router import AIProviderRouter
from ..data.market_data import DatasetRegistry, dataset_from_simulation, load_ohlcv_csv
from ..market.matching_engine import MatchingEngine
from ..market.order_book import DEFAULT_TICK_SIZE, OrderBook
from ..ml.regime_detection import VolatilityLiquidityRegimeClassifier
from ..research.experiments import ExperimentConfig, ExperimentRunner, ExperimentStore
from ..simulation.market_simulator import (
    MarketSimulator,
    PRESET_SCENARIOS,
    SimulationConfig,
    seed_demo_market,
)

SAMPLE_SYNTHETIC_OHLCV = """timestamp,open,high,low,close,volume
2026-01-01T09:30:00Z,100.00,100.35,99.85,100.20,12400
2026-01-01T09:31:00Z,100.20,100.50,100.05,100.40,14100
2026-01-01T09:32:00Z,100.40,100.60,100.10,100.15,11200
2026-01-01T09:33:00Z,100.15,100.30,99.90,99.95,15300
2026-01-01T09:34:00Z,99.95,100.25,99.80,100.10,10800
2026-01-01T09:35:00Z,100.10,100.45,100.00,100.35,16500
2026-01-01T09:36:00Z,100.35,100.55,100.20,100.50,13200
2026-01-01T09:37:00Z,100.50,100.70,100.30,100.45,12900
2026-01-01T09:38:00Z,100.45,100.65,100.15,100.25,11900
2026-01-01T09:39:00Z,100.25,100.40,100.00,100.05,14700
2026-01-01T09:40:00Z,100.05,100.30,99.95,100.20,11600
2026-01-01T09:41:00Z,100.20,100.60,100.15,100.55,17200
2026-01-01T09:42:00Z,100.55,100.80,100.40,100.70,15900
2026-01-01T09:43:00Z,100.70,100.85,100.45,100.50,13800
2026-01-01T09:44:00Z,100.50,100.65,100.25,100.30,12100
2026-01-01T09:45:00Z,100.30,100.55,100.10,100.45,14500
2026-01-01T09:46:00Z,100.45,100.75,100.35,100.65,16100
2026-01-01T09:47:00Z,100.65,100.90,100.50,100.80,15400
2026-01-01T09:48:00Z,100.80,101.00,100.60,100.70,13600
2026-01-01T09:49:00Z,100.70,100.85,100.40,100.55,12700
2026-01-01T09:50:00Z,100.55,100.75,100.35,100.65,11800
2026-01-01T09:51:00Z,100.65,100.95,100.55,100.85,15200
2026-01-01T09:52:00Z,100.85,101.05,100.70,100.90,14900
2026-01-01T09:53:00Z,100.90,101.10,100.65,100.75,13100
2026-01-01T09:54:00Z,100.75,100.90,100.50,100.60,12400
2026-01-01T09:55:00Z,100.60,100.80,100.45,100.70,11900
2026-01-01T09:56:00Z,100.70,101.00,100.60,100.95,16300
2026-01-01T09:57:00Z,100.95,101.15,100.80,101.05,15800
2026-01-01T09:58:00Z,101.05,101.20,100.75,100.85,14200
2026-01-01T09:59:00Z,100.85,101.00,100.65,100.75,12600
"""


class LabState:
    """Holds live deterministic engine, datasets, simulation output, experiments, and AI router."""

    def __init__(self) -> None:
        self.engine = MatchingEngine(OrderBook(tick_size=DEFAULT_TICK_SIZE))
        seed_demo_market(self.engine)

        self.datasets = DatasetRegistry()
        self.experiments = ExperimentStore()
        self.runner = ExperimentRunner()
        self.ai_router = AIProviderRouter()
        self.assistant = ResearchAssistant(self.ai_router)
        self.last_simulation: dict[str, Any] | None = None
        self.simulation_count: int = 0

        self._bootstrap_initial_datasets()

    def _bootstrap_initial_datasets(self) -> None:
        """Seed one deterministic synthetic LOB run + one synthetic OHLCV sample for immediate inspection."""
        baseline_cfg = SimulationConfig(**PRESET_SCENARIOS["baseline_symmetric"]["config"])
        sim_out = MarketSimulator(baseline_cfg).run()
        self.last_simulation = sim_out
        self.simulation_count = 1
        ds_lob = dataset_from_simulation(
            sim_out,
            dataset_id="sim_baseline_42",
            name="SYNTHETIC LOB — Baseline Symmetric (seed=42, 250 steps)",
        )
        self.datasets.register(ds_lob)

        ds_ohlcv = load_ohlcv_csv(
            SAMPLE_SYNTHETIC_OHLCV,
            dataset_id="sample_synthetic_ohlcv",
            name="SYNTHETIC OHLCV — 30-Bar Demonstration Candles (No L2 Depth)",
            is_synthetic=True,
            description=(
                "Synthetic 1-minute candle series demonstrating strict separation "
                "between OHLCV bars and L2 order-book depth."
            ),
        )
        self.datasets.register(ds_ohlcv)

        # Run one initial baseline experiment so Research Dashboard starts with real computed data
        initial_exp = self.runner.run(
            ds_lob,
            ExperimentConfig(
                hypothesis_id="H1_IMBALANCE_RETURN",
                dataset_id="sim_baseline_42",
                horizon=1,
                train_ratio=0.70,
                walk_forward_folds=3,
                signal_threshold=0.20,
                fee_bps=1.0,
                slippage_bps=2.0,
                notes="Initial seeded baseline experiment on synthetic symmetric LOB.",
            ),
        )
        self.experiments.save(initial_exp)

    def reset_book(self, tick_size: Decimal = DEFAULT_TICK_SIZE, seed_demo: bool = True) -> None:
        self.engine = MatchingEngine(OrderBook(tick_size=tick_size))
        if seed_demo:
            seed_demo_market(self.engine)

    def compute_regimes(self, dataset_id: str) -> dict[str, Any]:
        ds = self.datasets.get(dataset_id)
        rows = ds.records
        price_key = "mid_price" if "mid_price" in rows[0] else "close"
        prices = [r.get(price_key) for r in rows]
        spreads = [r.get("spread") for r in rows] if "spread" in rows[0] else None
        split = int(len(prices) * 0.70)
        clf = VolatilityLiquidityRegimeClassifier(window=12)
        thresholds = clf.fit(
            prices[:split],
            spreads[:split] if spreads is not None else None,
        )
        labels = clf.classify(prices, spreads)
        counts: dict[str, int] = {}
        for lbl in labels[split:]:
            counts[lbl] = counts.get(lbl, 0) + 1
        return {
            "dataset_id": dataset_id,
            "train_rows": split,
            "test_rows": len(prices) - split,
            "fitted_train_thresholds": thresholds.to_dict(),
            "out_of_sample_regime_counts": counts,
        }
