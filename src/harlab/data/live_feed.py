"""Multi-venue live Level-2 order-book feed (Binance, Coinbase, Kraken)."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx

VENUE_SYMBOLS: dict[str, dict[str, str]] = {
    "binance": {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT"},
    "coinbase": {"BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD"},
    "kraken": {"BTC": "XBTUSD", "ETH": "ETHUSD", "SOL": "SOLUSD"},
}


def _build_snapshot(
    venue: str,
    asset: str,
    pair: str,
    bids: list[list[Decimal]],
    asks: list[list[Decimal]],
    recent_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    if not bids or not asks:
        raise ValueError(f"{venue} returned an empty order book for {pair}.")

    best_bid, bid_q1 = bids[0]
    best_ask, ask_q1 = asks[0]
    spread = best_ask - best_bid
    mid = (best_bid + best_ask) / Decimal("2")
    rel_spread = spread / mid if mid > 0 else Decimal("0")

    l1_total = bid_q1 + ask_q1
    imb_l1 = float((bid_q1 - ask_q1) / l1_total) if l1_total > 0 else None
    micro = (best_bid * ask_q1 + best_ask * bid_q1) / l1_total if l1_total > 0 else None

    bid_l5 = sum(q for _, q in bids[:5])
    ask_l5 = sum(q for _, q in asks[:5])
    imb_l5 = float((bid_l5 - ask_l5) / (bid_l5 + ask_l5)) if (bid_l5 + ask_l5) > 0 else None

    bid_total = sum(q for _, q in bids)
    ask_total = sum(q for _, q in asks)
    notional_l5 = sum(p * q for p, q in bids[:5]) + sum(p * q for p, q in asks[:5])
    w_mid = notional_l5 / (bid_l5 + ask_l5) if (bid_l5 + ask_l5) > 0 else None

    return {
        "data_origin": f"LIVE_{venue.upper()}_{pair}",
        "is_synthetic": False,
        "venue": venue,
        "asset": asset,
        "symbol": pair,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "tick_size": 0.01,
        "bids": [[float(p), round(float(q), 5)] for p, q in bids],
        "asks": [[float(p), round(float(q), 5)] for p, q in asks],
        "active_orders": [],
        "recent_trades": recent_trades,
        "metrics": {
            "best_bid": float(best_bid),
            "best_ask": float(best_ask),
            "spread": float(spread),
            "relative_spread": float(rel_spread),
            "relative_spread_bps": float(rel_spread * Decimal("10000")),
            "mid_price": float(mid),
            "weighted_mid_price": float(w_mid) if w_mid is not None else None,
            "microprice": float(micro) if micro is not None else None,
            "order_imbalance_l1": imb_l1,
            "order_imbalance_l5": imb_l5,
            "bid_depth_l1": round(float(bid_q1), 5),
            "ask_depth_l1": round(float(ask_q1), 5),
            "bid_depth_total": round(float(bid_total), 5),
            "ask_depth_total": round(float(ask_total), 5),
            "total_displayed_depth": round(float(bid_total + ask_total), 5),
            "tick_size": 0.01,
        },
    }


def fetch_live_book(venue: str = "binance", asset: str = "BTC", levels: int = 10) -> dict[str, Any]:
    """Fetch authentic real-time L2 depth from Binance, Coinbase, or Kraken."""
    v = venue.lower().strip()
    a = asset.upper().strip()
    if v not in VENUE_SYMBOLS:
        raise ValueError(f"Unsupported venue '{v}'. Choose from {list(VENUE_SYMBOLS)}.")
    if a not in VENUE_SYMBOLS[v]:
        raise ValueError(f"Unsupported asset '{a}'. Choose from {list(VENUE_SYMBOLS[v])}.")

    pair = VENUE_SYMBOLS[v][a]
    limit = max(5, min(levels, 20))

    with httpx.Client(timeout=8.0, headers={"User-Agent": "HARLAB/0.2"}) as client:
        if v == "binance":
            r = client.get(
                "https://data-api.binance.vision/api/v3/depth",
                params={"symbol": pair, "limit": limit},
            )
            r.raise_for_status()
            d = r.json()
            bids = [[Decimal(p), Decimal(q)] for p, q in d["bids"][:limit]]
            asks = [[Decimal(p), Decimal(q)] for p, q in d["asks"][:limit]]
            return _build_snapshot(v, a, pair, bids, asks, [])

        if v == "coinbase":
            r = client.get(
                f"https://api.exchange.coinbase.com/products/{pair}/book",
                params={"level": 2},
            )
            r.raise_for_status()
            d = r.json()
            bids = [[Decimal(str(row[0])), Decimal(str(row[1]))] for row in d["bids"][:limit]]
            asks = [[Decimal(str(row[0])), Decimal(str(row[1]))] for row in d["asks"][:limit]]
            return _build_snapshot(v, a, pair, bids, asks, [])

        r = client.get(
            "https://api.kraken.com/0/public/Depth",
            params={"pair": pair, "count": limit},
        )
        r.raise_for_status()
        d = r.json()
        if d.get("error"):
            raise ValueError(f"Kraken error: {d['error']}")
        book_obj = next(iter(d["result"].values()))
        bids = [[Decimal(str(row[0])), Decimal(str(row[1]))] for row in book_obj["bids"][:limit]]
        asks = [[Decimal(str(row[0])), Decimal(str(row[1]))] for row in book_obj["asks"][:limit]]
        return _build_snapshot(v, a, pair, bids, asks, [])