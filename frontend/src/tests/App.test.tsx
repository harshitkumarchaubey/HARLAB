import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import App from "../App";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch as unknown as typeof fetch;

function jsonResponse(data: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
  });
}

describe("HARLAB Frontend Workstation", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/health")) {
        return jsonResponse({
          status: "ok",
          project: "HARLAB",
          version: "0.2.0",
          datasets_count: 1,
          experiments_count: 0,
          simulations_run: 1,
          ai: { priority_order: ["gemini", "groq", "openrouter"], any_configured: false, cooldown_seconds: 60, providers: [] },
        });
      }
      if (url.includes("/api/book/snapshot")) {
        return jsonResponse({
          data_origin: "SYNTHETIC_WORKBENCH",
          is_synthetic: true,
          tick_size: 0.01,
          bids: [[99.9, 500]],
          asks: [[100.1, 300]],
          active_orders: [],
          recent_trades: [],
          metrics: {
            best_bid: 99.9,
            best_ask: 100.1,
            spread: 0.2,
            relative_spread: 0.002,
            relative_spread_bps: 20,
            mid_price: 100.0,
            weighted_mid_price: 99.975,
            microprice: 100.025,
            order_imbalance_l1: 0.25,
            order_imbalance_l5: 0.25,
            bid_depth_l1: 500,
            ask_depth_l1: 300,
            bid_depth_total: 500,
            ask_depth_total: 300,
            total_displayed_depth: 800,
            tick_size: 0.01,
          },
        });
      }
      if (url.includes("/api/datasets")) return jsonResponse({ datasets: [] });
      if (url.includes("/api/research/hypotheses")) return jsonResponse({ hypotheses: [] });
      if (url.includes("/api/research/experiments")) return jsonResponse({ experiments: [] });
      return jsonResponse({}, 404);
    });
  });

  it("renders dashboard with synthetic banner and live API metrics", async () => {
    render(<App />);
    expect(screen.getByText(/Synthetic Research Mode/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/API v0.2.0 Connected/i)).toBeInTheDocument();
    });
  });

  it("navigates to Order Book Explorer and shows bid/ask ladders", async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByText(/API v0.2.0 Connected/i)).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /Order Book Explorer/i }));
    expect(screen.getByText(/Interactive Limit Order Book Explorer/i)).toBeInTheDocument();
    expect(screen.getByText("99.90")).toBeInTheDocument();
    expect(screen.getByText("100.10")).toBeInTheDocument();
  });

  it("displays backend error state when API is unreachable", async () => {
    mockFetch.mockRejectedValue(new Error("Connection refused"));
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText(/Backend connection error/i)).toBeInTheDocument();
    });
  });
});
