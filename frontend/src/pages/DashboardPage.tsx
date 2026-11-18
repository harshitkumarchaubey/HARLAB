import React from "react";
import type {
  BookSnapshot,
  DatasetMetadata,
  ExperimentResult,
  HealthResponse,
} from "../types/harlab";

interface DashboardPageProps {
  health: HealthResponse | null;
  snapshot: BookSnapshot | null;
  datasets: DatasetMetadata[];
  experiments: ExperimentResult[];
  onNavigate: (tab: string) => void;
}

const fmt = (v: number | null | undefined, digits = 2) =>
  v === null || v === undefined ? "—" : v.toFixed(digits);

export const DashboardPage: React.FC<DashboardPageProps> = ({
  health,
  snapshot,
  datasets,
  experiments,
  onNavigate,
}) => {
  const m = snapshot?.metrics;

  return (
    <>
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title" style={{ fontSize: 16 }}>
              HARLAB — Quantitative Market Research Overview
            </h2>
            <p className="muted" style={{ margin: "4px 0 0", fontSize: 13 }}>
              Understand Markets. Test Hypotheses. Discover Evidence. All displayed metrics originate
              directly from the deterministic Python engine.
            </p>
          </div>
          <span className="badge badge-synthetic">Synthetic Research Environment</span>
        </div>

        <div className="kpi-grid">
          <div className="kpi-card">
            <div className="kpi-label">Active Best Bid / Ask</div>
            <div className="kpi-value mono">
              {fmt(m?.best_bid)} / {fmt(m?.best_ask)}
            </div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Quoted Spread</div>
            <div className="kpi-value mono">
              {fmt(m?.spread)} ({fmt(m?.relative_spread_bps, 1)} bps)
            </div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">L1 Imbalance / Microprice</div>
            <div className="kpi-value mono">
              {fmt(m?.order_imbalance_l1, 3)} / {fmt(m?.microprice, 3)}
            </div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Registered Datasets</div>
            <div className="kpi-value mono">{health?.datasets_count ?? datasets.length}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Completed Experiments</div>
            <div className="kpi-value mono">{health?.experiments_count ?? experiments.length}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Simulations Run</div>
            <div className="kpi-value mono">{health?.simulations_run ?? 0}</div>
          </div>
        </div>
      </div>

      <div className="grid-2">
        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title">Available Datasets</h3>
            <button className="btn btn-secondary" onClick={() => onNavigate("research")}>
              Open Research Workbench
            </button>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Rows</th>
                  <th>Provenance</th>
                </tr>
              </thead>
              <tbody>
                {datasets.map((ds) => (
                  <tr key={ds.dataset_id}>
                    <td>{ds.name}</td>
                    <td className="mono">{ds.has_order_book_depth ? "L2 LOB" : "OHLCV ONLY"}</td>
                    <td className="mono">{ds.row_count}</td>
                    <td>
                      <span className={`badge ${ds.is_synthetic ? "badge-synthetic" : "badge-info"}`}>
                        {ds.is_synthetic ? "Synthetic" : "Imported"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title">Recent Experiments</h3>
            <button className="btn btn-secondary" onClick={() => onNavigate("simulation")}>
              Run New Simulation
            </button>
          </div>
          {experiments.length === 0 ? (
            <p className="muted">No experiments recorded yet.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Hypothesis</th>
                    <th>OOS r</th>
                    <th>OOS p</th>
                    <th>Leakage</th>
                  </tr>
                </thead>
                <tbody>
                  {experiments.slice(0, 6).map((exp) => (
                    <tr key={exp.experiment_id}>
                      <td className="mono">{exp.experiment_id}</td>
                      <td>{exp.hypothesis.hypothesis_id}</td>
                      <td className="mono">{fmt(exp.out_of_sample_stats.pearson_r, 4)}</td>
                      <td className="mono">{fmt(exp.out_of_sample_stats.pearson_p, 4)}</td>
                      <td>
                        <span className={`badge ${exp.leakage_check.passed ? "badge-ok" : "badge-err"}`}>
                          {exp.leakage_check.passed ? "Pass" : "Flag"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  );
};
