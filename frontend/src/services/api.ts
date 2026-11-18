import type {
  AIRouterStatus,
  BookSnapshot,
  DatasetMetadata,
  ExperimentResult,
  HealthResponse,
  Hypothesis,
  RegimeSummary,
  Side,
  SimulationOutput,
} from "../types/harlab";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") {
        message = body.detail;
      } else if (Array.isArray(body.detail) && body.detail[0]?.msg) {
        message = body.detail.map((d: { msg: string }) => d.msg).join("; ");
      }
    } catch {
      // Fallback to HTTP status
    }
    throw new Error(message);
  }
  return (await res.json()) as T;
}

export const harlabApi = {
  health: () => request<HealthResponse>("/api/health"),

  getBookSnapshot: (levels = 10) =>
    request<BookSnapshot>(`/api/book/snapshot?levels=${levels}`),
  getLiveBook: (venue = "binance", asset = "BTC", levels = 10) =>
    request<BookSnapshot>(
      `/api/live/book?venue=${encodeURIComponent(venue)}&asset=${encodeURIComponent(asset)}&levels=${levels}`
    ),

  submitOrder: (payload: {
    order_id: string;
    side: Side;
    price: string;
    quantity: number;
  }) =>
    request<{ accepted: boolean; trades: unknown[]; snapshot: BookSnapshot }>(
      "/api/book/orders",
      { method: "POST", body: JSON.stringify(payload) }
    ),

  cancelOrder: (orderId: string) =>
    request<{ cancelled: boolean; snapshot: BookSnapshot }>(
      `/api/book/orders/${encodeURIComponent(orderId)}`,
      { method: "DELETE" }
    ),

  resetBook: (tickSize = "0.01", seedDemo = true) =>
    request<{ reset: boolean; snapshot: BookSnapshot }>("/api/book/reset", {
      method: "POST",
      body: JSON.stringify({ tick_size: tickSize, seed_demo: seedDemo }),
    }),

  getScenarios: () =>
    request<{ scenarios: Record<string, { label: string; description: string; config: Record<string, unknown> }> }>(
      "/api/simulation/scenarios"
    ),

  getLatestSimulation: () => request<SimulationOutput>("/api/simulation/latest"),

  runSimulation: (payload: Record<string, unknown>) =>
    request<{ dataset: DatasetMetadata; simulation: SimulationOutput }>(
      "/api/simulation/run",
      { method: "POST", body: JSON.stringify(payload) }
    ),

  listDatasets: () => request<{ datasets: DatasetMetadata[] }>("/api/datasets"),

  uploadOhlcv: (payload: {
    name: string;
    csv_text: string;
    is_synthetic: boolean;
    description: string;
  }) =>
    request<{ dataset: DatasetMetadata }>("/api/datasets/upload-ohlcv", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getDatasetRegimes: (datasetId: string) =>
    request<RegimeSummary>(`/api/datasets/${encodeURIComponent(datasetId)}/regimes`),

  listHypotheses: () =>
    request<{ hypotheses: Hypothesis[] }>("/api/research/hypotheses"),

  listExperiments: () =>
    request<{ experiments: ExperimentResult[] }>("/api/research/experiments"),

  runExperiment: (payload: Record<string, unknown>) =>
    request<ExperimentResult>("/api/research/experiments", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  exportExperimentUrl: (experimentId: string, fmt: "json" | "csv") =>
    `${API_BASE}/api/research/experiments/${encodeURIComponent(experimentId)}/export?fmt=${fmt}`,

  getAiStatus: () => request<AIRouterStatus>("/api/ai/status"),

  askAi: (payload: {
    question: string;
    experiment_id?: string | null;
    include_book_context: boolean;
  }) =>
    request<{
      ok: boolean;
      provider: string | null;
      model: string | null;
      interpretation: string | null;
      measured_context_attached: boolean;
      attempts: Record<string, unknown>[];
      error: string | null;
    }>("/api/ai/assist", { method: "POST", body: JSON.stringify(payload) }),
};
