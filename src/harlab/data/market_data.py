"""Clean market-data architecture with strict provenance and schema validation.

Key guarantees:
- Synthetic data is ALWAYS explicitly labelled ``is_synthetic=True``.
- Historical OHLCV datasets are explicitly marked ``has_order_book_depth=False``
  so candle data can never be misrepresented as L2 order-book depth.
- ``DataProvider`` defines a clean extension seam for future licensed market feeds.
"""
from __future__ import annotations

import csv
import io
import math
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal

SourceType = Literal[
    "synthetic_lob",
    "historical_ohlcv",
    "historical_trades",
    "historical_l2",
]


@dataclass
class DatasetMetadata:
    """Provenance and structural metadata for a registered HARLAB dataset."""

    dataset_id: str
    name: str
    source_type: SourceType
    is_synthetic: bool
    has_order_book_depth: bool
    row_count: int
    columns: list[str]
    timestamp_column: str
    missing_values_dropped: int = 0
    description: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Dataset:
    """In-memory validated dataset paired with provenance metadata."""

    metadata: DatasetMetadata
    records: list[dict[str, Any]] = field(default_factory=list)


class DataProvider(ABC):
    """Extension interface for integrating external licensed data providers later."""

    @abstractmethod
    def load(self, **kwargs: Any) -> Dataset:
        """Load and validate a dataset from an external or local source."""


REQUIRED_OHLCV_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")


def _parse_float(value: str, field_name: str, row_idx: int) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Row {row_idx}: invalid float for '{field_name}': {value!r}") from exc
    if math.isnan(num) or math.isinf(num):
        raise ValueError(f"Row {row_idx}: non-finite value for '{field_name}'")
    return num


def _parse_timestamp(value: str, row_idx: int) -> str:
    text = (value or "").strip()
    if not text:
        raise ValueError(f"Row {row_idx}: empty timestamp")
    # Accept ISO-8601 strings or numeric epoch/step integers
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
        return text
    except ValueError:
        try:
            float(text)
            return text
        except ValueError as exc:
            raise ValueError(
                f"Row {row_idx}: timestamp must be ISO-8601 or numeric (got {text!r})"
            ) from exc


def load_ohlcv_csv(
    csv_text: str,
    dataset_id: str,
    name: str,
    is_synthetic: bool = False,
    drop_missing: bool = True,
    description: str = "",
) -> Dataset:
    """Parse and strictly validate a historical OHLCV CSV string.

    Explicitly marks ``has_order_book_depth=False`` so OHLCV bars are never
    treated as reconstructed order-book snapshots.
    """
    if not csv_text or not csv_text.strip():
        raise ValueError("CSV content is empty")

    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    if reader.fieldnames is None:
        raise ValueError("CSV must contain a header row")

    normalized_fields = [f.strip().lower() for f in reader.fieldnames]
    missing_cols = [c for c in REQUIRED_OHLCV_COLUMNS if c not in normalized_fields]
    if missing_cols:
        raise ValueError(f"CSV missing required OHLCV columns: {missing_cols}")

    field_map = {f.strip().lower(): f for f in reader.fieldnames}
    records: list[dict[str, Any]] = []
    dropped = 0
    prev_ts: str | None = None

    for row_idx, raw_row in enumerate(reader, start=2):
        vals = {col: (raw_row.get(field_map[col]) or "").strip() for col in REQUIRED_OHLCV_COLUMNS}
        if any(v == "" for v in vals.values()):
            if drop_missing:
                dropped += 1
                continue
            raise ValueError(f"Row {row_idx}: missing value(s) in OHLCV row")

        ts = _parse_timestamp(vals["timestamp"], row_idx)
        o = _parse_float(vals["open"], "open", row_idx)
        h = _parse_float(vals["high"], "high", row_idx)
        lo = _parse_float(vals["low"], "low", row_idx)
        c = _parse_float(vals["close"], "close", row_idx)
        v = _parse_float(vals["volume"], "volume", row_idx)

        if min(o, h, lo, c) <= 0:
            raise ValueError(f"Row {row_idx}: OHLC prices must be positive")
        if h < max(o, c) or lo > min(o, c) or lo > h:
            raise ValueError(f"Row {row_idx}: inconsistent OHLC bar (high/low bounds violated)")
        if v < 0:
            raise ValueError(f"Row {row_idx}: volume cannot be negative")
        if prev_ts is not None and ts < prev_ts:
            raise ValueError(f"Row {row_idx}: timestamps must be non-decreasing")
        prev_ts = ts

        records.append(
            {
                "timestamp": ts,
                "open": o,
                "high": h,
                "low": lo,
                "close": c,
                "volume": v,
            }
        )

    if not records:
        raise ValueError("No valid OHLCV rows remained after validation")

    metadata = DatasetMetadata(
        dataset_id=dataset_id,
        name=name,
        source_type="historical_ohlcv",
        is_synthetic=is_synthetic,
        has_order_book_depth=False,
        row_count=len(records),
        columns=list(REQUIRED_OHLCV_COLUMNS),
        timestamp_column="timestamp",
        missing_values_dropped=dropped,
        description=description or "Imported OHLCV candle dataset (no L2 order-book depth).",
        notes="OHLCV bars cannot reconstruct limit order book queues or L2 imbalance.",
    )
    return Dataset(metadata=metadata, records=records)


def dataset_from_simulation(
    sim_result: dict[str, Any],
    dataset_id: str,
    name: str,
) -> Dataset:
    """Wrap a ``MarketSimulator.run()`` output as a validated synthetic LOB dataset."""
    series = sim_result.get("series", [])
    if not series:
        raise ValueError("Simulation output contains no time-series records")
    columns = list(series[0].keys())
    cfg = sim_result.get("config", {})
    metadata = DatasetMetadata(
        dataset_id=dataset_id,
        name=name,
        source_type="synthetic_lob",
        is_synthetic=True,
        has_order_book_depth=True,
        row_count=len(series),
        columns=columns,
        timestamp_column="step",
        missing_values_dropped=0,
        description=(
            f"SYNTHETIC LOB dataset (scenario={cfg.get('scenario_name', 'custom')}, "
            f"seed={cfg.get('seed')}, steps={cfg.get('steps')})."
        ),
        notes="Generated by deterministic HARLAB MarketSimulator. Not live market data.",
    )
    return Dataset(metadata=metadata, records=series)


class DatasetRegistry:
    """In-memory registry of validated synthetic and imported datasets."""

    def __init__(self) -> None:
        self._datasets: dict[str, Dataset] = {}

    def register(self, dataset: Dataset) -> DatasetMetadata:
        self._datasets[dataset.metadata.dataset_id] = dataset
        return dataset.metadata

    def get(self, dataset_id: str) -> Dataset:
        if dataset_id not in self._datasets:
            raise KeyError(f"Dataset not found: {dataset_id}")
        return self._datasets[dataset_id]

    def list_metadata(self) -> list[dict[str, Any]]:
        return [ds.metadata.to_dict() for ds in self._datasets.values()]
