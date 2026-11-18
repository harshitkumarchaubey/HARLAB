import React, { useEffect, useState } from "react";
import { ImbalanceBarChart, LineSeriesChart } from "../components/Charts";
import { harlabApi } from "../services/api";
import type { DatasetMetadata, RegimeSummary, SimulationOutput } from "../types/harlab";

interface AnalyticsPageProps {
  simulation: SimulationOutput | null;
  datasets: DatasetMetadata[];
}

export const AnalyticsPage: React.FC<AnalyticsPageProps> = ({ simulation, datasets }) => {
  const [selectedDs, setSelectedDs] = useState<string>(datasets[0]?.dataset_id ?? "");
  const [regimes, setRegimes] = useState<RegimeSummary | null>(null);
  const [regimeErr, setRegimeErr] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedDs && datasets.length > 0) {
      setSelectedDs(datasets[0].dataset_id);
    }
  }, [datasets, selectedDs]);

  useEffect(() => {
    if (!selectedDs) return;
    setRegimeErr(null);
    harlabApi
      .getDatasetRegimes(selectedDs)
      .then(setRegimes)
      .catch((err) => setRegimeErr(err instanceof Error ? err.message : "Failed to load regimes"));
  }, [selectedDs]);

  if (!simulation) {
    return (
      <div className="panel">
        <h2 className="panel-title">Market Microstructure Analytics</h2>
        <p className="muted">Run a simulation in the Simulation Lab to populate time-series charts.</p>
      </div>
    );
  }

  const stats = simulation.execution_stats;

  return (
    <>
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Market Microstructure Analytics</h2>
            <p className="muted" style={{ margin: "4px 0 0", fontSize: 12 }}>
              Computed directly from the latest reproducible simulation run (seed ={" "}
              <span className="mono">{String(simulation.config.seed)}</span>).
            </p>
          </div>
          <span className="badge badge-synthetic">{simulation.data_origin}</span>
        </div>

        <div className="kpi-grid">
          <div className="kpi-card">
            <div className="kpi-label">Total Trades</div>
            <div className="kpi-value mono">{stats.trade_count}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Executed Volume</div>
            <div className="kpi-value mono">{stats.total_executed_quantity}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">VWAP</div>
            <div className="kpi-value mono">{stats.vwap !== null ? stats.vwap.toFixed(3) : "—"}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Avg Trade Size</div>
            <div className="kpi-value mono">
              {stats.average_trade_size !== null ? stats.average_trade_size.toFixed(1) : "—"}
            </div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Buy / Sell Aggressor Vol</div>
            <div className="kpi-value mono">
              {stats.buy_aggressor_volume} / {stats.sell_aggressor_volume}
            </div>
          </div>
        </div>
      </div>

      <div className="grid-2">
        <LineSeriesChart
          title="Mid-Price vs. Top-of-Book Microprice"
          primaryLabel="Mid-Price"
          secondaryLabel="Microprice"
          data={simulation.series.map((pt) => ({
            x: pt.step,
            y: pt.mid_price,
            y2: pt.microprice,
          }))}
        />
        <LineSeriesChart
          title="Quoted Bid-Ask Spread Evolution"
          primaryLabel="Spread"
          data={simulation.series.map((pt) => ({
            x: pt.step,
            y: pt.spread,
          }))}
        />
      </div>

      <div className="grid-2">
        <ImbalanceBarChart
          title="Level-1 Order-Book Imbalance [-1, +1]"
          data={simulation.series.map((pt) => ({ step: pt.step, value: pt.imbalance_l1 }))}
        />
        <LineSeriesChart
          title="Total Displayed Liquidity Depth (Bid vs. Ask)"
          primaryLabel="Bid Depth"
          secondaryLabel="Ask Depth"
          data={simulation.series.map((pt) => ({
            x: pt.step,
            y: pt.bid_depth_total,
            y2: pt.ask_depth_total,
          }))}
        />
      </div>

      <div className="panel">
        <div className="panel-header">
          <h3 className="panel-title">Out-of-Sample Volatility & Liquidity Regimes (Leakage-Free)</h3>
          <select value={selectedDs} onChange={(e) => setSelectedDs(e.target.value)}>
            {datasets.map((d) => (
              <option key={d.dataset_id} value={d.dataset_id}>
                {d.name}
              </option>
            ))}
          </select>
        </div>
        {regimeErr ? <div className="error-banner">{regimeErr}</div> : null}
        {regimes ? (
          <div className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-label">Train / Test Split</div>
              <div className="kpi-value mono">
                {regimes.train_rows} / {regimes.test_rows}
              </div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Train Vol Cutoffs (bps)</div>
              <div className="kpi-value mono">
                {regimes.fitted_train_thresholds.vol_low} / {regimes.fitted_train_thresholds.vol_high}
              </div>
            </div>
            {Object.entries(regimes.out_of_sample_regime_counts).map(([lbl, cnt]) => (
              <div className="kpi-card" key={lbl}>
                <div className="kpi-label">{lbl}</div>
                <div className="kpi-value mono">{cnt} steps</div>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </>
  );
};
