# Changelog

## v0.2.0 — Complete Quantitative Research Workstation
### Preserved
- Original `src/harlab/` package layout, `scripts/demo_order_book.py`, `seed_demo_market`, `deque` FIFO queues, and `.env.example` AI provider lineup (`GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`).

### Fixed (Phase 2)
- Replaced IEEE-754 `float` price keys with exact `Decimal` + integer tick indexing (`tick_size` policy); eliminated spread drift (`0.19999999999998863` → `0.20`).
- Unified order validation and blocked `NaN`, `Inf`, `-Inf`, off-tick prices, boolean quantities (`True`/`False`), and reuse of filled/cancelled `order_id`s.
- Fixed `MatchingEngine` hardcoded `timestamp=0` bug by issuing monotonic sequence IDs from `OrderBook.next_sequence()`.
- Removed private `_orders`/`_bids`/`_asks` coupling between `MatchingEngine` and `OrderBook`.

### Added (Phases 3–8)
- All 12 documented market microstructure metrics (`market_metrics.py`).
- Reproducible seeded `MarketSimulator` with 3 preset scenarios and explicit `SYNTHETIC` tags.
- Validated `DatasetRegistry` and OHLCV CSV ingestion with strict OHLCV-vs-L2 separation.
- Structured `ExperimentRunner` with chronological train/test splits, purged horizon gap, leakage verification, walk-forward folds, Pearson/Spearman/OLS/95% CI statistics, cost-aware backtester, and JSON/CSV export.
- Leakage-free `VolatilityLiquidityRegimeClassifier` fit strictly on training splits.
- Three-provider AI failover router (`Gemini → Groq → OpenRouter`) with failure classification, exponential backoff retries, cooldown recovery, usage tracking, and zero secret exposure.
- FastAPI REST backend (`src/harlab/api/`) and React 18 + TypeScript + Vite institutional dark frontend (`frontend/`).
- Expanded automated backend test suite from 9 to 30 tests (including 1,500-operation randomized invariant fuzzing and FastAPI endpoint tests) plus Vitest frontend tests.
