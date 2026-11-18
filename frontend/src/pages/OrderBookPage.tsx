import React, { useState } from "react";
import { harlabApi } from "../services/api";
import type { BookSnapshot, Side } from "../types/harlab";

interface OrderBookPageProps {
  snapshot: BookSnapshot | null;
  onRefresh: (next: BookSnapshot) => void;
}

const fmt = (v: number | null | undefined, digits = 2) =>
  v === null || v === undefined ? "—" : v.toFixed(digits);

export const OrderBookPage: React.FC<OrderBookPageProps> = ({ snapshot, onRefresh }) => {
  const [orderId, setOrderId] = useState("UI-101");
  const [side, setSide] = useState<Side>("buy");
  const [price, setPrice] = useState("100.00");
  const [quantity, setQuantity] = useState("100");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setStatusMsg(null);
    try {
      const res = await harlabApi.submitOrder({
        order_id: orderId,
        side,
        price,
        quantity: Number(quantity),
      });
      onRefresh(res.snapshot);
      setStatusMsg(
        `Submitted ${orderId} (${side.toUpperCase()} ${quantity} @ ${price}) — ${res.trades.length} trade(s) executed.`
      );
      const numericPart = Number(orderId.replace(/\D/g, "")) || 100;
      setOrderId(`UI-${numericPart + 1}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Order submission failed");
    } finally {
      setBusy(false);
    }
  };

  const handleCancel = async (id: string) => {
    setBusy(true);
    setError(null);
    try {
      const res = await harlabApi.cancelOrder(id);
      onRefresh(res.snapshot);
      setStatusMsg(`Cancelled resting order ${id}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cancel failed");
    } finally {
      setBusy(false);
    }
  };

  const handleReset = async (seedDemo: boolean) => {
    setBusy(true);
    setError(null);
    try {
      const res = await harlabApi.resetBook("0.01", seedDemo);
      onRefresh(res.snapshot);
      setStatusMsg(seedDemo ? "Reset order book and re-seeded demo levels." : "Cleared order book.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed");
    } finally {
      setBusy(false);
    }
  };

  if (!snapshot) {
    return <div className="panel">Loading order book snapshot...</div>;
  }

  const m = snapshot.metrics;
  const maxQty = Math.max(
    1,
    ...snapshot.bids.map((b) => b[1]),
    ...snapshot.asks.map((a) => a[1])
  );

  return (
    <>
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Interactive Limit Order Book Explorer</h2>
            <span className="muted" style={{ fontSize: 12 }}>
              Exact-tick continuous matching engine (tick = {snapshot.tick_size})
            </span>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-secondary" disabled={busy} onClick={() => handleReset(true)}>
              Reset & Seed Demo
            </button>
            <button className="btn btn-secondary" disabled={busy} onClick={() => handleReset(false)}>
              Clear Book
            </button>
          </div>
        </div>

        <div className="kpi-grid">
          <div className="kpi-card">
            <div className="kpi-label">Best Bid</div>
            <div className="kpi-value mono" style={{ color: "var(--bid-green)" }}>{fmt(m.best_bid)}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Best Ask</div>
            <div className="kpi-value mono" style={{ color: "var(--ask-red)" }}>{fmt(m.best_ask)}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Spread</div>
            <div className="kpi-value mono">{fmt(m.spread)}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Mid-Price</div>
            <div className="kpi-value mono">{fmt(m.mid_price)}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Microprice</div>
            <div className="kpi-value mono">{fmt(m.microprice, 4)}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">L1 Imbalance</div>
            <div className="kpi-value mono">{fmt(m.order_imbalance_l1, 3)}</div>
          </div>
        </div>
      </div>

      <div className="panel">
        <h3 className="panel-title" style={{ marginBottom: 10 }}>Submit Limit Order</h3>
        {error ? <div className="error-banner" style={{ marginBottom: 10 }}>{error}</div> : null}
        {statusMsg ? <div className="warn-banner" style={{ marginBottom: 10 }}>{statusMsg}</div> : null}
        <form className="form-grid" onSubmit={handleSubmit}>
          <label className="field">
            Order ID
            <input value={orderId} onChange={(e) => setOrderId(e.target.value)} required />
          </label>
          <label className="field">
            Side
            <select value={side} onChange={(e) => setSide(e.target.value as Side)}>
              <option value="buy">BUY</option>
              <option value="sell">SELL</option>
            </select>
          </label>
          <label className="field">
            Limit Price (tick {snapshot.tick_size})
            <input value={price} onChange={(e) => setPrice(e.target.value)} required />
          </label>
          <label className="field">
            Quantity (int)
            <input
              type="number"
              min={1}
              step={1}
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              required
            />
          </label>
          <button className="btn" type="submit" disabled={busy}>
            {busy ? "Submitting..." : "Submit Limit Order"}
          </button>
        </form>
      </div>

      <div className="grid-2">
        <div className="panel">
          <h3 className="panel-title" style={{ marginBottom: 10, color: "var(--bid-green)" }}>
            Bids (Total Depth: {m.bid_depth_total})
          </h3>
          {snapshot.bids.length === 0 ? (
            <p className="muted">No resting bids.</p>
          ) : (
            snapshot.bids.map(([px, qty]) => (
              <div className="ladder-row mono" key={`b-${px}`}>
                <span style={{ color: "var(--bid-green)" }}>{px.toFixed(2)}</span>
                <span>{qty}</span>
                <div className="bar-track">
                  <div className="bar-bid" style={{ width: `${(qty / maxQty) * 100}%` }} />
                </div>
              </div>
            ))
          )}
        </div>

        <div className="panel">
          <h3 className="panel-title" style={{ marginBottom: 10, color: "var(--ask-red)" }}>
            Asks (Total Depth: {m.ask_depth_total})
          </h3>
          {snapshot.asks.length === 0 ? (
            <p className="muted">No resting asks.</p>
          ) : (
            snapshot.asks.map(([px, qty]) => (
              <div className="ladder-row mono" key={`a-${px}`}>
                <span style={{ color: "var(--ask-red)" }}>{px.toFixed(2)}</span>
                <span>{qty}</span>
                <div className="bar-track">
                  <div className="bar-ask" style={{ width: `${(qty / maxQty) * 100}%` }} />
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="grid-2">
        <div className="panel">
          <h3 className="panel-title" style={{ marginBottom: 10 }}>
            Resting Orders ({snapshot.active_orders.length})
          </h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Side</th>
                  <th>Price</th>
                  <th>Rem / Init</th>
                  <th>Seq</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {snapshot.active_orders.map((o) => (
                  <tr key={o.order_id}>
                    <td className="mono">{o.order_id}</td>
                    <td className="mono" style={{ color: o.side === "buy" ? "var(--bid-green)" : "var(--ask-red)" }}>
                      {o.side.toUpperCase()}
                    </td>
                    <td className="mono">{o.price.toFixed(2)}</td>
                    <td className="mono">{o.quantity} / {o.initial_quantity}</td>
                    <td className="mono">#{o.timestamp}</td>
                    <td>
                      <button
                        className="btn btn-danger"
                        disabled={busy}
                        onClick={() => handleCancel(o.order_id)}
                      >
                        Cancel
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel">
          <h3 className="panel-title" style={{ marginBottom: 10 }}>
            Executed Trades ({snapshot.recent_trades.length})
          </h3>
          {snapshot.recent_trades.length === 0 ? (
            <p className="muted">No executions yet. Submit a crossing limit order to observe fills.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Price</th>
                    <th>Qty</th>
                    <th>Aggressor</th>
                    <th>Buy / Sell IDs</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshot.recent_trades.map((t) => (
                    <tr key={t.trade_id}>
                      <td className="mono">{t.trade_id}</td>
                      <td className="mono">{t.price.toFixed(2)}</td>
                      <td className="mono">{t.quantity}</td>
                      <td className="mono">{t.aggressor_side.toUpperCase()}</td>
                      <td className="mono">{t.buy_order_id} / {t.sell_order_id}</td>
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
