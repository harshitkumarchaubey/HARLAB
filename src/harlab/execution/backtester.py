"""Cost-aware, leakage-checked research backtester for evaluating signal hypotheses.

Assumptions (documented explicitly):
- A signal ``s_t in {-1, 0, +1}`` observed at step ``t`` enters at ``price[t]``
  and exits after ``horizon`` steps at ``price[t + horizon]``.
- Each non-zero trade incurs round-trip transaction fees (``fee_bps``) plus
  execution slippage (``slippage_bps``).
- This is a simplified research evaluation harness—it does NOT model queue
  position, market impact feedback, or real exchange latency.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Sequence


@dataclass
class BacktestSummary:
    trade_count: int
    gross_return_bps: float
    net_return_bps: float
    total_cost_bps: float
    mean_net_trade_bps: float
    hit_rate: float | None
    sharpe_like: float | None
    fee_bps: float
    slippage_bps: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_cost_aware_backtest(
    prices: Sequence[float | None],
    signals: Sequence[int],
    horizon: int = 1,
    fee_bps: float = 1.0,
    slippage_bps: float = 2.0,
) -> BacktestSummary:
    """Evaluate directional signals over ``horizon`` steps with explicit costs."""
    if len(prices) != len(signals):
        raise ValueError("prices and signals must have identical lengths")
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    if fee_bps < 0 or slippage_bps < 0:
        raise ValueError("fee_bps and slippage_bps must be non-negative")

    round_trip_cost_bps = 2.0 * (fee_bps + slippage_bps)
    gross_trades: list[float] = []
    net_trades: list[float] = []
    hits = 0

    for t in range(len(prices) - horizon):
        sig = signals[t]
        if sig == 0:
            continue
        p0 = prices[t]
        p1 = prices[t + horizon]
        if p0 is None or p1 is None or p0 <= 0:
            continue
        raw_ret_bps = ((p1 - p0) / p0) * 10000.0 * sig
        net_ret_bps = raw_ret_bps - round_trip_cost_bps
        gross_trades.append(raw_ret_bps)
        net_trades.append(net_ret_bps)
        if raw_ret_bps > 0:
            hits += 1

    n = len(net_trades)
    if n == 0:
        return BacktestSummary(
            trade_count=0,
            gross_return_bps=0.0,
            net_return_bps=0.0,
            total_cost_bps=0.0,
            mean_net_trade_bps=0.0,
            hit_rate=None,
            sharpe_like=None,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
        )

    gross_total = sum(gross_trades)
    net_total = sum(net_trades)
    mean_net = net_total / n
    variance = sum((x - mean_net) ** 2 for x in net_trades) / max(1, n - 1)
    std = math.sqrt(variance)
    sharpe_like = (mean_net / std) * math.sqrt(n) if std > 1e-12 else None

    return BacktestSummary(
        trade_count=n,
        gross_return_bps=round(gross_total, 4),
        net_return_bps=round(net_total, 4),
        total_cost_bps=round(n * round_trip_cost_bps, 4),
        mean_net_trade_bps=round(mean_net, 4),
        hit_rate=round(hits / n, 4),
        sharpe_like=round(sharpe_like, 4) if sharpe_like is not None else None,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
    )
