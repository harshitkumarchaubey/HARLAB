"""Documented market microstructure metrics derived from order-book snapshots and trades.

All metrics handle empty books and zero denominators explicitly by returning ``None``
(or ``0`` for counts/volumes) rather than raising ZeroDivisionError or emitting NaN.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Sequence

from .matching_engine import MatchingEngine, Trade
from .order_book import OrderBook


def bid_ask_spread(book: OrderBook) -> Decimal | None:
    """Quoted spread = best_ask - best_bid (units: quote currency).

    Returns ``None`` if either side of the book is empty.
    """
    return book.spread


def mid_price(book: OrderBook) -> Decimal | None:
    """Arithmetic mid-price = (best_bid + best_ask) / 2 (units: quote currency).

    Returns ``None`` if either side of the book is empty.
    """
    if book.best_bid is None or book.best_ask is None:
        return None
    return (book.best_bid + book.best_ask) / Decimal("2")


def relative_spread(book: OrderBook) -> Decimal | None:
    """Relative spread = (best_ask - best_bid) / mid_price (dimensionless ratio).

    Multiply by 10,000 for basis points (bps). Returns ``None`` if empty or mid == 0.
    """
    spread = bid_ask_spread(book)
    mid = mid_price(book)
    if spread is None or mid is None or mid == 0:
        return None
    return spread / mid


def bid_depth(book: OrderBook, levels: int | None = None) -> int:
    """Total displayed bid quantity across top ``levels`` (or all levels if None).

    Units: shares / lots (non-negative integer).
    """
    return sum(qty for _, qty in book.depth("buy", levels))


def ask_depth(book: OrderBook, levels: int | None = None) -> int:
    """Total displayed ask quantity across top ``levels`` (or all levels if None).

    Units: shares / lots (non-negative integer).
    """
    return sum(qty for _, qty in book.depth("sell", levels))


def total_displayed_depth(book: OrderBook, levels: int | None = None) -> int:
    """Combined displayed bid + ask quantity across top ``levels`` (units: shares/lots)."""
    return bid_depth(book, levels) + ask_depth(book, levels)


def order_imbalance(book: OrderBook, levels: int = 1) -> float | None:
    """Order-book imbalance = (bid_depth - ask_depth) / (bid_depth + ask_depth).

    Range: ``[-1.0, 1.0]`` (dimensionless). Positive values indicate heavier displayed
    bid volume; negative values indicate heavier displayed ask volume.
    Returns ``None`` when total displayed depth across ``levels`` is zero.
    """
    if isinstance(levels, bool) or not isinstance(levels, int) or levels < 1:
        raise ValueError("levels must be a positive integer")
    b_qty = bid_depth(book, levels)
    a_qty = ask_depth(book, levels)
    total = b_qty + a_qty
    if total == 0:
        return None
    return (b_qty - a_qty) / total


def weighted_mid_price(book: OrderBook, levels: int = 1) -> Decimal | None:
    """Volume-weighted mid-price across top ``levels`` on both sides (quote currency).

    Formula:
        ``(sum_{i=1..L} P_{bid,i} * Q_{bid,i} + sum_{j=1..L} P_{ask,j} * Q_{ask,j})
         / (sum Q_{bid,i} + sum Q_{ask,j})``

    Requires non-empty depth on BOTH bid and ask sides so the value is a valid
    two-sided mid-price estimate. Returns ``None`` if either side is empty.
    """
    if isinstance(levels, bool) or not isinstance(levels, int) or levels < 1:
        raise ValueError("levels must be a positive integer")
    bids = book.depth("buy", levels)
    asks = book.depth("sell", levels)
    if not bids or not asks:
        return None
    notional = sum(p * q for p, q in bids) + sum(p * q for p, q in asks)
    total_qty = sum(q for _, q in bids) + sum(q for _, q in asks)
    if total_qty == 0:
        return None
    return notional / Decimal(total_qty)


def microprice(book: OrderBook) -> Decimal | None:
    """Top-of-book imbalance-adjusted microprice (Gatheral / Stoikov definition).

    Formula:
        ``microprice = (P_bid * Q_ask + P_ask * Q_bid) / (Q_bid + Q_ask)``
    where ``P_bid, Q_bid`` are best bid price and top-level bid quantity, and
    ``P_ask, Q_ask`` are best ask price and top-level ask quantity.

    Intuition: when bid queue ``Q_bid`` is much larger than ask queue ``Q_ask``,
    buying pressure pushes the microprice closer to ``P_ask``.
    Units: quote currency. Returns ``None`` if either side is empty.
    """
    top_bids = book.depth("buy", 1)
    top_asks = book.depth("sell", 1)
    if not top_bids or not top_asks:
        return None
    p_bid, q_bid = top_bids[0]
    p_ask, q_ask = top_asks[0]
    denom = q_bid + q_ask
    if denom == 0:
        return None
    return (p_bid * Decimal(q_ask) + p_ask * Decimal(q_bid)) / Decimal(denom)


def price_changes(prices: Sequence[Decimal | float]) -> list[Decimal]:
    """First differences ``Delta P_t = P_t - P_{t-1}`` (units: quote currency)."""
    dec_prices = [p if isinstance(p, Decimal) else Decimal(str(p)) for p in prices]
    if len(dec_prices) < 2:
        return []
    return [dec_prices[i] - dec_prices[i - 1] for i in range(1, len(dec_prices))]


def simple_returns(prices: Sequence[Decimal | float]) -> list[float | None]:
    """Simple returns ``(P_t - P_{t-1}) / P_{t-1}`` (dimensionless); None if P_{t-1} == 0."""
    dec_prices = [p if isinstance(p, Decimal) else Decimal(str(p)) for p in prices]
    if len(dec_prices) < 2:
        return []
    out: list[float | None] = []
    for i in range(1, len(dec_prices)):
        prev = dec_prices[i - 1]
        if prev == 0:
            out.append(None)
        else:
            out.append(float((dec_prices[i] - prev) / prev))
    return out


def trade_volume(trades: Sequence[Trade]) -> dict[str, Any]:
    """Aggregate executed volume, trade count, notional value, and VWAP."""
    if not trades:
        return {
            "trade_count": 0,
            "total_quantity": 0,
            "notional_value": Decimal("0"),
            "vwap": None,
        }
    total_qty = sum(t.quantity for t in trades)
    notional = sum((t.price * Decimal(t.quantity) for t in trades), Decimal("0"))
    vwap = (notional / Decimal(total_qty)) if total_qty > 0 else None
    return {
        "trade_count": len(trades),
        "total_quantity": total_qty,
        "notional_value": notional,
        "vwap": vwap,
    }


def execution_statistics(engine: MatchingEngine) -> dict[str, Any]:
    """Execution summary statistics for a ``MatchingEngine`` instance."""
    vol = trade_volume(engine.trades)
    buy_agg_vol = sum(t.quantity for t in engine.trades if t.aggressor_side == "buy")
    sell_agg_vol = sum(t.quantity for t in engine.trades if t.aggressor_side == "sell")
    # Each trade matches 1 share of buy + 1 share of sell, so 2 * executed_qty leaves submitted qty
    submitted_qty = engine.total_submitted_quantity
    fill_rate = (
        (2 * engine.total_executed_quantity) / submitted_qty
        if submitted_qty > 0
        else None
    )
    avg_trade_size = (
        vol["total_quantity"] / vol["trade_count"] if vol["trade_count"] > 0 else None
    )
    return {
        "submitted_orders": engine.submitted_orders,
        "cancelled_orders": engine.cancelled_orders,
        "active_orders": len(engine.book.active_orders()),
        "trade_count": vol["trade_count"],
        "total_executed_quantity": vol["total_quantity"],
        "notional_value": float(vol["notional_value"]),
        "vwap": float(vol["vwap"]) if vol["vwap"] is not None else None,
        "average_trade_size": avg_trade_size,
        "fill_rate": fill_rate,
        "buy_aggressor_volume": buy_agg_vol,
        "sell_aggressor_volume": sell_agg_vol,
    }


def snapshot_metrics(
    book: OrderBook,
    engine: MatchingEngine | None = None,
    levels: int = 5,
) -> dict[str, Any]:
    """Compute a complete JSON-ready dictionary of order-book microstructure metrics."""
    spread = bid_ask_spread(book)
    mid = mid_price(book)
    rel_spread = relative_spread(book)
    w_mid = weighted_mid_price(book, levels=levels)
    m_price = microprice(book)
    metrics: dict[str, Any] = {
        "best_bid": float(book.best_bid) if book.best_bid is not None else None,
        "best_ask": float(book.best_ask) if book.best_ask is not None else None,
        "spread": float(spread) if spread is not None else None,
        "relative_spread": float(rel_spread) if rel_spread is not None else None,
        "relative_spread_bps": (
            float(rel_spread * Decimal("10000")) if rel_spread is not None else None
        ),
        "mid_price": float(mid) if mid is not None else None,
        "weighted_mid_price": float(w_mid) if w_mid is not None else None,
        "microprice": float(m_price) if m_price is not None else None,
        "order_imbalance_l1": order_imbalance(book, levels=1),
        "order_imbalance_l5": order_imbalance(book, levels=levels),
        "bid_depth_l1": bid_depth(book, levels=1),
        "ask_depth_l1": ask_depth(book, levels=1),
        "bid_depth_total": bid_depth(book, levels=None),
        "ask_depth_total": ask_depth(book, levels=None),
        "total_displayed_depth": total_displayed_depth(book, levels=None),
        "tick_size": float(book.tick_size),
    }
    if engine is not None:
        metrics["execution"] = execution_statistics(engine)
    return metrics
