"""Reproducible hypothesis-testing & experiment evaluation framework.

Supports:
- Strict dataset-to-hypothesis compatibility checks (OHLCV cannot run L2 LOB tests).
- Chronological train/test separation (no random shuffling).
- Explicit data-leakage verification (feature index strictly precedes target horizon).
- Walk-forward out-of-sample evaluation across rolling folds.
- Statistical inference: Pearson r, Spearman rho, OLS slope & R^2, t-stat,
  two-sided p-value, and 95% Fisher-z confidence interval.
- Cost-aware strategy evaluation vs. naive baseline.
- JSON and CSV export of experiment findings.
"""
from __future__ import annotations

import csv
import io
import json
import math
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
from scipy import stats

from ..data.market_data import Dataset
from ..execution.backtester import run_cost_aware_backtest
from ..execution.strategies import imbalance_threshold_signals
from .hypotheses import DEFAULT_HYPOTHESES, Hypothesis, get_hypothesis


@dataclass
class ExperimentConfig:
    hypothesis_id: str = "H1_IMBALANCE_RETURN"
    dataset_id: str = "sim_baseline_42"
    horizon: int = 1
    train_ratio: float = 0.70
    walk_forward_folds: int = 3
    signal_threshold: float = 0.20
    fee_bps: float = 1.0
    slippage_bps: float = 2.0
    imbalance_levels: int = 1
    notes: str = ""

    def validate(self) -> None:
        if self.horizon < 1 or self.horizon > 50:
            raise ValueError("horizon must be between 1 and 50")
        if not (0.4 <= self.train_ratio <= 0.9):
            raise ValueError("train_ratio must be in [0.4, 0.9]")
        if self.walk_forward_folds < 2 or self.walk_forward_folds > 10:
            raise ValueError("walk_forward_folds must be between 2 and 10")
        if not (0.0 <= self.signal_threshold <= 1.0):
            raise ValueError("signal_threshold must be in [0.0, 1.0]")
        if self.fee_bps < 0 or self.slippage_bps < 0:
            raise ValueError("fee_bps and slippage_bps must be non-negative")
        if self.imbalance_levels not in (1, 5):
            raise ValueError("imbalance_levels must be 1 or 5")


def _compute_stats(x: list[float], y: list[float]) -> dict[str, Any]:
    """Compute Pearson r, Spearman rho, OLS fit, t-stat, p-value, and 95% CI."""
    n = len(x)
    if n < 5:
        return {
            "n": n,
            "pearson_r": None,
            "pearson_p": None,
            "spearman_rho": None,
            "spearman_p": None,
            "ols_slope": None,
            "ols_intercept": None,
            "r_squared": None,
            "ci_95_low": None,
            "ci_95_high": None,
            "note": "Insufficient paired observations (need >= 5).",
        }

    xa = np.asarray(x, dtype=float)
    ya = np.asarray(y, dtype=float)
    if np.std(xa) < 1e-12 or np.std(ya) < 1e-12:
        return {
            "n": n,
            "pearson_r": 0.0,
            "pearson_p": 1.0,
            "spearman_rho": 0.0,
            "spearman_p": 1.0,
            "ols_slope": 0.0,
            "ols_intercept": float(np.mean(ya)),
            "r_squared": 0.0,
            "ci_95_low": None,
            "ci_95_high": None,
            "note": "Zero variance in independent or dependent variable.",
        }

    r_val, p_val = stats.pearsonr(xa, ya)
    rho_val, sp_p = stats.spearmanr(xa, ya)
    lin = stats.linregress(xa, ya)

    # 95% confidence interval for Pearson r via Fisher z-transform
    r_clamped = max(-0.999999, min(0.999999, float(r_val)))
    z = math.atanh(r_clamped)
    se = 1.0 / math.sqrt(max(1, n - 3))
    ci_low = math.tanh(z - 1.959964 * se)
    ci_high = math.tanh(z + 1.959964 * se)

    return {
        "n": n,
        "pearson_r": round(float(r_val), 5),
        "pearson_p": round(float(p_val), 6),
        "spearman_rho": round(float(rho_val), 5),
        "spearman_p": round(float(sp_p), 6),
        "ols_slope": round(float(lin.slope), 5),
        "ols_intercept": round(float(lin.intercept), 5),
        "r_squared": round(float(r_val) ** 2, 5),
        "ci_95_low": round(ci_low, 5),
        "ci_95_high": round(ci_high, 5),
        "note": None,
    }


