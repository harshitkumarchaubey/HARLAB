"""Leakage-free deterministic market regime classification module.

Separates ML/statistical regime detection cleanly from the deterministic LOB engine.
Thresholds are fit strictly on the chronological training segment and applied
out-of-sample to the test segment to prevent lookahead leakage.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

import numpy as np


@dataclass
class RegimeThresholds:
    vol_low: float
    vol_high: float
    spread_high: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class VolatilityLiquidityRegimeClassifier:
    """Quantile-based volatility and liquidity regime detector (fit on train only)."""

    def __init__(self, window: int = 15) -> None:
        if window < 3:
            raise ValueError("window must be >= 3")
        self.window = window
        self.thresholds: RegimeThresholds | None = None

    def _rolling_vol(self, prices: Sequence[float | None]) -> list[float | None]:
        vols: list[float | None] = [None] * len(prices)
        rets: list[float | None] = [None]
        for i in range(1, len(prices)):
            p0, p1 = prices[i - 1], prices[i]
            if p0 is None or p1 is None or p0 <= 0:
                rets.append(None)
            else:
                rets.append(((p1 - p0) / p0) * 10000.0)
        for i in range(self.window, len(prices)):
            seg = [r for r in rets[i - self.window + 1 : i + 1] if r is not None]
            if len(seg) >= 3:
                vols[i] = float(np.std(seg, ddof=1))
        return vols

    def fit(
        self,
        train_prices: Sequence[float | None],
        train_spreads: Sequence[float | None] | None = None,
    ) -> RegimeThresholds:
        """Fit quantile cutoffs strictly on training data."""
        vols = [v for v in self._rolling_vol(train_prices) if v is not None]
        if len(vols) < 5:
            raise ValueError("Insufficient training observations to fit regime thresholds")
        vol_low = float(np.quantile(vols, 0.33))
        vol_high = float(np.quantile(vols, 0.67))

        spread_high: float | None = None
        if train_spreads is not None:
            valid_spr = [float(s) for s in train_spreads if s is not None]
            if len(valid_spr) >= 5:
                spread_high = float(np.quantile(valid_spr, 0.75))

        self.thresholds = RegimeThresholds(
            vol_low=round(vol_low, 4),
            vol_high=round(vol_high, 4),
            spread_high=round(spread_high, 4) if spread_high is not None else None,
        )
        return self.thresholds

    def classify(
        self,
        prices: Sequence[float | None],
        spreads: Sequence[float | None] | None = None,
    ) -> list[str]:
        """Assign regime labels using previously fitted training thresholds."""
        if self.thresholds is None:
            raise RuntimeError("Classifier must be fit on training data before classify()")
        vols = self._rolling_vol(prices)
        labels: list[str] = []
        for i, v in enumerate(vols):
            if v is None:
                labels.append("warmup")
                continue
            if v >= self.thresholds.vol_high:
                vol_tag = "high_vol"
            elif v <= self.thresholds.vol_low:
                vol_tag = "low_vol"
            else:
                vol_tag = "normal_vol"

            if (
                spreads is not None
                and self.thresholds.spread_high is not None
                and spreads[i] is not None
                and float(spreads[i]) > self.thresholds.spread_high
            ):
                labels.append(f"{vol_tag}_wide_spread")
            else:
                labels.append(vol_tag)
        return labels
