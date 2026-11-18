"""Three-provider AI router with automatic failover, backoff retries, and cooldown recovery.

Routing policy:
1. Providers are ordered by configurable priority (default: gemini -> groq -> openrouter).
2. On transient failure (timeout / 5xx), retry up to ``max_retries`` with exponential backoff.
3. On rate-limit, quota exhaustion, auth failure, or exhausted retries, place the provider
   into cooldown (``cooldown_seconds``) and immediately fail over to the next provider.
4. Once a higher-priority provider's cooldown expires, subsequent requests automatically
   resume trying the preferred provider first.
5. Application-level usage and failure counts are tracked locally; we never assume a
   provider exposes remaining free-tier quota.
"""
from __future__ import annotations

import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from .env_loader import load_local_env
from .providers import (
    AIProviderAdapter,
    AIRequest,
    AIResponse,
    FailureKind,
    GeminiAdapter,
    GroqAdapter,
    OpenRouterAdapter,
    ProviderError,
)


@dataclass
class ProviderStats:
    provider: str
    model: str
    configured: bool
    requests_succeeded: int = 0
    requests_failed: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    last_error_kind: str | None = None
    last_error_message: str | None = None
    cooldown_until: float = 0.0

    def is_in_cooldown(self, now: float) -> bool:
        return now < self.cooldown_until


@dataclass
class RouterResult:
    ok: bool
    response: AIResponse | None
    attempts: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "provider": self.response.provider if self.response else None,
            "model": self.response.model if self.response else None,
            "text": self.response.text if self.response else None,
            "attempts": self.attempts,
            "error": self.error,
        }


class AIProviderRouter:
    """Automatic A -> B -> C failover router with cooldown recovery."""

    def __init__(
        self,
        providers: list[AIProviderAdapter] | None = None,
        cooldown_seconds: float = 60.0,
        max_retries: int = 1,
        backoff_base_seconds: float = 0.25,
        clock: Callable[[], float] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self.providers: list[AIProviderAdapter] = (
            providers if providers is not None else self._build_default_providers()
        )
        self.cooldown_seconds = cooldown_seconds
        self.max_retries = max_retries
        self.backoff_base_seconds = backoff_base_seconds
        self._clock = clock or time.monotonic
        self._sleep = sleep_fn or time.sleep
        self._stats: dict[str, ProviderStats] = {
            p.name: ProviderStats(
                provider=p.name,
                model=p.model,
                configured=p.is_configured,
            )
            for p in self.providers
        }

    @staticmethod
    def _build_default_providers() -> list[AIProviderAdapter]:
        load_local_env()
        registry: dict[str, Callable[[], AIProviderAdapter]] = {
            "gemini": GeminiAdapter,
            "groq": GroqAdapter,
            "openrouter": OpenRouterAdapter,
        }
        raw_priority = os.getenv("AI_PROVIDER_PRIORITY", "gemini,groq,openrouter")
        names = [n.strip().lower() for n in raw_priority.split(",") if n.strip()]
        ordered: list[AIProviderAdapter] = []
        seen: set[str] = set()
        for name in names:
            if name in registry and name not in seen:
                ordered.append(registry[name]())
                seen.add(name)
        for name, factory in registry.items():
            if name not in seen:
                ordered.append(factory())
        return ordered

    def route(self, request: AIRequest) -> RouterResult:
        """Route ``request`` across configured providers with retry and failover."""
        now = self._clock()
        attempts: list[dict[str, Any]] = []

        for adapter in self.providers:
            st = self._stats[adapter.name]
            st.configured = adapter.is_configured

            if not adapter.is_configured:
                attempts.append(
                    {
                        "provider": adapter.name,
                        "status": "skipped",
                        "reason": FailureKind.UNCONFIGURED.value,
                    }
                )
                continue

            if st.is_in_cooldown(now):
                remaining = round(st.cooldown_until - now, 1)
                attempts.append(
                    {
                        "provider": adapter.name,
                        "status": "skipped",
                        "reason": f"cooldown ({remaining}s remaining)",
                    }
                )
                continue

            retries_allowed = self.max_retries
            for attempt_idx in range(retries_allowed + 1):
                try:
                    resp = adapter.generate(request)
                    st.requests_succeeded += 1
                    st.last_error_kind = None
                    st.last_error_message = None
                    st.cooldown_until = 0.0
                    if resp.prompt_tokens:
                        st.total_prompt_tokens += resp.prompt_tokens
                    if resp.completion_tokens:
                        st.total_completion_tokens += resp.completion_tokens
                    attempts.append(
                        {
                            "provider": adapter.name,
                            "model": adapter.model,
                            "status": "succeeded",
                            "attempt": attempt_idx + 1,
                        }
                    )
                    return RouterResult(ok=True, response=resp, attempts=attempts)
                except ProviderError as err:
                    st.requests_failed += 1
                    st.last_error_kind = err.kind.value
                    st.last_error_message = str(err)
                    attempts.append(
                        {
                            "provider": adapter.name,
                            "model": adapter.model,
                            "status": "failed",
                            "kind": err.kind.value,
                            "attempt": attempt_idx + 1,
                        }
                    )
                    # Retry transient server/timeout errors with backoff; fail over immediately on quota/rate/auth
                    should_retry = (
                        err.retryable
                        and err.kind in (FailureKind.TIMEOUT, FailureKind.UNAVAILABLE)
                        and attempt_idx < retries_allowed
                    )
                    if should_retry:
                        delay = self.backoff_base_seconds * (2 ** attempt_idx)
                        if delay > 0:
                            self._sleep(delay)
                        continue

                    # Enter cooldown before failing over to next provider
                    st.cooldown_until = self._clock() + self.cooldown_seconds
                    break

        return RouterResult(
            ok=False,
            response=None,
            attempts=attempts,
            error=(
                "All AI providers are currently unconfigured, rate-limited, or unavailable. "
                "The deterministic HARLAB quantitative engine remains fully operational."
            ),
        )

    def status(self) -> dict[str, Any]:
        """Return safe status summary (no API keys or secrets)."""
        now = self._clock()
        providers_info: list[dict[str, Any]] = []
        for idx, adapter in enumerate(self.providers, start=1):
            st = self._stats[adapter.name]
            st.configured = adapter.is_configured
            info = asdict(st)
            info["priority"] = idx
            info["in_cooldown"] = st.is_in_cooldown(now)
            info["cooldown_remaining_seconds"] = (
                round(max(0.0, st.cooldown_until - now), 1)
                if st.is_in_cooldown(now)
                else 0.0
            )
            info.pop("cooldown_until", None)
            providers_info.append(info)
        return {
            "priority_order": [p.name for p in self.providers],
            "any_configured": any(p.is_configured for p in self.providers),
            "cooldown_seconds": self.cooldown_seconds,
            "providers": providers_info,
        }