def _extract_xy(
    dataset: Dataset,
    hypothesis: Hypothesis,
    config: ExperimentConfig,
) -> tuple[list[float], list[float], list[int], list[int], list[float | None]]:
    """Extract aligned (x, y, feature_idx, target_idx, price_series) strictly causally."""
    rows = dataset.records
    h = config.horizon
    x_vals: list[float] = []
    y_vals: list[float] = []
    f_idx: list[int] = []
    t_idx: list[int] = []

    if hypothesis.hypothesis_id == "H1_IMBALANCE_RETURN":
        imb_key = "imbalance_l1" if config.imbalance_levels == 1 else "imbalance_l5"
        prices = [r.get("mid_price") for r in rows]
        for i in range(len(rows) - h):
            imb = rows[i].get(imb_key)
            p0 = prices[i]
            p1 = prices[i + h]
            if imb is None or p0 is None or p1 is None or p0 <= 0:
                continue
            ret_bps = ((p1 - p0) / p0) * 10000.0
            x_vals.append(float(imb))
            y_vals.append(float(ret_bps))
            f_idx.append(i)
            t_idx.append(i + h)
        return x_vals, y_vals, f_idx, t_idx, prices

    if hypothesis.hypothesis_id == "H2_DEPTH_SPREAD":
        prices = [r.get("mid_price") for r in rows]
        for i, r in enumerate(rows):
            b_d = r.get("bid_depth_l1")
            a_d = r.get("ask_depth_l1")
            spr = r.get("spread")
            if b_d is None or a_d is None or spr is None:
                continue
            x_vals.append(float(b_d + a_d))
            y_vals.append(float(spr))
            f_idx.append(i)
            t_idx.append(i)
        return x_vals, y_vals, f_idx, t_idx, prices

    if hypothesis.hypothesis_id == "H3_OHLCV_MOMENTUM":
        price_key = "close" if "close" in rows[0] else "mid_price"
        prices = [r.get(price_key) for r in rows]
        for i in range(1, len(rows) - h):
            p_prev, p0, p1 = prices[i - 1], prices[i], prices[i + h]
            if not p_prev or not p0 or not p1 or p_prev <= 0 or p0 <= 0:
                continue
            lag_ret = ((p0 - p_prev) / p_prev) * 10000.0
            fwd_ret = ((p1 - p0) / p0) * 10000.0
            x_vals.append(float(lag_ret))
            y_vals.append(float(fwd_ret))
            f_idx.append(i)
            t_idx.append(i + h)
        return x_vals, y_vals, f_idx, t_idx, prices

    raise ValueError(f"Unsupported hypothesis_id: {hypothesis.hypothesis_id}")


def _check_leakage(
    f_idx: list[int],
    t_idx: list[int],
    split_pos: int,
    require_strict_forward: bool,
) -> dict[str, Any]:
    """Verify chronological non-overlap and causal feature-to-target ordering."""
    if not f_idx:
        return {"passed": False, "details": "No observations available."}
    causal_ok = all(
        (t > f if require_strict_forward else t >= f)
        for f, t in zip(f_idx, t_idx)
    )
    train_max_target = max(t_idx[:split_pos]) if split_pos > 0 else -1
    test_min_feature = min(f_idx[split_pos:]) if split_pos < len(f_idx) else float("inf")
    # Strict temporal boundary: test features must start after train targets end
    temporal_boundary_ok = test_min_feature >= train_max_target
    return {
        "passed": bool(causal_ok and temporal_boundary_ok),
        "causal_ordering_ok": causal_ok,
        "temporal_boundary_ok": temporal_boundary_ok,
        "train_max_target_index": train_max_target,
        "test_min_feature_index": test_min_feature if test_min_feature != float("inf") else None,
    }


