"""Tests for the three-provider AI fallback router, backoff, cooldown, and security."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from harlab.ai.providers import (
    AIProviderAdapter,
    AIRequest,
    AIResponse,
    FailureKind,
    ProviderError,
)
from harlab.ai.env_loader import load_local_env
from harlab.ai.router import AIProviderRouter


class StubAdapter(AIProviderAdapter):
    """Deterministic in-memory stub adapter for testing failover logic without network."""

    def __init__(
        self,
        name: str,
        api_key: str = "test-secret-key-xyz",
        outcomes: list[AIResponse | ProviderError] | None = None,
    ) -> None:
        self.name = name
        self.env_var = f"{name.upper()}_API_KEY"
        self.default_model = f"{name}-model"
        super().__init__(api_key=api_key, model=f"{name}-model")
        self.outcomes = list(outcomes or [])
        self.calls = 0

    def generate(self, request: AIRequest) -> AIResponse:
        if not self.is_configured:
            raise ProviderError(self.name, FailureKind.UNCONFIGURED, "not configured")
        self.calls += 1
        if not self.outcomes:
            return AIResponse(provider=self.name, model=self.model, text=f"ok from {self.name}")
        item = self.outcomes.pop(0)
        if isinstance(item, ProviderError):
            raise item
        return item


class FakeClock:
    def __init__(self, start: float = 100.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class TestAIRouter(unittest.TestCase):
    def test_automatic_failover_a_to_b_to_c_and_recovery(self) -> None:
        clock = FakeClock(1000.0)
        sleeps: list[float] = []

        prov_a = StubAdapter(
            "gemini",
            outcomes=[
                ProviderError("gemini", FailureKind.RATE_LIMITED, "429 rate limit", 429, True),
                AIResponse("gemini", "gemini-model", "recovered A", 10, 20),
            ],
        )
        prov_b = StubAdapter(
            "groq",
            outcomes=[
                ProviderError("groq", FailureKind.QUOTA_EXCEEDED, "quota hit", 429, False),
            ],
        )
        prov_c = StubAdapter(
            "openrouter",
            outcomes=[
                AIResponse("openrouter", "openrouter-model", "served by C", 12, 18),
                AIResponse("openrouter", "openrouter-model", "served by C again", 12, 18),
            ],
        )

        router = AIProviderRouter(
            providers=[prov_a, prov_b, prov_c],
            cooldown_seconds=30.0,
            max_retries=1,
            backoff_base_seconds=0.1,
            clock=clock,
            sleep_fn=sleeps.append,
        )

        req = AIRequest(system_prompt="sys", user_prompt="hello")

        # Call 1: A hits 429 -> B hits quota -> C succeeds
        r1 = router.route(req)
        self.assertTrue(r1.ok)
        assert r1.response is not None
        self.assertEqual(r1.response.provider, "openrouter")
        self.assertEqual(r1.response.text, "served by C")

        # Call 2 (10s later): A and B are in cooldown -> router skips straight to C
        clock.advance(10.0)
        r2 = router.route(req)
        self.assertTrue(r2.ok)
        assert r2.response is not None
        self.assertEqual(r2.response.provider, "openrouter")
        self.assertEqual(prov_a.calls, 1)  # Skipped during cooldown

        # Call 3 (25s later, total 35s > 30s cooldown): A recovers and handles request
        clock.advance(25.0)
        r3 = router.route(req)
        self.assertTrue(r3.ok)
        assert r3.response is not None
        self.assertEqual(r3.response.provider, "gemini")
        self.assertEqual(r3.response.text, "recovered A")

    def test_transient_timeout_retries_with_backoff_before_failover(self) -> None:
        clock = FakeClock(500.0)
        sleeps: list[float] = []
        prov_a = StubAdapter(
            "gemini",
            outcomes=[
                ProviderError("gemini", FailureKind.TIMEOUT, "timeout", None, True),
                AIResponse("gemini", "gemini-model", "succeeded on retry"),
            ],
        )
        router = AIProviderRouter(
            providers=[prov_a],
            max_retries=1,
            backoff_base_seconds=0.25,
            clock=clock,
            sleep_fn=sleeps.append,
        )
        res = router.route(AIRequest("sys", "hi"))
        self.assertTrue(res.ok)
        self.assertEqual(prov_a.calls, 2)
        self.assertEqual(sleeps, [0.25])

    def test_graceful_failure_and_no_secret_leakage(self) -> None:
        secret = "SUPER_SECRET_KEY_12345"
        prov_a = StubAdapter("gemini", api_key=secret, outcomes=[
            ProviderError("gemini", FailureKind.AUTH_ERROR, "auth failed", 401, False)
        ])
        prov_b = StubAdapter("groq", api_key="")
        router = AIProviderRouter(providers=[prov_a, prov_b])

        res = router.route(AIRequest("sys", "hi"))
        self.assertFalse(res.ok)
        self.assertIsNotNone(res.error)
        status_str = str(router.status()) + str(res.to_dict())
        self.assertNotIn(secret, status_str)


    def test_local_env_loader_preserves_existing_env(self) -> None:
        key_a = "HARLAB_TEST_KEY_A"
        key_b = "HARLAB_TEST_KEY_B"
        os.environ[key_a] = "from_shell"
        os.environ.pop(key_b, None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                env_file = Path(tmp) / ".env"
                env_file.write_text(
                    f"# comment\n{key_a}=from_file\n{key_b}='loaded_value'\n",
                    encoding="utf-8",
                )
                self.assertTrue(load_local_env(env_file))
                self.assertEqual(os.environ[key_a], "from_shell")
                self.assertEqual(os.environ[key_b], "loaded_value")
        finally:
            os.environ.pop(key_a, None)
            os.environ.pop(key_b, None)

if __name__ == "__main__":
    unittest.main()
