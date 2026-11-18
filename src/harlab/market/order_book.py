"""Exact-tick in-memory limit order book with strict price-time priority.

Design assumptions & documented limitations:
- Single-threaded, synchronous execution (not a concurrent exchange gateway).
- Limit orders only (no stop, iceberg, hidden, peg, or FOK/IOC orders).
- Prices are represented as exact ``Decimal`` multiples of a fixed ``tick_size``
  and indexed internally by integer ticks to eliminate IEEE-754 rounding drift.
- Quantities are strictly positive integers (lot/share units); booleans are rejected.
- Order identifiers are unique over the lifetime of the book (filled or cancelled
  IDs cannot be reused) so trade and audit logs remain unambiguous.
- Direct ``OrderBook.add_limit_order`` inserts a resting order without matching;
  use ``MatchingEngine.submit_limit_order`` for continuous limit-order matching.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Deque, Literal, Union

Side = Literal["buy", "sell"]
OrderStatus = Literal["active", "partial", "filled", "cancelled"]
PriceInput = Union[Decimal, int, float, str]

DEFAULT_TICK_SIZE = Decimal("0.01")


def parse_tick_size(tick_size: PriceInput) -> Decimal:
    """Validate and normalize a positive finite tick size."""
    if isinstance(tick_size, bool):
        raise ValueError("tick_size cannot be a boolean")
    if isinstance(tick_size, float):
        if math.isnan(tick_size) or math.isinf(tick_size):
            raise ValueError("tick_size must be finite")
        dec = Decimal(str(tick_size))
    elif isinstance(tick_size, (int, str, Decimal)):
        try:
            dec = Decimal(tick_size)
        except InvalidOperation as exc:
            raise ValueError(f"invalid tick_size: {tick_size!r}") from exc
    else:
        raise ValueError(f"unsupported tick_size type: {type(tick_size).__name__}")

    if not dec.is_finite() or dec <= 0:
        raise ValueError("tick_size must be a finite positive number")
    return dec.normalize() if dec != dec.to_integral_value() else dec


def parse_price(price: PriceInput, tick_size: Decimal) -> tuple[Decimal, int]:
    """Validate a price against ``tick_size`` and return ``(decimal_price, ticks)``."""
    if isinstance(price, bool):
        raise ValueError("price cannot be a boolean")
    if isinstance(price, float):
        if math.isnan(price) or math.isinf(price):
            raise ValueError("price must be finite (NaN/Inf rejected)")
        dec = Decimal(str(price))
    elif isinstance(price, (int, str, Decimal)):
        try:
            dec = Decimal(price)
        except InvalidOperation as exc:
            raise ValueError(f"invalid price: {price!r}") from exc
    else:
        raise ValueError(f"unsupported price type: {type(price).__name__}")

    if not dec.is_finite() or dec <= 0:
        raise ValueError("price must be a finite positive number")

    remainder = dec % tick_size
    if remainder != 0:
        raise ValueError(
            f"price {dec} is not aligned to tick_size {tick_size}"
        )

    ticks = int(dec // tick_size)
    canonical_price = (ticks * tick_size).quantize(tick_size)
    return canonical_price, ticks


def validate_quantity(quantity: object) -> int:
    """Validate that quantity is a strictly positive integer (excluding booleans)."""
    if isinstance(quantity, bool) or not isinstance(quantity, int):
        raise ValueError("quantity must be a positive integer (booleans rejected)")
    if quantity <= 0:
        raise ValueError("quantity must be a positive integer")
    return quantity


@dataclass
class Order:
    """A single limit order tracked by the order book."""

    order_id: str
    side: Side
    price: Decimal
    quantity: int
    timestamp: int
    price_ticks: int = 0
    initial_quantity: int = 0
    status: OrderStatus = "active"

    def __post_init__(self) -> None:
        if self.initial_quantity == 0:
            self.initial_quantity = self.quantity


class OrderBook:
    """Price-time-priority limit order book using exact integer-tick indexing."""

    def __init__(self, tick_size: PriceInput = DEFAULT_TICK_SIZE) -> None:
        self.tick_size: Decimal = parse_tick_size(tick_size)
        self._bids: dict[int, Deque[Order]] = {}
        self._asks: dict[int, Deque[Order]] = {}
        self._orders: dict[str, Order] = {}
        self._seen_order_ids: set[str] = set()
        self._clock: int = 0

    def next_sequence(self) -> int:
        """Advance and return the monotonic arrival sequence counter."""
        self._clock += 1
        return self._clock

    def validate_order_params(
        self,
        order_id: str,
        side: Side,
        price: PriceInput,
        quantity: int,
    ) -> tuple[str, Side, Decimal, int, int]:
        """Single validation entry point shared by OrderBook and MatchingEngine."""
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        if not isinstance(order_id, str) or not order_id.strip():
            raise ValueError("order_id must be a non-empty string")
        clean_id = order_id.strip()
        if clean_id in self._seen_order_ids:
            raise ValueError(f"duplicate order_id: {clean_id}")
        dec_price, ticks = parse_price(price, self.tick_size)
        qty = validate_quantity(quantity)
        return clean_id, side, dec_price, ticks, qty

    def mark_order_id_seen(self, order_id: str) -> None:
        """Record an order ID as used so filled/cancelled IDs cannot be reused."""
        self._seen_order_ids.add(order_id)

    def add_limit_order(
        self,
        order_id: str,
        side: Side,
        price: PriceInput,
        quantity: int,
    ) -> Order:
        """Insert a validated limit order directly onto the resting book."""
        clean_id, valid_side, dec_price, ticks, qty = self.validate_order_params(
            order_id, side, price, quantity
        )
        seq = self.next_sequence()
        order = Order(
            order_id=clean_id,
            side=valid_side,
            price=dec_price,
            quantity=qty,
            timestamp=seq,
            price_ticks=ticks,
            initial_quantity=qty,
            status="active",
        )
        self.rest_order(order)
        return order

    def rest_order(self, order: Order) -> None:
        """Place an order (or unfilled remainder) at the back of its price queue."""
        levels = self._bids if order.side == "buy" else self._asks
        levels.setdefault(order.price_ticks, deque()).append(order)
        self._orders[order.order_id] = order
        self._seen_order_ids.add(order.order_id)

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an active resting order. Returns True if cancelled, False if not active."""
        order = self._orders.get(order_id)
        if order is None:
            return False
        levels = self._bids if order.side == "buy" else self._asks
        queue = levels.get(order.price_ticks)
        if queue is not None:
            try:
                queue.remove(order)
            except ValueError:
                pass
            if not queue:
                del levels[order.price_ticks]
        del self._orders[order_id]
        order.status = "cancelled"
        return True

    def get_order(self, order_id: str) -> Order | None:
        """Return an active resting order by ID, or None if not resting."""
        return self._orders.get(order_id)

    def active_orders(self) -> list[Order]:
        """Return all currently resting orders sorted by arrival sequence."""
        return sorted(self._orders.values(), key=lambda o: o.timestamp)

    def _ticks_to_price(self, ticks: int) -> Decimal:
        return (ticks * self.tick_size).quantize(self.tick_size)

    @property
    def best_bid_ticks(self) -> int | None:
        return max(self._bids) if self._bids else None

    @property
    def best_ask_ticks(self) -> int | None:
        return min(self._asks) if self._asks else None

    @property
    def best_bid(self) -> Decimal | None:
        ticks = self.best_bid_ticks
        return self._ticks_to_price(ticks) if ticks is not None else None

    @property
    def best_ask(self) -> Decimal | None:
        ticks = self.best_ask_ticks
        return self._ticks_to_price(ticks) if ticks is not None else None

    @property
    def spread(self) -> Decimal | None:
        if self.best_bid_ticks is None or self.best_ask_ticks is None:
            return None
        return self._ticks_to_price(self.best_ask_ticks - self.best_bid_ticks)

    @property
    def is_crossed(self) -> bool:
        if self.best_bid_ticks is None or self.best_ask_ticks is None:
            return False
        return self.best_bid_ticks >= self.best_ask_ticks

    def peek_best_order(self, side: Side) -> Order | None:
        """Return the front FIFO order at the best price on ``side`` without removing it."""
        if side == "buy":
            ticks = self.best_bid_ticks
            levels = self._bids
        else:
            ticks = self.best_ask_ticks
            levels = self._asks
        if ticks is None:
            return None
        return levels[ticks][0]

    def remove_filled_best_order(self, order: Order) -> None:
        """Remove a fully filled order from the front of its price-level queue."""
        levels = self._bids if order.side == "buy" else self._asks
        queue = levels.get(order.price_ticks)
        if queue:
            if queue[0] is order:
                queue.popleft()
            else:
                queue.remove(order)
            if not queue:
                del levels[order.price_ticks]
        self._orders.pop(order.order_id, None)
        order.status = "filled"

    def depth(self, side: Side, levels: int | None = 5) -> list[tuple[Decimal, int]]:
        """Return aggregated ``[(price, total_qty), ...]`` sorted best-to-worst."""
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        if levels is not None:
            if isinstance(levels, bool) or not isinstance(levels, int) or levels < 0:
                raise ValueError("levels must be a non-negative integer or None")
        book = self._bids if side == "buy" else self._asks
        sorted_ticks = sorted(book, reverse=(side == "buy"))
        if levels is not None:
            sorted_ticks = sorted_ticks[:levels]
        return [
            (
                self._ticks_to_price(ticks),
                sum(order.quantity for order in book[ticks]),
            )
            for ticks in sorted_ticks
        ]

    def snapshot(self, levels: int = 5) -> dict[str, list[tuple[Decimal, int]]]:
        """Return top-of-book aggregated bid and ask ladders."""
        return {
            "bids": self.depth("buy", levels),
            "asks": self.depth("sell", levels),
        }

    def total_resting_quantity(self) -> int:
        """Return total remaining quantity across all active resting orders."""
        return sum(order.quantity for order in self._orders.values())
