import React, { useEffect, useState } from "react";
import { AIAssistantPage } from "./pages/AIAssistantPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { OrderBookPage } from "./pages/OrderBookPage";
import { ResearchWorkbenchPage } from "./pages/ResearchWorkbenchPage";
import { SimulationLabPage } from "./pages/SimulationLabPage";
import { harlabApi } from "./services/api";
import type {
  BookSnapshot,
  DatasetMetadata,
  ExperimentResult,
  HealthResponse,
  Hypothesis,
  SimulationOutput,
} from "./types/harlab";

type TabKey = "dashboard" | "orderbook" | "analytics" | "simulation" | "research" | "ai";
type VenueKey = "binance" | "coinbase" | "kraken" | "synthetic";
type AssetKey = "BTC" | "ETH" | "SOL";

const NAV_ITEMS: { key: TabKey; label: string }[] = [
  { key: "dashboard", label: "Research Dashboard" },
  { key: "orderbook", label: "Order Book Explorer" },
  { key: "analytics", label: "Market Analytics" },
  { key: "simulation", label: "Simulation Lab" },
  { key: "research", label: "Research Workbench" },
  { key: "ai", label: "AI Research Assistant" },
];

export const App: React.FC = () => {
  const [tab, setTab] = useState<TabKey>("dashboard");
  const [theme, setTheme] = useState<"dark" | "light">(() =>
    localStorage.getItem("harlab-theme") === "light" ? "light" : "dark"
  );
  const [venue, setVenue] = useState<VenueKey>("binance");
  const [asset, setAsset] = useState<AssetKey>("BTC");

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [snapshot, setSnapshot] = useState<BookSnapshot | null>(null);
  const [simulation, setSimulation] = useState<SimulationOutput | null>(null);
  const [datasets, setDatasets] = useState<DatasetMetadata[]>([]);
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([]);
  const [experiments, setExperiments] = useState<ExperimentResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("harlab-theme", theme);
  }, [theme]);

  const loadAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const [h, snap, ds, hyps, exps] = await Promise.all([
        harlabApi.health(),
        harlabApi.getBookSnapshot(10),
        harlabApi.listDatasets(),
        harlabApi.listHypotheses(),
        harlabApi.listExperiments(),
      ]);
      setHealth(h);
      if (venue === "synthetic") setSnapshot(snap);
      setDatasets(ds.datasets);
      setHypotheses(hyps.hypotheses);
      setExperiments(exps.experiments);
      try {
        const sim = await harlabApi.getLatestSimulation();
        setSimulation(sim);
      } catch {
        setSimulation(null);
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? `Backend connection error: ${err.message}. Ensure FastAPI is running on port 8000.`
          : "Unable to connect to HARLAB backend."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadAll();
  }, []);

  useEffect(() => {
    if (venue === "synthetic") return;
    let active = true;
    const poll = async () => {
      try {
        const liveSnap = await harlabApi.getLiveBook(venue, asset, 10);
        if (active) {
          setSnapshot(liveSnap);
          setError(null);
        }
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "Live feed failed");
      }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 2000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [venue, asset]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <h1 className="brand-title">HARLAB</h1>
          <p className="brand-sub">Quantitative Market Research Laboratory</p>
        </div>

        <nav className="nav-list" aria-label="HARLAB Sections">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`nav-btn ${tab === item.key ? "active" : ""}`}
              onClick={() => setTab(item.key)}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div style={{ marginTop: "auto", fontSize: 11 }} className="muted">
          <div>Understand Markets.</div>
          <div>Test Hypotheses.</div>
          <div>Discover Evidence.</div>
        </div>
      </aside>

      <div className="main-area">
        <header className="topbar">
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <span className={`badge ${venue === "synthetic" ? "badge-synthetic" : "badge-ok"}`}>
              {venue === "synthetic"
                ? "SYNTHETIC LOCAL ENGINE"
                : `LIVE — ${venue.toUpperCase()} (${asset})`}
            </span>
            <select
              value={venue}
              onChange={(e) => {
                const next = e.target.value as VenueKey;
                setVenue(next);
                if (next === "synthetic") void loadAll();
              }}
            >
              <option value="binance">Binance Spot (Live L2)</option>
              <option value="coinbase">Coinbase Exchange (Live L2)</option>
              <option value="kraken">Kraken Spot (Live L2)</option>
              <option value="synthetic">Synthetic Local Book</option>
            </select>
            {venue !== "synthetic" ? (
              <select
                value={asset}
                onChange={(e) => setAsset(e.target.value as AssetKey)}
              >
                <option value="BTC">BTC</option>
                <option value="ETH">ETH</option>
                <option value="SOL">SOL</option>
              </select>
            ) : null}
            {!health ? <span className="badge badge-err">Engine Offline</span> : null}
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <button
              className="btn btn-secondary"
              type="button"
              onClick={() => setTheme((prev) => (prev === "dark" ? "light" : "dark"))}
            >
              {theme === "dark" ? "Light Mode" : "Dark Mode"}
            </button>
            <button className="btn btn-secondary" onClick={() => void loadAll()} disabled={loading}>
              {loading ? "Syncing..." : "Refresh State"}
            </button>
          </div>
        </header>

        <main className="content">
          {error ? <div className="error-banner">{error}</div> : null}

          {tab === "dashboard" ? (
            <DashboardPage
              health={health}
              snapshot={snapshot}
              datasets={datasets}
              experiments={experiments}
              onNavigate={(next) => setTab(next as TabKey)}
            />
          ) : null}

          {tab === "orderbook" ? (
            <OrderBookPage snapshot={snapshot} onRefresh={setSnapshot} />
          ) : null}

          {tab === "analytics" ? (
            <AnalyticsPage simulation={simulation} datasets={datasets} />
          ) : null}

          {tab === "simulation" ? (
            <SimulationLabPage
              latestSimulation={simulation}
              onSimulationComplete={(sim, ds) => {
                setSimulation(sim);
                setDatasets((prev) => [ds, ...prev]);
              }}
            />
          ) : null}

          {tab === "research" ? (
            <ResearchWorkbenchPage
              hypotheses={hypotheses}
              datasets={datasets}
              experiments={experiments}
              onExperimentCreated={(exp) => setExperiments((prev) => [exp, ...prev])}
              onDatasetUploaded={(ds) => setDatasets((prev) => [ds, ...prev])}
            />
          ) : null}

          {tab === "ai" ? <AIAssistantPage experiments={experiments} /> : null}
        </main>
      </div>
    </div>
  );
};

export default App;