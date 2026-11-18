"""HARLAB FastAPI backend application.

Reuses the deterministic ``harlab`` research engine directly—no duplicated logic.
"""
from __future__ import annotations

import os
import uuid
from decimal import Decimal
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from .. import __version__
from ..ai.env_loader import load_local_env
from ..data.market_data import dataset_from_simulation, load_ohlcv_csv
from ..data.live_feed import fetch_live_book
from ..market.market_metrics import snapshot_metrics
from ..research.experiments import ExperimentConfig, list_default_hypotheses
from ..simulation.market_simulator import (
    MarketSimulator,
    PRESET_SCENARIOS,
    SimulationConfig,
)
from .schemas import (
    AIAssistRequest,
    ExperimentRunRequest,
    ResetBookRequest,
    SimulationRunRequest,
    SubmitOrderRequest,
    UploadOhlcvRequest,
)
from .state import LabState


def create_app(lab_state: LabState | None = None) -> FastAPI:
    load_local_env()
    """Application factory enabling clean isolated test instances."""
    state = lab_state or LabState()

    app = FastAPI(
        title="HARLAB — Quantitative Market Research Laboratory API",
        version=__version__,
        description=(
            "Deterministic limit order book, market microstructure metrics, "
            "reproducible simulation, hypothesis evaluation, and three-provider AI assistant."
        ),
    )

    allowed_origins = os.getenv(
        "HARLAB_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000",
    ).split(",")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in allowed_origins if o.strip()],
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    def _book_payload(levels: int = 10) -> dict[str, Any]:
        book = state.engine.book
        return {
            "data_origin": "SYNTHETIC_WORKBENCH",
            "is_synthetic": True,
            "tick_size": float(book.tick_size),
            "bids": [[float(p), q] for p, q in book.depth("buy", levels)],
            "asks": [[float(p), q] for p, q in book.depth("sell", levels)],
            "active_orders": [
                {
                    "order_id": o.order_id,
                    "side": o.side,
                    "price": float(o.price),
                    "quantity": o.quantity,
                    "initial_quantity": o.initial_quantity,
                    "status": o.status,
                    "timestamp": o.timestamp,
                }
                for o in book.active_orders()
            ],
            "recent_trades": [
                {
                    "trade_id": t.trade_id,
                    "buy_order_id": t.buy_order_id,
                    "sell_order_id": t.sell_order_id,
                    "price": float(t.price),
                    "quantity": t.quantity,
                    "aggressor_side": t.aggressor_side,
                    "timestamp": t.timestamp,
                }
                for t in reversed(state.engine.trades[-50:])
            ],
            "metrics": snapshot_metrics(book, engine=state.engine, levels=5),
        }

    # --- Health & System Status ---
    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "project": "HARLAB",
            "version": __version__,
            "datasets_count": len(state.datasets.list_metadata()),
            "experiments_count": len(state.experiments.list_all()),
            "simulations_run": state.simulation_count,
            "ai": state.ai_router.status(),
        }

    # --- Order Book Explorer ---
    @app.get("/api/book/snapshot")
    def get_book_snapshot(levels: int = Query(10, ge=1, le=50)) -> dict[str, Any]:
        return _book_payload(levels=levels)



    
    @app.get("/api/live/book")
    def get_live_book(
        venue: str = Query("binance"),
        asset: str = Query("BTC"),
        levels: int = Query(10, ge=5, le=20),
    ) -> dict[str, Any]:
        try:
            return fetch_live_book(venue=venue, asset=asset, levels=levels)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Live feed unavailable: {exc}") from exc

    @app.post("/api/book/orders")
    def submit_order(req: SubmitOrderRequest) -> dict[str, Any]:
        try:
            trades = state.engine.submit_limit_order(
                order_id=req.order_id,
                side=req.side,
                price=req.price,
                quantity=req.quantity,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return {
            "accepted": True,
            "order_id": req.order_id.strip(),
            "trades": [
                {
                    "trade_id": t.trade_id,
                    "buy_order_id": t.buy_order_id,
                    "sell_order_id": t.sell_order_id,
                    "price": float(t.price),
                    "quantity": t.quantity,
                    "aggressor_side": t.aggressor_side,
                    "timestamp": t.timestamp,
                }
                for t in trades
            ],
            "snapshot": _book_payload(levels=10),
        }

    @app.delete("/api/book/orders/{order_id}")
    def cancel_order(order_id: str) -> dict[str, Any]:
        cancelled = state.engine.cancel_order(order_id)
        if not cancelled:
            raise HTTPException(
                status_code=404,
                detail=f"Active resting order not found: {order_id}",
            )
        return {
            "cancelled": True,
            "order_id": order_id,
            "snapshot": _book_payload(levels=10),
        }

    @app.post("/api/book/reset")
    def reset_book(req: ResetBookRequest) -> dict[str, Any]:
        try:
            tick = Decimal(req.tick_size)
            state.reset_book(tick_size=tick, seed_demo=req.seed_demo)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"reset": True, "snapshot": _book_payload(levels=10)}

    # --- Simulation Lab ---
    @app.get("/api/simulation/scenarios")
    def get_scenarios() -> dict[str, Any]:
        return {"scenarios": PRESET_SCENARIOS}

    @app.get("/api/simulation/latest")
    def get_latest_simulation() -> dict[str, Any]:
        if state.last_simulation is None:
            raise HTTPException(status_code=404, detail="No simulation has been run yet.")
        return state.last_simulation

    @app.post("/api/simulation/run")
    def run_simulation(req: SimulationRunRequest) -> dict[str, Any]:
        try:
            cfg = SimulationConfig(
                seed=req.seed,
                steps=req.steps,
                initial_mid=Decimal(req.initial_mid),
                tick_size=Decimal(req.tick_size),
                initial_levels=req.initial_levels,
                base_spread_ticks=req.base_spread_ticks,
                limit_order_prob=req.limit_order_prob,
                marketable_order_prob=req.marketable_order_prob,
                cancel_prob=req.cancel_prob,
                buy_bias=req.buy_bias,
                volatility_ticks=req.volatility_ticks,
                min_qty=req.min_qty,
                max_qty=req.max_qty,
                scenario_name=req.scenario_name,
            )
            sim_out = MarketSimulator(cfg).run()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        state.last_simulation = sim_out
        state.simulation_count += 1
        ds_id = f"sim_{req.scenario_name}_{req.seed}_{uuid.uuid4().hex[:4]}"
        ds_name = req.dataset_name or (
            f"SYNTHETIC LOB — {req.scenario_name} (seed={req.seed}, {req.steps} steps)"
        )
        ds = dataset_from_simulation(sim_out, dataset_id=ds_id, name=ds_name)
        meta = state.datasets.register(ds)
        return {
            "dataset": meta.to_dict(),
            "simulation": sim_out,
        }

    # --- Datasets & Regimes ---
    @app.get("/api/datasets")
    def list_datasets() -> dict[str, Any]:
        return {"datasets": state.datasets.list_metadata()}

    @app.post("/api/datasets/upload-ohlcv")
    def upload_ohlcv(req: UploadOhlcvRequest) -> dict[str, Any]:
        ds_id = f"ohlcv_{uuid.uuid4().hex[:6]}"
        try:
            ds = load_ohlcv_csv(
                csv_text=req.csv_text,
                dataset_id=ds_id,
                name=req.name,
                is_synthetic=req.is_synthetic,
                description=req.description,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        meta = state.datasets.register(ds)
        return {"dataset": meta.to_dict()}

    @app.get("/api/datasets/{dataset_id}/regimes")
    def dataset_regimes(dataset_id: str) -> dict[str, Any]:
        try:
            return state.compute_regimes(dataset_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # --- Research Workbench ---
    @app.get("/api/research/hypotheses")
    def get_hypotheses() -> dict[str, Any]:
        return {"hypotheses": list_default_hypotheses()}

    @app.get("/api/research/experiments")
    def list_experiments() -> dict[str, Any]:
        return {"experiments": state.experiments.list_all()}

    @app.post("/api/research/experiments")
    def run_experiment(req: ExperimentRunRequest) -> dict[str, Any]:
        try:
            ds = state.datasets.get(req.dataset_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        try:
            cfg = ExperimentConfig(
                hypothesis_id=req.hypothesis_id,
                dataset_id=req.dataset_id,
                horizon=req.horizon,
                train_ratio=req.train_ratio,
                walk_forward_folds=req.walk_forward_folds,
                signal_threshold=req.signal_threshold,
                fee_bps=req.fee_bps,
                slippage_bps=req.slippage_bps,
                imbalance_levels=req.imbalance_levels,
                notes=req.notes,
            )
            result = state.runner.run(ds, cfg)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        state.experiments.save(result)
        return result.to_dict()

    @app.get("/api/research/experiments/{experiment_id}/export")
    def export_experiment(
        experiment_id: str,
        fmt: str = Query("json"),
    ) -> PlainTextResponse:
        if fmt not in ("json", "csv"):
            raise HTTPException(status_code=400, detail="fmt must be 'json' or 'csv'")
        try:
            if fmt == "csv":
                content = state.experiments.export_csv(experiment_id)
                return PlainTextResponse(content, media_type="text/csv")
            content = state.experiments.export_json(experiment_id)
            return PlainTextResponse(content, media_type="application/json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    # --- AI Research Assistant (Three-Provider Failover) ---
    @app.get("/api/ai/status")
    def ai_status() -> dict[str, Any]:
        return state.ai_router.status()

    @app.post("/api/ai/assist")
    def ai_assist(req: AIAssistRequest) -> dict[str, Any]:
        context: dict[str, Any] = {}
        if req.experiment_id:
            try:
                exp = state.experiments.get(req.experiment_id)
                context["experiment"] = {
                    "experiment_id": exp.experiment_id,
                    "hypothesis": exp.hypothesis["title"],
                    "dataset": exp.dataset["name"],
                    "is_synthetic": exp.dataset["is_synthetic"],
                    "out_of_sample_stats": exp.out_of_sample_stats,
                    "cost_aware_backtest": exp.cost_aware_backtest,
                    "conclusion": exp.conclusion,
                    "warnings": exp.warnings,
                }
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc

        if req.include_book_context:
            context["active_order_book_metrics"] = snapshot_metrics(
                state.engine.book, engine=state.engine, levels=5
            )

        try:
            return state.assistant.ask(req.question, context=context)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


app = create_app()
