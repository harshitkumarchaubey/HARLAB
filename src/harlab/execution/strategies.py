"""Simple, transparent research signal rules for hypothesis evaluation.

Signals are strictly causal: a signal generated at index ``t`` may only use
information observable at or before ``t``, and is evaluated on subsequent
price changes from ``t`` to ``t + horizon``.
"""
from __future__ import annotations

from typing import Sequence


def imbalance_threshold_signals(
    imbalances: Sequence[float | None],
    threshold: float = 0.20,
) -> list[int]:
    """Map displayed order-book imbalance to ``{-1, 0, +1}`` directional signals.

    - ``+1`` when ``imbalance >= threshold``
    - ``-1`` when ``imbalance <= -threshold``
    - ``0`` otherwise (or when imbalance is ``None``)
    """
    if threshold < 0 or threshold > 1:
        raise ValueError("threshold must be in [0, 1]")
    signals: list[int] = []
    for imb in imbalances:
        if imb is None:
            signals.append(0)
        elif imb >= threshold:
            signals.append(1)
        elif imb <= -threshold:
            signals.append(-1)
        else:
            signals.append(0)
    return signals


def naive_zero_signals(length: int) -> list[int]:
    """Zero-exposure baseline benchmark."""
    return [0] * length
