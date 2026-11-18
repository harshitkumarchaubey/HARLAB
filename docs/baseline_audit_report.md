# Phase 1 — Baseline Audit & Independent Report Verification

This document verifies every claim in `HARLAB Quantitative Audit Report.pdf` against the original `HARLAB.zip` source code before any modifications were made.

## Baseline Inventory
- **Files inspected:** 22 active files (`src/harlab/market/{order_book,matching_engine,market_metrics}.py`, `simulation/market_simulator.py`, `research/hypotheses.py`, 4 test files, `scripts/demo_order_book.py`, config, and empty scaffold modules).
- **Baseline tests:** 9/9 passed (`test_order_book.py`, `test_matching_engine.py`, `test_market_metrics.py`, `test_simulator.py`).
- **Baseline demo output:** `scripts/demo_order_book.py` printed `Spread: 0.19999999999998863` due to binary float subtraction (`100.1 - 99.9`).

## Verification of Independent Audit Report Findings

| Audit Finding | Audit Severity | Verification Against Code | Resolution in HARLAB v0.2.0 |
| :--- | :--- | :--- | :--- |
| **1. Price-Time Priority & Queue Instability** (`order_book.py`) | HIGH | **Incorrect / Overstated.** Each price level uses `collections.deque` (strict FIFO) and `OrderBook._clock` is monotonic. However, `MatchingEngine.submit_limit_order` hardcoded `timestamp=0` and bypassed `_clock`. | Preserved `deque` FIFO; fixed `MatchingEngine` to allocate monotonic sequence timestamps via `book.next_sequence()`. |
| **2. Matching Engine Remainder Priority Loss** (`matching_engine.py`) | CRITICAL | **Incorrect & Conceptually Flawed.** Incoming aggressive orders did NOT get a new timestamp on partial fill; conceptually, an incoming order's unfilled remainder *must* join the back of its limit queue (behind earlier resting orders). Resting partial fills already stayed at `queue[0]`. | Preserved correct resting `queue[0]` priority and back-of-queue resting for incoming remainders; assigned arrival sequence on submission. |
| **3. Cancellation State Desynchronization** (`order_book.py`) | MEDIUM | **Overstated.** The engine is single-threaded and synchronous—there are no concurrent cancellation races. Real gaps were direct access to private `_orders`/`_bids` attributes and allowing reuse of filled/cancelled `order_id`s. | Replaced private attribute access with explicit book methods; tracked `_seen_order_ids` to prevent ID reuse; guarded cancellation cleanup. |
| **4. Floating-Point Price Handling** (`order_book.py`, `market_metrics.py`) | HIGH | **CONFIRMED.** Live demo showed `Spread: 0.19999999999998863`; raw `float` dict keys allow `100.1 + 0.2` and `100.3` to split into distinct levels. Note: the audit's `math.isclose` suggestion is unsafe for dict keys. | Migrated to exact `Decimal` prices indexed by integer ticks (`price_ticks = int(price // tick_size)`) with explicit `tick_size` alignment. |
| **5. Empty-Book Imbalance Division by Zero** (`market_metrics.py`) | MEDIUM | **Incorrect.** `order_imbalance` already returned `None` when `total == 0` and was already covered by `test_empty_imbalance_is_none`. | Preserved `None` guard; added `levels >= 1` validation and expanded from 2 to all 12 documented microstructure metrics. |

## Additional Bugs Found via Direct Code Inspection (Missed by Audit Report)
1. **Boolean quantity bypass:** `isinstance(True, int)` is `True` in Python, so `quantity=True` was accepted as `1`. Fixed via explicit `isinstance(quantity, bool)` rejection.
2. **`NaN` and `Inf` price bypass:** `float('nan') <= 0` evaluates to `False`, allowing `NaN`/`inf` into book keys and breaking `max()`/`min()`. Fixed via explicit `math.isnan`/`math.isinf` and `Decimal.is_finite()` checks.
3. **Duplicated inconsistent validation:** `OrderBook` raised `TypeError` for non-int quantities while `MatchingEngine` raised `ValueError`. Unified into `OrderBook.validate_order_params()`.
4. **Unimplemented research/data/AI/API layers:** `data`, `research/experiments`, `execution`, `ml`, and `ai` were one-line docstring stubs. All are now implemented and tested.