@dataclass
class ExperimentResult:
    experiment_id: str
    created_at: str
    hypothesis: dict[str, Any]
    dataset: dict[str, Any]
    config: dict[str, Any]
    leakage_check: dict[str, Any]
    in_sample_stats: dict[str, Any]
    out_of_sample_stats: dict[str, Any]
    walk_forward: list[dict[str, Any]]
    baseline_comparison: dict[str, Any]
    cost_aware_backtest: dict[str, Any] | None
    conclusion: str
    warnings: list[str] = field(default_factory=list)
    scatter_sample: list[dict[str, float]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExperimentRunner:
    """Executes structured, reproducible quantitative experiments."""

    def run(self, dataset: Dataset, config: ExperimentConfig) -> ExperimentResult:
        config.validate()
        hypothesis = get_hypothesis(config.hypothesis_id)

        if hypothesis.requires_order_book_depth and not dataset.metadata.has_order_book_depth:
            raise ValueError(
                f"Hypothesis '{hypothesis.hypothesis_id}' requires L2 order-book depth, "
                f"but dataset '{dataset.metadata.dataset_id}' ({dataset.metadata.source_type}) "
                "does not contain order-book data. OHLCV candles cannot reconstruct L2 queues."
            )

        x_vals, y_vals, f_idx, t_idx, prices = _extract_xy(dataset, hypothesis, config)
        n = len(x_vals)
        if n < 20:
            raise ValueError(
                f"Dataset produced only {n} valid paired observations (minimum 20 required)."
            )

        # Reserve gap of `horizon` observations between train and test to prevent target overlap
        raw_split = int(n * config.train_ratio)
        gap = config.horizon if hypothesis.hypothesis_id != "H2_DEPTH_SPREAD" else 0
        test_start = min(n - 5, raw_split + gap)
        train_end = max(5, raw_split)

        x_train, y_train = x_vals[:train_end], y_vals[:train_end]
        x_test, y_test = x_vals[test_start:], y_vals[test_start:]

        # Build combined leakage index arrays reflecting purged gap
        purged_f = f_idx[:train_end] + f_idx[test_start:]
        purged_t = t_idx[:train_end] + t_idx[test_start:]
        leakage = _check_leakage(
            purged_f,
            purged_t,
            split_pos=train_end,
            require_strict_forward=(hypothesis.hypothesis_id != "H2_DEPTH_SPREAD"),
        )

        in_stats = _compute_stats(x_train, y_train)
        out_stats = _compute_stats(x_test, y_test)

        # Walk-forward evaluation (expanding train, sequential out-of-sample test blocks)
        wf_results: list[dict[str, Any]] = []
        fold_size = max(10, n // (config.walk_forward_folds + 1))
        for fold in range(1, config.walk_forward_folds + 1):
            wf_train_end = fold * fold_size
            wf_test_start = wf_train_end + gap
            wf_test_end = min(n, wf_test_start + fold_size)
            if wf_test_end - wf_test_start < 5:
                break
            fold_st = _compute_stats(
                x_vals[wf_test_start:wf_test_end],
                y_vals[wf_test_start:wf_test_end],
            )
            wf_results.append(
                {
                    "fold": fold,
                    "train_count": wf_train_end,
                    "test_count": wf_test_end - wf_test_start,
                    "pearson_r": fold_st["pearson_r"],
                    "pearson_p": fold_st["pearson_p"],
                    "r_squared": fold_st["r_squared"],
                }
            )

        # Baseline comparison on out-of-sample directional accuracy
        nonzero_test = [(xv, yv) for xv, yv in zip(x_test, y_test) if abs(yv) > 1e-12]
        if nonzero_test:
            sign_matches = sum(1 for xv, yv in nonzero_test if (xv > 0 and yv > 0) or (xv < 0 and yv < 0))
            pos_rate = sum(1 for _, yv in nonzero_test if yv > 0) / len(nonzero_test)
            majority_baseline = max(pos_rate, 1.0 - pos_rate)
            directional_acc = sign_matches / len(nonzero_test)
        else:
            directional_acc = None
            majority_baseline = None

        baseline_comp = {
            "out_of_sample_directional_accuracy": round(directional_acc, 4) if directional_acc is not None else None,
            "naive_majority_baseline_accuracy": round(majority_baseline, 4) if majority_baseline is not None else None,
            "nonzero_target_count": len(nonzero_test),
        }

        # Cost-aware backtest on out-of-sample slice for H1
        bt_summary: dict[str, Any] | None = None
        if hypothesis.hypothesis_id == "H1_IMBALANCE_RETURN":
            imb_key = "imbalance_l1" if config.imbalance_levels == 1 else "imbalance_l5"
            oos_start_row = f_idx[test_start]
            oos_rows = dataset.records[oos_start_row:]
            oos_prices = [r.get("mid_price") for r in oos_rows]
            oos_imbs = [r.get(imb_key) for r in oos_rows]
            sigs = imbalance_threshold_signals(oos_imbs, threshold=config.signal_threshold)
            bt = run_cost_aware_backtest(
                oos_prices,
                sigs,
                horizon=config.horizon,
                fee_bps=config.fee_bps,
                slippage_bps=config.slippage_bps,
            )
            bt_summary = bt.to_dict()

        # Honest, evidence-grounded conclusion and warnings
        warnings: list[str] = []
        if dataset.metadata.is_synthetic:
            warnings.append(
                "SYNTHETIC DATA: Findings reflect the simulator's order-flow mechanics only "
                "and must not be extrapolated to live markets."
            )
        if not leakage["passed"]:
            warnings.append("Leakage check flagged a boundary overlap; inspect split indices.")

        oos_r = out_stats.get("pearson_r")
        oos_p = out_stats.get("pearson_p")
        if oos_r is None or oos_p is None:
            conclusion = "Insufficient out-of-sample variance or observations to evaluate H0."
        elif oos_p < 0.05:
            conclusion = (
                f"Out-of-sample association is statistically distinguishable from zero "
                f"(r = {oos_r:.4f}, p = {oos_p:.4f}, n = {out_stats['n']}). "
                f"Null hypothesis H0 is rejected at alpha = 0.05."
            )
        else:
            conclusion = (
                f"No statistically significant out-of-sample linear relationship detected "
                f"(r = {oos_r:.4f}, p = {oos_p:.4f}, n = {out_stats['n']}). "
                f"Fail to reject null hypothesis H0 at alpha = 0.05."
            )

        if bt_summary is not None and bt_summary["trade_count"] > 0:
            if bt_summary["net_return_bps"] <= 0:
                warnings.append(
                    f"After {config.fee_bps} bps fee + {config.slippage_bps} bps slippage per leg, "
                    f"out-of-sample net return is {bt_summary['net_return_bps']:.2f} bps "
                    f"(gross: {bt_summary['gross_return_bps']:.2f} bps)."
                )

        # Downsample scatter plot points for clean frontend rendering
        step_stride = max(1, len(x_test) // 120)
        scatter = [
            {"x": round(x_test[i], 5), "y": round(y_test[i], 5)}
            for i in range(0, len(x_test), step_stride)
        ]

        return ExperimentResult(
            experiment_id=f"EXP-{uuid.uuid4().hex[:8].upper()}",
            created_at=datetime.now(timezone.utc).isoformat(),
            hypothesis=hypothesis.to_dict(),
            dataset=dataset.metadata.to_dict(),
            config=asdict(config),
            leakage_check=leakage,
            in_sample_stats=in_stats,
            out_of_sample_stats=out_stats,
            walk_forward=wf_results,
            baseline_comparison=baseline_comp,
            cost_aware_backtest=bt_summary,
            conclusion=conclusion,
            warnings=warnings,
            scatter_sample=scatter,
        )


class ExperimentStore:
    """In-memory store of completed experiments with JSON/CSV export."""

    def __init__(self) -> None:
        self._experiments: dict[str, ExperimentResult] = {}

    def save(self, result: ExperimentResult) -> ExperimentResult:
        self._experiments[result.experiment_id] = result
        return result

    def get(self, experiment_id: str) -> ExperimentResult:
        if experiment_id not in self._experiments:
            raise KeyError(f"Experiment not found: {experiment_id}")
        return self._experiments[experiment_id]

    def list_all(self) -> list[dict[str, Any]]:
        return [exp.to_dict() for exp in reversed(list(self._experiments.values()))]

    def export_json(self, experiment_id: str) -> str:
        return json.dumps(self.get(experiment_id).to_dict(), indent=2)

    def export_csv(self, experiment_id: str) -> str:
        exp = self.get(experiment_id)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["section", "metric", "value"])
        writer.writerow(["meta", "experiment_id", exp.experiment_id])
        writer.writerow(["meta", "created_at", exp.created_at])
        writer.writerow(["meta", "hypothesis_id", exp.hypothesis["hypothesis_id"]])
        writer.writerow(["meta", "dataset_id", exp.dataset["dataset_id"]])
        writer.writerow(["meta", "is_synthetic", exp.dataset["is_synthetic"]])
        for k, v in exp.in_sample_stats.items():
            writer.writerow(["in_sample", k, v])
        for k, v in exp.out_of_sample_stats.items():
            writer.writerow(["out_of_sample", k, v])
        if exp.cost_aware_backtest:
            for k, v in exp.cost_aware_backtest.items():
                writer.writerow(["cost_aware_backtest", k, v])
        writer.writerow(["conclusion", "summary", exp.conclusion])
        return buf.getvalue()


def list_default_hypotheses() -> list[dict[str, Any]]:
    return [h.to_dict() for h in DEFAULT_HYPOTHESES]
