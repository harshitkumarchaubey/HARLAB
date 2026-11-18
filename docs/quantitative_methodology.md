# HARLAB Quantitative Methodology & Assumptions

## 1. Exact-Tick Order Book Representation
- All prices are exact `Decimal` multiples of a configured positive `tick_size` (default `0.01`).
- Internally, price levels are keyed by integer ticks `k = int(price // tick_size)`, eliminating IEEE-754 binary floating-point drift in spread calculation and price-level hashing.
- **Conservation invariant:** At every step of continuous matching and cancellation,
  $$\text{Total Submitted Qty} = \text{Resting Qty} + \text{Cancelled Qty} + 2 \times \text{Executed Qty}$$
  (each executed share consumes 1 share of buy quantity and 1 share of sell quantity).

## 2. Market Microstructure Metrics
All metrics return `None` when the book is empty or a denominator is zero (counts/volumes return `0`).

1. **Bid-Ask Spread** (quote currency): $S = P_{\text{ask},1} - P_{\text{bid},1}$.
2. **Mid-Price** (quote currency): $M = \frac{P_{\text{bid},1} + P_{\text{ask},1}}{2}$.
3. **Relative Spread** (dimensionless; $\times 10^4$ for bps): $S_{\text{rel}} = \frac{S}{M}$.
4. **Order-Book Imbalance** (dimensionless, $[-1, 1]$):
   $$I_L = \frac{\sum_{i=1}^L Q_{\text{bid},i} - \sum_{j=1}^L Q_{\text{ask},j}}{\sum_{i=1}^L Q_{\text{bid},i} + \sum_{j=1}^L Q_{\text{ask},j}}$$
5. **Bid / Ask / Total Displayed Depth** (shares/lots): summed resting quantity across top $L$ levels (or all levels).
6. **Weighted Mid-Price** (quote currency, requires both sides non-empty):
   $$M_w = \frac{\sum_{i=1}^L P_{\text{bid},i} Q_{\text{bid},i} + \sum_{j=1}^L P_{\text{ask},j} Q_{\text{ask},j}}{\sum_{i=1}^L Q_{\text{bid},i} + \sum_{j=1}^L Q_{\text{ask},j}}$$
7. **Microprice** (quote currency, Gatheral/Stoikov top-of-book definition):
   $$P_{\text{micro}} = \frac{P_{\text{bid},1} Q_{\text{ask},1} + P_{\text{ask},1} Q_{\text{bid},1}}{Q_{\text{bid},1} + Q_{\text{ask},1}}$$
8. **Price Changes & Simple Returns**: $\Delta P_t = P_t - P_{t-1}$ and $r_t = (P_t - P_{t-1}) / P_{t-1}$.
9. **Trade Volume & VWAP**: $\text{VWAP} = \frac{\sum_k P_k Q_k}{\sum_k Q_k}$.
10. **Execution Statistics**: trade count, total executed volume, average trade size, fill rate, and buy/sell aggressor breakdown.

## 3. Simulation & Experiment Assumptions
- **Synthetic simulator:** Uses a local `random.Random(seed)` instance for byte-identical reproducibility across runs. It models stylized passive limit, aggressive crossing limit, and cancellation arrivals—not real market microstructure or adverse selection.
- **OHLCV vs. L2 Separation:** OHLCV CSV imports set `has_order_book_depth = False`. The `ExperimentRunner` rejects L2 imbalance hypotheses on OHLCV-only datasets.
- **Leakage Controls:** Train/test splits are strictly chronological with a purged horizon gap (`test_start = split + horizon`) so no training target overlaps with test feature timestamps.
- **Cost-Aware Backtesting:** Evaluates directional signals net of round-trip transaction costs `2 * (fee_bps + slippage_bps)` per trade, without assuming queue-priority fills or zero market impact.
