"""Pydantic request schemas for the HARLAB backend API."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class SubmitOrderRequest(BaseModel):
    order_id: str = Field(..., min_length=1, max_length=64)
    side: Literal["buy", "sell"]
    price: str = Field(..., description="Exact decimal price string aligned to tick_size")
    quantity: int = Field(..., gt=0)


class ResetBookRequest(BaseModel):
    tick_size: str = Field("0.01", description="Positive decimal tick size")
    seed_demo: bool = True


class SimulationRunRequest(BaseModel):
    seed: int = Field(42, ge=0, le=2_000_000_000)
    steps: int = Field(250, ge=20, le=5000)
    initial_mid: str = Field("100.00")
    tick_size: str = Field("0.01")
    initial_levels: int = Field(5, ge=1, le=20)
    base_spread_ticks: int = Field(2, ge=1, le=20)
    limit_order_prob: float = Field(0.65, ge=0.0, le=1.0)
    marketable_order_prob: float = Field(0.20, ge=0.0, le=1.0)
    cancel_prob: float = Field(0.15, ge=0.0, le=1.0)
    buy_bias: float = Field(0.50, ge=0.0, le=1.0)
    volatility_ticks: int = Field(3, ge=1, le=20)
    min_qty: int = Field(10, ge=1, le=10000)
    max_qty: int = Field(200, ge=1, le=100000)
    scenario_name: str = Field("custom", min_length=1, max_length=64)
    dataset_name: Optional[str] = None


class UploadOhlcvRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    csv_text: str = Field(..., min_length=10)
    is_synthetic: bool = False
    description: str = ""


class ExperimentRunRequest(BaseModel):
    hypothesis_id: str = Field("H1_IMBALANCE_RETURN")
    dataset_id: str
    horizon: int = Field(1, ge=1, le=50)
    train_ratio: float = Field(0.70, ge=0.40, le=0.90)
    walk_forward_folds: int = Field(3, ge=2, le=10)
    signal_threshold: float = Field(0.20, ge=0.0, le=1.0)
    fee_bps: float = Field(1.0, ge=0.0, le=200.0)
    slippage_bps: float = Field(2.0, ge=0.0, le=200.0)
    imbalance_levels: Literal[1, 5] = 1
    notes: str = ""


class AIAssistRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)
    experiment_id: Optional[str] = None
    include_book_context: bool = True
