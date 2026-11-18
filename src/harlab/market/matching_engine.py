"""Continuous price-time-priority limit-order matching engine.

Documented matching rules & assumptions:
- Strictly continuous limit-order matching (no auctions, no stop/market/iceberg types).
- Price priority: incoming buy orders match against lowest ask ticks first;
  incoming sell orders match against highest bid ticks first.
- Time priority (FIFO): within each price tick, resting orders execute strictly
  in arrival order (``collections.deque`` front-to-back).
- Execution price: every trade executes at the resting order's limit price.
- Partial fills:
  - A partially filled resting order remains at the front of its price queue
    (preserving its time priority) with reduced ``quantity``.
  - An incoming aggressive order's unfilled remainder rests at the back of its
    limit price queue (behind any orders already resting at that price),
    retaining its monotonic arrival sequence number.
- Single-threaded synchronous engine; not a live exchange gateway.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .order_book import Order, OrderBook, PriceInput, Side


@dataclass(frozen=True)
class Trade:
    """An executed fill between an incoming aggressive order and a resting order."""

    buy_order_id: str
    sell_order_id: str
    price: Decimal
    quantity: int
    aggressor_side: Side = "buy"
    timestamp: int = 0
    trade_id: int = 0


class MatchingEngine:
    """Continuous price-time-priority matching engine backed by an ``OrderBook``."""

    def __init__(self, book: OrderBook | None = None) -> None:
        self.book: OrderBook = book if book is not None else OrderBook()
        self.trades: list[Trade] = []
        self._trade_seq: int = 0
        self.submitted_orders: int = 0
        self.cancelled_orders: int = 0
        self.total_submitted_quantity: int = 0
        self.total_cancelled_quantity: int = 0
        self.total_executed_quantity: int = 0

    def submit_limit_order(
        self,
        order_id: str,
        side: Side,
        price: PriceInput,
        quantity: int,
    ) -> list[Trade]:
        """Match an incoming limit order against the opposite side; rest any remainder."""
        clean_id, valid_side, dec_price, ticks, qty = self.book.validate_order_params(
            order_id, side, price, quantity
        )
        seq = self.book.next_sequence()
        self.book.mark_order_id_seen(clean_id)

        incoming = Order(
            order_id=clean_id,
            side=valid_side,
            price=dec_price,
            quantity=qty,
            timestamp=seq,
            price_ticks=ticks,
            initial_quantity=qty,
            status="active",
        )
        self.submitted_orders += 1
        self.total_submitted_quantity += qty

        new_trades: list[Trade] = []
        resting_side: Side = "sell" if valid_side == "buy" else "buy"

        while incoming.quantity > 0:
            resting = self.book.peek_best_order(resting_side)
            if resting is None:
                break

            crosses = (
                incoming.price_ticks >= resting.price_ticks
                if valid_side == "buy"
                else incoming.price_ticks <= resting.price_ticks
            )
            if not crosses:
                break

            traded_qty = min(incoming.quantity, resting.quantity)
            self._trade_seq += 1
            trade = Trade(
                buy_order_id=clean_id if valid_side == "buy" else resting.order_id,
                sell_order_id=resting.order_id if valid_side == "buy" else clean_id,
                price=resting.price,
                quantity=traded_qty,
                aggressor_side=valid_side,
                timestamp=seq,
                trade_id=self._trade_seq,
            )
            new_trades.append(trade)
            self.trades.append(trade)

            incoming.quantity -= traded_qty
            resting.quantity -= traded_qty
            self.total_executed_quantity += traded_qty

            if resting.quantity == 0:
                self.book.remove_filled_best_order(resting)
            else:
                resting.status = "partial"

        if incoming.quantity > 0:
            if incoming.quantity < incoming.initial_quantity:
                incoming.status = "partial"
            self.book.rest_order(incoming)
        else:
            incoming.status = "filled"

        return new_trades

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a resting order and update execution conservation counters."""
        order = self.book.get_order(order_id)
        if order is None:
            return False
        remaining = order.quantity
        cancelled = self.book.cancel_order(order_id)
        if cancelled:
            self.cancelled_orders += 1
            self.total_cancelled_quantity += remaining
        return cancelled
