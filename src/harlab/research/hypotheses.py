"""Structured research hypotheses for HARLAB experiments.

Hypotheses are testable empirical questions—never pre-assumed conclusions.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

INITIAL_QUESTIONS = [
    "Does displayed order-book imbalance relate to the next price change?",
    "How does quoted spread vary with simulated liquidity?",
    "How do execution costs change with order size?",
]


@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    title: str
    question: str
    null_hypothesis: str
    independent_variable: str
    dependent_variable: str
    requires_order_book_depth: bool
    assumptions: list[str]
    limitations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_HYPOTHESES: list[Hypothesis] = [
    Hypothesis(
        hypothesis_id="H1_IMBALANCE_RETURN",
        title="Order-Book Imbalance vs. Subsequent Mid-Price Change",
        question=(
            "Can displayed top-of-book order-book imbalance provide statistically "
            "measurable information about subsequent short-term mid-price changes?"
        ),
        null_hypothesis=(
            "H0: The correlation between displayed imbalance at step t and "
            "subsequent mid-price change from t to t+h is zero (r = 0)."
        ),
        independent_variable="imbalance_l1",
        dependent_variable="forward_mid_return_bps",
        requires_order_book_depth=True,
        assumptions=[
            "Chronological train/test separation with strictly causal lag (feature at t, target at t+h).",
            "Mid-price is observed at discrete event steps without hidden liquidity.",
        ],
        limitations=[
            "Results on synthetic data test software and model mechanics only, not real-market edge.",
            "Gross statistical correlation does not imply net profitability after fees and slippage.",
        ],
    ),
    Hypothesis(
        hypothesis_id="H2_DEPTH_SPREAD",
        title="Displayed Liquidity Depth vs. Quoted Bid-Ask Spread",
        question=(
            "Does quoted bid-ask spread widen when total displayed top-of-book "
            "liquidity decreases?"
        ),
        null_hypothesis=(
            "H0: Displayed top-level depth and contemporaneous quoted spread are "
            "uncorrelated (r = 0)."
        ),
        independent_variable="total_depth_l1",
        dependent_variable="spread",
        requires_order_book_depth=True,
        assumptions=[
            "Both bid and ask sides are populated at evaluated snapshots.",
        ],
        limitations=[
            "Contemporaneous liquidity-spread association does not establish causality.",
        ],
    ),
    Hypothesis(
        hypothesis_id="H3_OHLCV_MOMENTUM",
        title="OHLCV Short-Term Return Autocorrelation (Candle-Only)",
        question=(
            "Do lagged close-to-close returns in an OHLCV candle dataset exhibit "
            "non-zero autocorrelation with next-bar returns?"
        ),
        null_hypothesis=(
            "H0: Lag-1 close-to-close return autocorrelation equals zero (r = 0)."
        ),
        independent_variable="lag1_return_bps",
        dependent_variable="forward_close_return_bps",
        requires_order_book_depth=False,
        assumptions=[
            "OHLCV bars represent close-to-close price series only (no order-book reconstruction).",
        ],
        limitations=[
            "Cannot infer intra-bar execution, spread, or queue dynamics from OHLCV candles.",
        ],
    ),
]


def get_hypothesis(hypothesis_id: str) -> Hypothesis:
    for h in DEFAULT_HYPOTHESES:
        if h.hypothesis_id == hypothesis_id:
            return h
    raise KeyError(f"Unknown hypothesis_id: {hypothesis_id}")
