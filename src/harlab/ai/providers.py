"""Provider-specific AI adapters behind a common interface.

Supports three independent providers with distinct wire formats:
1. Google Gemini (Generative Language REST API)
2. Groq (OpenAI-compatible Chat Completions API)
3. OpenRouter (OpenRouter Chat Completions API)

Security guarantees:
- API keys are read strictly from environment variables (never hardcoded).
- API keys are never included in exceptions, status dicts, or logs.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx


class FailureKind(str, Enum):
    UNCONFIGURED = "unconfigured"
    QUOTA_EXCEEDED = "quota_exceeded"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    AUTH_ERROR = "auth_error"
    UNAVAILABLE = "unavailable"
    INVALID_REQUEST = "invalid_request"


class ProviderError(Exception):
    """Classified error raised by an AI provider adapter."""

    def __init__(
        self,
        provider: str,
        kind: FailureKind,
        message: str,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.kind = kind
        self.status_code = status_code
        self.retryable = retryable


@dataclass(frozen=True)
class AIRequest:
    system_prompt: str
    user_prompt: str
    temperature: float = 0.2
    max_tokens: int = 700


@dataclass(frozen=True)
class AIResponse:
    provider: str
    model: str
    text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


def _classify_http_error(provider: str, status_code: int, body_text: str) -> ProviderError:
    lower = body_text.lower()
    if status_code in (401, 403):
        if "quota" in lower or "billing" in lower:
            return ProviderError(
                provider, FailureKind.QUOTA_EXCEEDED,
                f"{provider} quota/billing limit reached (HTTP {status_code}).",
                status_code=status_code, retryable=False,
            )
        return ProviderError(
            provider, FailureKind.AUTH_ERROR,
            f"{provider} authentication failed (HTTP {status_code}). Check API key.",
            status_code=status_code, retryable=False,
        )
    if status_code == 429:
        kind = FailureKind.QUOTA_EXCEEDED if "quota" in lower else FailureKind.RATE_LIMITED
        return ProviderError(
            provider, kind,
            f"{provider} rate or quota limit exceeded (HTTP 429).",
            status_code=429, retryable=True,
        )
    if status_code >= 500:
        return ProviderError(
            provider, FailureKind.UNAVAILABLE,
            f"{provider} temporary server error (HTTP {status_code}).",
            status_code=status_code, retryable=True,
        )
    return ProviderError(
        provider, FailureKind.INVALID_REQUEST,
        f"{provider} rejected request (HTTP {status_code}).",
        status_code=status_code, retryable=False,
    )


class AIProviderAdapter(ABC):
    """Common interface implemented by each provider-specific client."""

    name: str
    env_var: str
    default_model: str

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        self._api_key = (api_key if api_key is not None else os.getenv(self.env_var, "")).strip()
        self.model = (model or os.getenv(f"{self.name.upper()}_MODEL") or self.default_model).strip()
        self.timeout_seconds = timeout_seconds

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    @abstractmethod
    def generate(self, request: AIRequest) -> AIResponse:
        """Send ``request`` to the provider and return a normalized ``AIResponse``."""


class GeminiAdapter(AIProviderAdapter):
    """Google Gemini Generative Language REST API adapter."""

    name = "gemini"
    env_var = "GEMINI_API_KEY"
    default_model = "gemini-2.5-flash"

    def generate(self, request: AIRequest) -> AIResponse:
        if not self.is_configured:
            raise ProviderError(
                self.name, FailureKind.UNCONFIGURED,
                f"{self.env_var} is not configured.",
            )
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }
        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": request.system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": request.user_prompt}]}],
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
        }
        try:
            resp = httpx.post(url, headers=headers, json=payload, timeout=self.timeout_seconds)
        except httpx.TimeoutException as exc:
            raise ProviderError(
                self.name, FailureKind.TIMEOUT, f"{self.name} request timed out.", retryable=True
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                self.name, FailureKind.UNAVAILABLE, f"{self.name} network error.", retryable=True
            ) from exc

        if resp.status_code != 200:
            raise _classify_http_error(self.name, resp.status_code, resp.text)

        data = resp.json()
        candidates = data.get("candidates") or []
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text = "".join(p.get("text", "") for p in parts).strip()
        usage = data.get("usageMetadata") or {}
        return AIResponse(
            provider=self.name,
            model=self.model,
            text=text,
            prompt_tokens=usage.get("promptTokenCount"),
            completion_tokens=usage.get("candidatesTokenCount"),
        )


class GroqAdapter(AIProviderAdapter):
    """Groq OpenAI-compatible Chat Completions adapter."""

    name = "groq"
    env_var = "GROQ_API_KEY"
    default_model = "llama-3.3-70b-versatile"

    def generate(self, request: AIRequest) -> AIResponse:
        if not self.is_configured:
            raise ProviderError(
                self.name, FailureKind.UNCONFIGURED,
                f"{self.env_var} is not configured.",
            )
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        try:
            resp = httpx.post(url, headers=headers, json=payload, timeout=self.timeout_seconds)
        except httpx.TimeoutException as exc:
            raise ProviderError(
                self.name, FailureKind.TIMEOUT, f"{self.name} request timed out.", retryable=True
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                self.name, FailureKind.UNAVAILABLE, f"{self.name} network error.", retryable=True
            ) from exc

        if resp.status_code != 200:
            raise _classify_http_error(self.name, resp.status_code, resp.text)

        data = resp.json()
        choices = data.get("choices") or []
        text = choices[0].get("message", {}).get("content", "").strip() if choices else ""
        usage = data.get("usage") or {}
        return AIResponse(
            provider=self.name,
            model=self.model,
            text=text,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )


class OpenRouterAdapter(AIProviderAdapter):
    """OpenRouter Chat Completions adapter."""

    name = "openrouter"
    env_var = "OPENROUTER_API_KEY"
    default_model = "google/gemini-2.0-flash-001"

    def generate(self, request: AIRequest) -> AIResponse:
        if not self.is_configured:
            raise ProviderError(
                self.name, FailureKind.UNCONFIGURED,
                f"{self.env_var} is not configured.",
            )
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
            "HTTP-Referer": "https://harlab.local",
            "X-Title": "HARLAB Quantitative Market Research Laboratory",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        try:
            resp = httpx.post(url, headers=headers, json=payload, timeout=self.timeout_seconds)
        except httpx.TimeoutException as exc:
            raise ProviderError(
                self.name, FailureKind.TIMEOUT, f"{self.name} request timed out.", retryable=True
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                self.name, FailureKind.UNAVAILABLE, f"{self.name} network error.", retryable=True
            ) from exc

        if resp.status_code != 200:
            raise _classify_http_error(self.name, resp.status_code, resp.text)

        data = resp.json()
        choices = data.get("choices") or []
        text = choices[0].get("message", {}).get("content", "").strip() if choices else ""
        usage = data.get("usage") or {}
        return AIResponse(
            provider=self.name,
            model=self.model,
            text=text,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )
