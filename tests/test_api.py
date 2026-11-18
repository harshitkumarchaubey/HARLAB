"""API endpoint tests using FastAPI TestClient."""
from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from harlab.api.app import create_app
from harlab.api.state import LabState


class TestHarlabAPI(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app(LabState()))

    def test_health_and_initial_book_snapshot(self) -> None:
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["status"], "ok")
        self.assertGreaterEqual(data["datasets_count"], 2)
        self.assertGreaterEqual(data["experiments_count"], 1)

        snap = self.client.get("/api/book/snapshot")
        self.assertEqual(snap.status_code, 200)
        sdata = snap.json()
        self.assertTrue(sdata["is_synthetic"])
        self.assertEqual(sdata["metrics"]["spread"], 0.2)
        self.assertEqual(sdata["metrics"]["mid_price"], 100.0)

    def test_order_submit_match_cancel_and_validation_errors(self) -> None:
        # Submit aggressive buy order crossing S1 at 100.10
        r = self.client.post(
            "/api/book/orders",
            json={"order_id": "API-B1", "side": "buy", "price": "100.10", "quantity": 100},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body["trades"]), 1)
        self.assertEqual(body["trades"][0]["price"], 100.1)
        self.assertEqual(body["trades"][0]["quantity"], 100)

        # Submit resting order then cancel it
        r2 = self.client.post(
            "/api/book/orders",
            json={"order_id": "API-B2", "side": "buy", "price": "99.70", "quantity": 50},
        )
        self.assertEqual(r2.status_code, 200)
        rc = self.client.delete("/api/book/orders/API-B2")
        self.assertEqual(rc.status_code, 200)
        self.assertTrue(rc.json()["cancelled"])

        # Cancelling missing order -> 404
        rc_missing = self.client.delete("/api/book/orders/DOES-NOT-EXIST")
        self.assertEqual(rc_missing.status_code, 404)

        # Off-tick price -> 400
        bad_tick = self.client.post(
            "/api/book/orders",
            json={"order_id": "BAD-1", "side": "buy", "price": "99.999", "quantity": 10},
        )
        self.assertEqual(bad_tick.status_code, 400)

        # Negative quantity -> 422 Pydantic validation
        bad_qty = self.client.post(
            "/api/book/orders",
            json={"order_id": "BAD-2", "side": "buy", "price": "99.90", "quantity": -5},
        )
        self.assertEqual(bad_qty.status_code, 422)

    def test_simulation_datasets_experiments_and_export(self) -> None:
        sim_resp = self.client.post(
            "/api/simulation/run",
            json={"seed": 77, "steps": 120, "buy_bias": 0.60, "scenario_name": "api_test"},
        )
        self.assertEqual(sim_resp.status_code, 200)
        sim_body = sim_resp.json()
        ds_id = sim_body["dataset"]["dataset_id"]
        self.assertTrue(sim_body["simulation"]["is_synthetic"])

        # Run hypothesis experiment on the new synthetic dataset
        exp_resp = self.client.post(
            "/api/research/experiments",
            json={"hypothesis_id": "H1_IMBALANCE_RETURN", "dataset_id": ds_id, "horizon": 1},
        )
        self.assertEqual(exp_resp.status_code, 200)
        exp = exp_resp.json()
        self.assertTrue(exp["leakage_check"]["passed"])

        # Export JSON & CSV
        exp_id = exp["experiment_id"]
        self.assertEqual(
            self.client.get(f"/api/research/experiments/{exp_id}/export?fmt=json").status_code,
            200,
        )
        self.assertEqual(
            self.client.get(f"/api/research/experiments/{exp_id}/export?fmt=csv").status_code,
            200,
        )

        # Regimes endpoint
        reg = self.client.get(f"/api/datasets/{ds_id}/regimes")
        self.assertEqual(reg.status_code, 200)
        self.assertIn("out_of_sample_regime_counts", reg.json())

        # OHLCV upload + guardrail rejection for H1
        csv_text = (
            "timestamp,open,high,low,close,volume\n"
            + "\n".join(
                f"2026-01-01T09:{m:02d}:00Z,100.0,101.0,99.0,100.5,500"
                for m in range(25)
            )
        )
        up = self.client.post(
            "/api/datasets/upload-ohlcv",
            json={"name": "Uploaded Test Candles", "csv_text": csv_text, "is_synthetic": True},
        )
        self.assertEqual(up.status_code, 200)
        ohlcv_id = up.json()["dataset"]["dataset_id"]
        blocked = self.client.post(
            "/api/research/experiments",
            json={"hypothesis_id": "H1_IMBALANCE_RETURN", "dataset_id": ohlcv_id},
        )
        self.assertEqual(blocked.status_code, 400)
        self.assertIn("OHLCV", blocked.json()["detail"])

    def test_ai_status_and_graceful_unconfigured_assist(self) -> None:
        st = self.client.get("/api/ai/status")
        self.assertEqual(st.status_code, 200)
        self.assertEqual(st.json()["priority_order"], ["gemini", "groq", "openrouter"])

        resp = self.client.post(
            "/api/ai/assist",
            json={"question": "Explain the current order book spread."},
        )
        self.assertEqual(resp.status_code, 200)
        # Without live API keys in test environment, router degrades gracefully
        body = resp.json()
        self.assertIn("ok", body)
        self.assertIn("attempts", body)


if __name__ == "__main__":
    unittest.main()
