import React, { useState } from "react";
import { ScatterPlot } from "../components/Charts";
import { harlabApi } from "../services/api";
import type { DatasetMetadata, ExperimentResult, Hypothesis } from "../types/harlab";

interface ResearchWorkbenchPageProps {
  hypotheses: Hypothesis[];
  datasets: DatasetMetadata[];
  experiments: ExperimentResult[];
  onExperimentCreated: (exp: ExperimentResult) => void;
  onDatasetUploaded: (ds: DatasetMetadata) => void;
}

const fmt = (v: number | null | undefined, digits = 4) =>
  v === null || v === undefined ? "—" : v.toFixed(digits);

export const ResearchWorkbenchPage: React.FC<ResearchWorkbenchPageProps> = ({
  hypotheses,
  datasets,
  experiments,
  onExperimentCreated,
  onDatasetUploaded,
}) => {
  const [hypothesisId, setHypothesisId] = useState(
    hypotheses[0]?.hypothesis_id ?? "H1_IMBALANCE_RETURN"
  );
  const [datasetId, setDatasetId] = useState(datasets[0]?.dataset_id ?? "");
  const [horizon, setHorizon] = useState(1);
  const [trainRatio, setTrainRatio] = useState(0.7);
  const [folds, setFolds] = useState(3);
  const [threshold, setThreshold] = useState(0.2);
  const [feeBps, setFeeBps] = useState(1.0);
  const [slippageBps, setSlippageBps] = useState(2.0);
  const [selectedExpId, setSelectedExpId] = useState<string>(experiments[0]?.experiment_id ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // OHLCV CSV import state
  const [csvName, setCsvName] = useState("Imported OHLCV Dataset");
  const [csvText, setCsvText] = useState("");
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);

  const selectedHypothesis = hypotheses.find((h) => h.hypothesis_id === hypothesisId);
  const activeExp =
    experiments.find((e) => e.experiment_id === selectedExpId) ?? experiments[0] ?? null;

  const handleRunExperiment = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const exp = await harlabApi.runExperiment({
        hypothesis_id: hypothesisId,
        dataset_id: datasetId || datasets[0]?.dataset_id,
        horizon,
        train_ratio: trainRatio,
        walk_forward_folds: folds,
        signal_threshold: threshold,
        fee_bps: feeBps,
        slippage_bps: slippageBps,
      });
      onExperimentCreated(exp);
      setSelectedExpId(exp.experiment_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Experiment failed");
    } finally {
      setBusy(false);
    }
  };

  const handleUploadCsv = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setUploadMsg(null);
    try {
      const res = await harlabApi.uploadOhlcv({
        name: csvName,
        csv_text: csvText,
        is_synthetic: false,
        description: "User-uploaded historical OHLCV CSV (no L2 depth).",
      });
      onDatasetUploaded(res.dataset);
      setDatasetId(res.dataset.dataset_id);
      setUploadMsg(`Registered OHLCV dataset (${res.dataset.row_count} valid bars).`);
      setCsvText("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "CSV validation failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">Research Workbench — Hypothesis Evaluation</h2>
          <span className="badge badge-info">Chronological Split & Leakage Checked</span>
        </div>

        {selectedHypothesis ? (
          <div style={{ marginBottom: 14, fontSize: 13 }}>
            <div><strong>Question:</strong> {selectedHypothesis.question}</div>
            <div className="muted" style={{ marginTop: 4 }}>
              <strong>Null:</strong> {selectedHypothesis.null_hypothesis}
            </div>
          </div>
        ) : null}

        {error ? <div className="error-banner" style={{ marginBottom: 10 }}>{error}</div> : null}

        <form className="form-grid" onSubmit={handleRunExperiment}>
          <label className="field">
            Hypothesis
            <select value={hypothesisId} onChange={(e) => setHypothesisId(e.target.value)}>
              {hypotheses.map((h) => (
                <option key={h.hypothesis_id} value={h.hypothesis_id}>
                  {h.hypothesis_id} — {h.title}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Dataset
            <select
              value={datasetId || datasets[0]?.dataset_id || ""}
              onChange={(e) => setDatasetId(e.target.value)}
            >
              {datasets.map((d) => (
                <option key={d.dataset_id} value={d.dataset_id}>
                  {d.name} [{d.has_order_book_depth ? "L2" : "OHLCV"}]
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Horizon (steps)
            <input
              type="number"
              min={1}
              max={50}
              value={horizon}
              onChange={(e) => setHorizon(Number(e.target.value))}
            />
          </label>
          <label className="field">
            Train Ratio
            <input
              type="number"
              step="0.05"
              min={0.4}
              max={0.9}
              value={trainRatio}
              onChange={(e) => setTrainRatio(Number(e.target.value))}
            />
          </label>
          <label className="field">
            Walk-Forward Folds
            <input
              type="number"
              min={2}
              max={10}
              value={folds}
              onChange={(e) => setFolds(Number(e.target.value))}
            />
          </label>
          <label className="field">
            Signal Threshold
            <input
              type="number"
              step="0.05"
              min={0}
              max={1}
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
            />
          </label>
          <label className="field">
            Fee (bps / leg)
            <input
              type="number"
              step="0.5"
              min={0}
              value={feeBps}
              onChange={(e) => setFeeBps(Number(e.target.value))}
            />
          </label>
          <label className="field">
            Slippage (bps / leg)
            <input
              type="number"
              step="0.5"
              min={0}
              value={slippageBps}
              onChange={(e) => setSlippageBps(Number(e.target.value))}
            />
          </label>
          <button className="btn" type="submit" disabled={busy}>
            {busy ? "Evaluating..." : "Run Experiment"}
          </button>
        </form>
      </div>

      {activeExp ? (
        <>
          <div className="panel">
            <div className="panel-header">
              <div>
                <h3 className="panel-title">
                  {activeExp.experiment_id} — {activeExp.hypothesis.title}
                </h3>
                <div className="muted" style={{ fontSize: 12 }}>
                  Dataset: {activeExp.dataset.name}
                </div>
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <span className={`badge ${activeExp.leakage_check.passed ? "badge-ok" : "badge-err"}`}>
                  Leakage Check: {activeExp.leakage_check.passed ? "PASS" : "FLAG"}
                </span>
                <a
                  className="btn btn-secondary"
                  href={harlabApi.exportExperimentUrl(activeExp.experiment_id, "json")}
                  target="_blank"
                  rel="noreferrer"
                >
                  Export JSON
                </a>
                <a
                  className="btn btn-secondary"
                  href={harlabApi.exportExperimentUrl(activeExp.experiment_id, "csv")}
                  target="_blank"
                  rel="noreferrer"
                >
                  Export CSV
                </a>
              </div>
            </div>

            <p style={{ margin: "0 0 12px" }}>{activeExp.conclusion}</p>
            {activeExp.warnings.map((w, i) => (
              <div className="warn-banner" key={i} style={{ marginBottom: 8 }}>
                {w}
              </div>
            ))}

            <div className="kpi-grid" style={{ marginTop: 12 }}>
              <div className="kpi-card">
                <div className="kpi-label">OOS Pearson r (p-val)</div>
                <div className="kpi-value mono">
                  {fmt(activeExp.out_of_sample_stats.pearson_r, 3)} (p=
                  {fmt(activeExp.out_of_sample_stats.pearson_p, 3)})
                </div>
              </div>
              <div className="kpi-card">
                <div className="kpi-label">OOS 95% CI for r</div>
                <div className="kpi-value mono">
                  [{fmt(activeExp.out_of_sample_stats.ci_95_low, 2)},{" "}
                  {fmt(activeExp.out_of_sample_stats.ci_95_high, 2)}]
                </div>
              </div>
              <div className="kpi-card">
                <div className="kpi-label">OOS Spearman rho</div>
                <div className="kpi-value mono">
                  {fmt(activeExp.out_of_sample_stats.spearman_rho, 3)}
                </div>
              </div>
              <div className="kpi-card">
                <div className="kpi-label">Directional vs. Baseline</div>
                <div className="kpi-value mono">
                  {fmt(activeExp.baseline_comparison.out_of_sample_directional_accuracy, 3)} vs{" "}
                  {fmt(activeExp.baseline_comparison.naive_majority_baseline_accuracy, 3)}
                </div>
              </div>
              {activeExp.cost_aware_backtest ? (
                <>
                  <div className="kpi-card">
                    <div className="kpi-label">Gross Return (OOS)</div>
                    <div className="kpi-value mono">
                      {activeExp.cost_aware_backtest.gross_return_bps.toFixed(2)} bps
                    </div>
                  </div>
                  <div className="kpi-card">
                    <div className="kpi-label">Net Return After Costs</div>
                    <div
                      className="kpi-value mono"
                      style={{
                        color:
                          activeExp.cost_aware_backtest.net_return_bps > 0
                            ? "var(--bid-green)"
                            : "var(--ask-red)",
                      }}
                    >
                      {activeExp.cost_aware_backtest.net_return_bps.toFixed(2)} bps
                    </div>
                  </div>
                </>
              ) : null}
            </div>
          </div>

          <div className="grid-2">
            <ScatterPlot
              title="Out-of-Sample Scatter (Feature vs. Target)"
              xLabel={activeExp.hypothesis.independent_variable}
              yLabel={activeExp.hypothesis.dependent_variable}
              points={activeExp.scatter_sample}
            />

            <div className="panel">
              <h3 className="panel-title" style={{ marginBottom: 10 }}>
                Walk-Forward Out-of-Sample Folds
              </h3>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Fold</th>
                      <th>Train N</th>
                      <th>Test N</th>
                      <th>Pearson r</th>
                      <th>p-value</th>
                      <th>R²</th>
                    </tr>
                  </thead>
                  <tbody>
                    {activeExp.walk_forward.map((wf) => (
                      <tr key={wf.fold}>
                        <td className="mono">#{wf.fold}</td>
                        <td className="mono">{wf.train_count}</td>
                        <td className="mono">{wf.test_count}</td>
                        <td className="mono">{fmt(wf.pearson_r, 4)}</td>
                        <td className="mono">{fmt(wf.pearson_p, 4)}</td>
                        <td className="mono">{fmt(wf.r_squared, 4)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </>
      ) : null}

      <div className="grid-2">
        <div className="panel">
          <h3 className="panel-title" style={{ marginBottom: 10 }}>
            Experiment Comparison ({experiments.length})
          </h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Hypothesis</th>
                  <th>Dataset</th>
                  <th>OOS r</th>
                  <th>OOS p</th>
                </tr>
              </thead>
              <tbody>
                {experiments.map((exp) => (
                  <tr
                    key={exp.experiment_id}
                    onClick={() => setSelectedExpId(exp.experiment_id)}
                    style={{
                      cursor: "pointer",
                      background:
                        activeExp?.experiment_id === exp.experiment_id
                          ? "var(--bg-elevated)"
                          : undefined,
                    }}
                  >
                    <td className="mono">{exp.experiment_id}</td>
                    <td>{exp.hypothesis.hypothesis_id}</td>
                    <td>{exp.dataset.dataset_id}</td>
                    <td className="mono">{fmt(exp.out_of_sample_stats.pearson_r, 3)}</td>
                    <td className="mono">{fmt(exp.out_of_sample_stats.pearson_p, 3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel">
          <h3 className="panel-title" style={{ marginBottom: 8 }}>
            Import Historical OHLCV CSV (Candle-Only)
          </h3>
          <p className="muted" style={{ marginTop: 0, fontSize: 12 }}>
            Required headers: <span className="mono">timestamp,open,high,low,close,volume</span>.
            OHLCV datasets are strictly marked <span className="mono">has_order_book_depth=false</span>.
          </p>
          {uploadMsg ? <div className="warn-banner" style={{ marginBottom: 8 }}>{uploadMsg}</div> : null}
          <form onSubmit={handleUploadCsv} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <input value={csvName} onChange={(e) => setCsvName(e.target.value)} required />
            <textarea
              rows={4}
              placeholder="timestamp,open,high,low,close,volume&#10;2026-01-01T09:30:00Z,100,101,99.5,100.5,12000"
              value={csvText}
              onChange={(e) => setCsvText(e.target.value)}
              required
            />
            <button className="btn btn-secondary" type="submit" disabled={busy}>
              Validate & Register OHLCV CSV
            </button>
          </form>
        </div>
      </div>
    </>
  );
};
