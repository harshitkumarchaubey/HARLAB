import React, { useEffect, useState } from "react";
import { harlabApi } from "../services/api";
import type { DatasetMetadata, SimulationOutput } from "../types/harlab";

interface SimulationLabPageProps {
  latestSimulation: SimulationOutput | null;
  onSimulationComplete: (sim: SimulationOutput, ds: DatasetMetadata) => void;
}

export const SimulationLabPage: React.FC<SimulationLabPageProps> = ({
  latestSimulation,
  onSimulationComplete,
}) => {
  const [scenarios, setScenarios] = useState<
    Record<string, { label: string; description: string; config: Record<string, unknown> }>
  >({});
  const [seed, setSeed] = useState(42);
  const [steps, setSteps] = useState(250);
  const [buyBias, setBuyBias] = useState(0.5);
  const [limitProb, setLimitProb] = useState(0.65);
  const [marketableProb, setMarketableProb] = useState(0.2);
  const [cancelProb, setCancelProb] = useState(0.15);
  const [spreadTicks, setSpreadTicks] = useState(2);
  const [scenarioName, setScenarioName] = useState("baseline_symmetric");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [registeredMsg, setRegisteredMsg] = useState<string | null>(null);

  useEffect(() => {
    harlabApi
      .getScenarios()
      .then((res) => setScenarios(res.scenarios))
      .catch(() => {});
  }, []);

  const applyPreset = (key: string) => {
    const preset = scenarios[key];
    if (!preset) return;
    const c = preset.config;
    setScenarioName(key);
    setSeed(Number(c.seed ?? 42));
    setSteps(Number(c.steps ?? 250));
    setBuyBias(Number(c.buy_bias ?? 0.5));
    setLimitProb(Number(c.limit_order_prob ?? 0.65));
    setMarketableProb(Number(c.marketable_order_prob ?? 0.2));
    setCancelProb(Number(c.cancel_prob ?? 0.15));
    setSpreadTicks(Number(c.base_spread_ticks ?? 2));
  };

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault();
    setRunning(true);
    setError(null);
    setRegisteredMsg(null);
    try {
      const res = await harlabApi.runSimulation({
        seed,
        steps,
        buy_bias: buyBias,
        limit_order_prob: limitProb,
        marketable_order_prob: marketableProb,
        cancel_prob: cancelProb,
        base_spread_ticks: spreadTicks,
        scenario_name: scenarioName,
      });
      onSimulationComplete(res.simulation, res.dataset);
      setRegisteredMsg(`Completed & registered dataset: ${res.dataset.name}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Simulation failed");
    } finally {
      setRunning(false);
    }
  };

  return (
    <>
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Reproducible Synthetic Simulation Lab</h2>
            <p className="muted" style={{ margin: "4px 0 0", fontSize: 12 }}>
              Identical seeds produce byte-identical synthetic order-book trajectories. Results are
              automatically registered as selectable datasets for hypothesis testing.
            </p>
          </div>
          <span className="badge badge-synthetic">Synthetic Generator Only</span>
        </div>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
          {Object.entries(scenarios).map(([key, sc]) => (
            <button
              key={key}
              type="button"
              className="btn btn-secondary"
              onClick={() => applyPreset(key)}
              title={sc.description}
            >
              Preset: {sc.label}
            </button>
          ))}
        </div>

        {error ? <div className="error-banner" style={{ marginBottom: 10 }}>{error}</div> : null}
        {registeredMsg ? (
          <div className="warn-banner" style={{ marginBottom: 10 }}>{registeredMsg}</div>
        ) : null}

        <form className="form-grid" onSubmit={handleRun}>
          <label className="field">
            Random Seed
            <input type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} />
          </label>
          <label className="field">
            Simulation Steps
            <input
              type="number"
              min={20}
              max={5000}
              value={steps}
              onChange={(e) => setSteps(Number(e.target.value))}
            />
          </label>
          <label className="field">
            Buy Arrival Bias (0–1)
            <input
              type="number"
              step="0.02"
              min={0}
              max={1}
              value={buyBias}
              onChange={(e) => setBuyBias(Number(e.target.value))}
            />
          </label>
          <label className="field">
            Passive Limit Prob
            <input
              type="number"
              step="0.05"
              min={0}
              max={1}
              value={limitProb}
              onChange={(e) => setLimitProb(Number(e.target.value))}
            />
          </label>
          <label className="field">
            Aggressive Limit Prob
            <input
              type="number"
              step="0.05"
              min={0}
              max={1}
              value={marketableProb}
              onChange={(e) => setMarketableProb(Number(e.target.value))}
            />
          </label>
          <label className="field">
            Cancel Prob
            <input
              type="number"
              step="0.05"
              min={0}
              max={1}
              value={cancelProb}
              onChange={(e) => setCancelProb(Number(e.target.value))}
            />
          </label>
          <label className="field">
            Initial Spread (ticks)
            <input
              type="number"
              min={1}
              max={20}
              value={spreadTicks}
              onChange={(e) => setSpreadTicks(Number(e.target.value))}
            />
          </label>
          <button className="btn" type="submit" disabled={running}>
            {running ? "Running..." : "Run Simulation"}
          </button>
        </form>
      </div>

      {latestSimulation ? (
        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title">
              Latest Event Log (showing last {latestSimulation.events.length} of{" "}
              {latestSimulation.total_events} synthetic events)
            </h3>
            <span className="muted mono" style={{ fontSize: 12 }}>
              Trades: {latestSimulation.execution_stats.trade_count} | Exec Qty:{" "}
              {latestSimulation.execution_stats.total_executed_quantity}
            </span>
          </div>
          <div className="table-wrap" style={{ maxHeight: 340, overflowY: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Step</th>
                  <th>Event</th>
                  <th>Order ID</th>
                  <th>Side</th>
                  <th>Price</th>
                  <th>Qty</th>
                  <th>Trades</th>
                </tr>
              </thead>
              <tbody>
                {[...latestSimulation.events].reverse().slice(0, 40).map((ev, idx) => (
                  <tr key={idx}>
                    <td className="mono">{String(ev.step)}</td>
                    <td className="mono">{String(ev.event_type)}</td>
                    <td className="mono">{String(ev.order_id ?? "—")}</td>
                    <td className="mono">{String(ev.side ?? "").toUpperCase()}</td>
                    <td className="mono">
                      {typeof ev.price === "number" ? ev.price.toFixed(2) : "—"}
                    </td>
                    <td className="mono">{String(ev.quantity ?? "—")}</td>
                    <td className="mono">{String(ev.trades_count ?? 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </>
  );
};
