"""HARLAB AI Research Assistant grounded strictly in deterministic engine outputs.

Separation of concerns:
- All quantitative metrics, order-book states, and statistical tests are computed
  exclusively by the deterministic Python research engine.
- The AI assistant only interprets, explains, or helps formulate hypotheses from
  those measured outputs. It must never fabricate numbers or override calculations.
"""
from __future__ import annotations

import json
from typing import Any

from .providers import AIRequest
from .router import AIProviderRouter

SYSTEM_PROMPT = (
    "You are the HARLAB Quantitative Market Research Assistant. "
    "You help researchers interpret deterministic market microstructure outputs, "
    "formulate testable hypotheses, and explain order-book concepts clearly.\n"
    "STRICT RULES:\n"
    "1. Never invent experimental results, statistics, or prices not present in the provided JSON context.\n"
    "2. Explicitly distinguish 'Measured Results (Deterministic Engine)' from 'Interpretation'.\n"
    "3. Remind the user when data is SYNTHETIC and never claim real-market profitability.\n"
    "4. Keep responses concise, technically rigorous, and honest about statistical uncertainty."
)


class ResearchAssistant:
    """Grounded AI assistant backed by ``AIProviderRouter``."""

    def __init__(self, router: AIProviderRouter | None = None) -> None:
        self.router = router or AIProviderRouter()

    def ask(
        self,
        question: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not question or not question.strip():
            raise ValueError("question cannot be empty")

        measured_context = context or {}
        user_prompt = (
            f"Researcher question:\n{question.strip()}\n\n"
            f"Measured deterministic context (JSON — source of truth):\n"
            f"{json.dumps(measured_context, indent=2, default=str)[:4000]}"
        )
        result = self.router.route(
            AIRequest(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)
        )
        return {
            "ok": result.ok,
            "provider": result.response.provider if result.response else None,
            "model": result.response.model if result.response else None,
            "interpretation": result.response.text if result.response else None,
            "measured_context_attached": bool(measured_context),
            "attempts": result.attempts,
            "error": result.error,
        }
